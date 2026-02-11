# backend/engine.py
"""
Pipeline déterministe : edge-cases → session → FAQ → booking/qualif → transfer
Aucune créativité, aucune improvisation.
"""

from __future__ import annotations
from typing import List, Optional
from dataclasses import dataclass
import logging
import re

from backend import config, prompts, guards, tools_booking, intent_parser
from backend.guards_medical import is_medical_emergency  # legacy / tests
from backend.guards_medical_triage import (
    detect_medical_red_flag,
    classify_medical_symptoms,
    extract_symptom_motif_short,
)
from backend.log_events import MEDICAL_RED_FLAG_TRIGGERED
from backend import db as backend_db
from backend.session import Session, SessionStore
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

logger = logging.getLogger(__name__)

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


def _persist_ivr_event(
    session: Session,
    event: str,
    context: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    """
    Persiste un event dans ivr_events (rapport quotidien).
    Skip si client_id manquant (évite polluer client #1).
    Skip si call_id manquant pour booking_confirmed (qualité booking).
    """
    try:
        client_id = getattr(session, "client_id", None)
        if client_id is None:
            logger.debug("persist_ivr_event skip: reason=missing_client_id event=%s", event)
            return
        call_id = session.conv_id or ""
        if event == "booking_confirmed" and not call_id.strip():
            logger.debug("persist_ivr_event skip: reason=missing_call_id event=booking_confirmed")
            return
        backend_db.create_ivr_event(
            client_id=int(client_id),
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
    
    # Keywords avec variantes
    keywords = [
        "rdv",
        "rendez vous",  # Après normalisation, "rendez-vous" devient "rendez vous"
        "rendezvous",
        "dispo",
        "disponibilité",
        "créneau",
        "réserver",
        "réservation",
        "prendre",
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
    Persiste transfer_human une seule fois par call (idempotence).
    """
    setattr(session, "_turn_assistant_text", (events[0].text if events and getattr(events[0], "text", None) else "") or "")
    _log_turn_debug(session)
    if getattr(session, "state", None) == "TRANSFERRED" and not getattr(session, "transfer_logged", False):
        _persist_ivr_event(session, "transfer_human")
        session.transfer_logged = True
    if not events:
        log_ivr_event(logger, session, "safe_reply")
        msg = SAFE_REPLY_FALLBACK
        session.add_message("agent", msg)
        return [Event("final", msg, conv_state=session.state)]
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
        return {"state": "CONFIRMED", "message": "Parfait, je n'annule pas. Bonne journée !"}

    if st == "MODIFY_CONFIRM":
        return {"state": "CONFIRMED", "message": "Parfait, je ne le modifie pas. Bonne journée !"}

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
        print(f"⏱️ Session loaded in {(t_load_end - t_load_start) * 1000:.0f}ms")
        setattr(session, "_turn_state_before", session.state)
        session.add_message("user", user_text)
        
        turn_count = getattr(session, "turn_count", 0)
        print(f"🔍 handle_message: conv_id={conv_id}, state={session.state}, name={session.qualif_data.name}, pending_slots={len(session.pending_slots or [])}, user='{user_text[:50]}'")
        logger.info(
            "[FLOW] conv_id=%s state=%s turn_count=%s user=%s",
            conv_id,
            session.state,
            turn_count,
            (user_text or "")[:50],
        )
        
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
        # 1. ANTI-LOOP GUARD (spec V3 — ordre pipeline NON NÉGOCIABLE)
        # ========================
        session.turn_count = getattr(session, "turn_count", 0) + 1
        max_turns = getattr(Session, "MAX_TURNS_ANTI_LOOP", 25)
        if session.turn_count > max_turns:
            logger.info(
                "[ANTI_LOOP] conv_id=%s turn_count=%s max=%s",
                conv_id,
                session.turn_count,
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
                session.state = "TRANSFERRED"
                msg = self._say(session, "transfer_complex")
                if not msg:
                    msg = prompts.VOCAL_TRANSFER_COMPLEX if channel == "vocal" else prompts.MSG_TRANSFER
                    session.add_message("agent", msg)
                    session.last_say_key, session.last_say_kwargs = "transfer_complex", {}
                self._save_session(session)
                return safe_reply([Event("final", msg, conv_state=session.state)], session)
            if strong == "ABANDON":
                session.state = "CONFIRMED"
                msg = prompts.MSG_END_POLITE_ABANDON if hasattr(prompts, "MSG_END_POLITE_ABANDON") else (prompts.VOCAL_USER_ABANDON if channel == "vocal" else prompts.MSG_ABANDON_WEB)
                session.add_message("agent", msg)
                _persist_ivr_event(session, "abandon")
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
        print(f"🎯 Intent detected: '{intent}' from '{user_text}'")
        print(f"📞 State: {session.state} | Intent: {intent} | User: '{user_text[:50]}...'")
        
        # REPEAT : relire le dernier prompt exact (pas re-router, pas d'escalade, état inchangé)
        if intent == "REPEAT":
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
        
        # --- FLOWS EN COURS ---
        
        # P1.6 — Strong intents (CANCEL/MODIFY/TRANSFER/ABANDON/FAQ) préemptent même en plein booking
        if session.state in ("QUALIF_NAME", "QUALIF_MOTIF", "QUALIF_PREF", "QUALIF_CONTACT", "WAIT_CONFIRM"):
            strong = detect_strong_intent(user_text or "")
            if strong == "CANCEL":
                return safe_reply(self._start_cancel(session), session)
            if strong == "MODIFY":
                return safe_reply(self._start_modify(session), session)
            if strong == "TRANSFER":  # "humain" seul = OK (mapping STT)
                session.state = "TRANSFERRED"
                msg = self._say(session, "transfer_complex")
                if not msg:
                    msg = prompts.VOCAL_TRANSFER_COMPLEX if channel == "vocal" else prompts.MSG_TRANSFER
                    session.add_message("agent", msg)
                    session.last_say_key, session.last_say_kwargs = "transfer_complex", {}
                return safe_reply([Event("final", msg, conv_state=session.state)], session)
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
            
            # TRANSFER → Transfert direct (doc: phrase explicite >=14 car., pas interruption courte)
            if intent == "TRANSFER":
                if len(user_text.strip()) >= 14:
                    session.start_unclear_count = 0
                    session.state = "TRANSFERRED"
                    msg = prompts.VOCAL_TRANSFER_COMPLEX if channel == "vocal" else prompts.MSG_TRANSFER
                    session.add_message("agent", msg)
                    return safe_reply([Event("final", msg, conv_state=session.state)], session)
                # Message court type "humain" → traiter comme unclear, pas transfert
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
                # 3e et plus : transfert direct avec message UX dédié (pas "abandon")
                session.start_unclear_count = 0
                session.state = "TRANSFERRED"
                msg = self._say(session, "transfer_filler_silence")
                if not msg:
                    msg = prompts.get_message("transfer_filler_silence", channel=channel) or prompts.MSG_TRANSFER_FILLER_SILENCE
                    session.add_message("agent", msg)
                    session.last_say_key, session.last_say_kwargs = "transfer_filler_silence", {}
                self._save_session(session)
                return safe_reply([Event("final", msg, conv_state=session.state)], session)

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
        
        # Si état inconnu ou non géré → transfer par sécurité
        session.state = "TRANSFERRED"
        msg = self._say(session, "transfer")
        if not msg:
            msg = prompts.get_message("transfer", channel=getattr(session, "channel", "web"))
            session.add_message("agent", msg)
            session.last_say_key, session.last_say_kwargs = "transfer", {}
        return safe_reply([Event("final", msg, conv_state=session.state)], session)
    
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
            session.state = "TRANSFERRED"
            msg = self._say(session, "transfer_complex")
            if not msg:
                msg = prompts.VOCAL_TRANSFER_COMPLEX if channel == "vocal" else prompts.MSG_TRANSFER
                session.add_message("agent", msg)
                session.last_say_key, session.last_say_kwargs = "transfer_complex", {}
            self._save_session(session)
            return [Event("final", msg, conv_state=session.state)]
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
        print(f"🔍 _next_qualif_step: context={context}")
        
        # Skip contact pour le moment - sera demandé après le choix de créneau
        next_field = get_next_missing_field(context, skip_contact=True)
        print(f"🔍 _next_qualif_step: next_field={next_field}")
        
        if not next_field:
            # name + pref remplis → proposer créneaux (contact viendra après)
            print(f"🔍 _next_qualif_step: name+pref FILLED → propose_slots")
            session.consecutive_questions = 0
            return self._propose_slots(session)
        
        # Spec V3 : max 3 questions consécutives → action concrète (proposer créneaux si name+pref)
        max_q = getattr(Session, "MAX_CONSECUTIVE_QUESTIONS", 3)
        if session.consecutive_questions >= max_q and context.get("name") and context.get("pref"):
            print(f"🔍 _next_qualif_step: consecutive_questions={session.consecutive_questions} → propose_slots (fatigue cognitive)")
            session.consecutive_questions = 0
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
                    print(f"📱 Using caller ID directly: {phone[:10]}")
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]
            except Exception as e:
                print(f"⚠️ Error using caller ID: {e}")
                # Continue avec le flow normal (demander le numéro)
        
        # Mapper le champ vers l'état
        state_map = {
            "name": "QUALIF_NAME",
            "motif": "QUALIF_MOTIF",
            "pref": "QUALIF_PREF",
            "contact": "QUALIF_CONTACT",
        }
        session.state = state_map[next_field]
        session.consecutive_questions = getattr(session, "consecutive_questions", 0) + 1
        
        # Question adaptée au canal AVEC prénom si disponible
        client_name = session.qualif_data.name or ""
        print(f"🔍 _next_qualif_step: client_name='{client_name}', channel={channel}, consecutive_questions={session.consecutive_questions}")
        
        if client_name and channel == "vocal":
            question = prompts.get_qualif_question_with_name(
                next_field, client_name, channel=channel, ack_index=session.next_ack_index()
            )
        else:
            question = prompts.get_qualif_question(next_field, channel=channel)
        # Vocal : pas de wrap_with_signal ici (évite 2e "Parfait" en start après le nom)
        # Les questions sont déjà formulées sans ack redondant (get_qualif_question_with_name).
        
        session.last_question_asked = question
        print(f"🔍 _next_qualif_step: asking for {next_field} → '{question}'")
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
            print(f"🔍 QUALIF_NAME: raw='{user_text}' → extracted='{extracted_name}', reject_reason={reject_reason}")
            
            if extracted_name is not None:
                # Réponse valide → stocker et continuer (spec V3 : reset compteurs)
                session.qualif_data.name = extracted_name.title()
                session.consecutive_questions = 0
                session.qualif_name_intent_repeat_count = 0
                print(f"✅ QUALIF_NAME: stored name='{session.qualif_data.name}'")
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
            
            # Validation PRD
            if not guards.validate_qualif_motif(user_text):
                session.state = "TRANSFERRED"
                msg = self._say(session, "transfer")
                if not msg:
                    msg = prompts.get_message("transfer", channel=channel)
                    session.add_message("agent", msg)
                    session.last_say_key, session.last_say_kwargs = "transfer", {}
                return [Event("final", msg, conv_state=session.state)]
            
            # Motif valide et utile (spec V3 : reset compteur)
            session.qualif_data.motif = user_text.strip()
            session.consecutive_questions = 0
            return self._next_qualif_step(session)
        
        # ========================
        # QUALIF_PREF (spec V3 : extraction + inférence contextuelle)
        # ========================
        elif current_step == "QUALIF_PREF":
            channel = getattr(session, "channel", "web")
            print(f"🔍 QUALIF_PREF handler: user_text='{user_text}'")

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
                        router_events = self._trigger_intent_router(session, "time_constraint_impossible", user_text)
                        return safe_reply([Event("final", msg, conv_state=session.state)] + router_events, session)

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
            
            print(f"📞 QUALIF_CONTACT: received '{contact_raw}'")
            
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

            # ✅ Parsing email dicté (vocal)
            if channel == "vocal" and guards.looks_like_dictated_email(contact_raw):
                contact_raw = guards.parse_vocal_email_min(contact_raw)
                # Pour email, pas d'accumulation
                is_valid, contact_type = guards.validate_qualif_contact(contact_raw)
                if is_valid:
                    session.qualif_data.contact = contact_raw
                    session.qualif_data.contact_type = contact_type
                    # Si un créneau est déjà choisi → CONTACT_CONFIRM, sinon proposer slots
                    if session.pending_slot_choice is not None:
                        session.state = "CONTACT_CONFIRM"
                        msg = prompts.VOCAL_EMAIL_CONFIRM.format(email=contact_raw) if getattr(prompts, "VOCAL_EMAIL_CONFIRM", None) else f"Votre email est bien {contact_raw} ?"
                        session.add_message("agent", msg)
                        return [Event("final", msg, conv_state=session.state)]
                    return self._propose_slots(session)

            # ✅ ACCUMULATION des chiffres du téléphone (vocal) - seulement si pas de numéro auto
            if channel == "vocal" and not session.customer_phone:
                new_digits = guards.parse_vocal_phone(contact_raw)
                print(f"📞 New digits from '{contact_raw}': '{new_digits}' ({len(new_digits)} digits)")
                
                # Ajouter aux chiffres déjà accumulés
                session.partial_phone_digits += new_digits
                total_digits = session.partial_phone_digits
                print(f"📞 Total accumulated: '{total_digits}' ({len(total_digits)} digits)")
                
                # Si on a 10 chiffres ou plus → validation plausible puis confirmation
                if len(total_digits) >= 10:
                    digits_10 = total_digits[:10]
                    ok_phone, phone10, reason = guards.is_plausible_phone_input(digits_10)
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
                    contact_raw = phone10
                    session.partial_phone_digits = ""  # Reset
                    print(f"📞 Got 10 digits! Phone: {contact_raw}")
                    session.qualif_data.contact = contact_raw
                    session.qualif_data.contact_type = "phone"
                    session.contact_retry_count = 0
                    session.state = "CONTACT_CONFIRM"
                    phone_spaced = prompts.format_phone_for_voice(contact_raw)
                    msg = prompts.VOCAL_PHONE_CONFIRM.format(phone_spaced=phone_spaced)
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]
                
                else:
                    # Pas encore 10 chiffres → demander la suite
                    session.contact_retry_count += 1
                    
                    if session.contact_retry_count >= 6:
                        # Trop de tentatives → transfert
                        session.state = "TRANSFERRED"
                        session.partial_phone_digits = ""
                        msg = self._say(session, "transfer")
                        if not msg:
                            msg = prompts.get_message("transfer", channel=channel)
                            session.add_message("agent", msg)
                            session.last_say_key, session.last_say_kwargs = "transfer", {}
                        return [Event("final", msg, conv_state=session.state)]
                    
                    # Messages ultra-courts pour pas ralentir
                    if len(total_digits) == 0:
                        msg = "J'écoute."
                    elif len(total_digits) < 10:
                        msg = "Oui, continuez."
                    
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
            print(f"📞 Validation result: is_valid={is_valid}, type={contact_type}")
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
        """
        import time
        t_start = time.time()
        
        channel = getattr(session, "channel", "web")
        print(f"🔍 _propose_slots: fetching slots...")
        
        try:
            # Récupérer slots en cohérence avec la préférence (ne pas proposer 10h si "je finis à 17h")
            pref = getattr(session.qualif_data, "pref", None) or None
            slots = tools_booking.get_slots_for_display(
                limit=config.MAX_SLOTS_PROPOSED, pref=pref, session=session
            )
            print(f"🔍 _propose_slots: got {len(slots) if slots else 0} slots (pref={pref}) in {(time.time() - t_start) * 1000:.0f}ms")
        except Exception as e:
            print(f"❌ _propose_slots ERROR: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: transfert
            session.state = "TRANSFERRED"
            msg = self._say(session, "transfer")
            if not msg:
                msg = prompts.get_message("transfer", channel=channel)
                session.add_message("agent", msg)
                session.last_say_key, session.last_say_kwargs = "transfer", {}
            return [Event("final", msg, conv_state=session.state)]
        
        if not slots:
            print(f"⚠️ _propose_slots: NO SLOTS AVAILABLE")
            session.state = "TRANSFERRED"
            msg = prompts.get_message("no_slots", channel=channel)
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]

        # P0: source de vérité = slots affichés (évite re-fetch et mismatch index/slot)
        try:
            source = "google" if tools_booking._get_calendar_service() else "sqlite"
            session.pending_slots_display = tools_booking.serialize_slots_for_session(slots, source)
        except Exception:
            session.pending_slots_display = []

        # Stocker slots
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
            label0 = getattr(slot0, "label", None) or getattr(slot0, "label_vocal", None) or str(slot0)
            msg = prompts.VOCAL_SLOT_ONE_PROPOSE.format(label=label0)
            session.is_reading_slots = False
        else:
            msg = prompts.format_slot_proposal(slots, include_instruction=True, channel=channel)
            session.is_reading_slots = True
        if channel == "vocal" and msg:
            msg = prompts.TransitionSignals.wrap_with_signal(msg, "PROCESSING")
        logger.info(
            "[SLOTS_SENT] conv_id=%s channel=%s len=%s preview=%s",
            session.conv_id,
            channel,
            len(msg or ""),
            (msg or "")[:200],
        )
        print(f"✅ _propose_slots: proposing {'1 (sequential)' if channel == 'vocal' else len(slots)} slots")
        session.add_message("agent", msg)
        if channel == "vocal" and slots:
            label0 = getattr(slots[0], "label", None) or getattr(slots[0], "label_vocal", None) or str(slots[0])
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
        
        print(f"🔍 _handle_booking_confirm: user_text='{user_text}', pending_slots={len(session.pending_slots or [])}, state={session.state}")
        
        # 🔄 Si pas de slots en mémoire (session perdue) → re-proposer
        if not session.pending_slots or len(session.pending_slots) == 0:
            print(f"⚠️ WAIT_CONFIRM but no pending_slots → re-proposing")
            return self._propose_slots(session)

        # P0.2 — Vocal séquentiel : 1 créneau à la fois. OUI = ce créneau, NON = suivant ou transfert. "répéter" = relire.
        if channel == "vocal" and getattr(session, "slot_proposal_sequential", False) and session.pending_slots:
            idx = getattr(session, "slot_offer_index", 0)
            if idx < len(session.pending_slots):
                slot_obj = session.pending_slots[idx]
                label_cur = getattr(slot_obj, "label", None) or getattr(slot_obj, "label_vocal", None) or str(slot_obj)
                _t = (user_text or "").strip().lower()
                _t_norm = "".join(c for c in _t if c.isalnum() or c in " '\"-")
                _t_norm = _t_norm.replace("'", "").replace("'", "").strip()
                # "répéter" / "redire" / filler (euh, hein) → relire le créneau courant (Test 5.1)
                if any(x in _t_norm for x in ("repeter", "répéter", "repetes", "redire", "reprendre", "reécoute")):
                    msg = prompts.VOCAL_SLOT_ONE_PROPOSE.format(label=label_cur)
                    session.add_message("agent", msg)
                    session.last_say_key, session.last_say_kwargs = "slot_one_propose", {"label": label_cur}
                    return [Event("final", msg, conv_state=session.state)]
                if _t_norm in ("euh", "hein", "hum", "euhh") or _t_norm in getattr(guards, "FILLER_GLOBAL", frozenset()):
                    msg = prompts.VOCAL_SLOT_ONE_PROPOSE.format(label=label_cur)
                    session.add_message("agent", msg)
                    session.last_say_key, session.last_say_kwargs = "slot_one_propose", {"label": label_cur}
                    return [Event("final", msg, conv_state=session.state)]
                # "le deuxième" / "le second" selon contexte (Test 5.2) : idx 0 → suivant (NO), idx 1 → ce créneau (YES)
                if any(x in _t_norm for x in ("le deuxième", "le second", "deuxième", "second")) and len(_t_norm) <= 15:
                    if idx == 0:
                        session.slot_offer_index = 1
                        if session.slot_offer_index >= len(session.pending_slots):
                            session.state = "TRANSFERRED"
                            msg = prompts.VOCAL_NO_SLOTS
                            session.add_message("agent", msg)
                            self._save_session(session)
                            return [Event("final", msg, conv_state=session.state)]
                        next_slot = session.pending_slots[session.slot_offer_index]
                        next_label = getattr(next_slot, "label", None) or getattr(next_slot, "label_vocal", None) or str(next_slot)
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
                        self._save_session(session)
                        return [Event("final", msg, conv_state=session.state)]
                # Test 5.3 — "oui de…" ambigu (oui deux ?) → clarification, ne pas planter
                if _t_norm.startswith("oui de") or _t_norm == "oui de" or (_t_norm.startswith("oui") and " de " in _t_norm and len(_t_norm) < 20):
                    msg = getattr(prompts, "VOCAL_SLOT_SEQUENTIAL_NEED_YES_NO", "Dites oui si ça vous convient, ou non pour un autre créneau.")
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]
                # OUI → accepter ce créneau (1-based choice = idx+1)
                _yes_set = guards.YES_WORDS | {"ouaip", "okay", "parfait", "daccord"}
                if _t_norm in _yes_set or (_t_norm.startswith("oui") and len(_t_norm) <= 12 and " de " not in _t_norm):
                    session.slot_sequential_refuse_count = 0
                    session.pending_slot_choice = idx + 1
                    session.slot_proposal_sequential = False
                    try:
                        slot_label = tools_booking.get_label_for_choice(session, idx + 1) or label_cur
                    except Exception:
                        slot_label = label_cur
                    msg = prompts.format_slot_early_confirm(idx + 1, slot_label, channel=channel)
                    session.add_message("agent", msg)
                    self._save_session(session)
                    return [Event("final", msg, conv_state=session.state)]
                # NON → créneau suivant ou plus de dispo (exclure ce créneau des futures re-propositions ±90 min)
                _no_set = guards.NO_WORDS | {"pas celui la", "pas celui-la", "pas ca", "pas ça", "autre", "suivant", "non merci"}
                if _t_norm in _no_set or _t_norm.startswith("non"):
                    cur_slot = session.pending_slots[idx] if idx < len(session.pending_slots or []) else None
                    if cur_slot and getattr(cur_slot, "start", None):
                        rejected = getattr(session, "rejected_slot_starts", None) or []
                        if not isinstance(rejected, list):
                            rejected = []
                        session.rejected_slot_starts = rejected + [cur_slot.start]
                        # Mémoire (day, period) refusé : anti-spam matin/après-midi
                        day = getattr(cur_slot, "day", "") or ""
                        period = tools_booking.slot_period(cur_slot)
                        if day and period:
                            rdp = getattr(session, "rejected_day_periods", None) or []
                            key = f"{day}|{period}"
                            if key not in rdp:
                                session.rejected_day_periods = rdp + [key]
                    session.slot_sequential_refuse_count = getattr(session, "slot_sequential_refuse_count", 0) + 1
                    # Après 2 "non" consécutifs → demander préférence ouverte (matin / aprem / autre jour)
                    if session.slot_sequential_refuse_count >= 2:
                        session.slot_sequential_refuse_count = 0
                        session.slot_proposal_sequential = False
                        session.state = "QUALIF_PREF"
                        session.pending_slots = []
                        session.pending_slots_display = []
                        session.slot_offer_index = 0
                        # Reset refus pour le prochain pool (évite "il ne me propose plus rien" après préférence)
                        session.rejected_slot_starts = []
                        session.rejected_day_periods = []
                        msg = getattr(prompts, "VOCAL_SLOT_REFUSE_PREF_PROMPT", "Vous préférez plutôt le matin, l'après-midi, ou un autre jour ?")
                        session.add_message("agent", msg)
                        _persist_ivr_event(session, "slot_refuse_pref_asked")  # Métrique : % refus x2 → QUALIF_PREF
                        self._save_session(session)
                        return [Event("final", msg, conv_state=session.state)]
                    # Skip neighbor slots + (day, period) refusés dans la liste courante (évite 9h → 9h15)
                    next_idx = idx + 1
                    seq_skip = 0
                    rejected_dp = set(getattr(session, "rejected_day_periods", None) or [])
                    while next_idx < len(session.pending_slots or []):
                        cand = session.pending_slots[next_idx]
                        cand_start = getattr(cand, "start", None)
                        cand_day = getattr(cand, "day", "") or ""
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

        # P1.2 Vocal : préface déjà envoyée, liste pas encore → envoyer liste puis traiter le message user
        if channel == "vocal" and getattr(session, "slots_preface_sent", False) and not getattr(session, "slots_list_sent", False):
            session.slots_list_sent = True
            session.is_reading_slots = True
            list_msg = prompts.format_slot_list_vocal_only(session.pending_slots)
            session.add_message("agent", list_msg)
            self._save_session(session)
            early_idx = detect_slot_choice_early(user_text, session.pending_slots)
            if early_idx is not None:
                logger.info(
                    "[INTERRUPTION] conv_id=%s client chose slot %s during enumeration (preface just sent), slots_count=%s",
                    session.conv_id,
                    early_idx,
                    len(session.pending_slots or []),
                )
                session.is_reading_slots = False
                session.pending_slot_choice = early_idx
                try:
                    slot_label = tools_booking.get_label_for_choice(session, early_idx) or "votre créneau"
                except Exception:
                    slot_label = "votre créneau"
                confirm_msg = prompts.format_slot_early_confirm(early_idx, slot_label, channel=channel)
                session.add_message("agent", confirm_msg)
                # Un seul event : le webhook vocal n'utilise que events[0].text → envoyer la confirmation, pas la liste
                return [Event("final", confirm_msg, conv_state=session.state)]
            help_msg = getattr(prompts, "MSG_SLOT_BARGE_IN_HELP", "D'accord. Dites juste 1, 2 ou 3.")
            session.add_message("agent", help_msg)
            return [Event("final", list_msg, conv_state=session.state), Event("final", help_msg, conv_state=session.state)]

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
                session.is_reading_slots = False
                session.pending_slot_choice = early_idx
                self._save_session(session)
                try:
                    slot_label = tools_booking.get_label_for_choice(session, early_idx) or "votre créneau"
                except Exception:
                    slot_label = "votre créneau"
                msg = prompts.format_slot_early_confirm(early_idx, slot_label, channel=channel)
                session.add_message("agent", msg)
                print(f"✅ barge-in: choix clair {early_idx} → early confirm")
                return [Event("final", msg, conv_state=session.state)]
            # Pas un choix clair → une phrase courte, ne pas incrémenter les fails
            session.is_reading_slots = False
            msg = getattr(prompts, "MSG_SLOT_BARGE_IN_HELP", "D'accord. Dites juste 1, 2 ou 3.")
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        slot_idx: Optional[int] = None

        # Confirmation du créneau déjà choisi (après "c'est bien ça ?") : "oui" ou "oui c'est bien ça" → on passe au contact
        if session.pending_slot_choice is not None:
            _t = (user_text or "").strip().lower()
            _t_norm = "".join(c for c in _t if c.isalnum() or c in " '\"-")
            _t_norm = _t_norm.replace("'", "").replace("'", "").strip()
            _confirm_words = guards.YES_WORDS | {"ouaip", "okay", "parfait", "daccord"}
            if _t_norm in _confirm_words:
                slot_idx = session.pending_slot_choice
                print(f"✅ slot_choice: confirmation du créneau {slot_idx} → passage au contact")
            else:
                # Accepter les phrases du type "oui c'est bien ça", "c'est bien ça", "oui cest bien ca"
                _norm_compact = _t_norm.replace(" ", "")
                if "bienca" in _norm_compact or "bien ca" in _t_norm or "cestbienca" in _norm_compact:
                    slot_idx = session.pending_slot_choice
                    print(f"✅ slot_choice: confirmation phrase du créneau {slot_idx} → passage au contact")
                elif _t_norm.startswith("oui") and len(_t_norm) <= 25 and ("bien" in _t_norm or "ca" in _t_norm or "ça" in _t):
                    slot_idx = session.pending_slot_choice
                    print(f"✅ slot_choice: confirmation oui+ du créneau {slot_idx} → passage au contact")

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

        print(f"📋 Pending slots: {[(s.idx, s.label) for s in session.pending_slots]}")
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
                session.is_reading_slots = False
                session.pending_slot_choice = early_idx
                self._save_session(session)
                try:
                    slot_label = tools_booking.get_label_for_choice(session, early_idx) or "votre créneau"
                except Exception:
                    slot_label = "votre créneau"
                msg = prompts.format_slot_early_confirm(early_idx, slot_label, channel=channel)
                session.add_message("agent", msg)
                print(f"✅ early commit: choix {early_idx} → « C'est bien ça ? »")
                return [Event("final", msg, conv_state=session.state)]

        if slot_idx is None:
            # IVR pro : choix flexible par numéro / jour / heure (ambiguïté → recovery). Pas "oui" seul.
            proposed_slots = [
                {
                    "start": getattr(s, "start", ""),
                    "label_vocal": getattr(s, "label_vocal", None) or s.label,
                    "day": getattr(s, "day", ""),
                    "hour": getattr(s, "hour", 0),
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
        print(f"🔍 slot_choice: '{user_text}' → slot_idx={slot_idx}")
        
        if slot_idx is not None:
            print(f"✅ Slot choice validated: slot_idx={slot_idx}")
            
            # Stocker le choix de créneau
            try:
                slot_label = tools_booking.get_label_for_choice(session, slot_idx) or "votre créneau"
                print(f"📅 Slot label: '{slot_label}'")
            except Exception as e:
                print(f"⚠️ Error getting slot label: {e}")
                import traceback
                traceback.print_exc()
                slot_label = "votre créneau"
            
            name = session.qualif_data.name or ""
            
            # Stocker temporairement le slot choisi (on bookera après confirmation du contact)
            session.pending_slot_choice = slot_idx
            print(f"📌 Stored pending_slot_choice={slot_idx}")
            
            # 💾 Sauvegarder le choix immédiatement
            self._save_session(session)
            
            session.is_reading_slots = False
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
                        print(f"📱 Using caller ID for confirmation: {phone[:10]}")
                        session.add_message("agent", msg)
                        return [Event("final", msg, conv_state=session.state)]
                except Exception as e:
                    print(f"⚠️ Error using caller ID in booking confirm: {e}")
                    import traceback
                    traceback.print_exc()
                    # Continue avec le flow normal
            
            # Sinon demander le contact normalement
            print(f"📞 No caller ID, asking for contact normally")
            session.state = "QUALIF_CONTACT"
            self._save_session(session)
            print(f"👤 name='{name}'")
            
            msg = prompts.get_qualif_question("contact", channel=channel)
            
            print(f"✅ Final message: '{msg}'")
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]

        # ❌ Invalide → retry (compteur par contexte pour analytics)
        fail_count = increment_recovery_counter(session, "slot_choice")
        log_ivr_event(logger, session, "recovery_step", context="slot_choice", reason="no_match")
        if should_escalate_recovery(session, "slot_choice"):
            session.is_reading_slots = False
            return self._trigger_intent_router(session, "slot_choice_fails_3", user_text)
        if fail_count >= config.CONFIRM_RETRY_MAX:
            session.is_reading_slots = False
            session.state = "TRANSFERRED"
            msg = self._say(session, "transfer")
            if not msg:
                msg = prompts.get_message("transfer", channel=channel)
                session.add_message("agent", msg)
                session.last_say_key, session.last_say_kwargs = "transfer", {}
            return [Event("final", msg, conv_state=session.state)]
        msg = prompts.get_clarification_message(
            "slot_choice",
            fail_count,
            user_text,
            channel=channel,
        )
        session.add_message("agent", msg)
        return [Event("final", msg, conv_state=session.state)]
    
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
            existing_slot = tools_booking.find_booking_by_name(session.qualif_data.name)
            if existing_slot:
                session.state = "CANCEL_CONFIRM"
                session.pending_cancel_slot = existing_slot
                slot_label = existing_slot.get("label", "votre rendez-vous")
                msg = prompts.VOCAL_CANCEL_CONFIRM.format(slot_label=slot_label) if channel == "vocal" else prompts.MSG_CANCEL_CONFIRM_WEB.format(slot_label=slot_label)
                session.add_message("agent", msg)
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
            existing_slot = tools_booking.find_booking_by_name(session.qualif_data.name)
            
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
            return [Event("final", msg, conv_state=session.state)]
        
        elif session.state == "CANCEL_CONFIRM":
            intent = detect_intent(user_text, session.state)
            
            if intent == "YES":
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
                    ok = bool(tools_booking.cancel_booking(slot))
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
            existing_slot = tools_booking.find_booking_by_name(session.qualif_data.name)
            if existing_slot:
                session.state = "MODIFY_CONFIRM"
                session.pending_cancel_slot = existing_slot
                slot_label = existing_slot.get("label", "votre rendez-vous")
                msg = prompts.VOCAL_MODIFY_CONFIRM.format(slot_label=slot_label) if channel == "vocal" else prompts.MSG_MODIFY_CONFIRM_WEB.format(slot_label=slot_label)
                session.add_message("agent", msg)
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
            existing_slot = tools_booking.find_booking_by_name(session.qualif_data.name)
            
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
            return [Event("final", msg, conv_state=session.state)]
        
        elif session.state == "MODIFY_CONFIRM":
            intent = detect_intent(user_text, session.state)
            
            if intent == "YES":
                # P0.4 — Ne pas annuler l'ancien avant d'avoir sécurisé le nouveau (ordre : nouveau confirmé → puis annuler ancien)
                session.state = "QUALIF_PREF"
                msg = prompts.VOCAL_MODIFY_NEW_PREF if channel == "vocal" else prompts.MSG_MODIFY_NEW_PREF_WEB
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            elif intent == "NO":
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
        # Filet : affirmation sans négation ("c'est bien ça", "ok", "exact") → YES_IMPLICIT ; exclure "euh", "attends"
        if intent != "YES" and (user_text or "").strip():
            _raw = (user_text or "").strip().lower()
            if not _raw.startswith(("non", "pas ")) and "attends" not in _raw and _raw not in ("euh", "euhh", "mmh"):
                _norm = "".join(c for c in _raw if c.isalnum() or c in " ")
                if "bienca" in _norm.replace(" ", "") or "bien ca" in _norm:
                    logger.info("[YES_IMPLICIT] conv_id=%s reason=echo_cest_bien_ca user_text_len=%s", session.conv_id, len(_raw))
                    intent = "YES"

        if intent == "YES":
            session.contact_confirm_intent_repeat_count = 0
            # Numéro confirmé
            
            # Si on a déjà un slot choisi (nouveau flow) → booker et confirmer
            if session.pending_slot_choice is not None:
                slot_idx = session.pending_slot_choice
                pending_display_len = len(getattr(session, "pending_slots_display", None) or [])
                logger.info(
                    "[BOOKING_ATTEMPT] conv_id=%s slot_idx=%s pending_slots_display_len=%s",
                    session.conv_id,
                    slot_idx,
                    pending_display_len,
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
                        if taken_slot and getattr(taken_slot, "start", None):
                            rejected = getattr(session, "rejected_slot_starts", None) or []
                            if not isinstance(rejected, list):
                                rejected = []
                            session.rejected_slot_starts = rejected + [taken_slot.start]
                    except (IndexError, TypeError):
                        pass
                    session.pending_slots = []
                    session.pending_slot_choice = None
                    session.pending_slots_display = []
                    session.state = "QUALIF_PREF"
                    msg = prompts.MSG_SLOT_TAKEN_REPROPOSE
                    session.add_message("agent", msg)
                    self._save_session(session)
                    return [Event("final", msg, conv_state=session.state)]
                # P0.4 — Si on vient d'un MODIFY : annuler l'ancien seulement après création du nouveau
                old_slot = getattr(session, "pending_cancel_slot", None)
                if old_slot:
                    tools_booking.cancel_booking(old_slot)
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
                print(f"📞 Correction partielle: {current_phone} → {corrected_phone}")
                
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
        # P1.7 — Anti-boucle : >= 2 visites au router → transfert direct
        session.intent_router_visits = getattr(session, "intent_router_visits", 0) + 1
        if session.intent_router_visits >= 2:
            session.state = "TRANSFERRED"
            msg = getattr(prompts, "VOCAL_INTENT_ROUTER_LOOP", prompts.VOCAL_STILL_UNCLEAR) if channel == "vocal" else prompts.MSG_TRANSFER
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        session.state = "INTENT_ROUTER"
        session.intent_router_unclear_count = 0
        session.last_question_asked = None
        session.consecutive_questions = 0
        session.global_recovery_fails = 0
        session.correction_count = 0
        session.empty_message_count = 0
        session.start_unclear_count = 0
        session.turn_count = 0  # Redonner 25 tours après le menu (spec V3)
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
        
        # Ambiguïté (hein, de seul) => retry puis transfert après 2
        if choice is None:
            session.intent_router_unclear_count = getattr(session, "intent_router_unclear_count", 0) + 1
            if session.intent_router_unclear_count >= 2:
                session.state = "TRANSFERRED"
                msg = prompts.VOCAL_STILL_UNCLEAR if channel == "vocal" else prompts.MSG_TRANSFER
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
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
            session.consecutive_questions = 0
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
        
        # Incompréhension (ne devrait pas arriver si parse_router_choice couvre 1-4)
        session.intent_router_unclear_count = getattr(session, "intent_router_unclear_count", 0) + 1
        if session.intent_router_unclear_count >= 2:
            session.state = "TRANSFERRED"
            msg = prompts.VOCAL_STILL_UNCLEAR if channel == "vocal" else prompts.MSG_TRANSFER
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
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
            session.consecutive_questions = 0
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
            session.consecutive_questions = 0
            return self._next_qualif_step(session)
        # Ré-inférence : user répète une phrase qui mène à la MÊME préférence → confirmation implicite
        inferred = infer_preference_from_context(user_text)
        if inferred and pending and inferred == pending:
            session.qualif_data.pref = pending
            session.pending_preference = None
            session.last_preference_user_text = None
            session.consecutive_questions = 0
            return self._next_qualif_step(session)
        # Ré-inférence vers une AUTRE préférence → mettre à jour et re-demander confirmation
        if inferred and inferred != pending:
            session.pending_preference = inferred
            session.last_preference_user_text = user_text.strip()
            msg = prompts.format_inference_confirmation(inferred)
            session.last_question_asked = msg
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        # Vraie incompréhension (pas d'inférence) → recovery progressive
        fail_count = increment_recovery_counter(session, "preference")
        if should_escalate_recovery(session, "preference"):
            return self._trigger_intent_router(session, "preference_fails_3", user_text)
        msg = prompts.format_inference_confirmation(pending) if pending else prompts.MSG_PREFERENCE_CONFIRM.format(pref="ce créneau")
        session.add_message("agent", msg)
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
        
        # Intent TRANSFER (doc: phrase explicite >=14 car.)
        if intent == "TRANSFER" and len(user_text.strip()) >= 14:
            session.state = "TRANSFERRED"
            msg = prompts.VOCAL_TRANSFER_COMPLEX if channel == "vocal" else prompts.MSG_TRANSFER
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
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
