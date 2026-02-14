# backend/engine.py
"""
Pipeline déterministe : edge-cases → session → FAQ → booking/qualif → transfer
Aucune créativité, aucune improvisation.
"""

from __future__ import annotations
from typing import List, Optional
from dataclasses import dataclass
import json
import logging
import re

from backend import config, prompts, guards, tools_booking, intent_parser, contact_parser
from backend.guards_medical import is_medical_emergency  # legacy / tests
from backend.guards_medical_triage import (
    detect_medical_red_flag,
    classify_medical_symptoms,
    extract_symptom_motif_short,
)
from backend.log_events import MEDICAL_RED_FLAG_TRIGGERED
from backend import db as backend_db
from backend.session import Session, SessionStore, reset_slots_reading, set_reading_slots
from backend.slot_choice import detect_slot_choice_early
from backend.time_constraints import extract_time_constraint
from backend.session_store_sqlite import SQLiteSessionStore
from backend.tools_faq import FaqStore, FaqResult
from backend.llm_assist import (
    LLMClient,
    get_default_llm_client,
    LLM_ASSIST_MIN_CONFIDENCE,
    LLM_ASSIST_MAX_TEXT_LEN,
)
from backend.entity_extraction import (
    extract_entities,
    get_next_missing_field,
    extract_pref,
    infer_preference_from_context,
)
from backend.start_router import route_start, FAQ_BUCKET_WHITELIST
from backend.tenant_flags_cache import get_tenant_flags
from backend.tenant_config import get_consent_mode

logger = logging.getLogger(__name__)


def _assert_pending_slots_invariants(session: Session, state: str) -> None:
    """
    Anti-régression Fix 3: invariants pending_slots (dev only, logs warning).
    Appelé à l'entrée de WAIT_CONFIRM / CONTACT_CONFIRM quand pending_slots est utilisé.
    """
    pending = getattr(session, "pending_slots", None) or []
    if not pending:
        return
    conv_id = getattr(session, "conv_id", "")[:20]
    if len(pending) > config.MAX_SLOTS_PROPOSED:
        logger.warning(
            "[PENDING_SLOTS_INVARIANT] conv_id=%s state=%s len=%s > MAX=%s",
            conv_id, state, len(pending), config.MAX_SLOTS_PROPOSED,
        )
    for i, s in enumerate(pending):
        slot_id = tools_booking._slot_get(s, "id") or tools_booking._slot_get(s, "slot_id")
        start = tools_booking._slot_get(s, "start") or tools_booking._slot_get(s, "start_iso")
        label = tools_booking._slot_get(s, "label_vocal") or tools_booking._slot_get(s, "label")
        src = tools_booking._slot_get(s, "source")
        has_id_or_start = slot_id is not None or (start and str(start).strip())
        if not (has_id_or_start and label and src):
            logger.warning(
                "[PENDING_SLOTS_INVARIANT] conv_id=%s state=%s slot_idx=%s missing id/start=%s label=%s source=%s",
                conv_id, state, i, has_id_or_start, bool(label), src,
            )


def _mask_for_log(text: str, max_len: int = 50) -> str:
    """Fix 12: masque téléphone/email dans les logs (évite fuite données)."""
    if not text or not isinstance(text, str):
        return ""
    t = text.strip()[:max_len]
    # Masquer email (prenom@domaine)
    t = re.sub(r"\S+@\S+\.\S+", "[EMAIL]", t)
    # Masquer séquences 8+ chiffres (numéros)
    t = re.sub(r"\d[\d\s\-\.]{7,}", "[TEL]", t)
    return t


# Round-robin ACK après refus de créneau (évite "D'accord" répété)
# Vocal : question fermée pour clore le tour et éviter oui/non ambigus
SLOT_REFUSAL_ACK_VARIANTS_VOCAL = [
    "D'accord. Dans ce cas, plutôt {label}. Ça vous convient ?",
    "Très bien. Je vous propose {label}. Ça vous convient ?",
    "Ok. Alors plutôt {label}. Ça vous convient ?",
]
SLOT_REFUSAL_ACK_VARIANTS_WEB = [
    "D'accord. Je vous propose {label}.",
    "Très bien. Que pensez-vous de {label} ?",
    "Je vous propose plutôt {label}.",
]


def pick_slot_refusal_message(session: Session, label: str, channel: str) -> str:
    """Variante round-robin pour proposition après refus (ton naturel, pas robot)."""
    variants = SLOT_REFUSAL_ACK_VARIANTS_VOCAL if channel == "vocal" else SLOT_REFUSAL_ACK_VARIANTS_WEB
    idx = session.next_ack_index() % len(variants)
    return variants[idx].format(label=label)


def log_filler_detected(
    logger_instance,
    session: Session,
    user_msg: str,
    field: str,
    detail: Optional[str] = None,
) -> None:
    """
    Log dédié : reason="filler_detected" pour savoir où ça bloque et pourquoi, sans bruit.
    À appeler juste avant de déclencher un recovery (name, preference, phone, slot_choice).
    detail: optionnel (ex: "no_digits", "invalid_format", "too_repetitive" pour phone).
    """
    extra = {
        "reason": "filler_detected",
        "state": session.state,
        "field": field,
        "turn_count": getattr(session, "turn_count", 0),
        "raw_user_msg": (user_msg or "")[:200],
    }
    if detail is not None:
        extra["detail"] = detail
    logger_instance.info("filler_detected", extra=extra)


def _fail_count_for_context(session: Session, context: Optional[str]) -> int:
    """Compte d'échecs pour un contexte (analytics)."""
    if not context:
        return 0
    m = {
        "name": getattr(session, "name_fails", 0),
        "phone": getattr(session, "phone_fails", 0),
        "slot_choice": getattr(session, "slot_choice_fails", 0),
        "preference": getattr(session, "preference_fails", 0),
        "contact_confirm": getattr(session, "contact_confirm_fails", 0),
        "cancel_name": getattr(session, "cancel_name_fails", 0),
        "modify_name": getattr(session, "modify_name_fails", 0),
        "cancel_rdv_not_found": getattr(session, "cancel_rdv_not_found_count", 0),
        "modify_rdv_not_found": getattr(session, "modify_rdv_not_found_count", 0),
        "faq": getattr(session, "faq_fails", 0),
    }
    return m.get(context, 0)


def persist_consent_obtained(session: Session, channel: str = "vocal") -> None:
    """
    Persiste consent_obtained avec context (version + channel).
    Format: {"consent_version": "2026-02-12_v1", "channel": "vocal"}
    À appeler quand le consentement est obtenu (ex: premier message utilisateur).
    Idempotent : 1 par call_id (évite doublons sur retry webhook).
    """
    try:
        scope_id = None
        if getattr(session, "channel", "") == "vocal" and getattr(session, "tenant_id", None):
            scope_id = session.tenant_id
        if scope_id is None:
            scope_id = getattr(session, "client_id", None)
        if scope_id is None:
            return
        call_id = (session.conv_id or "").strip()
        if not call_id:
            return
        if backend_db.consent_obtained_exists(int(scope_id), call_id):
            logger.debug("persist_consent_obtained skip: already exists call_id=%s", call_id[:20])
            return
        import json
        ctx = json.dumps({"consent_version": config.CONSENT_VERSION, "channel": channel})
        _persist_ivr_event(session, "consent_obtained", context=ctx)
    except Exception as e:
        logger.debug("persist_consent_obtained skip: %s", e)


def _persist_ivr_event(
    session: Session,
    event: str,
    context: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    """
    Persiste un event dans ivr_events (rapport quotidien).
    Multi-tenant vocal : utilise tenant_id (DID routing) pour scoping.
    Sinon : client_id (legacy).
    Skip si call_id manquant pour booking_confirmed (qualité booking).
    """
    try:
        scope_id = None
        if getattr(session, "channel", "") == "vocal" and getattr(session, "tenant_id", None):
            scope_id = session.tenant_id  # DID routing : scope par tenant
        if scope_id is None:
            scope_id = getattr(session, "client_id", None)
        if scope_id is None:
            logger.debug("persist_ivr_event skip: reason=missing_scope event=%s", event)
            return
        call_id = session.conv_id or ""
        if event == "booking_confirmed" and not call_id.strip():
            logger.debug("persist_ivr_event skip: reason=missing_call_id event=booking_confirmed")
            return
        backend_db.create_ivr_event(
            client_id=int(scope_id),
            call_id=call_id,
            event=event,
            context=context,
            reason=reason,
        )
    except Exception as e:
        logger.debug("persist_ivr_event skip: %s", e)


def log_ivr_event(
    logger_instance,
    session: Session,
    event: str,
    context: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    """
    Log structuré pour tableau de bord produit (recovery, intent_router, override, safe_reply).
    Persiste aussi en base pour les events canoniques (recovery_step, intent_router_trigger).
    """
    extra = {
        "event": event,
        "state": session.state,
        "call_id": session.conv_id,
        "client_id": getattr(session, "client_id", None) or session.conv_id,
    }
    if context is not None:
        extra["context"] = context
        extra["count"] = _fail_count_for_context(session, context)
    if reason is not None:
        extra["reason"] = reason
    logger_instance.info("ivr_event", extra=extra)
    if event in ("recovery_step", "intent_router_trigger"):
        _persist_ivr_event(session, event, context=context, reason=reason)


def log_preference_inferred(
    logger_instance,
    session: Session,
    raw_input: str,
    inferred: str,
) -> None:
    """Log design signal : préférence inférée (morning/afternoon/neutral)."""
    logger_instance.info(
        "preference_inferred",
        extra={
            "inferred": inferred,
            "raw_input": (raw_input or "")[:200],
            "state": session.state,
        },
    )


def log_preference_failed(
    logger_instance,
    session: Session,
    raw_input: str,
    reason: str = "ambiguous_input",
) -> None:
    """Log design signal : préférence non reconnue (recovery)."""
    logger_instance.info(
        "preference_failed",
        extra={
            "reason": reason,
            "raw_input": (raw_input or "")[:200],
            "state": session.state,
        },
    )


def log_name_rejected(
    logger_instance,
    session: Session,
    raw_input: str,
    reason: str,
) -> None:
    """
    Log dédié : name_rejected pour design signals (filler_detected / not_plausible_name).
    """
    logger_instance.info(
        "name_rejected",
        extra={
            "reason": reason,
            "raw_input": (raw_input or "")[:200],
            "state": session.state,
            "turn_count": getattr(session, "turn_count", 0),
        },
    )


@dataclass(frozen=True)
class Event:
    """Événement à envoyer au client (SSE)"""
    type: str  # "partial" | "final" | "transfer" | "error"
    text: str
    conv_state: Optional[str] = None
    transfer_reason: Optional[str] = None
    silent: bool = False


# ========================
# DÉTECTION INTENT BOOKING
# ========================

def _detect_booking_intent(text: str) -> bool:
    """Détecte si le message exprime une intention de RDV"""
    text_lower = text.lower()
    
    # Normaliser les espaces/tirets
    text_normalized = text_lower.replace("-", " ").replace("_", " ")
    
    # Keywords avec variantes. Fix 11: pas "prendre" seul (je prends note, je prends le 1er)
    keywords = [
        "rdv",
        "rendez vous",  # Après normalisation, "rendez-vous" devient "rendez vous"
        "rendezvous",
        "dispo",
        "disponibilité",
        "créneau",
        "réserver",
        "réservation",
    ]
    
    # Patterns plus flexibles
    booking_phrases = [
        "veux un rendez",
        "veux un rdv",
        "prendre rendez",
        "prendre un rendez",
        "besoin d'un rendez",
        "avoir un rendez",
    ]
    
    # Check keywords
    if any(kw in text_normalized for kw in keywords):
        return True
    
    # Check phrases
    if any(phrase in text_normalized for phrase in booking_phrases):
        return True
    
    return False


# ========================
# DÉTECTION "MOTIF = INTENTION RDV"
# ========================

_MOTIF_INTENT_KEYWORDS = [
    "rdv",
    "rendez-vous",
    "rendez vous",
    "rendezvous",
    "appointment",
]


def _looks_like_booking_intent(text: str) -> bool:
    """
    Détecte si un texte ressemble à une intention de booking plutôt qu'à un motif réel.
    Utilisé pour valider les motifs lors de la qualification.
    """
    t = text.strip().lower()
    if not t:
        return True
    
    # Si c'est très court + keywords => quasi sûr que c'est l'intention, pas le motif
    if len(t) <= 32 and any(k in t for k in _MOTIF_INTENT_KEYWORDS):
        return True
    
    # Si la phrase contient explicitement "je veux un rdv" / "je voudrais un rdv"
    if re.search(r"\b(je\s+veux|je\s+voudrais)\b.*\b(rdv|rendez)\b", t):
        return True
    
    return False


# ========================
# DÉTECTION INTENT COMPLET
# ========================

def detect_intent(text: str, state: str = "") -> str:
    """
    Détecte l'intention de l'utilisateur (délégation au module intent_parser).
    Garde-fou : en state START, "oui" => UNCLEAR (jamais BOOKING).
    Returns:
        str: "YES", "NO", "BOOKING", "FAQ", "CANCEL", "MODIFY", "TRANSFER", "ABANDON", "REPEAT", "UNCLEAR"
    """
    return intent_parser.detect_intent(text or "", state).value


def detect_slot_choice(text: str, num_slots: int = 3) -> Optional[int]:
    """
    Détecte le choix de créneau de l'utilisateur.
    
    Args:
        text: Message de l'utilisateur
        num_slots: Nombre de créneaux proposés (1, 2 ou 3)
    
    Returns:
        int: Index du slot (0, 1, 2) ou None si non reconnu
    """
    t = text.strip().lower()
    
    # Check patterns pour chaque choix
    if any(p in t for p in prompts.SLOT_CHOICE_FIRST):
        return 0
    if num_slots >= 2 and any(p in t for p in prompts.SLOT_CHOICE_SECOND):
        return 1
    if num_slots >= 3 and any(p in t for p in prompts.SLOT_CHOICE_THIRD):
        return 2
    
    # Check jours (lundi, mardi, etc.) - nécessite les slots pour matcher
    # Pour l'instant, on retourne None et on laisse le code existant gérer
    
    return None


# ========================
# PRODUCTION-GRADE V3 (safe_reply, intent override, INTENT_ROUTER)
# ========================

SAFE_REPLY_FALLBACK = "D'accord. Je vous écoute."

# États où la question posée est explicitement oui/non (confirmations).
YESNO_CONFIRM_STATES = frozenset({
    "CONTACT_CONFIRM", "CANCEL_CONFIRM", "MODIFY_CONFIRM", "WAIT_CONFIRM",
    "PREFERENCE_CONFIRM",
})
# États où YES/NO sont acceptés (confirmations + POST_FAQ disambiguation). Hors de ce set → override YES/NO en UNCLEAR.
STATES_ACCEPTING_YESNO = YESNO_CONFIRM_STATES | frozenset({"POST_FAQ", "POST_FAQ_CHOICE"})
# NO contextuel : handle_no_contextual s'applique à ces états (plus WAIT_CONFIRM géré plus bas en séquentiel).
NO_CONTEXTUAL_STATES = YESNO_CONFIRM_STATES | frozenset({"QUALIF_CONTACT"})


def _log_turn_debug(session: Session) -> None:
    """Log structuré (debug) par tour pour diagnostic d'appel sans rejeu.
    Ne jamais logger téléphone/email en clair (même en DEBUG). turn_count aide à repérer les boucles.
    llm_meta (si présent) : merger pour diagnostic LLM Assist."""
    # Diagnostic fin d'appel "ça sera tout merci" : comparer state_before, assistant_text_sent, state_after.
    # A) state_before != POST_FAQ → bug state/session. B) assistant_text_sent="au revoir" mais audio dit autre chose → bridge/TTS.
    # C) tout OK mais tours suivants → manque hangup/endCall côté provider.
    assistant_sent = (getattr(session, "_turn_assistant_text", None) or "")[:200]
    llm_meta = getattr(session, "_turn_llm_meta", None)
    if llm_meta:
        logger.info(
            "[TURN] conv_id=%s state_before=%s state_after=%s intent_detected=%s strong_intent=%s last_say_key=%s assistant_text_sent=%s llm_used=%s",
            getattr(session, "conv_id", ""),
            getattr(session, "_turn_state_before", None),
            getattr(session, "state", None),
            getattr(session, "last_intent", None),
            getattr(session, "last_strong_intent", None),
            getattr(session, "last_say_key", None),
            assistant_sent or "(none)",
            llm_meta.get("llm_used"),
        )
    else:
        logger.info(
            "[TURN] conv_id=%s state_before=%s state_after=%s intent_detected=%s strong_intent=%s last_say_key=%s assistant_text_sent=%s",
            getattr(session, "conv_id", ""),
            getattr(session, "_turn_state_before", None),
            getattr(session, "state", None),
            getattr(session, "last_intent", None),
            getattr(session, "last_strong_intent", None),
            getattr(session, "last_say_key", None),
            assistant_sent or "(none)",
        )


def safe_reply(events: List[Event], session: Session) -> List[Event]:
    """
    Dernière barrière anti-silence (spec V3).
    Aucun message utilisateur ne doit mener à zéro output.
    Persiste transferred_human une seule fois par call (idempotence).
    Fix 7: en vocal, un seul Event final (webhook n'utilise que events[0].text) → garder le premier si plusieurs.
    """
    if not events:
        log_ivr_event(logger, session, "safe_reply")
        msg = SAFE_REPLY_FALLBACK
        session.add_message("agent", msg)
        return [Event("final", msg, conv_state=session.state)]
    channel = getattr(session, "channel", "web")
    if channel == "vocal":
        finals = [e for e in events if getattr(e, "type", None) == "final"]
        if len(finals) > 1:
            logger.warning(
                "[FIX7] vocal: %s final events (webhook uses only first), conv_id=%s",
                len(finals),
                getattr(session, "conv_id", "")[:20],
            )
            events = [events[0]]
    setattr(session, "_turn_assistant_text", (events[0].text if events and getattr(events[0], "text", None) else "") or "")
    _log_turn_debug(session)
    if getattr(session, "state", None) == "TRANSFERRED" and not getattr(session, "transfer_logged", False):
        _persist_ivr_event(session, "transferred_human")
        session.transfer_logged = True
    for ev in events:
        if ev.text and ev.text.strip():
            return events
    log_ivr_event(logger, session, "safe_reply")
    msg = SAFE_REPLY_FALLBACK
    session.add_message("agent", msg)
    return [Event("final", msg, conv_state=session.state)]


def detect_strong_intent(text: str) -> Optional[str]:
    """
    Détecte les intents qui préemptent le flow (priorité: TRANSFER > CANCEL > MODIFY > ABANDON > ORDONNANCE > FAQ).
    Délégation au module intent_parser (pur, testable).
    """
    r = intent_parser.detect_strong_intent(text or "", "")
    return r.value if r else None


def detect_ordonnance_choice(user_text: str) -> Optional[str]:
    """
    Détecte si l'utilisateur veut RDV ou MESSAGE (langage naturel, pas menu 1/2).
    Returns: 'rdv' | 'message' | None
    """
    if not user_text or not user_text.strip():
        return None
    msg_lower = user_text.lower().strip()
    rdv_patterns = [
        "rendez-vous", "rdv", "rendez vous",
        "consultation", "consulter",
        "voir le médecin", "voir le docteur",
        "venir", "passer", "viens",
    ]
    message_patterns = [
        "message", "transmett", "transmet",
        "rappel", "rappelez", "rappeler",
        "laiss", "laisser",
        "contact", "contacter",
    ]
    if any(p in msg_lower for p in rdv_patterns):
        return "rdv"
    if any(p in msg_lower for p in message_patterns):
        return "message"
    return None


def should_override_current_flow_v3(session: Session, message: str) -> bool:
    """
    Intent override avec garde-fou anti-boucle (spec V3).
    Ne pas rerouter si déjà dans le bon flow ou si même intent consécutif.
    TRANSFER : exiger une phrase explicite (éviter "humain" / "quelqu'un" seuls = interruption).
    """
    strong = detect_strong_intent(message)
    if not strong:
        return False
    # Ne pas transférer sur un mot court (interruption fréquente : "humain", "quelqu'un")
    if strong == "TRANSFER" and len(message.strip()) < 14:
        return False
    if strong == "CANCEL" and session.state in ("CANCEL_NAME", "CANCEL_NO_RDV", "CANCEL_CONFIRM"):
        return False
    if strong == "MODIFY" and session.state in ("MODIFY_NAME", "MODIFY_NO_RDV", "MODIFY_CONFIRM"):
        return False
    if strong == "ORDONNANCE" and session.state in ("ORDONNANCE_CHOICE", "ORDONNANCE_MESSAGE", "ORDONNANCE_PHONE_CONFIRM"):
        return False
    last = getattr(session, "last_intent", None)
    if strong == last:
        return False
    return True


def detect_correction_intent(text: str) -> bool:
    """Détecte si l'utilisateur demande à recommencer / corriger."""
    t = text.strip().lower()
    if not t:
        return False
    correction_words = [
        "attendez", "recommencez", "recommence", "repetez", "répétez",
        "non c'est pas", "pas ça", "refaites", "recommencer",
    ]
    return any(w in t for w in correction_words)


def detect_user_intent_repeat(message: str) -> Optional[str]:
    """
    Distingue correction (rejouer question) vs répétition (répéter message complet).
    Returns:
        'correction' : user veut corriger → rejouer last_question_asked
        'repeat' : user veut répéter → répéter last_agent_message
        None : autre
    """
    msg_lower = (message or "").strip().lower()
    if not msg_lower:
        return None
    correction_patterns = [
        "attendez", "attends",
        "erreur", "trompé", "je me suis trompé",
        "non attendez", "recommencez", "refaites", "recommence",
        "non c'est pas", "pas ça",
    ]
    if any(p in msg_lower for p in correction_patterns):
        return "correction"
    repeat_patterns = [
        "répét", "repet", "répète",
        "redis", "redire", "encore une fois", "redire encore",
        "vous pouvez répét", "pouvez-vous répét",
        "j'ai pas compris", "pas compris",
        "comprends pas", "comprend pas",
        "pardon", "comment",
    ]
    if any(p in msg_lower for p in repeat_patterns):
        return "repeat"
    return None


def should_trigger_intent_router(session: Session, user_message: str) -> tuple[bool, str]:
    """
    IVR Principe 3 — Un seul mécanisme de sortie universel.
    Détermine si on doit activer INTENT_ROUTER (menu 1/2/3/4).
    Seuils volontairement hauts : privilégier comprendre plutôt que transférer.
    """
    if session.state in ("INTENT_ROUTER", "TRANSFERRED", "CONFIRMED"):
        return False, ""
    if getattr(session, "global_recovery_fails", 0) >= 3:
        return True, "global_fails_3"
    if detect_correction_intent(user_message) and getattr(session, "correction_count", 0) >= 3:
        return True, "correction_repeated"
    if getattr(session, "consecutive_questions", 0) >= 7:
        return True, "blocked_state"
    return False, ""


def increment_recovery_counter(session: Session, context: str) -> int:
    """
    Incrémente le compteur de recovery pour un contexte (analytics + tuning).
    Retourne la valeur après incrément.
    """
    if context == "slot_choice":
        session.slot_choice_fails = getattr(session, "slot_choice_fails", 0) + 1
        return session.slot_choice_fails
    if context == "name":
        session.name_fails = getattr(session, "name_fails", 0) + 1
        return session.name_fails
    if context == "phone":
        session.phone_fails = getattr(session, "phone_fails", 0) + 1
        return session.phone_fails
    if context == "preference":
        session.preference_fails = getattr(session, "preference_fails", 0) + 1
        return session.preference_fails
    if context == "contact_confirm":
        session.contact_confirm_fails = getattr(session, "contact_confirm_fails", 0) + 1
        return session.contact_confirm_fails
    session.global_recovery_fails = getattr(session, "global_recovery_fails", 0) + 1
    return session.global_recovery_fails


def _recovery_limit_for(context: str) -> int:
    """Limite d'échecs pour ce contexte (spec RECOVERY_LIMITS)."""
    limits = getattr(config, "RECOVERY_LIMITS", None) or {}
    return limits.get(context, getattr(Session, "MAX_CONTEXT_FAILS", 3))


def should_escalate_recovery(session: Session, context: str) -> bool:
    """True si ≥ limite du contexte (RECOVERY_LIMITS) échecs sur ce contexte."""
    max_fails = _recovery_limit_for(context)
    if context == "silence":
        count = getattr(session, "empty_message_count", 0)
        return count >= max_fails
    counters = {
        "slot_choice": getattr(session, "slot_choice_fails", 0),
        "name": getattr(session, "name_fails", 0),
        "phone": getattr(session, "phone_fails", 0),
        "preference": getattr(session, "preference_fails", 0),
        "contact_confirm": getattr(session, "contact_confirm_fails", 0),
    }
    return counters.get(context, getattr(session, "global_recovery_fails", 0)) >= max_fails


def handle_no_contextual(session: Session) -> dict:
    """
    Routeur IVR pro : "non" n'est jamais terminal par défaut.
    Retourne {"state": str, "message": str} selon l'état courant.
    """
    st = session.state
    channel = getattr(session, "channel", "web")

    if st == "CONTACT_CONFIRM":
        return {"state": "QUALIF_CONTACT", "message": "D'accord. Quel est votre numéro de téléphone ?"}

    if st == "WAIT_CONFIRM":
        return {"state": "WAIT_CONFIRM", "message": "D'accord. Vous choisissez lequel : 1, 2 ou 3 ?"}

    if st == "CANCEL_CONFIRM":
        return {"state": "CONFIRMED", "message": "Très bien, je garde le rendez-vous. Bonne journée."}

    if st == "MODIFY_CONFIRM":
        return {"state": "CONFIRMED", "message": "Très bien, je garde la date. Bonne journée."}

    if st in {"QUALIF_NAME", "QUALIF_PREF", "QUALIF_CONTACT"}:
        msg = prompts.VOCAL_INTENT_ROUTER if channel == "vocal" else prompts.MSG_INTENT_ROUTER
        return {"state": "INTENT_ROUTER", "message": msg}

    return {"state": "INTENT_ROUTER", "message": prompts.VOCAL_INTENT_ROUTER if channel == "vocal" else prompts.MSG_INTENT_ROUTER}


# ========================
# ENGINE
# ========================

class Engine:
    """
    Moteur de conversation déterministe.
    Applique strictement le PRD + SYSTEM_PROMPT.
    llm_client optionnel : zone grise START uniquement (LLM_ASSIST_ENABLED).
    """
    
    def __init__(self, session_store, faq_store: FaqStore, llm_client: Optional[LLMClient] = None):
        self.session_store = session_store
        self.faq_store = faq_store
        self.llm_client = llm_client
    
    def _save_session(self, session: Session) -> None:
        """Sauvegarde la session (si le store le supporte)."""
        if hasattr(self.session_store, 'save'):
            self.session_store.save(session)

    def _final(self, session: Session, msg: str, *, state: Optional[str] = None) -> List[Event]:
        """
        Fix 7: un seul Event final par tour (critique vocal : webhook n'utilise que events[0].text).
        Ajoute le message à l'historique, sauvegarde, retourne [Event("final", ...)].
        """
        if state is not None:
            session.state = state
        session.add_message("agent", msg)
        self._save_session(session)
        return [Event("final", msg, conv_state=session.state)]

    def _say(self, session: Session, key: str, **kwargs) -> str:
        """
        Envoie un message agent à partir d'une clé prompts (get_message) et enregistre pour REPEAT.
        Retourne le texte envoyé. Aucune string user-facing hors prompts.py.
        """
        channel = getattr(session, "channel", "web")
        msg = prompts.get_message(key, channel=channel, **kwargs)
        if not msg:
            return ""
        session.add_message("agent", msg)
        session.last_say_key = key
        session.last_say_kwargs = dict(kwargs)
        return msg

    # P0 — Raisons techniques (budget s'applique) vs exemptées (transfert immédiat)
    # P0.5bis : toutes les raisons passées à _trigger_intent_router (visits>=2 → budget)
    _TECHNICAL_REASONS = frozenset({
        "start_unclear", "no_faq", "out_of_scope", "faq_no_match", "llm_unclear",
        "start_unclear_3", "out_of_scope_2", "no_faq_3", "faq_no_match_2", "llm_unclear_3",
        "intent_router_loop", "intent_router_unclear", "slot_choice_fails", "slot_choice_fails_3",
        "contact_failed", "phone_invalid", "phone_empty", "phone_partial", "contact_confirm_fails",
        "contact_confirm_fails_3", "noise_repeated", "anti_loop_25", "empty_repeated_3",
        "yes_ambiguous_2", "yes_ambiguous_3", "booking_intent_repeat_3",
        "name_fails_3", "preference_fails_3", "cancel_name_fails_3", "modify_name_fails_3",
        "cancel_not_found_3", "modify_not_found_3", "cancel_confirm_unclear_3",
        "time_constraint_impossible",
        "name_fails", "preference_fails", "cancel_name_fails", "modify_name_fails",
        "consent_fails", "qualif_motif_invalid", "unknown_state", "exception_fallback",
    })

    def _trigger_transfer(
        self,
        session: Session,
        channel: str,
        reason: str,
        user_text: str = "",
        msg_key: Optional[str] = None,
        custom_msg: Optional[str] = None,
    ) -> List[Event]:
        """
        Centralise le transfert : state=TRANSFERRED, log, persist avec reason.
        Ne pas appeler si _maybe_prevent_transfer a retourné une réponse.
        """
        state_before = getattr(session, "_turn_state_before", session.state)
        budget = getattr(session, "transfer_budget_remaining", 2)
        reset_slots_reading(session)  # Fix #4: sortie WAIT_CONFIRM
        session.state = "TRANSFERRED"
        session.transfer_logged = True
        ctx = json.dumps({
            "reason": reason,
            "state_at_transfer": state_before,
            "budget_remaining": budget,
            "turn_count": getattr(session, "turn_count", 0),
        })
        _persist_ivr_event(session, "transferred_human", context=ctx, reason=reason)
        logger.info(
            "[TRANSFER] conv_id=%s tenant_id=%s state=%s reason=%s budget=%s",
            session.conv_id,
            getattr(session, "tenant_id", None),
            state_before,
            reason,
            budget,
        )
        if custom_msg:
            msg = custom_msg
        elif msg_key:
            msg = prompts.get_message(msg_key, channel=channel)
        else:
            msg = prompts.VOCAL_TRANSFER_COMPLEX if channel == "vocal" else prompts.MSG_TRANSFER
        session.add_message("agent", msg)
        self._save_session(session)
        return [Event("final", msg, conv_state=session.state, transfer_reason=reason)]

    def _maybe_prevent_transfer(
        self,
        session: Session,
        channel: str,
        reason: str,
        user_text: str,
    ) -> Optional[List[Event]]:
        """
        Si reason technique et budget > 0 : consomme 1, envoie menu (contextuel ou global), pas de transfert.
        P0.6 : menu contextuel en WAIT_CONFIRM/QUALIF_CONTACT/CONTACT_CONFIRM → rester dans le flow.
        Retourne None si transfert doit avoir lieu (budget épuisé ou reason exemptée).
        """
        if reason not in self._TECHNICAL_REASONS:
            return None
        budget = getattr(session, "transfer_budget_remaining", 2)
        if budget <= 0:
            return None
        session.transfer_budget_remaining = budget - 1
        remaining = session.transfer_budget_remaining
        logger.info(
            "[TRANSFER_BUDGET] conv_id=%s reason=%s remaining=%s state=%s",
            session.conv_id,
            reason,
            remaining,
            session.state,
        )
        ctx = json.dumps({"reason": reason, "remaining": remaining})
        _persist_ivr_event(session, "transfer_prevented", context=ctx, reason=reason)
        channel = getattr(session, "channel", "web")
        # P0.6 — Menu contextuel : rester dans le flow, pas reset global
        state = session.state
        if state == "WAIT_CONFIRM":
            if getattr(session, "slot_proposal_sequential", False):
                msg = prompts.VOCAL_SAFE_RECOVERY_WAIT_CONFIRM_YESNO if channel == "vocal" else prompts.MSG_SAFE_RECOVERY_WAIT_CONFIRM_YESNO
            else:
                msg = prompts.VOCAL_SAFE_RECOVERY_WAIT_CONFIRM_123 if channel == "vocal" else prompts.MSG_SAFE_RECOVERY_WAIT_CONFIRM_123
            # Rester en WAIT_CONFIRM pour que l'utilisateur puisse répondre 1/2/3 ou oui/non
        elif state == "QUALIF_CONTACT":
            msg = prompts.VOCAL_SAFE_RECOVERY_QUALIF_CONTACT if channel == "vocal" else prompts.MSG_SAFE_RECOVERY_QUALIF_CONTACT
            # Rester en QUALIF_CONTACT
        elif state == "CONTACT_CONFIRM":
            msg = prompts.VOCAL_SAFE_RECOVERY_CONTACT_CONFIRM if channel == "vocal" else prompts.MSG_SAFE_RECOVERY_CONTACT_CONFIRM
            # Rester en CONTACT_CONFIRM
        else:
            # Menu global (START, INTENT_ROUTER, etc.)
            if remaining == 1:
                msg = prompts.VOCAL_SAFE_DEFAULT_MENU_1 if channel == "vocal" else prompts.MSG_SAFE_DEFAULT_MENU_1_WEB
            else:
                msg = prompts.VOCAL_SAFE_DEFAULT_MENU_2 if channel == "vocal" else prompts.MSG_SAFE_DEFAULT_MENU_2_WEB
            session.state = "INTENT_ROUTER"
            session.intent_router_unclear_count = 0
        session.add_message("agent", msg)
        self._save_session(session)
        return [Event("final", msg, conv_state=session.state)]

    def handle_message(self, conv_id: str, user_text: str) -> List[Event]:
        """
        Pipeline déterministe (ordre STRICT).
        
        Returns:
            Liste d'events à envoyer via SSE
        """
        import time
        t_load_start = time.time()
        
        session = self.session_store.get_or_create(conv_id)
        t_load_end = time.time()
        logger.debug("[SESSION] conv_id=%s loaded in %.0fms", conv_id, (t_load_end - t_load_start) * 1000)

        # Feature flags par tenant (P0) — cache TTL 60s, log 1x par call (premier tour)
        turn_count = getattr(session, "turn_count", 0)
        if turn_count == 0 or not getattr(session, "flags_effective", None):
            tf = get_tenant_flags(getattr(session, "tenant_id", None))
            session.flags_effective = tf.flags
            session.tenant_id = tf.tenant_id
            logger.info(
                "[TENANT_FLAGS] conv_id=%s tenant_id=%s source=%s updated_at=%s flags_effective=%s",
                conv_id,
                tf.tenant_id,
                tf.source,
                tf.updated_at,
                tf.flags,
            )

        setattr(session, "_turn_state_before", session.state)
        session.add_message("user", user_text)
        
        turn_count = getattr(session, "turn_count", 0)
        logger.debug(
            "[FLOW] conv_id=%s state=%s name=%s pending=%s user=%s",
            conv_id, session.state, (session.qualif_data.name or "")[:20],
            len(session.pending_slots or []), _mask_for_log(user_text or ""),
        )
        logger.info(
            "[FLOW] conv_id=%s state=%s turn_count=%s user=%s",
            conv_id,
            session.state,
            turn_count,
            (user_text or "")[:50],
        )

        # Fix #4: invariant — hors WAIT_CONFIRM ⇒ is_reading_slots False (correction si checkpoint incohérent)
        if session.state != "WAIT_CONFIRM" and getattr(session, "is_reading_slots", False):
            logger.warning("[SLOTS_READING] conv_id=%s state=%s reset is_reading_slots (invariant)", conv_id, session.state)
            reset_slots_reading(session)
        
        # ========================
        # RÈGLE -1 : TRIAGE MÉDICAL (priorité absolue, avant tout le reste)
        # ========================
        # 1) Urgence vitale (red flags) → hard stop + log d'audit (catégorie uniquement, pas de symptôme)
        red_flag_category = detect_medical_red_flag(user_text) if user_text else None
        if red_flag_category:
            logger.warning(
                MEDICAL_RED_FLAG_TRIGGERED,
                extra={
                    "event": MEDICAL_RED_FLAG_TRIGGERED,
                    "call_id": conv_id,
                    "category": red_flag_category,
                    "state": session.state,
                    "action": "emergency_orientation",
                    "channel": getattr(session, "channel", "web"),
                },
            )
            session.state = "EMERGENCY"
            self._save_session(session)
            msg = prompts.VOCAL_MEDICAL_EMERGENCY
            session.add_message("agent", msg)
            _log_turn_debug(session)
            return [Event("final", msg, conv_state=session.state)]
        
        # 2) Non vital / escalade douce → note motif, enchaîne sur créneau (QUALIF_PREF)
        if user_text:
            medical_class = classify_medical_symptoms(user_text)
            if medical_class:
                motif = extract_symptom_motif_short(user_text)
                setattr(session, "medical_motif", motif)
                session.qualif_data.motif = motif
                session.state = "QUALIF_PREF"
                if medical_class == "CAUTION":
                    reply = prompts.MSG_MEDICAL_CAUTION
                else:
                    reply = prompts.MSG_MEDICAL_NON_URGENT_ACK.format(motif=motif)
                session.last_question_asked = reply
                session.add_message("agent", reply)
                self._save_session(session)
                return safe_reply([Event("final", reply, conv_state=session.state)], session)
        
        # ========================
        # TERMINAL GATE (mourir proprement)
        # ========================
        # Si la conversation est déjà terminée (ou urgence médicale), on ne relance pas de flow.
        if session.state in ["CONFIRMED", "TRANSFERRED", "EMERGENCY"]:
            if session.state == "EMERGENCY":
                msg = prompts.VOCAL_MEDICAL_EMERGENCY
                session.add_message("agent", msg)
                setattr(session, "_turn_assistant_text", msg)
                _log_turn_debug(session)
                return [Event("final", msg, conv_state=session.state)]
            # Anti-boucle terminale : en CONFIRMED/TRANSFERRED, si user dit ABANDON/merci/au revoir → "Au revoir." une fois max (évite écho STT).
            if session.state in ["TRANSFERRED", "CONFIRMED"]:
                strong_terminal = detect_strong_intent(user_text or "")
                if strong_terminal == "ABANDON":
                    channel = getattr(session, "channel", "web")
                    msg = prompts.VOCAL_FAQ_GOODBYE if channel == "vocal" else prompts.MSG_FAQ_GOODBYE_WEB
                    session.add_message("agent", msg)
                    setattr(session, "_turn_assistant_text", msg)
                    _log_turn_debug(session)
                    return [Event("final", msg, conv_state=session.state)]
                intent_terminal = detect_intent(user_text, session.state)
                if intent_terminal == "REPEAT":
                    # 1) last_say_key prioritaire (re-render fiable, notamment transfer/transfer_complex)
                    last_key = getattr(session, "last_say_key", None)
                    last_kw = getattr(session, "last_say_kwargs", None) or {}
                    channel = getattr(session, "channel", "web")
                    if last_key:
                        try:
                            msg = prompts.get_message(last_key, channel=channel, **last_kw)
                            if msg:
                                session.add_message("agent", msg)
                                setattr(session, "_turn_assistant_text", msg)
                                _log_turn_debug(session)
                                return [Event("final", msg, conv_state=session.state)]
                        except Exception:
                            pass
                    # 2) Dernier message agent dans l'historique (session.messages)
                    last_msg = None
                    if session.messages:
                        agent_texts = [m.text for m in session.messages if m.role == "agent" and m.text and m.text.strip()]
                        if agent_texts:
                            last_msg = agent_texts[-1]
                    if not last_msg:
                        last_msg = getattr(session, "last_agent_message", None) or getattr(session, "last_question_asked", None)
                    if last_msg and (user_text or "").strip() and (last_msg.strip() or "").lower() == (user_text or "").strip().lower():
                        last_msg = None  # anti-echo : ne jamais relire le message user
                    if last_msg:
                        session.add_message("agent", last_msg)
                        setattr(session, "_turn_assistant_text", last_msg)
                        _log_turn_debug(session)
                        return [Event("final", last_msg, conv_state=session.state)]
            msg = prompts.MSG_CONVERSATION_CLOSED
            session.add_message("agent", msg)
            setattr(session, "_turn_assistant_text", msg)
            _log_turn_debug(session)
            return [Event("final", msg, conv_state=session.state)]
        
        # ========================
        # P0.5 CONSENT MODE EXPLICIT (vocal uniquement, state START)
        # ========================
        channel = getattr(session, "channel", "web")
        if channel == "vocal" and session.state == "START":
            consent_mode = get_consent_mode(getattr(session, "tenant_id", None))
            if consent_mode == "explicit":
                if not getattr(session, "consent_prompted", False):
                    # Premier message : demander le consentement (ignorer le contenu user)
                    session.consent_prompted = True
                    session.awaiting_confirmation = "CONFIRM_CONSENT"
                    msg = prompts.VOCAL_CONSENT_PROMPT
                    session.add_message("agent", msg)
                    self._save_session(session)
                    return safe_reply([Event("final", msg, conv_state=session.state)], session)
                if getattr(session, "awaiting_confirmation", None) == "CONFIRM_CONSENT":
                    # Réponse à la demande de consentement
                    if intent_parser._is_yes(user_text or ""):
                        try:
                            persist_consent_obtained(session, channel="vocal")
                            setattr(session, "_consent_obtained_persisted", True)
                        except Exception:
                            pass
                        session.consent_obtained = True
                        session.awaiting_confirmation = None
                        # Continue le flow avec user_text (ex. "oui" → clarification)
                    elif intent_parser._is_no(user_text or "") or (detect_strong_intent(user_text or "") == "ABANDON"):
                        session.awaiting_confirmation = None
                        evts = self._trigger_transfer(
                            session, channel, "consent_denied",
                            user_text=user_text or "",
                            custom_msg=prompts.VOCAL_CONSENT_DENIED_TRANSFER,
                        )
                        return safe_reply(evts, session)
                    else:
                        # UNCLEAR
                        session.consent_fails = getattr(session, "consent_fails", 0) + 1
                        if session.consent_fails >= 2:
                            session.awaiting_confirmation = None
                            prev = self._maybe_prevent_transfer(session, channel, "consent_fails", user_text or "")
                            if prev is not None:
                                return safe_reply(prev, session)
                            evts = self._trigger_transfer(session, channel, "consent_fails", user_text=user_text or "")
                            return safe_reply(evts, session)
                        msg = prompts.VOCAL_CONSENT_CLARIFY
                        session.add_message("agent", msg)
                        self._save_session(session)
                        return safe_reply([Event("final", msg, conv_state=session.state)], session)
        
        # ========================
        # 1. ANTI-LOOP GUARD (spec V3 — ordre pipeline NON NÉGOCIABLE)
        # ========================
        session.turn_count = getattr(session, "turn_count", 0) + 1
        session.router_epoch_turns = getattr(session, "router_epoch_turns", 0) + 1
        max_turns = getattr(Session, "MAX_TURNS_ANTI_LOOP", 25)
        # Anti-loop: router_epoch_turns (depuis dernier menu) ou turn_count total
        epoch = getattr(session, "router_epoch_turns", 0)
        if epoch > max_turns or session.turn_count > max_turns * 2:
            logger.info(
                "[ANTI_LOOP] conv_id=%s turn_count=%s router_epoch=%s max=%s",
                conv_id,
                session.turn_count,
                epoch,
                max_turns,
            )
            _persist_ivr_event(session, "anti_loop_trigger")
            return safe_reply(
                self._trigger_intent_router(session, "anti_loop_25", user_text or ""),
                session,
            )
        
        # ========================
        # 2. INTENT OVERRIDE CRITIQUES (CANCEL / TRANSFER / ABANDON) — priorité absolue
        # ========================
        channel = getattr(session, "channel", "web")
        if should_override_current_flow_v3(session, user_text):
            strong = detect_strong_intent(user_text)
            session.last_intent = strong
            setattr(session, "last_strong_intent", strong)
            log_ivr_event(logger, session, "intent_override")
            if strong == "CANCEL":
                return safe_reply(self._start_cancel(session), session)
            if strong == "MODIFY":
                return safe_reply(self._start_modify(session), session)
            if strong == "TRANSFER":
                from backend.transfer_policy import classify_transfer_request
                kind = classify_transfer_request(user_text or "")
                if kind == "SHORT":
                    session.state = "CLARIFY"
                    msg = prompts.VOCAL_CLARIFY if channel == "vocal" else prompts.MSG_CLARIFY_WEB
                    session.add_message("agent", msg)
                    return safe_reply([Event("final", msg, conv_state=session.state)], session)
                if kind == "EXPLICIT":
                    return safe_reply(self._trigger_transfer(session, channel, "user_requested", msg_key="transfer_complex"), session)
                # NONE: ne pas override, laisser le pipeline continuer
            if strong == "ABANDON":
                session.state = "CONFIRMED"
                msg = prompts.MSG_END_POLITE_ABANDON if hasattr(prompts, "MSG_END_POLITE_ABANDON") else (prompts.VOCAL_USER_ABANDON if channel == "vocal" else prompts.MSG_ABANDON_WEB)
                session.add_message("agent", msg)
                _persist_ivr_event(session, "user_abandon")
                return safe_reply([Event("final", msg, conv_state=session.state)], session)
            if strong == "ORDONNANCE":
                return safe_reply(self._handle_ordonnance_flow(session, user_text), session)
        
        # ========================
        # 2b. CORRECTION vs RÉPÉTITION (avant guards)
        # ========================
        repeat_intent = detect_user_intent_repeat(user_text)
        if repeat_intent == "correction":
            if getattr(session, "last_question_asked", None):
                msg = session.last_question_asked
                session.add_message("agent", msg)
                return safe_reply([Event("final", msg, conv_state=session.state)], session)
            msg = "D'accord. Que souhaitez-vous corriger ?"
            session.add_message("agent", msg)
            return safe_reply([Event("final", msg, conv_state=session.state)], session)
        if repeat_intent == "repeat":
            if getattr(session, "last_agent_message", None):
                msg = session.last_agent_message
                return safe_reply([Event("final", msg, conv_state=session.state)], session)
            msg = "Désolé, je n'ai rien à répéter."
            session.add_message("agent", msg)
            return safe_reply([Event("final", msg, conv_state=session.state)], session)
        
        # ========================
        # 3. GUARDS BASIQUES (vide, langue, spam)
        # ========================
        
        # --- Protection overlap pendant TTS (Règle 11) : silence pendant que l'agent parle → pas de pénalité ---
        import time as _time
        speaking_until = getattr(session, "speaking_until_ts", 0) or 0
        if speaking_until and _time.time() < speaking_until:
            if not user_text or not user_text.strip():
                channel = getattr(session, "channel", "web")
                msg = "Je vous écoute." if channel == "vocal" else getattr(prompts, "MSG_SILENCE_1", "Je n'ai rien entendu. Pouvez-vous répéter ?")
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
        
        # --- RÈGLE 3: SILENCE (2 messages distincts + 3e => INTENT_ROUTER) ---
        if not user_text or not user_text.strip():
            session.empty_message_count = getattr(session, "empty_message_count", 0) + 1
            _persist_ivr_event(session, "empty_message")

            if session.empty_message_count == 1:
                msg = getattr(prompts, "MSG_SILENCE_1", "Je n'ai rien entendu. Pouvez-vous répéter ?")
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]

            if session.empty_message_count == 2:
                msg = getattr(prompts, "MSG_SILENCE_2", "Êtes-vous toujours là ?")
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]

            # 3e fois => INTENT_ROUTER
            return safe_reply(
                self._trigger_intent_router(session, "empty_repeated_3", user_text or ""),
                session,
            )

        session.empty_message_count = 0  # Reset quand message non vide
        
        # ========================
        # Fast-path barge-in : choix créneau pendant lecture (prime sur REPEAT/UNCLEAR)
        # Gate : is_reading_slots + pending non vide (pas state, pour couvrir 2 tours / QUALIF→slots)
        # ========================
        pending = session.pending_slots or []
        num_slots = len(pending) if pending else 0
        if getattr(session, "is_reading_slots", False) and num_slots > 0 and user_text and user_text.strip():
            _t_ascii = intent_parser.normalize_stt_text(user_text or "")
            # Fix 5: strong intent AVANT slot_choice (annuler/humain pendant énumération → route direct)
            strong = detect_strong_intent(user_text or "")
            if strong in ("CANCEL", "MODIFY", "TRANSFER", "ABANDON"):
                reset_slots_reading(session)
                if strong == "CANCEL":
                    return safe_reply(self._start_cancel(session), session)
                if strong == "MODIFY":
                    return safe_reply(self._start_modify(session), session)
                if strong == "TRANSFER":
                    from backend.transfer_policy import classify_transfer_request
                    kind = classify_transfer_request(user_text or "")
                    if kind == "SHORT":
                        msg = prompts.VOCAL_CLARIFY if channel == "vocal" else prompts.MSG_CLARIFY_WEB
                        session.add_message("agent", msg)
                        return safe_reply([Event("final", msg, conv_state=session.state)], session)
                    if kind == "EXPLICIT":
                        return safe_reply(self._trigger_transfer(session, channel, "user_requested", msg_key="transfer_complex"), session)
                    # NONE: fallback transfer (comportement conservateur)
                    return safe_reply(self._trigger_transfer(session, channel, "user_requested", msg_key="transfer_complex"), session)
                if strong == "ABANDON":
                    session.state = "CONFIRMED"
                    msg = prompts.MSG_END_POLITE_ABANDON if hasattr(prompts, "MSG_END_POLITE_ABANDON") else (prompts.VOCAL_USER_ABANDON if channel == "vocal" else prompts.MSG_ABANDON_WEB)
                    session.add_message("agent", msg)
                    _persist_ivr_event(session, "user_abandon")
                    return safe_reply([Event("final", msg, conv_state=session.state)], session)
            slot_choice = intent_parser.extract_slot_choice(_t_ascii, num_slots=num_slots)
            if slot_choice and 1 <= slot_choice <= num_slots:
                logger.info(
                    "[INTERRUPTION] conv_id=%s client chose slot %s during enumeration (fast-path), slots_count=%s",
                    session.conv_id,
                    slot_choice,
                    num_slots,
                )
                reset_slots_reading(session)
                session.slots_preface_sent = False
                session.slots_list_sent = False
                return safe_reply(self._handle_booking_confirm(session, user_text), session)
            
            if intent_parser._is_no(user_text):
                reset_slots_reading(session)
                session.slots_preface_sent = False
                session.slots_list_sent = False
                msg = getattr(prompts, "MSG_SLOT_BARGE_IN_HELP", "D'accord. Dites juste 1, 2 ou 3.")
                session.add_message("agent", msg)
                return safe_reply([Event("final", msg, conv_state=session.state)], session)
            
            if intent_parser._is_repeat(user_text):
                ch = getattr(session, "channel", "web")
                slots = session.pending_slots or []
                if ch == "vocal":
                    list_msg = prompts.format_slot_list_vocal_only(slots) if len(slots) >= 3 else prompts.format_slot_proposal(slots, include_instruction=True, channel=ch)
                else:
                    list_msg = prompts.format_slot_proposal(slots, include_instruction=True, channel=ch)
                session.add_message("agent", list_msg)
                return safe_reply([Event("final", list_msg, conv_state=session.state)], session)
            
            if "attendez" in _t_ascii or "attends" in _t_ascii:
                reset_slots_reading(session)
                msg = getattr(prompts, "MSG_SLOT_BARGE_IN_HELP", "D'accord. Dites juste 1, 2 ou 3.")
                session.add_message("agent", msg)
                return safe_reply([Event("final", msg, conv_state=session.state)], session)
        
        # Message trop long
        is_valid, error_msg = guards.validate_length(user_text)
        if not is_valid:
            session.add_message("agent", error_msg)
            return [Event("final", error_msg, conv_state=session.state)]
        
        # Langue non française
        if not guards.detect_language_fr(user_text):
            msg = prompts.MSG_FRENCH_ONLY
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        # Test 10.1 — Frustration légère (putain ça marche pas) → réponse calme, recentrer (pas transfert)
        if getattr(session, "channel", "web") == "vocal" and guards.is_light_frustration(user_text):
            msg = prompts.VOCAL_INSULT_RESPONSE
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        # Spam/abus lourd → transfert silencieux
        if guards.is_spam_or_abuse(user_text):
            session.state = "TRANSFERRED"
            return [Event("transfer", "", transfer_reason="spam", silent=True)]
        
        # ========================
        # 2. SESSION GATE
        # ========================
        
        if session.is_expired():
            session.reset()
            msg = prompts.MSG_SESSION_EXPIRED
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state="START")]
        
        # ========================
        # 3. ROUTING : Intent-based
        # ========================
        
        # Détecter l'intent (state utilisé pour garde-fou START+YES => UNCLEAR)
        intent = detect_intent(user_text, session.state)
        # Garde-fou "rien" : ABANDON seulement en POST_FAQ / POST_FAQ_CHOICE, sinon UNCLEAR
        if intent == "ABANDON" and (user_text or "").strip().lower() == "rien":
            if session.state not in ("POST_FAQ", "POST_FAQ_CHOICE"):
                intent = "UNCLEAR"
        # YES/NO hors états acceptant oui/non => UNCLEAR (éviter "d'accord" = action directe)
        if intent in ("YES", "NO") and session.state not in STATES_ACCEPTING_YESNO:
            intent = "UNCLEAR"
        logger.debug("[INTENT] conv_id=%s intent=%s user=%s", session.conv_id, intent, _mask_for_log(user_text or ""))
        
        # REPEAT : relire le dernier prompt exact (pas re-router, pas d'escalade, état inchangé).
        # Idempotent sur is_reading_slots / slots_preface_sent / slots_list_sent : ne pas les modifier.
        if intent == "REPEAT":
            _persist_ivr_event(session, "repeat_used")
            last_key = getattr(session, "last_say_key", None)
            last_kw = getattr(session, "last_say_kwargs", None) or {}
            if last_key:
                try:
                    msg = prompts.get_message(last_key, channel=channel, **last_kw)
                    if msg:
                        session.add_message("agent", msg)
                        return safe_reply([Event("final", msg, conv_state=session.state)], session)
                except Exception:
                    pass
            last_msg = getattr(session, "last_agent_message", None) or getattr(session, "last_question_asked", None)
            # Anti-echo : ne jamais relire le message user (évite "ça sera tout merci" répété)
            if last_msg and (user_text or "").strip() and (last_msg.strip() or "").lower() == (user_text or "").strip().lower():
                last_msg = None
            if last_msg:
                session.add_message("agent", last_msg)
                return safe_reply([Event("final", last_msg, conv_state=session.state)], session)
            msg = getattr(prompts, "VOCAL_NOT_UNDERSTOOD", "Je n'ai pas bien compris. Pouvez-vous répéter ?")
            if channel != "vocal":
                msg = getattr(prompts, "MSG_UNCLEAR_1", msg)
            session.add_message("agent", msg)
            return safe_reply([Event("final", msg, conv_state=session.state)], session)
        
        # --- CORRECTION : incrémenter avant should_trigger (IVR Principe 3) ---
        if detect_correction_intent(user_text):
            session.correction_count = getattr(session, "correction_count", 0) + 1
        
        # --- IVR Principe 3 : Sortie universelle unique (should_trigger_intent_router) ---
        should_trigger, trigger_reason = should_trigger_intent_router(session, user_text)
        if should_trigger and trigger_reason:
            return safe_reply(
                self._trigger_intent_router(session, trigger_reason, user_text),
                session,
            )
        
        # --- NO contextuel (sauf WAIT_CONFIRM séquentiel → géré plus bas) ---
        if intent == "NO" and session.state in NO_CONTEXTUAL_STATES and session.state != "WAIT_CONFIRM":
            result = handle_no_contextual(session)
            session.state = result["state"]
            msg = result["message"]
            session.add_message("agent", msg)
            if result["state"] == "INTENT_ROUTER":
                session.last_question_asked = msg
            return safe_reply([Event("final", msg, conv_state=session.state)], session)
        
        # --- Reset yes_ambiguous_count sur toute réponse non-YES (éviter escalade trop tôt) ---
        if intent != "YES":
            session.yes_ambiguous_count = 0

        # --- YES disambiguation : éviter "oui" ambigu (créneau / préférence / contact / "ok j'écoute") ---
        if intent == "YES" and session.state in YESNO_CONFIRM_STATES:
            if getattr(session, "awaiting_confirmation", None):
                session.yes_ambiguous_count = 0
            else:
                last_msg = getattr(session, "last_agent_message", None) or ""
                last_q = getattr(session, "last_question_asked", None) or ""
                has_question = "?" in last_msg or "?" in last_q or any(
                    q in (last_msg + " " + last_q).lower() for q in ["dites", "quel", "préférez", "confirmez", "correct", "voulez"]
                )
                if not has_question:
                    session.yes_ambiguous_count = getattr(session, "yes_ambiguous_count", 0) + 1
                    _in_booking = session.state in (
                        "QUALIF_NAME", "QUALIF_MOTIF", "QUALIF_PREF", "QUALIF_CONTACT",
                        "WAIT_CONFIRM", "CONTACT_CONFIRM",
                    )
                    if session.yes_ambiguous_count >= 3:
                        _persist_ivr_event(session, "yes_ambiguous_router", reason="yes_ambiguous_3")
                        return safe_reply(self._trigger_intent_router(session, "yes_ambiguous_3", user_text), session)
                    if session.yes_ambiguous_count >= 2 and _in_booking:
                        msg = getattr(prompts, "CLARIFY_YES_BOOKING_TIGHT", "Pour être sûr : vous confirmez le créneau, oui ou non ?")
                        session.add_message("agent", msg)
                        return safe_reply([Event("final", msg, conv_state=session.state)], session)
                    if session.yes_ambiguous_count >= 2:
                        _persist_ivr_event(session, "yes_ambiguous_router", reason="yes_ambiguous_2")
                        return safe_reply(self._trigger_intent_router(session, "yes_ambiguous_2", user_text), session)
                    msg = getattr(prompts, "CLARIFY_YES_GENERIC", "Oui — vous confirmez le créneau, ou vous préférez autre chose ?")
                    session.add_message("agent", msg)
                    return safe_reply([Event("final", msg, conv_state=session.state)], session)
        
        # --- FLOWS EN COURS ---
        
        # P1.6 — Strong intents (CANCEL/MODIFY/TRANSFER/ABANDON/FAQ) préemptent même en plein booking
        if session.state in ("QUALIF_NAME", "QUALIF_MOTIF", "QUALIF_PREF", "QUALIF_CONTACT", "WAIT_CONFIRM"):
            strong = detect_strong_intent(user_text or "")
            if strong == "CANCEL":
                return safe_reply(self._start_cancel(session), session)
            if strong == "MODIFY":
                return safe_reply(self._start_modify(session), session)
            if strong == "TRANSFER":
                from backend.transfer_policy import classify_transfer_request
                kind = classify_transfer_request(user_text or "")
                if kind == "SHORT":
                    session.state = "CLARIFY"
                    msg = prompts.VOCAL_CLARIFY if channel == "vocal" else prompts.MSG_CLARIFY_WEB
                    session.add_message("agent", msg)
                    return safe_reply([Event("final", msg, conv_state=session.state)], session)
                if kind in ("EXPLICIT", "NONE"):
                    return safe_reply(self._trigger_transfer(session, channel, "user_requested", msg_key="transfer_complex"), session)
            if strong == "ABANDON":
                session.state = "CONFIRMED"
                msg = prompts.VOCAL_USER_ABANDON if channel == "vocal" else prompts.MSG_ABANDON_WEB
                session.add_message("agent", msg)
                return safe_reply([Event("final", msg, conv_state=session.state)], session)
            if strong == "FAQ":
                session.state = "START"
                return safe_reply(self._handle_faq(session, user_text, include_low=True), session)
        
        # P2.1 FSM2 : QUALIF_NAME et WAIT_CONFIRM via dispatcher (si USE_FSM2=True)
        if getattr(config, "USE_FSM2", False) and session.state in ("QUALIF_NAME", "WAIT_CONFIRM"):
            from backend.fsm2 import dispatch_handle, InputEvent, InputKind
            ev = InputEvent(
                kind=InputKind.TEXT,
                text=user_text or "",
                text_normalized=(user_text or "").strip().lower(),
                strong_intent=intent,
            )
            events = dispatch_handle(session, ev, self)
            if events:
                return safe_reply(events, session)
        
        # INTENT_ROUTER (menu 1/2/3/4)
        if session.state == "INTENT_ROUTER":
            return safe_reply(self._handle_intent_router(session, user_text), session)
        
        # PREFERENCE_CONFIRM (après inférence contextuelle)
        if session.state == "PREFERENCE_CONFIRM":
            return safe_reply(self._handle_preference_confirm(session, user_text), session)
        
        # Si en cours de qualification → continuer le flow
        if session.state in ["QUALIF_NAME", "QUALIF_MOTIF", "QUALIF_PREF", "QUALIF_CONTACT"]:
            return safe_reply(self._handle_qualification(session, user_text), session)
        
        # Si en aide contact → gérer guidance
        if session.state == "AIDE_CONTACT":
            return safe_reply(self._handle_aide_contact(session, user_text), session)
        
        # Si en attente de confirmation → valider
        if session.state == "WAIT_CONFIRM":
            return safe_reply(self._handle_booking_confirm(session, user_text), session)
        
        # Si en flow CANCEL
        if session.state in ["CANCEL_NAME", "CANCEL_NO_RDV", "CANCEL_CONFIRM"]:
            return safe_reply(self._handle_cancel(session, user_text), session)
        
        # Si en flow MODIFY
        if session.state in ["MODIFY_NAME", "MODIFY_NO_RDV", "MODIFY_CONFIRM"]:
            return safe_reply(self._handle_modify(session, user_text), session)
        
        # Si en flow ORDONNANCE (conversation naturelle RDV vs message)
        if session.state in ["ORDONNANCE_CHOICE"]:
            return safe_reply(self._handle_ordonnance_flow(session, user_text), session)
        if session.state == "ORDONNANCE_MESSAGE":
            return safe_reply(self._handle_ordonnance_message(session, user_text), session)
        if session.state == "ORDONNANCE_PHONE_CONFIRM":
            return safe_reply(self._handle_ordonnance_phone_confirm(session, user_text), session)
        
        # Si en flow CLARIFY
        if session.state == "CLARIFY":
            return safe_reply(self._handle_clarify(session, user_text, intent), session)
        
        # Si en confirmation de contact
        if session.state == "CONTACT_CONFIRM":
            return safe_reply(self._handle_contact_confirm(session, user_text), session)
        
        # --- NOUVEAU FLOW : First Message ---
        if session.state == "START":
            strong_intent = detect_strong_intent(user_text)
            r = route_start(
                user_text,
                state=session.state,
                channel=channel,
                llm_client=self.llm_client,
                should_try_llm_assist=lambda text, intent, strong: self._should_try_llm_assist(text, intent, strong),
                strong_intent=strong_intent,
                llm_assist_min_confidence=LLM_ASSIST_MIN_CONFIDENCE,
            )

            # 3) reconcile routing
            intent = r.intent
            # strong intents ALWAYS override (sauf BOOKING avec très haute confiance)
            if strong_intent in ("TRANSFER", "CANCEL", "MODIFY", "ABANDON", "ORDONNANCE"):
                if not (intent == "BOOKING" and getattr(r, "confidence", 0.0) >= 0.80):
                    intent = strong_intent
                    r.source = f"{getattr(r, 'source', 'router')}+strong_override"
                    r.confidence = max(getattr(r, "confidence", 0.0), 0.95)
            # FAQ strong override (UNCLEAR -> FAQ si lexique fort)
            if strong_intent == "FAQ" and intent == "UNCLEAR":
                intent = "FAQ"
                r.source = f"{getattr(r, 'source', 'router')}+strong_override"
                r.confidence = max(getattr(r, "confidence", 0.0), 0.85)

            why = ""
            ent = getattr(r, "entities", None) or {}
            if ent.get("heuristic_score") is not None:
                why = f"heuristic_score={ent['heuristic_score']}"
            elif ent.get("llm_bucket"):
                why = f"llm_bucket={ent.get('llm_bucket')}"
            decision_path = getattr(r, "source", "na")
            logger.info(
                "[TURN][START_ROUTE] decision_path=%s intent=%s conf=%.2f strong=%s why=%s text=%r",
                decision_path,
                intent,
                float(getattr(r, "confidence", 0.0)),
                strong_intent,
                why,
                (user_text or "")[:200],
            )

            # --- START: post-route special handling (ex-"Zone grise" via route_start) ---
            if intent == "OUT_OF_SCOPE":
                session.start_unclear_count = 0
                session.start_out_of_scope_count = getattr(session, "start_out_of_scope_count", 0) + 1
                if session.start_out_of_scope_count >= 2:
                    session.start_out_of_scope_count = 0
                    return safe_reply(
                        self._trigger_intent_router(session, "out_of_scope_2", user_text),
                        session,
                    )
                session.state = "START"  # pas terminal : relance structurée ("Que souhaitez-vous ?")
                msg = None
                if getattr(r, "entities", None):
                    msg = r.entities.get("out_of_scope_response")
                if msg:
                    session.add_message("agent", msg)
                    session.last_say_key, session.last_say_kwargs = "out_of_scope_llm", {}
                else:
                    msg = self._say(session, "out_of_scope")
                    if not msg:
                        msg = prompts.get_message("out_of_scope", channel=getattr(session, "channel", "web"))
                        session.add_message("agent", msg)
                self._save_session(session)
                return safe_reply([Event("final", msg, conv_state=session.state)], session)
            if intent == "FAQ" and getattr(r, "entities", None) and r.entities.get("faq_bucket"):
                bucket = r.entities["faq_bucket"]
                if bucket in FAQ_BUCKET_WHITELIST and bucket != "AUTRE":
                    return safe_reply(
                        self._handle_faq_bucket(session, bucket, user_text),
                        session,
                    )
                return safe_reply(self._handle_faq(session, user_text, include_low=True), session)

            # UNCLEAR type "oui" seul → CLARIFY (disambiguation RDV / question). Autre UNCLEAR → _handle_faq (progression 1→2→3 vers INTENT_ROUTER).
            if intent == "UNCLEAR" and guards.is_yes_only(user_text or ""):
                session.start_unclear_count = 0
                session.state = "CLARIFY"
                msg = prompts.VOCAL_CLARIFY_YES_START if channel == "vocal" else prompts.MSG_CLARIFY_YES_START
                session.add_message("agent", msg)
                return safe_reply([Event("final", msg, conv_state=session.state)], session)

            # YES en START (rare si intent_parser utilisé) → clarification
            if intent == "YES":
                session.start_unclear_count = 0
                session.state = "CLARIFY"
                msg = prompts.VOCAL_CLARIFY_YES_START if channel == "vocal" else prompts.MSG_CLARIFY_YES_START
                session.add_message("agent", msg)
                return safe_reply([Event("final", msg, conv_state=session.state)], session)
            
            # NO → demander clarification
            if intent == "NO":
                session.start_unclear_count = 0
                session.state = "CLARIFY"
                msg = prompts.VOCAL_CLARIFY if channel == "vocal" else prompts.MSG_CLARIFY_WEB_START
                session.add_message("agent", msg)
                return safe_reply([Event("final", msg, conv_state=session.state)], session)
            
            # CANCEL → Flow annulation
            if intent == "CANCEL":
                session.start_unclear_count = 0
                return safe_reply(self._start_cancel(session), session)
            
            # MODIFY → Flow modification
            if intent == "MODIFY":
                session.start_unclear_count = 0
                return safe_reply(self._start_modify(session), session)
            
            # Fix #6: TRANSFER → politique courte (clarify) vs explicite (transfert direct)
            if intent == "TRANSFER":
                from backend.transfer_policy import classify_transfer_request
                kind = classify_transfer_request(user_text)
                if kind == "SHORT":
                    session.start_unclear_count = 0
                    session.state = "CLARIFY"
                    return safe_reply(self._handle_clarify(session, user_text, "TRANSFER"), session)
                if kind == "EXPLICIT":
                    session.start_unclear_count = 0
                    msg = prompts.VOCAL_TRANSFER_COMPLEX if channel == "vocal" else prompts.MSG_TRANSFER
                    return safe_reply(
                        self._trigger_transfer(session, channel, "explicit_transfer_request", user_text=user_text or "", custom_msg=msg),
                        session,
                    )
                # NONE → laisser le routeur (FAQ/booking)
                return safe_reply(self._handle_faq(session, user_text, include_low=True), session)
            
            # ABANDON → Au revoir poli
            if intent == "ABANDON":
                session.start_unclear_count = 0
                session.state = "CONFIRMED"  # Terminal
                msg = prompts.VOCAL_USER_ABANDON if channel == "vocal" else prompts.MSG_ABANDON_WEB
                session.add_message("agent", msg)
                return safe_reply([Event("final", msg, conv_state=session.state)], session)
            
            # BOOKING → Démarrer qualification (start intent "rendez-vous" — audit)
            if intent == "BOOKING":
                session.start_unclear_count = 0
                raw = (user_text or "").strip()[:80]
                normalized = (intent_parser.normalize_stt_text(user_text or "") or "")[:80]
                logger.info(
                    "[INTENT_START_KEYWORD] conv_id=%s state=%s intent=BOOKING_START_KEYWORD text=%s normalized=%s",
                    session.conv_id,
                    session.state,
                    raw,
                    normalized,
                )
                return safe_reply(self._start_booking_with_extraction(session, user_text), session)
            
            # ORDONNANCE → Flow ordonnance (RDV ou message, conversation naturelle)
            if intent == "ORDONNANCE":
                session.start_unclear_count = 0
                return safe_reply(self._handle_ordonnance_flow(session, user_text), session)
            
            # UNCLEAR type filler (euh, hein, hum, silence) → progression 1 clarify → 2 guidance → 3 transfer ou INTENT_ROUTER
            # Guard prod : si start_unclear_count >= 3 et user reste filler → transfert direct (évite boucle "silence + euh")
            if intent == "UNCLEAR" and intent_parser.is_unclear_filler(user_text or ""):
                session.start_unclear_count = getattr(session, "start_unclear_count", 0) + 1
                if session.start_unclear_count == 1:
                    msg = self._say(session, "start_clarify_1")
                    if not msg:
                        msg = getattr(prompts, "VOCAL_START_CLARIFY_1", prompts.MSG_START_CLARIFY_1_WEB) if channel == "vocal" else prompts.MSG_START_CLARIFY_1_WEB
                        session.add_message("agent", msg)
                        session.last_say_key, session.last_say_kwargs = "start_clarify_1", {}
                    return safe_reply([Event("final", msg, conv_state=session.state)], session)
                if session.start_unclear_count == 2:
                    msg = prompts.VOCAL_START_GUIDANCE if channel == "vocal" else prompts.MSG_START_GUIDANCE_WEB
                    session.add_message("agent", msg)
                    return safe_reply([Event("final", msg, conv_state=session.state)], session)
                # 3e et plus : transfert (P0: budget peut prévenir)
                session.start_unclear_count = 0
                prev = self._maybe_prevent_transfer(session, channel, "start_unclear", user_text or "")
                if prev is not None:
                    return safe_reply(prev, session)
                msg = self._say(session, "transfer_filler_silence")
                if not msg:
                    msg = prompts.get_message("transfer_filler_silence", channel=channel) or prompts.MSG_TRANSFER_FILLER_SILENCE
                return safe_reply(
                    self._trigger_transfer(session, channel, "start_unclear", user_text=user_text or "", custom_msg=msg),
                    session,
                )

            # Si LLM Assist a classé UNCLEAR (vague/hors-sujet) => pas de _handle_faq ; 2 → guidance, 3 → INTENT_ROUTER
            if intent == "UNCLEAR" and getattr(r, "entities", None) and r.entities.get("no_faq") is True:
                session.start_no_faq_count = getattr(session, "start_no_faq_count", 0) + 1
                if session.start_no_faq_count >= 3:
                    session.start_no_faq_count = 0
                    return safe_reply(
                        self._trigger_intent_router(session, "no_faq_3", user_text),
                        session,
                    )
                if session.start_no_faq_count == 2:
                    session.start_unclear_count = 0
                    msg = prompts.VOCAL_START_GUIDANCE if channel == "vocal" else prompts.MSG_START_GUIDANCE_WEB
                    session.add_message("agent", msg)
                    return safe_reply([Event("final", msg, conv_state=session.state)], session)
                return safe_reply(self._handle_start_unclear_no_faq(session, user_text), session)

            # FAQ ou UNCLEAR (phrase réelle) → progression no-match 1→2→3 vers INTENT_ROUTER
            return safe_reply(self._handle_faq(session, user_text, include_low=True), session)
        
        # POST_FAQ_CHOICE : après "oui" ambigu en POST_FAQ → rendez-vous ou question ?
        if session.state == "POST_FAQ_CHOICE":
            # 1) Non / abandon → au revoir
            if intent == "NO" or intent == "ABANDON":
                session.state = "CONFIRMED"
                msg = prompts.VOCAL_FAQ_GOODBYE if channel == "vocal" else prompts.MSG_FAQ_GOODBYE_WEB
                session.add_message("agent", msg)
                return safe_reply([Event("final", msg, conv_state=session.state)], session)
            # 2) Rendez-vous explicite → démarrer booking
            msg_lower = (user_text or "").strip().lower()
            if intent == "BOOKING" or "rendez" in msg_lower or "rdv" in msg_lower:
                return safe_reply(self._start_booking_with_extraction(session, user_text), session)
            # 3) Question (explicite ou phrase type "et l'adresse ?") → re-FAQ
            if intent == "FAQ" or "?" in (user_text or "") or "question" in msg_lower:
                session.state = "START"
                return safe_reply(self._handle_faq(session, user_text, include_low=True), session)
            # 4) Sinon → une phrase de relance, rester en POST_FAQ_CHOICE
            msg = getattr(prompts, "VOCAL_POST_FAQ_CHOICE_RETRY", "Dites : rendez-vous, ou : question.")
            session.add_message("agent", msg)
            return safe_reply([Event("final", msg, conv_state=session.state)], session)

        # POST_FAQ : après réponse FAQ + relance "Puis-je vous aider pour autre chose ?"
        if session.state == "POST_FAQ":
            # 0) Priorité : fin d'appel (ABANDON) via strong intent pour éviter relance en boucle
            strong_abandon = detect_strong_intent(user_text or "")
            if strong_abandon == "ABANDON":
                setattr(session, "last_strong_intent", "ABANDON")
                setattr(session, "last_intent", "ABANDON")
                session.state = "CONFIRMED"
                msg = prompts.VOCAL_FAQ_GOODBYE if channel == "vocal" else prompts.MSG_FAQ_GOODBYE_WEB
                session.add_message("agent", msg)
                self._save_session(session)
                return safe_reply([Event("final", msg, conv_state=session.state)], session)
            # 1) Non merci / c'est tout → Au revoir
            if intent == "NO" or intent == "ABANDON":
                session.state = "CONFIRMED"
                msg = prompts.VOCAL_FAQ_GOODBYE if channel == "vocal" else prompts.MSG_FAQ_GOODBYE_WEB
                session.add_message("agent", msg)
                return safe_reply([Event("final", msg, conv_state=session.state)], session)
            # 2) "Oui" seul (ambigu) → disambiguation (jamais booking direct)
            if guards.is_yes_only(user_text or ""):
                session.state = "POST_FAQ_CHOICE"
                msg = (
                    getattr(prompts, "VOCAL_POST_FAQ_DISAMBIG", prompts.VOCAL_POST_FAQ_CHOICE)
                    if channel == "vocal"
                    else getattr(prompts, "MSG_POST_FAQ_DISAMBIG_WEB", prompts.MSG_FAQ_FOLLOWUP_WEB)
                )
                session.add_message("agent", msg)
                return safe_reply([Event("final", msg, conv_state=session.state)], session)
            # 3) Rendez-vous explicite ("oui rdv", "je veux un rdv") → booking direct
            if intent == "BOOKING" or _detect_booking_intent(user_text or ""):
                return safe_reply(self._start_booking_with_extraction(session, user_text), session)
            # 4) Intent YES restant (sans contexte) → disambiguation
            if intent == "YES":
                session.state = "POST_FAQ_CHOICE"
                msg = (
                    getattr(prompts, "VOCAL_POST_FAQ_DISAMBIG", prompts.VOCAL_POST_FAQ_CHOICE)
                    if channel == "vocal"
                    else getattr(prompts, "MSG_POST_FAQ_DISAMBIG_WEB", prompts.MSG_FAQ_FOLLOWUP_WEB)
                )
                session.add_message("agent", msg)
                return safe_reply([Event("final", msg, conv_state=session.state)], session)
            # 5) Autre (ex. nouvelle question) → re-FAQ
            session.state = "START"
            return safe_reply(self._handle_faq(session, user_text, include_low=True), session)
        
        # ========================
        # 5. FALLBACK TRANSFER
        # ========================
        
        # Si état inconnu ou non géré → transfer (P0: budget peut prévenir)
        channel = getattr(session, "channel", "web")
        prev = self._maybe_prevent_transfer(session, channel, "unknown_state", user_text or "")
        if prev is not None:
            return safe_reply(prev, session)
        msg = self._say(session, "transfer")
        if not msg:
            msg = prompts.get_message("transfer", channel=channel)
        return safe_reply(
            self._trigger_transfer(session, channel, "unknown_state", user_text=user_text or "", custom_msg=msg),
            session,
        )
    
    # ========================
    # HANDLERS
    # ========================

    def _should_try_llm_assist(
        self, user_text: str, intent: str, strong_intent: Optional[str]
    ) -> bool:
        """Zone grise START : UNCLEAR, pas filler, pas strong, pas oui/d'accord, longueur cap."""
        if strong_intent:
            return False
        if intent != "UNCLEAR":
            return False
        if intent_parser.is_unclear_filler(user_text or ""):
            return False
        t = (user_text or "").strip()
        if len(t) < 3:
            return False
        if len(t) > LLM_ASSIST_MAX_TEXT_LEN:
            return False
        normalized = intent_parser.normalize_stt_text(t)
        tokens = normalized.split() if normalized else []
        if len(tokens) <= 1:
            return False
        yes_safe_refuse = frozenset({"oui", "ouais", "ouai", "ok", "okay", "d accord", "daccord", "dac", "okey"})
        if normalized in yes_safe_refuse:
            return False
        return True

    def _route_strong_intent_from_start(
        self, session: Session, strong: str, user_text: str
    ) -> List[Event]:
        """Applique un strong intent (CANCEL/MODIFY/TRANSFER/ABANDON) depuis la zone grise LLM."""
        channel = getattr(session, "channel", "web")
        if strong == "CANCEL":
            return self._start_cancel(session)
        if strong == "MODIFY":
            return self._start_modify(session)
        if strong == "TRANSFER":
            from backend.transfer_policy import classify_transfer_request
            kind = classify_transfer_request(user_text or "")
            if kind == "SHORT":
                session.state = "CLARIFY"
                msg = prompts.VOCAL_CLARIFY if channel == "vocal" else prompts.MSG_CLARIFY_WEB
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            return self._trigger_transfer(session, channel, "user_requested", msg_key="transfer_complex")
        if strong == "ABANDON":
            session.state = "CONFIRMED"
            msg = (
                prompts.MSG_END_POLITE_ABANDON
                if hasattr(prompts, "MSG_END_POLITE_ABANDON")
                else (prompts.VOCAL_USER_ABANDON if channel == "vocal" else prompts.MSG_ABANDON_WEB)
            )
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        return self._handle_faq(session, user_text, include_low=True)

    # Alias optionnel bucket → faq_id si la base n'a pas FAQ_ACCES / FAQ_CONTACT (ex. ACCES → FAQ_PAIEMENT).
    BUCKET_FAQ_ALIAS: dict = {}

    def _handle_faq_bucket(
        self, session: Session, bucket: str, user_text: str
    ) -> List[Event]:
        """Réponse FAQ par bucket LLM. Si faq_id absent (None), fallback _handle_faq sans crash."""
        channel = getattr(session, "channel", "web")
        faq_id = f"FAQ_{bucket}"
        result = self.faq_store.get_answer_by_faq_id(faq_id)
        if not result and getattr(self, "BUCKET_FAQ_ALIAS", None):
            faq_id = self.BUCKET_FAQ_ALIAS.get(bucket, faq_id)
            result = self.faq_store.get_answer_by_faq_id(faq_id) if faq_id else None
        if not result:
            return self._handle_faq(session, user_text, include_low=True)
        answer, fid = result

        response = prompts.format_faq_response(answer, fid, channel=channel)
        if channel == "vocal":
            response = response + " " + prompts.VOCAL_FAQ_FOLLOWUP
        else:
            response = response + "\n\n" + getattr(prompts, "MSG_FAQ_FOLLOWUP_WEB", "Souhaitez-vous autre chose ?")
        session.state = "POST_FAQ"
        session.no_match_turns = 0
        session.faq_fails = 0
        session.start_unclear_count = 0
        session.add_message("agent", response)
        return [Event("final", response, conv_state=session.state)]
    
    def _handle_start_unclear_no_faq(self, session: Session, user_text: str) -> List[Event]:
        """Progression clarification START sans recherche FAQ (quand LLM a retourné UNCLEAR, ex. hors-sujet).
        N'incrémente pas no_match_turns ni faq_fails : on utilise uniquement start_unclear_count (flux START)."""
        channel = getattr(session, "channel", "web")
        session.start_unclear_count = getattr(session, "start_unclear_count", 0) + 1
        if session.start_unclear_count == 1:
            log_ivr_event(logger, session, "recovery_step", context="llm_unclear", reason="start_unclear_1")
            msg = self._say(session, "start_clarify_1")
            if not msg:
                msg = prompts.VOCAL_START_CLARIFY_1 if channel == "vocal" else prompts.MSG_START_CLARIFY_1_WEB
                session.add_message("agent", msg)
                session.last_say_key, session.last_say_kwargs = "start_clarify_1", {}
            self._save_session(session)
            return [Event("final", msg, conv_state=session.state)]
        if session.start_unclear_count == 2:
            log_ivr_event(logger, session, "recovery_step", context="llm_unclear", reason="start_unclear_2_guidance")
            msg = prompts.VOCAL_START_GUIDANCE if channel == "vocal" else prompts.MSG_START_GUIDANCE_WEB
            session.add_message("agent", msg)
            self._save_session(session)
            return [Event("final", msg, conv_state=session.state)]
        session.start_unclear_count = 0
        return self._trigger_intent_router(session, "llm_unclear_3", user_text)

    def _handle_faq(self, session: Session, user_text: str, include_low: bool = True) -> List[Event]:
        """
        Cherche dans FAQ.

        Args:
            include_low: Si False, exclut les FAQs priority="low"
        """
        channel = getattr(session, "channel", "web")
        faq_result = self.faq_store.search(user_text, include_low=include_low)

        if faq_result.match:
            # N'afficher la FAQ que si le score est fort (évite "pizza" → paiement, sans liste en dur).
            strong = getattr(config, "FAQ_STRONG_MATCH_THRESHOLD", 0.90) or 0.90
            if faq_result.score < strong:
                msg = getattr(prompts, "MSG_CONV_FALLBACK", prompts.MSG_OUT_OF_SCOPE_WEB)
                if channel == "vocal":
                    msg = getattr(prompts, "VOCAL_OUT_OF_SCOPE", msg)
                session.add_message("agent", msg)
                self._save_session(session)
                return [Event("final", msg, conv_state=session.state)]
            response = prompts.format_faq_response(faq_result.answer, faq_result.faq_id, channel=channel)
            # Toujours ajouter une relance pour permettre autre question ou RDV
            if channel == "vocal":
                response = response + " " + prompts.VOCAL_FAQ_FOLLOWUP
            else:
                response = response + "\n\n" + getattr(prompts, "MSG_FAQ_FOLLOWUP_WEB", "Souhaitez-vous autre chose ?")
            session.state = "POST_FAQ"
            session.no_match_turns = 0
            session.faq_fails = 0
            session.start_unclear_count = 0  # Reset guidage START sur succès FAQ
            session.add_message("agent", response)
            return [Event("final", response, conv_state=session.state)]

        session.no_match_turns += 1
        session.faq_fails = getattr(session, "faq_fails", 0) + 1
        session.global_recovery_fails = getattr(session, "global_recovery_fails", 0) + 1

        # En START (question ouverte) : guidage proactif avec start_unclear_count
        if session.state == "START":
            session.start_unclear_count = getattr(session, "start_unclear_count", 0) + 1
            # 1ère incompréhension → clarification générique (rendez-vous ou question)
            if session.start_unclear_count == 1:
                log_ivr_event(logger, session, "recovery_step", context="faq", reason="start_unclear_1")
                msg = self._say(session, "start_clarify_1")
                if not msg:
                    msg = prompts.VOCAL_START_CLARIFY_1 if channel == "vocal" else prompts.MSG_START_CLARIFY_1_WEB
                    session.add_message("agent", msg)
                    session.last_say_key, session.last_say_kwargs = "start_clarify_1", {}
                self._save_session(session)
                return [Event("final", msg, conv_state=session.state)]
            # 2e incompréhension → guidage proactif (RDV, horaires, adresse, services)
            if session.start_unclear_count == 2:
                log_ivr_event(logger, session, "recovery_step", context="faq", reason="start_unclear_2_guidance")
                msg = prompts.VOCAL_START_GUIDANCE if channel == "vocal" else prompts.MSG_START_GUIDANCE_WEB
                session.add_message("agent", msg)
                self._save_session(session)
                return [Event("final", msg, conv_state=session.state)]
            # 3e et plus → INTENT_ROUTER
            log_ivr_event(logger, session, "recovery_step", context="faq", reason="start_unclear_3")
            session.start_unclear_count = 0
            return self._trigger_intent_router(session, "start_unclear_3", user_text)

        # Hors START : comportement FAQ classique (no_match_turns)
        if session.no_match_turns == 1:
            log_ivr_event(logger, session, "recovery_step", context="faq", reason="retry_1")
            if channel == "vocal":
                msg = getattr(prompts, "MSG_FAQ_REFORMULATE_VOCAL", prompts.MSG_FAQ_REFORMULATE)
            else:
                msg = prompts.MSG_FAQ_REFORMULATE
            session.add_message("agent", msg)
            self._save_session(session)
            return [Event("final", msg, conv_state=session.state)]
        if session.no_match_turns == 2:
            log_ivr_event(logger, session, "recovery_step", context="faq", reason="retry_2_options")
            if channel == "vocal":
                msg = getattr(prompts, "MSG_FAQ_RETRY_EXEMPLES_VOCAL", prompts.MSG_FAQ_REFORMULATE)
            else:
                msg = getattr(prompts, "MSG_FAQ_RETRY_EXEMPLES", prompts.MSG_FAQ_REFORMULATE)
            session.add_message("agent", msg)
            self._save_session(session)
            return [Event("final", msg, conv_state=session.state)]
        log_ivr_event(logger, session, "recovery_step", context="faq", reason="escalate_intent_router")
        return self._trigger_intent_router(session, "faq_no_match_2", user_text)
    
    def _start_booking_with_extraction(self, session: Session, user_text: str) -> List[Event]:
        """
        Démarre le flow de booking avec extraction d'entités.
        
        Extrait nom, motif, préférence du premier message si présents,
        puis pose seulement les questions manquantes.
        """
        channel = getattr(session, "channel", "web")
        
        # Extraction conservatrice
        entities = extract_entities(user_text)
        
        # Pré-remplir les champs extraits
        if entities.name:
            session.qualif_data.name = entities.name
            session.extracted_name = True  # Flag pour confirmation implicite
        
        if entities.motif:
            session.qualif_data.motif = entities.motif
            session.extracted_motif = True
        
        if entities.pref:
            session.qualif_data.pref = entities.pref
            session.extracted_pref = True
        
        # Construire le contexte pour trouver le prochain champ manquant
        context = {
            "name": session.qualif_data.name,
            "motif": session.qualif_data.motif,
            "pref": session.qualif_data.pref,
            "contact": session.qualif_data.contact,
        }
        
        # Skip contact pour le moment - sera demandé après le choix de créneau
        next_field = get_next_missing_field(context, skip_contact=True)
        
        if not next_field:
            # name + pref remplis → proposer créneaux
            return self._propose_slots(session)
        
        # Mapper le champ vers l'état
        state_map = {
            "name": "QUALIF_NAME",
            "motif": "QUALIF_MOTIF",
            "pref": "QUALIF_PREF",
            "contact": "QUALIF_CONTACT",
        }
        session.state = state_map[next_field]
        
        # Construire la réponse avec confirmation implicite si extraction
        response_parts = []
        
        # Question suivante
        question = prompts.get_qualif_question(next_field, channel=channel)
        # 1 acknowledgement max par étape : pas d'ACK si la question commence déjà par un (Très bien / Parfait / D'accord)
        if entities.has_any():
            ack = prompts.pick_ack(session.next_ack_index())
            q_lower = question.strip().lower()
            if not (q_lower.startswith("très bien") or q_lower.startswith("parfait") or q_lower.startswith("d'accord") or q_lower.startswith("d accord")):
                if entities.name and entities.motif:
                    response_parts.append(f"{ack} Pour {entities.motif}.")
                elif entities.name:
                    response_parts.append(ack)
                elif entities.motif:
                    response_parts.append(f"{ack} Pour {entities.motif}.")
                else:
                    response_parts.append(ack)
        response_parts.append(question)
        
        response = " ".join(response_parts)
        session.add_message("agent", response)
        
        return [Event("final", response, conv_state=session.state)]
    
    def _next_qualif_step(self, session: Session) -> List[Event]:
        """
        Détermine et pose la prochaine question de qualification.
        Skip automatiquement les champs déjà remplis (par extraction ou réponse précédente).
        Utilise le prénom du client dans les questions si disponible.
        """
        channel = getattr(session, "channel", "web")
        
        # Construire le contexte actuel
        context = {
            "name": session.qualif_data.name,
            "motif": session.qualif_data.motif,
            "pref": session.qualif_data.pref,
            "contact": session.qualif_data.contact,
        }
        
        # DEBUG: Log context
        logger.debug("[QUALIF] conv_id=%s context=%s", session.conv_id, context)
        
        # Skip contact pour le moment - sera demandé après le choix de créneau
        next_field = get_next_missing_field(context, skip_contact=True)
        logger.debug("[QUALIF] conv_id=%s next_field=%s", session.conv_id, next_field)
        
        if not next_field:
            # name + pref remplis → proposer créneaux (contact viendra après)
            session.reset_questions()
            return self._propose_slots(session)
        
        # Spec V3 : max 3 questions consécutives → action concrète (proposer créneaux si name+pref)
        max_q = getattr(Session, "MAX_CONSECUTIVE_QUESTIONS", 3)
        if session.consecutive_questions >= max_q and context.get("name") and context.get("pref"):
            logger.info("[QUALIF] conv_id=%s fatigue_cognitive consecutive=%s → propose_slots", session.conv_id, session.consecutive_questions)
            session.reset_questions()
            return self._propose_slots(session)
        
        # 📱 Si le prochain champ est "contact" ET qu'on a le numéro de l'appelant → l'utiliser directement
        if next_field == "contact" and channel == "vocal" and session.customer_phone:
            try:
                phone = str(session.customer_phone)
                # Nettoyer le format (+33612345678 → 0612345678)
                if phone.startswith("+33"):
                    phone = "0" + phone[3:]
                elif phone.startswith("33"):
                    phone = "0" + phone[2:]
                phone = phone.replace(" ", "").replace("-", "").replace(".", "")
                
                if len(phone) >= 10:
                    session.qualif_data.contact = phone[:10]
                    session.qualif_data.contact_type = "phone"
                    session.state = "CONTACT_CONFIRM"
                    phone_formatted = prompts.format_phone_for_voice(phone[:10])
                    msg = f"Votre numéro est bien le {phone_formatted} ?"
                    logger.info("[QUALIF] conv_id=%s using_caller_id", session.conv_id)
                    session.awaiting_confirmation = "CONFIRM_CONTACT"
                    session.last_question_asked = msg
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]
            except Exception as e:
                logger.warning("[QUALIF] conv_id=%s caller_id_error=%s", session.conv_id, str(e)[:80])
                # Continue avec le flow normal (demander le numéro)
        
        # Mapper le champ vers l'état
        state_map = {
            "name": "QUALIF_NAME",
            "motif": "QUALIF_MOTIF",
            "pref": "QUALIF_PREF",
            "contact": "QUALIF_CONTACT",
        }
        session.state = state_map[next_field]
        session.bump_questions()
        
        # Question adaptée au canal AVEC prénom si disponible
        client_name = session.qualif_data.name or ""
        logger.info("[QUALIF] conv_id=%s asking=%s consecutive=%s", session.conv_id, next_field, session.consecutive_questions)
        
        if client_name and channel == "vocal":
            question = prompts.get_qualif_question_with_name(
                next_field, client_name, channel=channel, ack_index=session.next_ack_index()
            )
        else:
            question = prompts.get_qualif_question(next_field, channel=channel)
        # Vocal : pas de wrap_with_signal ici (évite 2e "Parfait" en start après le nom)
        # Les questions sont déjà formulées sans ack redondant (get_qualif_question_with_name).
        
        session.last_question_asked = question
        logger.info("[QUALIF] conv_id=%s asking=%s", session.conv_id, next_field)
        # Patch A: précharger créneaux pendant que l'utilisateur réfléchit (vocal)
        if next_field == "pref" and channel == "vocal":
            try:
                tools_booking.prefetch_slots_for_pref_question(session=session)
            except Exception:
                pass
        session.add_message("agent", question)
        
        return [Event("final", question, conv_state=session.state)]
    
    def _handle_qualification(self, session: Session, user_text: str) -> List[Event]:
        """
        Gère le flow de qualification (4 questions).
        AVEC validation des réponses et clarifications.
        """
        current_step = session.state
        
        # ========================
        # QUALIF_NAME
        # ========================
        if current_step == "QUALIF_NAME":
            channel = getattr(session, "channel", "web")
            
            # P0 : phrase d'intention RDV ("je veux un rdv") → message guidé ; P1.4 : 3x → INTENT_ROUTER
            if _detect_booking_intent(user_text):
                session.qualif_name_intent_repeat_count = getattr(session, "qualif_name_intent_repeat_count", 0) + 1
                if session.qualif_name_intent_repeat_count >= 3:
                    return self._trigger_intent_router(session, "booking_intent_repeat_3", user_text)
                if session.qualif_name_intent_repeat_count == 1:
                    msg = prompts.MSG_QUALIF_NAME_INTENT_1
                else:
                    msg = prompts.MSG_QUALIF_NAME_INTENT_2
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # Rejeter filler contextuel (euh, "oui" seul en QUALIF_NAME)
            if guards.is_contextual_filler(user_text, session.state):
                log_filler_detected(logger, session, user_text, field="name")
                log_name_rejected(logger, session, user_text, reason="filler_detected")
                fail_count = increment_recovery_counter(session, "name")
                if should_escalate_recovery(session, "name"):
                    return self._trigger_intent_router(session, "name_fails_3", user_text)
                msg = prompts.get_clarification_message(
                    "name",
                    min(fail_count, 3),
                    user_text,
                    channel=channel,
                )
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # Extraction du nom (préfixes FR, fillers, plausible) — on valide l’info extraite, pas le message
            extracted_name, reject_reason = guards.extract_name_from_speech(user_text)
            logger.debug("[QUALIF_NAME] conv_id=%s extracted=%s reject=%s", session.conv_id, extracted_name, reject_reason)
            
            if extracted_name is not None:
                # Réponse valide → stocker et continuer (spec V3 : reset compteurs)
                session.qualif_data.name = extracted_name.title()
                session.reset_questions()
                session.qualif_name_intent_repeat_count = 0
                logger.debug("[QUALIF_NAME] conv_id=%s stored", session.conv_id)
                return self._next_qualif_step(session)
            
            # Rejet : filler_detected ou not_plausible_name
            log_name_rejected(logger, session, user_text, reason=reject_reason or "filler_detected")
            log_filler_detected(logger, session, user_text, field="name", detail=reject_reason)
            fail_count = increment_recovery_counter(session, "name")
            if should_escalate_recovery(session, "name"):
                return self._trigger_intent_router(session, "name_fails_3", user_text)
            msg = prompts.get_clarification_message(
                "name",
                min(fail_count, 3),
                user_text,
                channel=channel,
            )
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        # ========================
        # QUALIF_MOTIF
        # ========================
        elif current_step == "QUALIF_MOTIF":
            channel = getattr(session, "channel", "web")
            
            # Vérifier répétition booking intent
            if _detect_booking_intent(user_text):
                # Vérifier AVANT d'incrémenter pour permettre 1 retry
                if session.confirm_retry_count >= config.CONFIRM_RETRY_MAX:
                    session.state = "TRANSFERRED"
                    msg = self._say(session, "transfer")
                    if not msg:
                        msg = prompts.get_message("transfer", channel=channel)
                        session.add_message("agent", msg)
                        session.last_say_key, session.last_say_kwargs = "transfer", {}
                    return [Event("final", msg, conv_state=session.state)]
                
                session.confirm_retry_count += 1
                msg = prompts.get_qualif_retry("motif", channel=channel)
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # NOUVEAU : Vérifier si motif générique
            if guards.is_generic_motif(user_text):
                # Vérifier AVANT d'incrémenter pour permettre 1 retry
                if session.confirm_retry_count >= config.CONFIRM_RETRY_MAX:
                    session.state = "TRANSFERRED"
                    msg = self._say(session, "transfer")
                    if not msg:
                        msg = prompts.get_message("transfer", channel=channel)
                        session.add_message("agent", msg)
                        session.last_say_key, session.last_say_kwargs = "transfer", {}
                    return [Event("final", msg, conv_state=session.state)]
                
                # 1ère fois générique → aide
                session.confirm_retry_count += 1
                msg = prompts.MSG_MOTIF_HELP
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # Reset compteur si motif valide
            session.confirm_retry_count = 0
            
            # Validation PRD (P0: budget peut prévenir)
            if not guards.validate_qualif_motif(user_text):
                prev = self._maybe_prevent_transfer(session, channel, "qualif_motif_invalid", user_text)
                if prev is not None:
                    return prev
                msg = self._say(session, "transfer")
                if not msg:
                    msg = prompts.get_message("transfer", channel=channel)
                return self._trigger_transfer(session, channel, "qualif_motif_invalid", user_text=user_text, custom_msg=msg)
            
            # Motif valide et utile (spec V3 : reset compteur)
            session.qualif_data.motif = user_text.strip()
            session.reset_questions()
            return self._next_qualif_step(session)
        
        # ========================
        # QUALIF_PREF (spec V3 : extraction + inférence contextuelle)
        # ========================
        elif current_step == "QUALIF_PREF":
            channel = getattr(session, "channel", "web")
            logger.info("[QUALIF_PREF] conv_id=%s user=%s", session.conv_id, _mask_for_log(user_text or ""))

            # --- P0: répétition intention RDV ("je veux un rdv") → message guidé, pas preference_fails ---
            if _detect_booking_intent(user_text):
                session.qualif_pref_intent_repeat_count += 1
                msg = (
                    prompts.MSG_QUALIF_PREF_INTENT_1
                    if session.qualif_pref_intent_repeat_count == 1
                    else prompts.MSG_QUALIF_PREF_INTENT_2
                )
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]

            # --- RÈGLE 7: contrainte horaire explicite (ex: "je finis à 17h") ---
            if getattr(config, "TIME_CONSTRAINT_ENABLED", False):
                try:
                    tc = extract_time_constraint(user_text)
                except Exception:
                    tc = None

                if tc:
                    session.time_constraint_type = tc.type
                    session.time_constraint_minute = tc.minute_of_day
                    log_ivr_event(logger, session, "time_constraint_detected")

                    closing_minutes = (
                        getattr(config, "CABINET_CLOSING_HOUR", 19) * 60
                        + getattr(config, "CABINET_CLOSING_MINUTE", 0)
                    )
                    # Impossible si "after" >= closing
                    if tc.type == "after" and tc.minute_of_day >= closing_minutes:
                        closing_str = f"{getattr(config, 'CABINET_CLOSING_HOUR', 19)}h{getattr(config, 'CABINET_CLOSING_MINUTE', 0):02d}"
                        msg_tpl = getattr(prompts, "MSG_TIME_CONSTRAINT_IMPOSSIBLE", None)
                        if msg_tpl:
                            msg = msg_tpl.format(closing=closing_str)
                        else:
                            msg = (
                                f"D'accord. Mais nous fermons à {closing_str}. "
                                "Je peux vous proposer un créneau plus tôt, ou je vous mets en relation avec quelqu'un. "
                                "Vous préférez : un créneau plus tôt, ou parler à quelqu'un ?"
                            )
                        session.add_message("agent", msg)
                        # Fix 10: 1 seul final (msg contient la question). state=INTENT_ROUTER pour prochain tour.
                        session.state = "INTENT_ROUTER"
                        session.intent_router_visits = getattr(session, "intent_router_visits", 0) + 1
                        _persist_ivr_event(session, "time_constraint_impossible")
                        return safe_reply([Event("final", msg, conv_state=session.state)], session)

            # Rejeter filler contextuel (euh, "oui" en QUALIF_PREF…) → recovery préférence
            if guards.is_contextual_filler(user_text, session.state):
                log_filler_detected(logger, session, user_text, field="preference")
                fail_count = increment_recovery_counter(session, "preference")
                if should_escalate_recovery(session, "preference"):
                    return self._trigger_intent_router(session, "preference_fails_3", user_text)
                msg = prompts.get_clarification_message(
                    "preference",
                    min(fail_count, 3),
                    user_text,
                    channel=channel,
                )
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]

            # 1. Inférence contextuelle (spec V3) — "je travaille jusqu'à 17h" → confirmation
            inferred_pref = infer_preference_from_context(user_text)
            if inferred_pref:
                session.qualif_pref_intent_repeat_count = 0
                session.pending_preference = inferred_pref
                session.last_preference_user_text = user_text.strip()
                session.state = "PREFERENCE_CONFIRM"
                msg = prompts.format_inference_confirmation(inferred_pref)
                session.last_question_asked = msg
                session.add_message("agent", msg)
                session.awaiting_confirmation = "CONFIRM_PREFERENCE"
                return [Event("final", msg, conv_state=session.state)]
            
            # 2. Inférence temporelle robuste ("vers 14h", "après le déjeuner", "peu importe", etc.)
            time_pref = guards.infer_time_preference(user_text)
            if time_pref == "morning":
                session.qualif_pref_intent_repeat_count = 0
                log_preference_inferred(logger, session, user_text, inferred="morning")
                session.pending_preference = "matin"
                session.last_preference_user_text = user_text.strip()
                session.state = "PREFERENCE_CONFIRM"
                msg = prompts.VOCAL_PREF_CONFIRM_MATIN
                session.last_question_asked = msg
                session.add_message("agent", msg)
                session.awaiting_confirmation = "CONFIRM_PREFERENCE"
                return [Event("final", msg, conv_state=session.state)]
            if time_pref == "afternoon":
                session.qualif_pref_intent_repeat_count = 0
                log_preference_inferred(logger, session, user_text, inferred="afternoon")
                session.pending_preference = "après-midi"
                session.last_preference_user_text = user_text.strip()
                session.state = "PREFERENCE_CONFIRM"
                msg = prompts.VOCAL_PREF_CONFIRM_APRES_MIDI
                session.last_question_asked = msg
                session.add_message("agent", msg)
                session.awaiting_confirmation = "CONFIRM_PREFERENCE"
                return [Event("final", msg, conv_state=session.state)]
            if time_pref == "neutral":
                session.qualif_pref_intent_repeat_count = 0
                log_preference_inferred(logger, session, user_text, inferred="neutral")
                session.pending_preference = "matin"
                session.last_preference_user_text = user_text.strip()
                session.state = "PREFERENCE_CONFIRM"
                msg = prompts.VOCAL_PREF_ANY
                session.last_question_asked = msg
                session.add_message("agent", msg)
                session.awaiting_confirmation = "CONFIRM_PREFERENCE"
                return [Event("final", msg, conv_state=session.state)]
            
            # 3. Fallback : infer_preference_plausible (mots directs + heures)
            pref_plausible = guards.infer_preference_plausible(user_text)
            if pref_plausible == "morning":
                session.qualif_pref_intent_repeat_count = 0
                log_preference_inferred(logger, session, user_text, inferred="morning")
                session.pending_preference = "matin"
                session.last_preference_user_text = user_text.strip()
                session.state = "PREFERENCE_CONFIRM"
                msg = prompts.VOCAL_PREF_CONFIRM_MATIN
                session.last_question_asked = msg
                session.add_message("agent", msg)
                session.awaiting_confirmation = "CONFIRM_PREFERENCE"
                return [Event("final", msg, conv_state=session.state)]
            if pref_plausible == "afternoon":
                session.qualif_pref_intent_repeat_count = 0
                log_preference_inferred(logger, session, user_text, inferred="afternoon")
                session.pending_preference = "après-midi"
                session.last_preference_user_text = user_text.strip()
                session.state = "PREFERENCE_CONFIRM"
                msg = prompts.VOCAL_PREF_CONFIRM_APRES_MIDI
                session.last_question_asked = msg
                session.add_message("agent", msg)
                session.awaiting_confirmation = "CONFIRM_PREFERENCE"
                return [Event("final", msg, conv_state=session.state)]
            if pref_plausible == "any":
                session.qualif_pref_intent_repeat_count = 0
                log_preference_inferred(logger, session, user_text, inferred="neutral")
                session.pending_preference = "matin"
                session.last_preference_user_text = user_text.strip()
                session.state = "PREFERENCE_CONFIRM"
                msg = prompts.VOCAL_PREF_ANY
                session.last_question_asked = msg
                session.add_message("agent", msg)
                session.awaiting_confirmation = "CONFIRM_PREFERENCE"
                return [Event("final", msg, conv_state=session.state)]
            
            # 4. Incompréhension → recovery progressive (fail 1, 2, 3 → INTENT_ROUTER)
            log_preference_failed(logger, session, user_text, reason="ambiguous_input")
            log_filler_detected(logger, session, user_text, field="preference")
            fail_count = increment_recovery_counter(session, "preference")
            if should_escalate_recovery(session, "preference"):
                return self._trigger_intent_router(session, "preference_fails_3", user_text)
            msg = prompts.get_clarification_message(
                "preference",
                min(fail_count, 3),
                user_text,
                channel=channel,
            )
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        # ========================
        # QUALIF_CONTACT
        # ========================
        elif current_step == "QUALIF_CONTACT":
            channel = getattr(session, "channel", "web")
            contact_raw = user_text.strip()
            
            logger.info("[QUALIF_CONTACT] conv_id=%s received=%s", session.conv_id, _mask_for_log(contact_raw or ""))
            
            # Rejeter filler contextuel (euh, "oui" en QUALIF_CONTACT…) → recovery téléphone (3 niveaux, puis fallback email)
            if guards.is_contextual_filler(contact_raw, session.state):
                log_filler_detected(logger, session, contact_raw, field="phone")
                fail_count = increment_recovery_counter(session, "phone")
                msg = prompts.get_clarification_message(
                    "phone",
                    min(fail_count, 3),
                    contact_raw,
                    channel=channel,
                )
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]

            # P0 : répétition intention RDV → message guidé contact, pas phone_fails ni transfert
            if _detect_booking_intent(contact_raw):
                msg = prompts.MSG_QUALIF_CONTACT_INTENT
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]

            # ✅ P0 : Parsing email dicté (vocal) — contact_parser + detect_contact_channel
            if channel == "vocal":
                ch = contact_parser.detect_contact_channel(contact_raw)
                if ch == "email" or guards.looks_like_dictated_email(contact_raw):
                    email_val, email_conf = contact_parser.extract_email_vocal(contact_raw)
                    if email_val and email_conf >= 0.5:
                        session.qualif_data.contact = email_val
                        session.qualif_data.contact_type = "email"
                        session.contact_fails = 0
                        session.contact_mode = "email"
                        log_ivr_event(logger, session, "contact_captured_email")
                        if session.pending_slot_choice is not None:
                            session.state = "CONTACT_CONFIRM"
                            msg = prompts.VOCAL_EMAIL_CONFIRM.format(email=email_val)
                            session.awaiting_confirmation = "CONFIRM_CONTACT"
                            session.last_question_asked = msg
                            session.add_message("agent", msg)
                            return [Event("final", msg, conv_state=session.state)]
                        return self._propose_slots(session)
                    # Email invalide → guidance 1er échec, transfert 2e (P0: budget peut prévenir)
                    session.contact_fails = getattr(session, "contact_fails", 0) + 1
                    if session.contact_fails >= 2:
                        log_ivr_event(logger, session, "contact_failed_transfer", reason="email_invalid_2")
                        prev = self._maybe_prevent_transfer(session, channel, "contact_failed", contact_raw)
                        if prev is not None:
                            return prev
                        msg = self._say(session, "transfer") or prompts.get_message("transfer", channel=channel)
                        return self._trigger_transfer(session, channel, "contact_failed", user_text=contact_raw, custom_msg=msg)
                    msg = prompts.MSG_CONTACT_EMAIL_GUIDANCE_1
                    log_ivr_event(logger, session, "contact_failed_1", reason="email_invalid")
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]

            # ✅ P0 : Téléphone vocal — contact_parser (double/triple) + contact_fails 2 max
            if channel == "vocal" and not session.customer_phone:
                digits, conf, is_partial = contact_parser.extract_phone_digits_vocal(contact_raw)
                new_digits = digits  # contact_parser inclut déjà l'accumulation logique
                if not new_digits and not session.partial_phone_digits:
                    # Aucun chiffre extrait : filler ou invalide (P0: budget peut prévenir)
                    session.contact_fails = getattr(session, "contact_fails", 0) + 1
                    if session.contact_fails >= 2:
                        log_ivr_event(logger, session, "contact_failed_transfer", reason="phone_empty_2")
                        prev = self._maybe_prevent_transfer(session, channel, "contact_failed", contact_raw)
                        if prev is not None:
                            return prev
                        msg = self._say(session, "transfer") or prompts.get_message("transfer", channel=channel)
                        return self._trigger_transfer(session, channel, "contact_failed", user_text=contact_raw, custom_msg=msg)
                    msg = prompts.MSG_CONTACT_PHONE_GUIDANCE_1 if session.contact_fails == 1 else prompts.get_clarification_message("phone", 1, contact_raw, channel=channel)
                    log_ivr_event(logger, session, "contact_failed_1", reason="phone_empty")
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]
                # Accumuler ou utiliser extraction directe
                session.partial_phone_digits += new_digits
                total_digits = session.partial_phone_digits
                if len(total_digits) >= 10:
                    digits_10 = total_digits[:10]
                    ok_phone, phone10, reason = guards.is_plausible_phone_input(digits_10)
                    if not ok_phone:
                        session.contact_fails = getattr(session, "contact_fails", 0) + 1
                        if session.contact_fails >= 2:
                            session.partial_phone_digits = ""
                            log_ivr_event(logger, session, "contact_failed_transfer", reason="phone_invalid_2")
                            prev = self._maybe_prevent_transfer(session, channel, "contact_failed", contact_raw)
                            if prev is not None:
                                return prev
                            msg = self._say(session, "transfer") or prompts.get_message("transfer", channel=channel)
                            return self._trigger_transfer(session, channel, "contact_failed", user_text=contact_raw, custom_msg=msg)
                        msg = prompts.MSG_CONTACT_PHONE_GUIDANCE_1 if session.contact_fails == 1 else prompts.get_clarification_message("phone", 1, contact_raw, channel=channel)
                        session.add_message("agent", msg)
                        return [Event("final", msg, conv_state=session.state)]
                    session.partial_phone_digits = ""
                    session.qualif_data.contact = phone10
                    session.qualif_data.contact_type = "phone"
                    session.contact_fails = 0
                    session.contact_mode = "phone"
                    session.state = "CONTACT_CONFIRM"
                    log_ivr_event(logger, session, "contact_captured_phone")
                    phone_spaced = prompts.format_phone_for_voice(phone10)
                    msg = prompts.VOCAL_CONTACT_CONFIRM_SHORT.format(phone_formatted=phone_spaced)
                    session.add_message("agent", msg)
                    session.awaiting_confirmation = "CONFIRM_CONTACT"
                    session.last_question_asked = msg
                    return [Event("final", msg, conv_state=session.state)]
                # Pas encore 10 chiffres → accumulation (6 tours max, pas contact_fails)
                session.contact_retry_count = getattr(session, "contact_retry_count", 0) + 1
                if session.contact_retry_count >= 6:
                    session.partial_phone_digits = ""
                    log_ivr_event(logger, session, "contact_failed_transfer", reason="phone_partial_6")
                    prev = self._maybe_prevent_transfer(session, channel, "contact_failed", contact_raw)
                    if prev is not None:
                        return prev
                    msg = self._say(session, "transfer") or prompts.get_message("transfer", channel=channel)
                    return self._trigger_transfer(session, channel, "contact_failed", user_text=contact_raw, custom_msg=msg)
                msg = "Oui, continuez." if len(total_digits) > 0 else "J'écoute."
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # Web / direct : phone plausible (FR + ASR) puis validation
            if any(c.isdigit() for c in contact_raw) and not guards.validate_email(contact_raw.strip()):
                ok_phone, phone10, reason = guards.is_plausible_phone_input(contact_raw)
                if not ok_phone:
                    log_filler_detected(logger, session, contact_raw, field="phone", detail=reason)
                    fail_count = increment_recovery_counter(session, "phone")
                    msg = prompts.get_clarification_message(
                        "phone",
                        min(fail_count, 3),
                        contact_raw,
                        channel=channel,
                    )
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]
                contact_raw = phone10 or contact_raw
            is_valid, contact_type = guards.validate_qualif_contact(contact_raw)
            logger.info("[QUALIF_CONTACT] conv_id=%s validation is_valid=%s type=%s", session.conv_id, is_valid, contact_type)
            if not is_valid:
                log_filler_detected(logger, session, contact_raw, field="phone", detail="invalid_format")
                fail_count = increment_recovery_counter(session, "phone")
                msg = prompts.get_clarification_message(
                    "phone",
                    min(fail_count, 3),
                    contact_raw,
                    channel=channel,
                )
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            session.qualif_data.contact = contact_raw
            session.qualif_data.contact_type = contact_type
            session.contact_retry_count = 0
            # Si un créneau est déjà choisi (on vient de WAIT_CONFIRM) → CONTACT_CONFIRM, pas re-proposer les slots
            if session.pending_slot_choice is not None:
                session.state = "CONTACT_CONFIRM"
                if contact_type == "phone":
                    phone_formatted = prompts.format_phone_for_voice(contact_raw)
                    msg = prompts.VOCAL_PHONE_CONFIRM.format(phone_spaced=phone_formatted) if channel == "vocal" else f"Votre numéro est bien le {contact_raw} ?"
                else:
                    msg = getattr(prompts, "VOCAL_EMAIL_CONFIRM", None)
                    if msg and channel == "vocal":
                        msg = msg.format(email=contact_raw)
                    else:
                        msg = f"Votre email est bien {contact_raw} ?"
                session.add_message("agent", msg)
                session.awaiting_confirmation = "CONFIRM_CONTACT"
                session.last_question_asked = msg
                return [Event("final", msg, conv_state=session.state)]
            return self._propose_slots(session)
        
        # ========================
        # FALLBACK (état inconnu)
        # ========================
        # Si aucun des états précédents n'a matché, transfert
        session.state = "TRANSFERRED"
        msg = self._say(session, "transfer")
        if not msg:
            channel = getattr(session, "channel", "web")
            msg = prompts.get_message("transfer", channel=channel)
            session.add_message("agent", msg)
            session.last_say_key, session.last_say_kwargs = "transfer", {}
        return [Event("final", msg, conv_state=session.state)]
    
    def _handle_aide_contact(self, session: Session, user_text: str) -> List[Event]:
        """
        État de guidance contact.
        Règle: 1 retry maximum, puis transfert (optionnel), mais jamais dès la 1ère erreur.
        """
        text = user_text.strip()
        
        is_valid, contact_type = guards.validate_qualif_contact(text)
        if is_valid:
            session.qualif_data.contact = text
            session.qualif_data.contact_type = contact_type
            session.contact_retry_count = 0
            session.state = "QUALIF_CONTACT"  # Retour à l'état normal avant de proposer slots
            return self._propose_slots(session)
        
        session.contact_retry_count += 1
        
        if session.contact_retry_count >= 2:
            session.state = "TRANSFERRED"
            msg = prompts.MSG_CONTACT_FAIL_TRANSFER
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        msg = prompts.get_clarification_message(
            "phone",
            min(session.contact_retry_count, 3),
            text,
            channel=getattr(session, "channel", "web"),
        )
        session.add_message("agent", msg)
        return [Event("final", msg, conv_state=session.state)]
    
    def _propose_slots(self, session: Session) -> List[Event]:
        """
        Propose 3 créneaux disponibles.
        Patch A: utilise prefetch si dispo. Patch B: préfixe "je consulte l'agenda" en vocal.
        """
        import time
        t_start = time.time()
        
        channel = getattr(session, "channel", "web")
        pref = getattr(session.qualif_data, "pref", None) or None
        logger.info("[PROPOSE_SLOTS] conv_id=%s pref=%s", session.conv_id, pref)
        
        # Patch A: utiliser prefetch si disponible (évite blanc après "le matin"/"l'après-midi")
        slots = None
        if channel == "vocal" and pref in ("matin", "après-midi"):
            prefetched = getattr(session, "_prefetch_morning", None) if pref == "matin" else getattr(session, "_prefetch_afternoon", None)
            if prefetched and len(prefetched) > 0:
                slots = prefetched
                logger.info("[PROPOSE_SLOTS] conv_id=%s prefetch hit len=%s pref=%s ms=%.0f", session.conv_id, len(slots), pref, (time.time() - t_start) * 1000)
        
        if not slots:
            try:
                slots = tools_booking.get_slots_for_display(
                    limit=config.MAX_SLOTS_PROPOSED, pref=pref, session=session
                )
                logger.info("[PROPOSE_SLOTS] conv_id=%s fetched len=%s pref=%s ms=%.0f", session.conv_id, len(slots) if slots else 0, pref, (time.time() - t_start) * 1000)
            except Exception as e:
                logger.warning("[PROPOSE_SLOTS] conv_id=%s error=%s", session.conv_id, str(e)[:100], exc_info=True)
                session.state = "TRANSFERRED"
                msg = self._say(session, "transfer")
                if not msg:
                    msg = prompts.get_message("transfer", channel=channel)
                    session.add_message("agent", msg)
                    session.last_say_key, session.last_say_kwargs = "transfer", {}
                return [Event("final", msg, conv_state=session.state)]
        
        if not slots:
            logger.info("[PROPOSE_SLOTS] conv_id=%s no_slots", session.conv_id)
            session.state = "TRANSFERRED"
            msg = prompts.get_message("no_slots", channel=channel)
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]

        # Stocker slots (Fix 3: pending_slots = seule source de vérité)
        tools_booking.store_pending_slots(session, slots)
        old_state = session.state
        session.state = "WAIT_CONFIRM"
        logger.info(
            "[STATE_CHANGE] conv_id=%s %s -> WAIT_CONFIRM (slots proposed)",
            session.conv_id,
            old_state,
        )
        
        # P0.2 — Vocal : 1 créneau à la fois (pas 3 dictés d'un coup). Web : liste complète.
        if channel == "vocal":
            session.slot_offer_index = 0
            session.slot_proposal_sequential = True
            session.slots_list_sent = True
            slot0 = slots[0]
            label0 = tools_booking._slot_get(slot0, "label_vocal") or tools_booking._slot_get(slot0, "label") or str(slot0)
            msg = prompts.VOCAL_SLOT_ONE_PROPOSE.format(label=label0)
            # Patch B: préfixe "je consulte l'agenda" → zéro silence perçu (même réponse que proposition)
            agenda_lookup = getattr(prompts, "VOCAL_AGENDA_LOOKUP", "")
            msg = f"{agenda_lookup} {msg}".strip() if agenda_lookup else msg
            reset_slots_reading(session)
        else:
            msg = prompts.format_slot_proposal(slots, include_instruction=True, channel=channel)
            set_reading_slots(session, True, "propose_slots")
        # Vocal: pas de wrap "Je regarde" si déjà VOCAL_AGENDA_LOOKUP (évite redondance)
        if channel == "vocal" and msg and not getattr(prompts, "VOCAL_AGENDA_LOOKUP", ""):
            msg = prompts.TransitionSignals.wrap_with_signal(msg, "PROCESSING")
        logger.info(
            "[SLOTS_SENT] conv_id=%s channel=%s len=%s preview=%s",
            session.conv_id,
            channel,
            len(msg or ""),
            (msg or "")[:200],
        )
        logger.info("[PROPOSE_SLOTS] conv_id=%s proposing mode=%s", session.conv_id, "sequential" if channel == "vocal" else len(slots))
        session.add_message("agent", msg)
        if channel == "vocal" and slots:
            label0 = tools_booking._slot_get(slots[0], "label_vocal") or tools_booking._slot_get(slots[0], "label") or str(slots[0])
            session.last_say_key, session.last_say_kwargs = "slot_one_propose", {"label": label0}
        self._save_session(session)
        return [Event("final", msg, conv_state=session.state)]
    
    def _handle_booking_confirm(self, session: Session, user_text: str) -> List[Event]:
        """
        Gère confirmation RDV (WAIT_CONFIRM).
        P1 / P0.5 / A6 : choix explicite uniquement (1/2/3, "choix 2", "vendredi 14h").
        - Choix explicite (detect_slot_choice_early) → confirmation immédiate, pas de ré-énumération.
        - "oui"/"ok"/"d'accord" seul → jamais de choix implicite ; micro-question "Dites 1, 2 ou 3." sans incrémenter fails.
        """
        channel = getattr(session, "channel", "web")
        _assert_pending_slots_invariants(session, session.state)

        logger.info("[BOOKING_CONFIRM] conv_id=%s user=%s pending_len=%s state=%s", session.conv_id, _mask_for_log(user_text or ""), len(session.pending_slots or []), session.state)
        
        # 🔄 Si pas de slots en mémoire (session perdue) → re-proposer
        if not session.pending_slots or len(session.pending_slots) == 0:
            logger.info("[BOOKING_CONFIRM] conv_id=%s no_pending_slots re_proposing", session.conv_id)
            return self._propose_slots(session)

        # P0.2 — Vocal séquentiel : 1 créneau à la fois. OUI = ce créneau, NON = suivant ou transfert. "répéter" = relire.
        if channel == "vocal" and getattr(session, "slot_proposal_sequential", False) and session.pending_slots:
            idx = getattr(session, "slot_offer_index", 0)
            if idx < len(session.pending_slots):
                slot_obj = session.pending_slots[idx]
                label_cur = tools_booking._slot_get(slot_obj, "label_vocal") or tools_booking._slot_get(slot_obj, "label") or str(slot_obj)
                _t = (user_text or "").strip().lower()
                _t_ascii = intent_parser.normalize_stt_text(_t)
                # "répéter" / "redire" / filler (euh, hein) → relire le créneau courant (Test 5.1)
                if any(x in _t_ascii for x in ("repeter", "repetes", "redire", "reprendre", "reecoute")):
                    msg = prompts.VOCAL_SLOT_ONE_PROPOSE.format(label=label_cur)
                    session.add_message("agent", msg)
                    session.last_say_key, session.last_say_kwargs = "slot_one_propose", {"label": label_cur}
                    return [Event("final", msg, conv_state=session.state)]
                if _t_ascii in ("euh", "hein", "hum", "euhh") or _t_ascii in getattr(guards, "FILLER_GLOBAL", frozenset()):
                    msg = prompts.VOCAL_SLOT_ONE_PROPOSE.format(label=label_cur)
                    session.add_message("agent", msg)
                    session.last_say_key, session.last_say_kwargs = "slot_one_propose", {"label": label_cur}
                    return [Event("final", msg, conv_state=session.state)]
                # "le deuxième" / "le second" selon contexte (Test 5.2) : idx 0 → suivant (NO), idx 1 → ce créneau (YES)
                if any(x in _t_ascii for x in ("le deuxieme", "le second", "deuxieme", "second")) and len(_t_ascii) <= 20:
                    if idx == 0:
                        session.slot_offer_index = 1
                        if session.slot_offer_index >= len(session.pending_slots):
                            session.state = "TRANSFERRED"
                            msg = prompts.VOCAL_NO_SLOTS
                            session.add_message("agent", msg)
                            self._save_session(session)
                            return [Event("final", msg, conv_state=session.state)]
                        next_slot = session.pending_slots[session.slot_offer_index]
                        next_label = tools_booking._slot_get(next_slot, "label_vocal") or tools_booking._slot_get(next_slot, "label") or str(next_slot)
                        msg = prompts.VOCAL_SLOT_ONE_PROPOSE.format(label=next_label)
                        session.add_message("agent", msg)
                        session.last_say_key, session.last_say_kwargs = "slot_one_propose", {"label": next_label}
                        self._save_session(session)
                        return [Event("final", msg, conv_state=session.state)]
                    if idx == 1:
                        session.pending_slot_choice = 2
                        session.slot_proposal_sequential = False
                        try:
                            slot_label = tools_booking.get_label_for_choice(session, 2) or label_cur
                        except Exception:
                            slot_label = label_cur
                        msg = prompts.format_slot_early_confirm(2, slot_label, channel=channel)
                        session.add_message("agent", msg)
                        session.awaiting_confirmation = "CONFIRM_SLOT"
                        self._save_session(session)
                        return [Event("final", msg, conv_state=session.state)]
                # Test 5.3 — "oui de…" ambigu (oui deux ?) → clarification, ne pas planter
                if _t_ascii.startswith("oui de") or _t_ascii == "oui de" or (_t_ascii.startswith("oui") and " de " in _t_ascii and len(_t_ascii) < 25):
                    msg = getattr(prompts, "VOCAL_SLOT_SEQUENTIAL_NEED_YES_NO", "Dites oui si ça vous convient, ou non pour un autre créneau.")
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]
                # "celui-là" / "celui ci" → confirmer le créneau en cours (séquentiel)
                if _t_ascii in ("celui la", "celui-la", "celui ci", "celui-ci"):
                    session.slot_sequential_refuse_count = 0
                    session.pending_slot_choice = idx + 1
                    session.slot_proposal_sequential = False
                    try:
                        slot_label = tools_booking.get_label_for_choice(session, idx + 1) or label_cur
                    except Exception:
                        slot_label = label_cur
                    msg = prompts.format_slot_early_confirm(idx + 1, slot_label, channel=channel)
                    session.add_message("agent", msg)
                    session.awaiting_confirmation = "CONFIRM_SLOT"
                    self._save_session(session)
                    return [Event("final", msg, conv_state=session.state)]
                # OUI → accepter ce créneau (1-based choice = idx+1). P0 : normaliser accents (ç→c) pour STT
                _confirm_norm = frozenset(intent_parser.normalize_stt_text(w) for w in (guards.YES_WORDS | {"ouaip", "okay", "parfait", "daccord"}) if w)
                _norm_compact = (_t_ascii or "").replace(" ", "")
                _yes_implicit = _t_ascii in _confirm_norm or (_t_ascii.startswith("oui") and len(_t_ascii) <= 15 and " de " not in _t_ascii) or "bienca" in _norm_compact or "cestbienca" in _norm_compact or "cestcorrect" in _norm_compact
                if _yes_implicit:
                    session.slot_sequential_refuse_count = 0
                    session.pending_slot_choice = idx + 1
                    session.slot_proposal_sequential = False
                    try:
                        slot_label = tools_booking.get_label_for_choice(session, idx + 1) or label_cur
                    except Exception:
                        slot_label = label_cur
                    msg = prompts.format_slot_early_confirm(idx + 1, slot_label, channel=channel)
                    session.add_message("agent", msg)
                    session.awaiting_confirmation = "CONFIRM_SLOT"
                    self._save_session(session)
                    return [Event("final", msg, conv_state=session.state)]
                # NON → créneau suivant ou plus de dispo (exclure ce créneau des futures re-propositions ±90 min). P0 : normaliser
                _no_norm = frozenset(intent_parser.normalize_stt_text(w) for w in (guards.NO_WORDS | {"pas celui la", "pas ca", "autre", "suivant", "non merci"}) if w)
                if _t_ascii in _no_norm or _t_ascii.startswith("non"):
                    cur_slot = session.pending_slots[idx] if idx < len(session.pending_slots or []) else None
                    cur_start = tools_booking._slot_get(cur_slot, "start") if cur_slot else None
                    if cur_slot and cur_start:
                        rejected = getattr(session, "rejected_slot_starts", None) or []
                        if not isinstance(rejected, list):
                            rejected = []
                        session.rejected_slot_starts = rejected + [cur_start]
                        # Mémoire (day, period) refusé : anti-spam matin/après-midi
                        day = tools_booking._slot_get(cur_slot, "day") or ""
                        period = tools_booking.slot_period(cur_slot)
                        if day and period:
                            rdp = getattr(session, "rejected_day_periods", None) or []
                            key = f"{day}|{period}"
                            if key not in rdp:
                                session.rejected_day_periods = rdp + [key]
                    session.slot_sequential_refuse_count = getattr(session, "slot_sequential_refuse_count", 0) + 1
                    # Après 2 "non" consécutifs → re-proposer OU demander préférence (si déjà connue, ne pas re-demandée)
                    if session.slot_sequential_refuse_count >= 2:
                        session.slot_sequential_refuse_count = 0
                        pref = getattr(session.qualif_data, "pref", None) or None
                        if pref in ("matin", "après-midi", "soir"):
                            # Préférence déjà connue : re-fetch avec rejected_slot_starts (pas de reset) → nouveaux créneaux
                            session.slot_proposal_sequential = False
                            session.pending_slots = []
                            session.slot_offer_index = 0
                            session.slots_list_sent = False
                            session.slots_preface_sent = False
                            return self._propose_slots(session)
                        # Pas de préférence connue → demander
                        session.slot_proposal_sequential = False
                        session.state = "QUALIF_PREF"
                        session.pending_slots = []
                        session.slot_offer_index = 0
                        session.rejected_slot_starts = []
                        session.rejected_day_periods = []
                        msg = getattr(prompts, "VOCAL_SLOT_REFUSE_PREF_PROMPT", "Vous préférez plutôt le matin, l'après-midi, ou un autre jour ?")
                        session.add_message("agent", msg)
                        _persist_ivr_event(session, "slot_refuse_pref_asked")
                        self._save_session(session)
                        return [Event("final", msg, conv_state=session.state)]
                    # Skip neighbor slots + (day, period) refusés dans la liste courante (évite 9h → 9h15)
                    next_idx = idx + 1
                    seq_skip = 0
                    rejected_dp = set(getattr(session, "rejected_day_periods", None) or [])
                    while next_idx < len(session.pending_slots or []):
                        cand = session.pending_slots[next_idx]
                        cand_start = tools_booking._slot_get(cand, "start")
                        cand_day = tools_booking._slot_get(cand, "day") or ""
                        cand_period = tools_booking.slot_period(cand)
                        cand_key = f"{cand_day}|{cand_period}" if cand_day and cand_period else ""
                        if not cand_start:
                            break
                        far = tools_booking.is_slot_far_from_rejected(
                            cand_start,
                            session.rejected_slot_starts,
                            tools_booking.REJECTED_SLOT_WINDOW_MINUTES,
                        )
                        if cand_key and cand_key in rejected_dp:
                            next_idx += 1
                            seq_skip += 1
                            continue
                        if far:
                            break
                        next_idx += 1
                        seq_skip += 1
                    logger.info(
                        "[SLOT_SEQUENTIAL] conv_id=%s non→skip seq_skip=%s next_idx=%s",
                        session.conv_id,
                        seq_skip,
                        next_idx,
                    )
                    session.slot_offer_index = next_idx
                    if session.slot_offer_index >= len(session.pending_slots):
                        session.state = "TRANSFERRED"
                        msg = prompts.VOCAL_NO_SLOTS
                        session.add_message("agent", msg)
                        self._save_session(session)
                        return [Event("final", msg, conv_state=session.state)]
                    next_slot = session.pending_slots[session.slot_offer_index]
                    next_label = getattr(next_slot, "label", None) or getattr(next_slot, "label_vocal", None) or str(next_slot)
                    # Après refus : variante round-robin (évite "D'accord" répété, ton naturel)
                    msg = pick_slot_refusal_message(session, next_label, channel)
                    session.add_message("agent", msg)
                    session.last_say_key, session.last_say_kwargs = "slot_one_propose", {"label": next_label}
                    self._save_session(session)
                    return [Event("final", msg, conv_state=session.state)]
                # Incompréhension → rappeler oui/non
                msg = getattr(prompts, "VOCAL_SLOT_SEQUENTIAL_NEED_YES_NO", "Dites oui si ça vous convient, ou non pour un autre créneau.")
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]

        # P1.2 Vocal : préface déjà envoyée, liste pas encore → un seul message (liste + help ou confirmation)
        if channel == "vocal" and getattr(session, "slots_preface_sent", False) and not getattr(session, "slots_list_sent", False):
            session.slots_list_sent = True
            set_reading_slots(session, True, "wait_confirm_list")
            list_msg = prompts.format_slot_list_vocal_only(session.pending_slots)
            early_idx = detect_slot_choice_early(user_text, session.pending_slots)
            if early_idx is not None:
                logger.info(
                    "[INTERRUPTION] conv_id=%s client chose slot %s during enumeration (preface just sent), slots_count=%s",
                    session.conv_id,
                    early_idx,
                    len(session.pending_slots or []),
                )
                reset_slots_reading(session)
                session.pending_slot_choice = early_idx
                try:
                    slot_label = tools_booking.get_label_for_choice(session, early_idx) or "votre créneau"
                except Exception:
                    slot_label = "votre créneau"
                confirm_msg = prompts.format_slot_early_confirm(early_idx, slot_label, channel=channel)
                session.awaiting_confirmation = "CONFIRM_SLOT"
                return self._final(session, confirm_msg)
            help_msg = getattr(prompts, "MSG_SLOT_BARGE_IN_HELP", "D'accord. Dites juste 1, 2 ou 3.")
            combined = f"{list_msg} {help_msg}".strip()
            return self._final(session, combined)

        # P1.1 Barge-in safe : user a parlé pendant l'énumération des créneaux (interruption positive)
        if getattr(session, "is_reading_slots", False):
            early_idx = detect_slot_choice_early(user_text, session.pending_slots)
            if early_idx is not None:
                logger.info(
                    "[INTERRUPTION] conv_id=%s client chose slot %s during enumeration, slots_count=%s",
                    session.conv_id,
                    early_idx,
                    len(session.pending_slots or []),
                )
                reset_slots_reading(session)
                session.pending_slot_choice = early_idx
                self._save_session(session)
                try:
                    slot_label = tools_booking.get_label_for_choice(session, early_idx) or "votre créneau"
                except Exception:
                    slot_label = "votre créneau"
                msg = prompts.format_slot_early_confirm(early_idx, slot_label, channel=channel)
                session.add_message("agent", msg)
                session.awaiting_confirmation = "CONFIRM_SLOT"
                logger.info("[BOOKING_CONFIRM] conv_id=%s barge_in early_confirm idx=%s", session.conv_id, early_idx)
                return [Event("final", msg, conv_state=session.state)]
            # Pas un choix clair → une phrase courte, ne pas incrémenter les fails
            reset_slots_reading(session)
            msg = getattr(prompts, "MSG_SLOT_BARGE_IN_HELP", "D'accord. Dites juste 1, 2 ou 3.")
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        slot_idx: Optional[int] = None

        # Confirmation du créneau déjà choisi : "oui", "oui je confirme", "c'est bien ça", etc. → on passe au contact
        # P0 : normaliser accents (ç→c) via normalize_stt_text pour toutes les variantes STT
        if session.pending_slot_choice is not None:
            _t = (user_text or "").strip().lower()
            _t_ascii = intent_parser.normalize_stt_text(_t)
            _confirm_words = guards.YES_WORDS | {"ouaip", "okay", "parfait", "daccord"}
            _confirm_norm = frozenset(intent_parser.normalize_stt_text(w) for w in _confirm_words if w)
            if _t_ascii in _confirm_norm:
                slot_idx = session.pending_slot_choice
                session.awaiting_confirmation = None
                logger.info("[BOOKING_CONFIRM] conv_id=%s slot_confirmed idx=%s → contact", session.conv_id, slot_idx)
            else:
                _norm_compact = (_t_ascii or "").replace(" ", "")
                if "bienca" in _norm_compact or "bien ca" in (_t_ascii or "") or "cestbienca" in _norm_compact:
                    slot_idx = session.pending_slot_choice
                    session.awaiting_confirmation = None
                    logger.info("[BOOKING_CONFIRM] conv_id=%s slot_confirmed_phrase idx=%s", session.conv_id, slot_idx)
                elif (_t_ascii or "").startswith("oui") and len(_t_ascii or "") <= 25 and ("bien" in (_t_ascii or "") or "ca" in (_t_ascii or "")):
                    slot_idx = session.pending_slot_choice
                    session.awaiting_confirmation = None
                    logger.info("[BOOKING_CONFIRM] conv_id=%s slot_confirmed_oui idx=%s", session.conv_id, slot_idx)
                elif "confirme" in (_t_ascii or "") and len(_t_ascii or "") <= 30:
                    # "oui je confirme", "je confirme", "confirme" (réponse à "Vous confirmez ?")
                    slot_idx = session.pending_slot_choice
                    session.awaiting_confirmation = None
                    logger.info("[BOOKING_CONFIRM] conv_id=%s slot_confirmed_explicit idx=%s", session.conv_id, slot_idx)

        # Validation vague (oui/ok/d'accord SANS choix explicite) → redemander 1/2/3 SANS incrémenter fails (P0.5, A6)
        if slot_idx is None:
            _vague = (user_text or "").strip().lower()
            _vague = "".join(c for c in _vague if c.isalnum() or c in " '\"-")
            _vague = _vague.replace("'", "").replace("'", "").strip()
            _vague_set = frozenset({
                "oui", "ouais", "ok", "okay", "d'accord", "daccord", "dac", "parfait",
                "celui-la", "celui la", "ça marche", "ca marche", "c'est ça", "c est ça",
            })
            if _vague in _vague_set or _vague.startswith("je prends") or _vague.startswith("je veux"):
                msg = getattr(prompts, "MSG_WAIT_CONFIRM_NEED_NUMBER", prompts.MSG_SLOT_BARGE_IN_HELP)
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]

        # Sinon : filler ou choix à détecter
        if slot_idx is None:
            if guards.is_contextual_filler(user_text, session.state):
                log_filler_detected(logger, session, user_text, field="slot_choice")
                fail_count = increment_recovery_counter(session, "slot_choice")
                log_ivr_event(logger, session, "recovery_step", context="slot_choice", reason="filler_detected")
                if should_escalate_recovery(session, "slot_choice"):
                    return self._trigger_intent_router(session, "slot_choice_fails_3", user_text)
                msg = prompts.get_clarification_message(
                    "slot_choice",
                    min(fail_count, 3),
                    user_text,
                    channel=channel,
                )
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]

        logger.debug("[BOOKING_CONFIRM] conv_id=%s pending_len=%s", session.conv_id, len(session.pending_slots or []))
        # Early commit : choix non ambigu ("oui 1", "le premier", "1") → confirmation immédiate, pas "oui" seul
        if slot_idx is None:
            early_idx = detect_slot_choice_early(user_text, session.pending_slots)
            if early_idx is not None:
                if getattr(session, "is_reading_slots", False):
                    logger.info(
                        "[INTERRUPTION] conv_id=%s client chose slot %s during enumeration, slots_count=%s",
                        session.conv_id,
                        early_idx,
                    len(session.pending_slots or []),
                )
                reset_slots_reading(session)
                session.pending_slot_choice = early_idx
                self._save_session(session)
                try:
                    slot_label = tools_booking.get_label_for_choice(session, early_idx) or "votre créneau"
                except Exception:
                    slot_label = "votre créneau"
                msg = prompts.format_slot_early_confirm(early_idx, slot_label, channel=channel)
                session.add_message("agent", msg)
                session.awaiting_confirmation = "CONFIRM_SLOT"
                logger.info("[BOOKING_CONFIRM] conv_id=%s early_commit idx=%s", session.conv_id, early_idx)
                return [Event("final", msg, conv_state=session.state)]

        if slot_idx is None:
            # IVR pro : choix flexible par numéro / jour / heure (ambiguïté → recovery). Pas "oui" seul.
            proposed_slots = [
                {
                    "start": tools_booking._slot_get(s, "start"),
                    "label_vocal": tools_booking._slot_get(s, "label_vocal") or tools_booking._slot_get(s, "label"),
                    "day": tools_booking._slot_get(s, "day"),
                    "hour": tools_booking._slot_get(s, "hour", 0),
                }
                for s in (session.pending_slots or [])
            ]
            slot_idx = guards.detect_slot_choice_flexible(user_text, proposed_slots)
            if slot_idx is None:
                _raw = detect_slot_choice(user_text, num_slots=len(session.pending_slots or []))
                if _raw is not None:
                    slot_idx = _raw + 1  # 0-based → 1-based
            if slot_idx is None:
                is_valid, slot_idx = guards.validate_booking_confirm(user_text, channel=channel)
                if not is_valid:
                    slot_idx = None
        logger.info("[BOOKING_CONFIRM] conv_id=%s slot_choice user=%s idx=%s", session.conv_id, _mask_for_log(user_text or ""), slot_idx)
        
        if slot_idx is not None:
            logger.info("[BOOKING_CONFIRM] conv_id=%s slot_validated idx=%s", session.conv_id, slot_idx)
            session.awaiting_confirmation = None
            
            # Stocker le choix de créneau
            try:
                slot_label = tools_booking.get_label_for_choice(session, slot_idx) or "votre créneau"
                logger.debug("[BOOKING_CONFIRM] conv_id=%s slot_label=%s", session.conv_id, (slot_label or "")[:40])
            except Exception as e:
                logger.warning("[BOOKING_CONFIRM] conv_id=%s slot_label_error=%s", session.conv_id, str(e)[:80], exc_info=True)
                slot_label = "votre créneau"
            
            name = session.qualif_data.name or ""
            
            # Stocker temporairement le slot choisi (on bookera après confirmation du contact)
            session.pending_slot_choice = slot_idx
            logger.info("[BOOKING_CONFIRM] conv_id=%s stored_choice=%s", session.conv_id, slot_idx)
            
            # 💾 Sauvegarder le choix immédiatement
            self._save_session(session)
            
            reset_slots_reading(session)
            # 📱 Maintenant demander le contact (avec numéro auto si disponible)
            if channel == "vocal" and session.customer_phone:
                try:
                    phone = str(session.customer_phone)
                    # Nettoyer le format
                    if phone.startswith("+33"):
                        phone = "0" + phone[3:]
                    elif phone.startswith("33"):
                        phone = "0" + phone[2:]
                    phone = phone.replace(" ", "").replace("-", "").replace(".", "")
                    
                    if len(phone) >= 10:
                        session.qualif_data.contact = phone[:10]
                        session.qualif_data.contact_type = "phone"
                        session.state = "CONTACT_CONFIRM"
                        phone_formatted = prompts.format_phone_for_voice(phone[:10])
                        msg = prompts.VOCAL_CONTACT_CONFIRM_SHORT.format(phone_formatted=phone_formatted) if channel == "vocal" else f"Parfait, {slot_label} pour {name}. Votre numéro est bien le {phone_formatted} ?"
                        logger.info("[BOOKING_CONFIRM] conv_id=%s using_caller_id", session.conv_id)
                        session.add_message("agent", msg)
                        session.awaiting_confirmation = "CONFIRM_CONTACT"
                        session.last_question_asked = msg
                        return [Event("final", msg, conv_state=session.state)]
                except Exception as e:
                    logger.warning("[BOOKING_CONFIRM] conv_id=%s caller_id_error=%s", session.conv_id, str(e)[:80], exc_info=True)
                    # Continue avec le flow normal
            
            # Sinon demander le contact normalement
            logger.info("[BOOKING_CONFIRM] conv_id=%s no_caller_id asking_contact", session.conv_id)
            session.state = "QUALIF_CONTACT"
            self._save_session(session)
            logger.info("[BOOKING_CONFIRM] conv_id=%s name=%s", session.conv_id, _mask_for_log(name or ""))
            
            msg = prompts.get_qualif_question("contact", channel=channel)
            
            logger.debug("[BOOKING_CONFIRM] conv_id=%s final_msg_len=%s", session.conv_id, len(msg or ""))
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]

        # ❌ Invalide → 1 clarification avant transfert (UX : pas de transfert brutal au 1er échec)
        fail_count = increment_recovery_counter(session, "slot_choice")
        log_ivr_event(logger, session, "recovery_step", context="slot_choice", reason="no_match")
        if should_escalate_recovery(session, "slot_choice"):
            reset_slots_reading(session)
            return self._trigger_intent_router(session, "slot_choice_fails_3", user_text)
        if fail_count == 1:
            # 1er échec : clarification, pas de transfert. Adapter au mode : séquentiel → oui/non, 3 slots → 1/2/3
            use_yesno = (session.pending_slot_choice is not None) or getattr(session, "slot_proposal_sequential", False)
            msg = (
                getattr(prompts, "VOCAL_CONFIRM_CLARIFY_YESNO", "Dites oui ou non, s'il vous plaît.")
                if use_yesno
                else prompts.get_clarification_message("slot_choice", 1, user_text, channel=channel)
            )
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        # 2e échec → transfert (P0: budget peut prévenir)
        reset_slots_reading(session)
        prev = self._maybe_prevent_transfer(session, channel, "slot_choice_fails", user_text)
        if prev is not None:
            return prev
        msg = self._say(session, "transfer")
        if not msg:
            msg = prompts.get_message("transfer", channel=channel)
        return self._trigger_transfer(session, channel, "slot_choice_fails", user_text=user_text, custom_msg=msg)
    
    # ========================
    # FLOW C: CANCEL
    # ========================
    
    def _start_cancel(self, session: Session) -> List[Event]:
        """Démarre le flow d'annulation (reset des compteurs recovery du flow)."""
        channel = getattr(session, "channel", "web")
        session.state = "CANCEL_NAME"
        session.name_fails = 0
        session.cancel_name_fails = 0
        session.cancel_rdv_not_found_count = 0
        session.confirm_retry_count = 0
        session.pending_cancel_slot = None
        msg = prompts.VOCAL_CANCEL_ASK_NAME if channel == "vocal" else prompts.MSG_CANCEL_ASK_NAME_WEB
        session.add_message("agent", msg)
        return [Event("final", msg, conv_state=session.state)]
    
    def _handle_cancel(self, session: Session, user_text: str) -> List[Event]:
        """Gère le flow d'annulation avec recovery progressive (nom pas compris, RDV non trouvé)."""
        channel = getattr(session, "channel", "web")
        max_fails = getattr(Session, "MAX_CONTEXT_FAILS", 3)
        
        # État CANCEL_NO_RDV : user a dit un nom, RDV pas trouvé → proposer vérifier ou humain (ou oui/non)
        if session.state == "CANCEL_NO_RDV":
            intent = detect_intent(user_text, session.state)
            msg_lower = user_text.strip().lower()
            # Oui = ré-épeler le nom (redemander)
            if intent == "YES" or any(p in msg_lower for p in ["vérifier", "verifier", "réessayer", "orthographe", "redonner", "redonne"]):
                session.state = "CANCEL_NAME"
                session.qualif_data.name = None
                session.cancel_rdv_not_found_count = 0
                msg = prompts.VOCAL_CANCEL_ASK_NAME if channel == "vocal" else prompts.MSG_CANCEL_ASK_NAME_WEB
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            # Non = parler à quelqu'un → transfert
            if intent == "NO" or any(p in msg_lower for p in ["humain", "quelqu'un", "parler à quelqu'un", "opérateur", "transfert", "conseiller"]):
                session.state = "TRANSFERRED"
                msg = self._say(session, "transfer")
                if not msg:
                    msg = prompts.get_message("transfer", channel=channel)
                    session.add_message("agent", msg)
                    session.last_say_key, session.last_say_kwargs = "transfer", {}
                return [Event("final", msg, conv_state=session.state)]
            # Nouveau nom fourni → rechercher à nouveau
            session.qualif_data.name = user_text.strip()
            existing_slot = tools_booking.find_booking_by_name(session.qualif_data.name, session)
            if isinstance(existing_slot, dict) and existing_slot.get("provider") == "none":
                session.state = "TRANSFERRED"
                msg = prompts.MSG_NO_AGENDA_TRANSFER
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            if existing_slot:
                session.state = "CANCEL_CONFIRM"
                session.pending_cancel_slot = existing_slot
                slot_label = existing_slot.get("label", "votre rendez-vous")
                msg = prompts.VOCAL_CANCEL_CONFIRM.format(slot_label=slot_label) if channel == "vocal" else prompts.MSG_CANCEL_CONFIRM_WEB.format(slot_label=slot_label)
                session.add_message("agent", msg)
                session.awaiting_confirmation = "CONFIRM_CANCEL"
                return [Event("final", msg, conv_state=session.state)]
            # Toujours pas trouvé : utiliser cancel_rdv_not_found_count
            session.cancel_rdv_not_found_count = getattr(session, "cancel_rdv_not_found_count", 0) + 1
            session.cancel_name_fails = getattr(session, "cancel_name_fails", 0) + 1
            if session.cancel_rdv_not_found_count >= max_fails or session.cancel_name_fails >= max_fails:
                log_ivr_event(logger, session, "recovery_step", context="cancel_rdv_not_found", reason="escalate_intent_router")
                return self._trigger_intent_router(session, "cancel_not_found_3", user_text)
            log_ivr_event(logger, session, "recovery_step", context="cancel_rdv_not_found", reason="offer_verify_or_human")
            name = session.qualif_data.name or "?"
            msg = prompts.VOCAL_CANCEL_NOT_FOUND_VERIFIER_HUMAN.format(name=name) if channel == "vocal" else prompts.MSG_CANCEL_NOT_FOUND_VERIFIER_HUMAN_WEB.format(name=name)
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        if session.state == "CANCEL_NAME":
            raw = user_text.strip()
            # Nom pas compris (vide, trop court, ou phrase d'intention type "annuler"/"je veux un rdv") — recovery progressive
            if not raw or len(raw) < 2 or not guards.is_valid_name_input(user_text):
                session.cancel_name_fails = getattr(session, "cancel_name_fails", 0) + 1
                if session.cancel_name_fails >= 3:
                    log_ivr_event(logger, session, "recovery_step", context="cancel_name", reason="escalate_intent_router")
                    return self._trigger_intent_router(session, "cancel_name_fails_3", user_text)
                if session.cancel_name_fails == 1:
                    log_ivr_event(logger, session, "recovery_step", context="cancel_name", reason="retry_1")
                    msg = prompts.VOCAL_CANCEL_NAME_RETRY_1 if channel == "vocal" else prompts.MSG_CANCEL_NAME_RETRY_1_WEB
                else:
                    log_ivr_event(logger, session, "recovery_step", context="cancel_name", reason="retry_2")
                    msg = prompts.VOCAL_CANCEL_NAME_RETRY_2 if channel == "vocal" else prompts.MSG_CANCEL_NAME_RETRY_2_WEB
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # Nom valide → chercher le RDV (reset compteur nom du flow cancel)
            session.qualif_data.name = raw
            session.name_fails = 0
            session.cancel_name_fails = 0
            existing_slot = tools_booking.find_booking_by_name(session.qualif_data.name, session)
            if isinstance(existing_slot, dict) and existing_slot.get("provider") == "none":
                session.state = "TRANSFERRED"
                msg = prompts.MSG_NO_AGENDA_TRANSFER
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            if not existing_slot:
                session.cancel_rdv_not_found_count = getattr(session, "cancel_rdv_not_found_count", 0) + 1
                session.cancel_name_fails = getattr(session, "cancel_name_fails", 0) + 1
                if session.cancel_rdv_not_found_count >= max_fails:
                    log_ivr_event(logger, session, "recovery_step", context="cancel_rdv_not_found", reason="escalate_intent_router")
                    return self._trigger_intent_router(session, "cancel_not_found_3", user_text)
                log_ivr_event(logger, session, "recovery_step", context="cancel_rdv_not_found", reason="offer_verify_or_human")
                session.state = "CANCEL_NO_RDV"
                name = session.qualif_data.name
                msg = prompts.VOCAL_CANCEL_NOT_FOUND_VERIFIER_HUMAN.format(name=name) if channel == "vocal" else prompts.MSG_CANCEL_NOT_FOUND_VERIFIER_HUMAN_WEB.format(name=name)
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # RDV trouvé → demander confirmation
            session.cancel_rdv_not_found_count = 0
            session.state = "CANCEL_CONFIRM"
            session.pending_cancel_slot = existing_slot
            slot_label = existing_slot.get("label", "votre rendez-vous")
            msg = prompts.VOCAL_CANCEL_CONFIRM.format(slot_label=slot_label) if channel == "vocal" else prompts.MSG_CANCEL_CONFIRM_WEB.format(slot_label=slot_label)
            session.add_message("agent", msg)
            session.awaiting_confirmation = "CONFIRM_CANCEL"
            return [Event("final", msg, conv_state=session.state)]
        
        elif session.state == "CANCEL_CONFIRM":
            intent = detect_intent(user_text, session.state)
            
            if intent == "YES":
                session.awaiting_confirmation = None
                # --- P0: Annulation Google (event_id) ou SQLite (slot_id) ---
                slot = getattr(session, "pending_cancel_slot", None) or {}
                event_id = None
                slot_id = None
                if isinstance(slot, dict):
                    event_id = slot.get("event_id") or slot.get("google_event_id")
                    slot_id = slot.get("slot_id")
                else:
                    event_id = getattr(slot, "event_id", None) or getattr(slot, "google_event_id", None)
                    slot_id = getattr(slot, "slot_id", None)

                if not event_id and slot_id is None:
                    log_ivr_event(logger, session, "cancel_not_supported_no_event_id")
                    _persist_ivr_event(session, "cancel_failed")
                    session.state = "TRANSFERRED"
                    msg = getattr(prompts, "CANCEL_NOT_SUPPORTED_TRANSFER", "Je vous mets en relation. Un instant.")
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]

                log_ivr_event(logger, session, "cancel_attempt")
                ok = False
                try:
                    ok = bool(tools_booking.cancel_booking(slot, session))
                except Exception:
                    ok = False

                if ok:
                    log_ivr_event(logger, session, "cancel_success")
                    _persist_ivr_event(session, "cancel_done")
                    session.state = "CONFIRMED"
                    msg = prompts.VOCAL_CANCEL_DONE if channel == "vocal" else prompts.MSG_CANCEL_DONE_WEB
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]

                # Annulation échouée (tool fail / event id invalide)
                log_ivr_event(logger, session, "cancel_failed")
                _persist_ivr_event(session, "cancel_failed")
                session.state = "TRANSFERRED"
                msg = getattr(prompts, "CANCEL_FAILED_TRANSFER", "Je vous mets en relation. Un instant.")
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            elif intent == "NO":
                session.awaiting_confirmation = None
                # Garder le RDV
                session.state = "CONFIRMED"
                msg = prompts.VOCAL_CANCEL_KEPT if channel == "vocal" else prompts.MSG_CANCEL_KEPT_WEB
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            else:
                # --- P1: Anti-boucle CANCEL_CONFIRM ---
                # unclear => clarification 1/2, puis 3e => INTENT_ROUTER
                session.confirm_retry_count = getattr(session, "confirm_retry_count", 0) + 1
                if session.confirm_retry_count == 1:
                    msg = prompts.get_clarification_message(
                        "cancel_confirm", 1, user_text, channel=channel,
                    )
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]
                if session.confirm_retry_count == 2:
                    msg = prompts.get_clarification_message(
                        "cancel_confirm", 2, user_text, channel=channel,
                    )
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]
                log_ivr_event(logger, session, "cancel_confirm_unclear_3")
                return safe_reply(
                    self._trigger_intent_router(session, "cancel_confirm_unclear_3", user_text),
                    session,
                )
        
        # Fallback
        return self._fallback_transfer(session)
    
    # ========================
    # FLOW D: MODIFY
    # ========================
    
    def _start_modify(self, session: Session) -> List[Event]:
        """Démarre le flow de modification (reset des compteurs recovery du flow)."""
        channel = getattr(session, "channel", "web")
        session.state = "MODIFY_NAME"
        session.name_fails = 0
        session.modify_name_fails = 0
        session.modify_rdv_not_found_count = 0
        msg = prompts.VOCAL_MODIFY_ASK_NAME if channel == "vocal" else prompts.MSG_MODIFY_ASK_NAME_WEB
        session.add_message("agent", msg)
        return [Event("final", msg, conv_state=session.state)]
    
    def _handle_modify(self, session: Session, user_text: str) -> List[Event]:
        """Gère le flow de modification avec recovery progressive (nom pas compris, RDV non trouvé)."""
        channel = getattr(session, "channel", "web")
        max_fails = getattr(Session, "MAX_CONTEXT_FAILS", 3)
        
        # État MODIFY_NO_RDV : proposer vérifier ou humain (ou oui/non)
        if session.state == "MODIFY_NO_RDV":
            intent = detect_intent(user_text, session.state)
            msg_lower = user_text.strip().lower()
            if intent == "YES" or any(p in msg_lower for p in ["vérifier", "verifier", "réessayer", "orthographe", "redonner", "redonne"]):
                session.state = "MODIFY_NAME"
                session.qualif_data.name = None
                session.modify_rdv_not_found_count = 0
                msg = prompts.VOCAL_MODIFY_ASK_NAME if channel == "vocal" else prompts.MSG_MODIFY_ASK_NAME_WEB
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            if intent == "NO" or any(p in msg_lower for p in ["humain", "quelqu'un", "parler à quelqu'un", "opérateur", "transfert", "conseiller"]):
                session.state = "TRANSFERRED"
                msg = self._say(session, "transfer")
                if not msg:
                    msg = prompts.get_message("transfer", channel=channel)
                    session.add_message("agent", msg)
                    session.last_say_key, session.last_say_kwargs = "transfer", {}
                return [Event("final", msg, conv_state=session.state)]
            session.qualif_data.name = user_text.strip()
            existing_slot = tools_booking.find_booking_by_name(session.qualif_data.name, session)
            if isinstance(existing_slot, dict) and existing_slot.get("provider") == "none":
                session.state = "TRANSFERRED"
                msg = prompts.MSG_NO_AGENDA_TRANSFER
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            if existing_slot:
                session.state = "MODIFY_CONFIRM"
                session.pending_cancel_slot = existing_slot
                slot_label = existing_slot.get("label", "votre rendez-vous")
                msg = prompts.VOCAL_MODIFY_CONFIRM.format(slot_label=slot_label) if channel == "vocal" else prompts.MSG_MODIFY_CONFIRM_WEB.format(slot_label=slot_label)
                session.add_message("agent", msg)
                session.awaiting_confirmation = "CONFIRM_MODIFY"
                return [Event("final", msg, conv_state=session.state)]
            session.modify_rdv_not_found_count = getattr(session, "modify_rdv_not_found_count", 0) + 1
            session.modify_name_fails = getattr(session, "modify_name_fails", 0) + 1
            if session.modify_rdv_not_found_count >= max_fails:
                log_ivr_event(logger, session, "recovery_step", context="modify_rdv_not_found", reason="escalate_intent_router")
                return self._trigger_intent_router(session, "modify_not_found_3", user_text)
            log_ivr_event(logger, session, "recovery_step", context="modify_rdv_not_found", reason="offer_verify_or_human")
            name = session.qualif_data.name or "?"
            msg = prompts.VOCAL_MODIFY_NOT_FOUND_VERIFIER_HUMAN.format(name=name) if channel == "vocal" else prompts.MSG_MODIFY_NOT_FOUND_VERIFIER_HUMAN_WEB.format(name=name)
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        if session.state == "MODIFY_NAME":
            raw = user_text.strip()
            # Nom pas compris (vide ou trop court) — recovery progressive avec compteur dédié
            if not raw or len(raw) < 2:
                session.modify_name_fails = getattr(session, "modify_name_fails", 0) + 1
                if session.modify_name_fails >= 3:
                    log_ivr_event(logger, session, "recovery_step", context="modify_name", reason="escalate_intent_router")
                    return self._trigger_intent_router(session, "modify_name_fails_3", user_text)
                if session.modify_name_fails == 1:
                    log_ivr_event(logger, session, "recovery_step", context="modify_name", reason="retry_1")
                    msg = prompts.VOCAL_MODIFY_NAME_RETRY_1 if channel == "vocal" else prompts.MSG_MODIFY_NAME_RETRY_1_WEB
                else:
                    log_ivr_event(logger, session, "recovery_step", context="modify_name", reason="retry_2")
                    msg = prompts.VOCAL_MODIFY_NAME_RETRY_2 if channel == "vocal" else prompts.MSG_MODIFY_NAME_RETRY_2_WEB
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            session.qualif_data.name = raw
            session.name_fails = 0
            session.modify_name_fails = 0
            existing_slot = tools_booking.find_booking_by_name(session.qualif_data.name, session)
            if isinstance(existing_slot, dict) and existing_slot.get("provider") == "none":
                session.state = "TRANSFERRED"
                msg = prompts.MSG_NO_AGENDA_TRANSFER
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            if not existing_slot:
                session.modify_rdv_not_found_count = getattr(session, "modify_rdv_not_found_count", 0) + 1
                session.modify_name_fails = getattr(session, "modify_name_fails", 0) + 1
                if session.modify_rdv_not_found_count >= max_fails:
                    log_ivr_event(logger, session, "recovery_step", context="modify_rdv_not_found", reason="escalate_intent_router")
                    return self._trigger_intent_router(session, "modify_not_found_3", user_text)
                log_ivr_event(logger, session, "recovery_step", context="modify_rdv_not_found", reason="offer_verify_or_human")
                session.state = "MODIFY_NO_RDV"
                name = session.qualif_data.name
                msg = prompts.VOCAL_MODIFY_NOT_FOUND_VERIFIER_HUMAN.format(name=name) if channel == "vocal" else prompts.MSG_MODIFY_NOT_FOUND_VERIFIER_HUMAN_WEB.format(name=name)
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            session.modify_rdv_not_found_count = 0
            session.state = "MODIFY_CONFIRM"
            session.pending_cancel_slot = existing_slot
            slot_label = existing_slot.get("label", "votre rendez-vous")
            msg = prompts.VOCAL_MODIFY_CONFIRM.format(slot_label=slot_label) if channel == "vocal" else prompts.MSG_MODIFY_CONFIRM_WEB.format(slot_label=slot_label)
            session.add_message("agent", msg)
            session.awaiting_confirmation = "CONFIRM_MODIFY"
            return [Event("final", msg, conv_state=session.state)]
        
        elif session.state == "MODIFY_CONFIRM":
            intent = detect_intent(user_text, session.state)
            
            if intent == "YES":
                session.awaiting_confirmation = None
                # P0.4 — Ne pas annuler l'ancien avant d'avoir sécurisé le nouveau (ordre : nouveau confirmé → puis annuler ancien)
                session.state = "QUALIF_PREF"
                msg = prompts.VOCAL_MODIFY_NEW_PREF if channel == "vocal" else prompts.MSG_MODIFY_NEW_PREF_WEB
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            elif intent == "NO":
                session.awaiting_confirmation = None
                # Garder le RDV
                session.state = "CONFIRMED"
                msg = prompts.VOCAL_CANCEL_KEPT if channel == "vocal" else prompts.MSG_CANCEL_KEPT_WEB
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            else:
                session.confirm_retry_count += 1
                msg = prompts.get_clarification_message(
                    "modify_confirm",
                    min(session.confirm_retry_count, 2),
                    user_text,
                    channel=channel,
                )
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
        
        return self._fallback_transfer(session)
    
    # ========================
    # FLOW ORDONNANCE (conversation naturelle : RDV ou message)
    # ========================
    
    def _handle_ordonnance_flow(self, session: Session, user_text: str) -> List[Event]:
        """Flow ordonnance : proposer RDV ou message (langage naturel, pas menu 1/2)."""
        channel = getattr(session, "channel", "web")
        if not getattr(session, "ordonnance_choice_asked", False):
            session.ordonnance_choice_asked = True
            msg = prompts.VOCAL_ORDONNANCE_ASK_CHOICE if channel == "vocal" else prompts.MSG_ORDONNANCE_ASK_CHOICE_WEB
            session.add_message("agent", msg)
            session.state = "ORDONNANCE_CHOICE"
            return [Event("final", msg, conv_state=session.state)]
        choice = detect_ordonnance_choice(user_text)
        if choice == "rdv":
            session.state = "QUALIF_NAME"
            session.qualif_data.name = None
            session.qualif_data.motif = None
            session.qualif_data.pref = None
            session.qualif_data.contact = None
            session.name_fails = 0
            msg = prompts.get_qualif_question("name", channel=channel)
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        if choice == "message":
            session.state = "ORDONNANCE_MESSAGE"
            session.qualif_data.name = None
            session.qualif_data.contact = None
            session.name_fails = 0
            msg = prompts.VOCAL_ORDONNANCE_ASK_NAME if channel == "vocal" else prompts.MSG_ORDONNANCE_ASK_NAME_WEB
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        session.ordonnance_choice_fails = getattr(session, "ordonnance_choice_fails", 0) + 1
        if session.ordonnance_choice_fails == 1:
            msg = prompts.VOCAL_ORDONNANCE_CHOICE_RETRY_1
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state="ORDONNANCE_CHOICE")]
        if session.ordonnance_choice_fails == 2:
            msg = prompts.VOCAL_ORDONNANCE_CHOICE_RETRY_2
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state="ORDONNANCE_CHOICE")]
        session.state = "TRANSFERRED"
        msg = self._say(session, "transfer")
        if not msg:
            msg = prompts.get_message("transfer", channel=channel)
            session.add_message("agent", msg)
            session.last_say_key, session.last_say_kwargs = "transfer", {}
        return [Event("final", msg, conv_state=session.state)]
    
    def _handle_ordonnance_message(self, session: Session, user_text: str) -> List[Event]:
        """Collecte nom + téléphone pour demande ordonnance (message), puis notification."""
        channel = getattr(session, "channel", "web")
        if not session.qualif_data.name:
            extracted_name, reject_reason = guards.extract_name_from_speech(user_text)
            if extracted_name is None:
                session.name_fails = getattr(session, "name_fails", 0) + 1
                if session.name_fails == 1:
                    msg = prompts.VOCAL_ORDONNANCE_NAME_RETRY_1
                elif session.name_fails == 2:
                    msg = prompts.VOCAL_ORDONNANCE_NAME_RETRY_2
                else:
                    session.state = "TRANSFERRED"
                    msg = self._say(session, "transfer")
                    if not msg:
                        msg = prompts.get_message("transfer", channel=channel)
                        session.add_message("agent", msg)
                        session.last_say_key, session.last_say_kwargs = "transfer", {}
                    return [Event("final", msg, conv_state=session.state)]
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state="ORDONNANCE_MESSAGE")]
            session.qualif_data.name = extracted_name.title()
            session.name_fails = 0
            # Demander le téléphone (ou confirmer Caller ID) au tour suivant
            if channel == "vocal" and session.customer_phone:
                phone = str(session.customer_phone).replace("+33", "0").replace(" ", "").replace("-", "")
                if phone.startswith("33"):
                    phone = "0" + phone[2:]
                if len("".join(c for c in phone if c.isdigit())) >= 10:
                    session.state = "ORDONNANCE_PHONE_CONFIRM"
                    formatted = prompts.format_phone_for_voice(phone[:10])
                    msg = f"Votre numéro est bien le {formatted} ?"
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]
            msg = prompts.VOCAL_ORDONNANCE_PHONE_ASK
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state="ORDONNANCE_MESSAGE")]
        if not session.qualif_data.contact:
            if channel == "vocal" and session.customer_phone:
                phone = str(session.customer_phone).replace("+33", "0").replace(" ", "").replace("-", "")
                if phone.startswith("33"):
                    phone = "0" + phone[2:]
                if len("".join(c for c in phone if c.isdigit())) >= 10:
                    session.state = "ORDONNANCE_PHONE_CONFIRM"
                    formatted = prompts.format_phone_for_voice(phone[:10])
                    msg = f"Votre numéro est bien le {formatted} ?"
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]
            ok, normalized, _ = guards.is_plausible_phone_input(user_text)
            if not ok:
                session.phone_fails = getattr(session, "phone_fails", 0) + 1
                if session.phone_fails >= 3:
                    session.state = "TRANSFERRED"
                    msg = self._say(session, "transfer")
                    if not msg:
                        msg = prompts.get_message("transfer", channel=channel)
                        session.add_message("agent", msg)
                        session.last_say_key, session.last_say_kwargs = "transfer", {}
                    return [Event("final", msg, conv_state=session.state)]
                msg = prompts.VOCAL_ORDONNANCE_PHONE_ASK
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state="ORDONNANCE_MESSAGE")]
            session.qualif_data.contact = normalized
            session.qualif_data.contact_type = "phone"
        from datetime import datetime
        from backend.services.email_service import send_ordonnance_notification
        req = {"type": "ordonnance", "name": session.qualif_data.name, "phone": session.qualif_data.contact or "?", "timestamp": datetime.utcnow().isoformat()}
        send_ordonnance_notification(req)
        session.state = "CONFIRMED"
        msg = prompts.VOCAL_ORDONNANCE_DONE if channel == "vocal" else prompts.MSG_ORDONNANCE_DONE_WEB
        session.add_message("agent", msg)
        return [Event("final", msg, conv_state=session.state)]
    
    def _handle_ordonnance_phone_confirm(self, session: Session, user_text: str) -> List[Event]:
        """Confirmation Caller ID pour ordonnance message."""
        channel = getattr(session, "channel", "web")
        intent = detect_intent(user_text, session.state)
        if intent == "YES":
            phone = str(session.customer_phone or "").replace("+33", "0").replace(" ", "").replace("-", "")
            if phone.startswith("33"):
                phone = "0" + phone[2:]
            session.qualif_data.contact = phone[:10] if len("".join(c for c in phone if c.isdigit())) >= 10 else phone
            session.qualif_data.contact_type = "phone"
            from datetime import datetime
            from backend.services.email_service import send_ordonnance_notification
            req = {"type": "ordonnance", "name": session.qualif_data.name, "phone": session.qualif_data.contact or "?", "timestamp": datetime.utcnow().isoformat()}
            send_ordonnance_notification(req)
            session.state = "CONFIRMED"
            msg = prompts.VOCAL_ORDONNANCE_DONE if channel == "vocal" else prompts.MSG_ORDONNANCE_DONE_WEB
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        if intent == "NO":
            msg = prompts.VOCAL_ORDONNANCE_PHONE_ASK
            session.add_message("agent", msg)
            session.state = "ORDONNANCE_MESSAGE"
            return [Event("final", msg, conv_state=session.state)]
        msg = "Dites oui ou non."
        session.add_message("agent", msg)
        return [Event("final", msg, conv_state="ORDONNANCE_PHONE_CONFIRM")]
    
    # ========================
    # CONFIRMATION CONTACT
    # ========================
    
    def _handle_contact_confirm(self, session: Session, user_text: str) -> List[Event]:
        """Gère la confirmation du numéro de téléphone."""
        channel = getattr(session, "channel", "web")
        if getattr(session, "pending_slot_choice", None) is not None:
            _assert_pending_slots_invariants(session, "CONTACT_CONFIRM")

        # --- P0: répétition intention RDV ("je veux un rdv") → message guidé oui/non, pas contact_confirm_fails ---
        if _detect_booking_intent(user_text):
            session.contact_confirm_intent_repeat_count += 1
            msg = (
                prompts.MSG_CONTACT_CONFIRM_INTENT_1
                if session.contact_confirm_intent_repeat_count == 1
                else prompts.MSG_CONTACT_CONFIRM_INTENT_2
            )
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]

        intent = detect_intent(user_text, session.state)
        # Filet : affirmation sans négation ("c'est bien ça", "c'est correct", "ok") → YES_IMPLICIT
        if intent != "YES" and (user_text or "").strip():
            _raw = (user_text or "").strip().lower()
            if not _raw.startswith(("non", "pas ")) and "attends" not in _raw and _raw not in ("euh", "euhh", "mmh"):
                _norm = intent_parser.normalize_stt_text(_raw).replace(" ", "")
                if "bienca" in _norm or "cestbienca" in _norm or "cestcorrect" in _norm or " correct" in (" " + intent_parser.normalize_stt_text(_raw)):
                    logger.info("[YES_IMPLICIT] conv_id=%s reason=echo_confirm user_text_len=%s", session.conv_id, len(_raw))
                    intent = "YES"

        if intent == "YES":
            session.contact_confirm_intent_repeat_count = 0
            session.awaiting_confirmation = None
            log_ivr_event(logger, session, "contact_confirmed")
            # Numéro confirmé

            # Si on a déjà un slot choisi (nouveau flow) → booker et confirmer
            if session.pending_slot_choice is not None:
                slot_idx = session.pending_slot_choice
                pending = getattr(session, "pending_slots", None) or []
                pending_len = len(pending)
                # P0: slots vides (session perdue/reconstruite) → re-fetch avant booking
                if not pending and slot_idx and 1 <= slot_idx <= 3:
                    try:
                        fresh_slots = tools_booking.get_slots_for_display(
                            limit=3,
                            pref=getattr(session.qualif_data, "pref", None),
                            session=session,
                        )
                        if fresh_slots:
                            from backend.calendar_adapter import get_calendar_adapter
                            adapter = get_calendar_adapter(session)
                            source = "google" if (adapter and adapter.can_propose_slots()) else "sqlite"
                            session.pending_slots = tools_booking.to_canonical_slots(fresh_slots, source)
                            pending_len = len(session.pending_slots)
                            logger.info(
                                "[BOOKING_PREFETCH] conv_id=%s re-fetched %s slots before booking",
                                session.conv_id,
                                pending_len,
                            )
                    except Exception as e:
                        logger.warning("[BOOKING_PREFETCH] failed: %s", e)
                logger.info(
                    "[BOOKING_ATTEMPT] conv_id=%s slot_idx=%s pending_len=%s",
                    session.conv_id,
                    slot_idx,
                    pending_len,
                )
                # Booker le créneau
                success, reason = tools_booking.book_slot_from_session(session, slot_idx)
                logger.info(
                    "[BOOKING_RESULT] conv_id=%s success=%s reason=%s",
                    session.conv_id,
                    success,
                    reason,
                )
                if not success:
                    # technical / permission → message technique + transfert (pas "créneau pris")
                    if reason in ("technical", "permission"):
                        logger.warning(
                            "[BOOKING_TECHNICAL] conv_id=%s reason=%s pending_len=%s",
                            session.conv_id,
                            reason,
                            len(getattr(session, "pending_slots", None) or []),
                        )
                        session.state = "TRANSFERRED"
                        msg = prompts.MSG_BOOKING_TECHNICAL
                        session.add_message("agent", msg)
                        return [Event("final", msg, conv_state=session.state)]
                    booking_retry = getattr(session, "booking_retry_count", 0) + 1
                    setattr(session, "booking_retry_count", booking_retry)
                    if booking_retry > 2:
                        session.state = "TRANSFERRED"
                        msg = prompts.MSG_SLOT_TAKEN_TRANSFER
                        session.add_message("agent", msg)
                        return [Event("final", msg, conv_state=session.state)]
                    logger.warning(
                        "[BOOKING_RETRY] slot taken, reproposing conv_id=%s retry=%s",
                        session.conv_id,
                        booking_retry,
                    )
                    # Exclure ce créneau (±90 min) des prochaines propositions
                    try:
                        taken_slot = (session.pending_slots or [])[slot_idx - 1] if slot_idx and session.pending_slots else None
                        taken_start = tools_booking._slot_get(taken_slot, "start") if taken_slot else None
                        if taken_slot and taken_start:
                            rejected = getattr(session, "rejected_slot_starts", None) or []
                            if not isinstance(rejected, list):
                                rejected = []
                            session.rejected_slot_starts = rejected + [taken_start]
                    except (IndexError, TypeError):
                        pass
                    session.pending_slots = []
                    session.pending_slot_choice = None
                    session.state = "QUALIF_PREF"
                    msg = prompts.MSG_SLOT_TAKEN_REPROPOSE
                    session.add_message("agent", msg)
                    self._save_session(session)
                    return [Event("final", msg, conv_state=session.state)]
                # P0.4 — Si on vient d'un MODIFY : annuler l'ancien seulement après création du nouveau
                old_slot = getattr(session, "pending_cancel_slot", None)
                if old_slot:
                    tools_booking.cancel_booking(old_slot, session)
                    session.pending_cancel_slot = None
                    slot_label = tools_booking.get_label_for_choice(session, slot_idx) or ""
                    msg = prompts.VOCAL_MODIFY_MOVED.format(new_label=slot_label) if channel == "vocal" else prompts.MSG_MODIFY_MOVED_WEB.format(new_label=slot_label)
                else:
                    slot_label = tools_booking.get_label_for_choice(session, slot_idx) or ""
                    name = session.qualif_data.name or ""
                    motif = session.qualif_data.motif or ""
                    msg = prompts.format_booking_confirmed(slot_label, name=name, motif=motif, channel=channel)
                session.state = "CONFIRMED"
                session.rejected_slot_starts = []
                session.rejected_day_periods = []
                session.slot_sequential_refuse_count = 0
                logger.info(
                    "[RDV_CONFIRMED] conv_id=%s slot_label=%s name=%s",
                    session.conv_id,
                    slot_label,
                    name,
                )
                _persist_ivr_event(session, "booking_confirmed")
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # Sinon (ancien flow) → proposer créneaux
            return self._propose_slots(session)
        
        elif intent == "NO":
            session.contact_confirm_intent_repeat_count = 0
            # Numéro incorrect
            # Vérifier si l'utilisateur donne une correction partielle (ex: "non c'est 8414")
            digits = guards.parse_vocal_phone(user_text)
            
            if len(digits) >= 4 and len(digits) < 10 and session.qualif_data.contact:
                # Correction partielle détectée - essayer de corriger les derniers chiffres
                current_phone = session.qualif_data.contact
                # Remplacer les derniers chiffres
                corrected_phone = current_phone[:10-len(digits)] + digits
                logger.info("[CONTACT] conv_id=%s partial_correction", session.conv_id)
                
                if len(corrected_phone) == 10:
                    session.qualif_data.contact = corrected_phone
                    phone_formatted = prompts.format_phone_for_voice(corrected_phone)
                    msg = f"D'accord, donc c'est bien le {phone_formatted} ?"
                    # Rester en CONTACT_CONFIRM pour re-confirmer
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]
            
            # Sinon, redemander le numéro complet (PHONE_CONFIRM_NO)
            session.state = "QUALIF_CONTACT"
            session.qualif_data.contact = None
            session.qualif_data.contact_type = None
            session.partial_phone_digits = ""  # Reset accumulation
            msg = prompts.VOCAL_PHONE_CONFIRM_NO
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        else:
            # Intent None/UNCLEAR → micro-relance "Dites oui ou non" (1 retry max), puis escalade
            fail_count = getattr(session, "contact_confirm_fails", 0)
            if fail_count == 0:
                session.contact_confirm_fails = 1
                msg = prompts.MSG_CONTACT_CONFIRM_INTENT_1
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            return self._trigger_intent_router(session, "contact_confirm_fails_3", user_text)
    
    # ========================
    # INTENT_ROUTER (spec V3 — menu reset universel)
    # ========================
    
    def _trigger_intent_router(
        self,
        session: Session,
        reason: str = "unknown",
        user_message: str = "",
    ) -> List[Event]:
        """Menu 1/2/3/4 quand perdu ou après 3 échecs (doc: privilégier comprendre). Logging structuré INFO."""
        import logging
        # Slots manquants au moment du menu (pour analytics)
        context = {
            "name": session.qualif_data.name,
            "motif": session.qualif_data.motif,
            "pref": session.qualif_data.pref,
            "contact": session.qualif_data.contact,
        }
        missing = [f for f in ["name", "motif", "pref", "contact"] if not context.get(f)]
        log_data = {
            "session_id": session.conv_id,
            "trigger_reason": reason,
            "previous_state": session.state,
            "missing_slots": missing,
            "turn_count": getattr(session, "turn_count", 0),
            "consecutive_questions": getattr(session, "consecutive_questions", 0),
            "global_recovery_fails": getattr(session, "global_recovery_fails", 0),
            "no_match_turns": session.no_match_turns,
            "user_last_message": (user_message or "")[:200],
            "all_counters": {
                "slot_choice": getattr(session, "slot_choice_fails", 0),
                "name": getattr(session, "name_fails", 0),
                "phone": getattr(session, "phone_fails", 0),
                "preference": getattr(session, "preference_fails", 0),
                "contact_confirm": getattr(session, "contact_confirm_fails", 0),
                "global": getattr(session, "global_recovery_fails", 0),
            },
        }
        logger_ir = logging.getLogger("uwi.intent_router")
        logger_ir.info(
            "intent_router_triggered reason=%s previous_state=%s missing=%s",
            reason,
            session.state,
            missing,
            extra=log_data,
        )
        log_ivr_event(logger, session, "intent_router_trigger", reason=reason)
        channel = getattr(session, "channel", "web")
        # P1.7 — Anti-boucle : >= 2 visites au router → transfert (P0: budget peut prévenir)
        # P0.5bis : passer la raison réelle (out_of_scope_2, no_faq_3, etc.) pour analytics
        session.intent_router_visits = getattr(session, "intent_router_visits", 0) + 1
        if session.intent_router_visits >= 2:
            prev = self._maybe_prevent_transfer(session, channel, reason, user_message)
            if prev is not None:
                return prev
            msg = getattr(prompts, "VOCAL_INTENT_ROUTER_LOOP", prompts.VOCAL_STILL_UNCLEAR) if channel == "vocal" else prompts.MSG_TRANSFER
            return self._trigger_transfer(session, channel, reason, user_text=user_message, custom_msg=msg)
        session.state = "INTENT_ROUTER"
        session.intent_router_unclear_count = 0
        session.last_question_asked = None
        session.reset_questions()
        session.global_recovery_fails = 0
        session.correction_count = 0
        session.empty_message_count = 0
        session.start_unclear_count = 0
        # Fix 1: Ne jamais reset turn_count (compteur total appel). router_epoch_turns pour analytics.
        session.router_epoch_turns = 0
        session.noise_detected_count = 0
        session.last_noise_ts = None
        session.slot_choice_fails = 0
        session.name_fails = 0
        session.phone_fails = 0
        session.preference_fails = 0
        session.contact_confirm_fails = 0
        session.cancel_name_fails = 0
        session.cancel_rdv_not_found_count = 0
        session.modify_name_fails = 0
        session.modify_rdv_not_found_count = 0
        session.faq_fails = 0
        if channel == "vocal" and reason == "name_fails_3":
            msg = prompts.VOCAL_NAME_FAIL_3_INTENT_ROUTER
        else:
            msg = prompts.VOCAL_INTENT_ROUTER if channel == "vocal" else prompts.MSG_INTENT_ROUTER
        session.last_question_asked = msg
        session.add_message("agent", msg)
        return [Event("final", msg, conv_state=session.state)]

    def handle_noise(self, session: Session) -> List[Event]:
        """
        Gestion du bruit STT (nova-2-phonecall : transcript vide/court + faible confidence).
        Cooldown anti-spam, 1er/2e => MSG_NOISE_1/2, 3e => INTENT_ROUTER.
        N'incrémente pas empty_message_count.
        """
        import time
        now = time.time()
        last_ts = getattr(session, "last_noise_ts", None)
        if last_ts is not None and (now - last_ts) < config.NOISE_COOLDOWN_SEC:
            return []  # no-op (cooldown)
        count = getattr(session, "noise_detected_count", 0) + 1
        session.noise_detected_count = count
        session.last_noise_ts = now
        if count == 1:
            msg = getattr(prompts, "MSG_NOISE_1", "Je n'ai pas bien entendu. Pouvez-vous répéter ?")
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        if count == 2:
            msg = getattr(prompts, "MSG_NOISE_2", "Il y a du bruit. Pouvez-vous répéter plus distinctement ?")
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        return safe_reply(
            self._trigger_intent_router(session, "noise_repeated", ""),
            session,
        )

    def _handle_intent_router(self, session: Session, user_text: str) -> List[Event]:
        """Menu 1/2/3/4. Délégation à intent_parser.parse_router_choice (hein/de => None ; cat/catre=>4)."""
        channel = getattr(session, "channel", "web")
        choice = intent_parser.parse_router_choice(user_text or "")
        
        # Ambiguïté (hein, de seul) => retry puis transfert après 2 (P0: budget peut prévenir)
        if choice is None:
            session.intent_router_unclear_count = getattr(session, "intent_router_unclear_count", 0) + 1
            if session.intent_router_unclear_count >= 2:
                prev = self._maybe_prevent_transfer(session, channel, "intent_router_unclear", user_text)
                if prev is not None:
                    return prev
                return self._trigger_transfer(
                    session, channel, "intent_router_unclear", user_text=user_text,
                    custom_msg=prompts.VOCAL_STILL_UNCLEAR if channel == "vocal" else prompts.MSG_TRANSFER,
                )
            msg = getattr(prompts, "MSG_INTENT_ROUTER_RETRY", "Pouvez-vous répéter ?")
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        session.intent_router_unclear_count = 0  # choix valide reçu
        
        if choice == intent_parser.RouterChoice.ROUTER_4:
            session.state = "TRANSFERRED"
            msg = prompts.VOCAL_TRANSFER_COMPLEX if channel == "vocal" else prompts.MSG_TRANSFER
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        if choice == intent_parser.RouterChoice.ROUTER_1:
            session.state = "QUALIF_NAME"
            session.reset_questions()
            msg = prompts.get_qualif_question("name", channel=channel)
            session.last_question_asked = msg
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        if choice == intent_parser.RouterChoice.ROUTER_2:
            return self._start_cancel(session)
        
        if choice == intent_parser.RouterChoice.ROUTER_3:
            session.state = "START"
            msg = getattr(prompts, "MSG_INTENT_ROUTER_FAQ", prompts.MSG_EMPTY_MESSAGE)
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        # Incompréhension (ne devrait pas arriver si parse_router_choice couvre 1-4) — P0: budget peut prévenir
        session.intent_router_unclear_count = getattr(session, "intent_router_unclear_count", 0) + 1
        if session.intent_router_unclear_count >= 2:
            prev = self._maybe_prevent_transfer(session, channel, "intent_router_unclear", user_text)
            if prev is not None:
                return prev
            return self._trigger_transfer(
                session, channel, "intent_router_unclear", user_text=user_text,
                custom_msg=prompts.VOCAL_STILL_UNCLEAR if channel == "vocal" else prompts.MSG_TRANSFER,
            )
        msg = getattr(prompts, "MSG_INTENT_ROUTER_RETRY", "Pouvez-vous répéter ?")
        session.add_message("agent", msg)
        return [Event("final", msg, conv_state=session.state)]
    
    # ========================
    # PREFERENCE_CONFIRM (spec V3 — inférence contextuelle)
    # ========================
    
    def _handle_preference_confirm(self, session: Session, user_text: str) -> List[Event]:
        """Confirmation de la préférence inférée (oui/non ou répétition = confirmation implicite)."""
        channel = getattr(session, "channel", "web")
        intent = detect_intent(user_text, session.state)
        pending = getattr(session, "pending_preference", None)
        
        if intent == "YES" and pending:
            session.qualif_data.pref = pending
            session.pending_preference = None
            session.last_preference_user_text = None
            session.reset_questions()
            return self._next_qualif_step(session)
        if intent == "NO":
            session.pending_preference = None
            session.last_preference_user_text = None
            session.state = "QUALIF_PREF"
            msg = prompts.get_qualif_question("pref", channel=channel)
            session.last_question_asked = msg
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        # Répétition de la même phrase (ex: "je finis à 17h" redit) → confirmation implicite
        last_txt = (getattr(session, "last_preference_user_text", None) or "").strip().lower()
        current_txt = user_text.strip().lower()
        if pending and last_txt and current_txt and last_txt == current_txt:
            session.qualif_data.pref = pending
            session.pending_preference = None
            session.last_preference_user_text = None
            session.awaiting_confirmation = None
            session.reset_questions()
            return self._next_qualif_step(session)
        # Ré-inférence : user répète une phrase qui mène à la MÊME préférence → confirmation implicite
        inferred = infer_preference_from_context(user_text)
        if inferred and pending and inferred == pending:
            session.qualif_data.pref = pending
            session.pending_preference = None
            session.last_preference_user_text = None
            session.awaiting_confirmation = None
            session.reset_questions()
            return self._next_qualif_step(session)
        # Ré-inférence vers une AUTRE préférence → mettre à jour et re-demander confirmation
        if inferred and inferred != pending:
            session.pending_preference = inferred
            session.last_preference_user_text = user_text.strip()
            msg = prompts.format_inference_confirmation(inferred)
            session.last_question_asked = msg
            session.add_message("agent", msg)
            session.awaiting_confirmation = "CONFIRM_PREFERENCE"
            return [Event("final", msg, conv_state=session.state)]
        # Vraie incompréhension (pas d'inférence) → recovery progressive
        fail_count = increment_recovery_counter(session, "preference")
        if should_escalate_recovery(session, "preference"):
            return self._trigger_intent_router(session, "preference_fails_3", user_text)
        msg = prompts.format_inference_confirmation(pending) if pending else prompts.MSG_PREFERENCE_CONFIRM.format(pref="ce créneau")
        session.add_message("agent", msg)
        session.awaiting_confirmation = "CONFIRM_PREFERENCE"
        return [Event("final", msg, conv_state=session.state)]
    
    # ========================
    # FLOW E: CLARIFY
    # ========================
    
    def _handle_clarify(self, session: Session, user_text: str, intent: str) -> List[Event]:
        """Gère la clarification après un 'non' au first message."""
        channel = getattr(session, "channel", "web")
        
        # Si l'utilisateur dit vouloir un RDV
        if intent == "YES" or intent == "BOOKING" or "rendez-vous" in user_text.lower() or "rdv" in user_text.lower():
            session.state = "QUALIF_NAME"
            msg = prompts.VOCAL_FAQ_TO_BOOKING if channel == "vocal" else prompts.MSG_FAQ_TO_BOOKING_WEB
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        # Si l'utilisateur dit avoir une question OU si c'est une question FAQ
        if "question" in user_text.lower() or intent == "FAQ":
            session.state = "START"
            return self._handle_faq(session, user_text, include_low=True)
        
        # Sinon essayer FAQ directement (ex. "je voudrais l'adresse", "horaires", "c'est où ?")
        try:
            faq_result = self.faq_store.search(user_text, include_low=True)
            if faq_result.match:
                session.state = "POST_FAQ"
                response = prompts.format_faq_response(faq_result.answer, faq_result.faq_id, channel=channel)
                if channel == "vocal":
                    response = response + " " + prompts.VOCAL_FAQ_FOLLOWUP
                else:
                    response = response + "\n\n" + getattr(prompts, "MSG_FAQ_FOLLOWUP_WEB", "Souhaitez-vous autre chose ?")
                session.add_message("agent", response)
                self._save_session(session)
                return [Event("final", response, conv_state=session.state)]
        except Exception as e:
            logger.warning("FAQ search in CLARIFY: %s", e)
        
        # Intent CANCEL
        if intent == "CANCEL":
            return self._start_cancel(session)
        
        # Intent MODIFY
        if intent == "MODIFY":
            return self._start_modify(session)
        
        # Fix #6: Intent TRANSFER → politique courte (clarify) vs explicite (transfert)
        if intent == "TRANSFER":
            from backend.transfer_policy import classify_transfer_request
            kind = classify_transfer_request(user_text)
            if kind == "EXPLICIT":
                return self._trigger_transfer(session, channel, "explicit_transfer_request", user_text=user_text, custom_msg=prompts.VOCAL_TRANSFER_COMPLEX if channel == "vocal" else prompts.MSG_TRANSFER)
        
        # Toujours pas clair → transfert après 3 relances (doc: privilégier comprendre)
        session.confirm_retry_count = getattr(session, "confirm_retry_count", 0) + 1
        if session.confirm_retry_count >= 3:
            session.state = "TRANSFERRED"
            msg = prompts.VOCAL_STILL_UNCLEAR if channel == "vocal" else prompts.MSG_TRANSFER
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        # Encore une chance
        msg = prompts.VOCAL_CLARIFY if channel == "vocal" else prompts.MSG_CLARIFY_WEB
        session.add_message("agent", msg)
        return [Event("final", msg, conv_state=session.state)]
    
    # ========================
    # FALLBACK
    # ========================
    
    def _fallback_transfer(self, session: Session) -> List[Event]:
        """Fallback vers transfert humain."""
        channel = getattr(session, "channel", "web")
        session.state = "TRANSFERRED"
        msg = self._say(session, "transfer")
        if not msg:
            msg = prompts.get_message("transfer", channel=channel)
            session.add_message("agent", msg)
            session.last_say_key, session.last_say_kwargs = "transfer", {}
        return [Event("final", msg, conv_state=session.state)]


# ========================
# FACTORY
# ========================

def create_engine(llm_client: Optional[LLMClient] = None) -> Engine:
    """Factory pour créer l'engine avec ses dépendances. llm_client optionnel (LLM Assist zone grise)."""
    from backend.tools_faq import default_faq_store
    
    session_store = SQLiteSessionStore()
    faq_store = default_faq_store()
    
    return Engine(session_store=session_store, faq_store=faq_store, llm_client=llm_client)


# Engine singleton (exporté pour vapi.py). Branché à un LLM si ANTHROPIC_API_KEY + LLM_ASSIST_ENABLED.
ENGINE = create_engine(llm_client=get_default_llm_client())
