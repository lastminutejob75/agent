# backend/session.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Deque, Dict, List, Optional, Tuple
from collections import deque

from backend import config


@dataclass
class Message:
    role: str  # "user" | "agent"
    text: str
    ts: datetime


@dataclass
class QualifData:
    name: Optional[str] = None
    motif: Optional[str] = None
    pref: Optional[str] = None
    contact: Optional[str] = None
    contact_type: Optional[str] = None  # "email" | "phone"
    contact_channel: Optional[str] = None  # "email" | "phone" (quand user dit "mail" / "téléphone")


@dataclass
class Session:
    conv_id: str
    state: str = "START"
    channel: str = "web"  # "web" | "vocal"
    customer_phone: Optional[str] = None  # Téléphone du client (Vapi)
    client_id: Optional[int] = None  # ID client (clients.db) pour ivr_events / rapport
    tenant_id: int = 1  # ID tenant (business) pour feature flags / tenant_config
    flags_effective: Dict[str, bool] = field(default_factory=dict)  # Flags chargés au 1er tour
    transfer_logged: bool = False  # idempotence: n'écrire qu'une fois transfer_human par call
    last_seen_at: datetime = field(default_factory=datetime.utcnow)
    messages: Deque[Message] = field(default_factory=lambda: deque(maxlen=config.MAX_MESSAGES_HISTORY))

    # PRD counters
    no_match_turns: int = 0
    confirm_retry_count: int = 0
    contact_retry_count: int = 0
    
    # Accumulation des chiffres du téléphone (vocal)
    partial_phone_digits: str = ""

    # P0 Contact vocal : canal en cours, échecs (2 max puis transfert)
    contact_mode: Optional[str] = None  # "phone" | "email"
    contact_fails: int = 0

    # Qualification
    qualif_step: str = "name"
    qualif_data: QualifData = field(default_factory=QualifData)
    motif_help_used: bool = False  # NEW: utilisé pour empêcher la boucle sur le motif

    # Extraction (Option 2 - entités extraites du premier message)
    extracted_name: bool = False
    extracted_motif: bool = False
    extracted_pref: bool = False

    # Booking pending
    pending_slot_ids: List[int] = field(default_factory=list)
    pending_slot_labels: List[str] = field(default_factory=list)
    pending_slots: List = field(default_factory=list)  # SlotDisplay objects
    pending_slot_choice: Optional[int] = None  # Slot choisi (avant confirmation contact)
    # P0: Slots EXACTEMENT affichés (source de vérité pour booking = pas de re-fetch)
    pending_slots_display: List[Dict[str, Any]] = field(default_factory=list)
    # Créneaux refusés (start ISO) : exclure ±90 min en re-proposition pour ne pas reproposer un voisin
    rejected_slot_starts: List[str] = field(default_factory=list)
    # (day, period) refusés : anti-spam matin/après-midi (ex. "lundi|MORNING")
    rejected_day_periods: List[str] = field(default_factory=list)
    # Séquentiel : "non" consécutifs → à 2, demander préférence ouverte
    slot_sequential_refuse_count: int = 0

    # CANCEL/MODIFY pending
    pending_cancel_slot: Optional[Dict] = None  # RDV à annuler/modifier

    # Production-grade V3 (PRODUCTION_GRADE_SPEC_V3)
    last_intent: Optional[str] = None  # Anti-boucle intent override
    consecutive_questions: int = 0  # Max 3 puis action concrète
    last_agent_message: Optional[str] = None  # Dernier message complet (répétition)
    last_question_asked: Optional[str] = None  # Dernière question (correction / rejouer)
    # REPEAT fiable : re-say exact (clé + kwargs pour re-render si besoin)
    last_say_key: Optional[str] = None
    last_say_kwargs: Optional[Dict[str, Any]] = None
    global_recovery_fails: int = 0  # Échecs globaux → INTENT_ROUTER si >= 2
    correction_count: int = 0  # Corrections répétées → INTENT_ROUTER si >= 2
    pending_preference: Optional[str] = None  # Préférence inférée (PREFERENCE_CONFIRM)
    last_preference_user_text: Optional[str] = None  # Phrase user ayant mené à pending (répétition = confirmation)
    empty_message_count: int = 0  # IVR Principe 3 : messages vides répétés → INTENT_ROUTER si >= 2
    turn_count: int = 0  # Nombre de tours (user+agent) → anti-loop si > 25 (spec V3)
    # Guidage START (question ouverte) : incompréhensions consécutives avant guidage proactif
    start_unclear_count: int = 0
    # UNCLEAR no_faq (LLM hors-sujet) : 2 → guidance, 3 → INTENT_ROUTER
    start_no_faq_count: int = 0
    # OUT_OF_SCOPE répété : >= 2 → transfert pour éviter spam hors-sujet
    start_out_of_scope_count: int = 0
    # Compteur ACK (round-robin Très bien / D'accord / Parfait) — persistant pendant l'appel
    ack_idx: int = 0
    # STT nova-2-phonecall : bruit (confidence faible) vs silence
    noise_detected_count: int = 0
    last_noise_ts: Optional[float] = None  # time.time() pour cooldown
    # Custom LLM (chat/completions) : texte incompréhensible / garbage
    unclear_text_count: int = 0
    # Crosstalk (barge-in) : timestamp dernière réponse assistant (time.time())
    last_assistant_ts: float = 0.0
    # Overlap guard : timestamp envoi dernière réponse agent (overlap ≠ unclear)
    last_agent_reply_ts: float = 0.0
    # Semi-sourd : timestamp fin TTS estimée (agent "parle" jusqu'à ce moment)
    speaking_until_ts: float = 0.0

    # Recovery par contexte (analytics + tuning fin — AJOUT_COMPTEURS_RECOVERY)
    slot_choice_fails: int = 0
    name_fails: int = 0
    qualif_name_intent_repeat_count: int = 0  # P0 : répétitions "je veux un rdv" en QUALIF_NAME (pas d'erreur, pas INTENT_ROUTER)
    phone_fails: int = 0
    preference_fails: int = 0
    qualif_pref_intent_repeat_count: int = 0  # P0 : répétitions "je veux un rdv" en QUALIF_PREF (pas d'erreur, pas INTENT_ROUTER)
    contact_confirm_fails: int = 0
    contact_confirm_intent_repeat_count: int = 0  # P0 : répétitions "je veux un rdv" en CONTACT_CONFIRM (pas contact_confirm_fails)
    cancel_name_fails: int = 0  # Flow CANCEL : RDV non trouvé (vérifier/humain puis INTENT_ROUTER)
    cancel_rdv_not_found_count: int = 0  # CANCEL : nb fois "RDV pas trouvé" (alternatives puis transfert)
    modify_name_fails: int = 0  # Flow MODIFY : RDV non trouvé (vérifier/humain puis INTENT_ROUTER)
    modify_rdv_not_found_count: int = 0  # MODIFY : nb fois "RDV pas trouvé"
    faq_fails: int = 0  # FAQ : question pas comprise (reformulation → exemples → INTENT_ROUTER)
    # RÈGLE 7 : contrainte horaire explicite (ex: "après 17h")
    time_constraint_type: str = ""  # "after" | "before" | ""
    time_constraint_minute: int = -1  # minute_of_day (ex 17h00 -> 1020), -1 si absent
    # Flow ordonnance (conversation naturelle RDV vs message)
    ordonnance_choice_fails: int = 0
    ordonnance_choice_asked: bool = False
    # P1.1 Barge-in : agent en train d'énoncer la liste des créneaux (interruption safe)
    is_reading_slots: bool = False
    # P1.2 Lecture créneaux en 2 tours : preface envoyée, puis liste
    slots_preface_sent: bool = False
    slots_list_sent: bool = False
    # P0.2 — Vocal séquentiel : 1 créneau à la fois (pas 3 d'un coup)
    slot_offer_index: int = 0
    slot_proposal_sequential: bool = False
    # P1.7 — Anti-boucle START <-> INTENT_ROUTER
    intent_router_visits: int = 0
    intent_router_unclear_count: int = 0

    # Yes disambiguation : quoi confirme le user quand il dit "oui" ? (éviter oui ambigu)
    awaiting_confirmation: Optional[str] = None  # CONFIRM_SLOT, CONFIRM_CONTACT, CONFIRM_PREFERENCE, CONFIRM_CANCEL, CONFIRM_MODIFY
    yes_ambiguous_count: int = 0  # "oui" ambigu répétés → 2e → guidance options

    MAX_CONSECUTIVE_QUESTIONS = 3  # Limite cognitive (spec V3)
    MAX_TURNS_ANTI_LOOP = 25  # Garde-fou : >25 tours sans DONE/TRANSFERRED → INTENT_ROUTER
    MAX_CONTEXT_FAILS = 3  # Échecs sur un même contexte → escalade INTENT_ROUTER

    def touch(self) -> None:
        self.last_seen_at = datetime.utcnow()

    def next_ack_index(self) -> int:
        """Incrémente le compteur ACK et retourne l'index pour pick_ack (round-robin)."""
        i = self.ack_idx
        self.ack_idx += 1
        return i

    def is_expired(self) -> bool:
        ttl = timedelta(minutes=config.SESSION_TTL_MINUTES)
        return datetime.utcnow() - self.last_seen_at > ttl

    def reset(self) -> None:
        self.state = "START"
        self.no_match_turns = 0
        self.confirm_retry_count = 0
        self.contact_retry_count = 0
        self.partial_phone_digits = ""
        self.contact_mode = None
        self.contact_fails = 0
        self.qualif_step = "name"
        self.qualif_data = QualifData()
        self.motif_help_used = False
        self.extracted_name = False
        self.extracted_motif = False
        self.extracted_pref = False
        self.pending_slot_ids = []
        self.pending_slot_labels = []
        self.pending_slots = []
        self.pending_slot_choice = None
        self.pending_slots_display = []
        self.pending_cancel_slot = None
        self.last_intent = None
        self.consecutive_questions = 0
        self.last_agent_message = None
        self.last_question_asked = None
        self.global_recovery_fails = 0
        self.correction_count = 0
        self.pending_preference = None
        self.empty_message_count = 0
        self.turn_count = 0
        self.start_unclear_count = 0
        self.ack_idx = 0
        self.noise_detected_count = 0
        self.last_noise_ts = None
        self.unclear_text_count = 0
        self.last_assistant_ts = 0.0
        self.last_agent_reply_ts = 0.0
        self.speaking_until_ts = 0.0
        self.slot_choice_fails = 0
        self.name_fails = 0
        self.qualif_name_intent_repeat_count = 0
        self.phone_fails = 0
        self.preference_fails = 0
        self.qualif_pref_intent_repeat_count = 0
        self.cancel_name_fails = 0
        self.cancel_rdv_not_found_count = 0
        self.modify_name_fails = 0
        self.modify_rdv_not_found_count = 0
        self.faq_fails = 0
        self.contact_confirm_fails = 0
        self.contact_confirm_intent_repeat_count = 0
        self.ordonnance_choice_fails = 0
        self.ordonnance_choice_asked = False
        self.is_reading_slots = False
        self.slots_preface_sent = False
        self.slots_list_sent = False
        self.slot_offer_index = 0
        self.slot_proposal_sequential = False
        self.intent_router_visits = 0
        self.intent_router_unclear_count = 0
        self.awaiting_confirmation = None
        self.yes_ambiguous_count = 0
        self.time_constraint_type = ""
        self.time_constraint_minute = -1
        self.client_id = None
        self.transfer_logged = False
        self.last_say_key = None
        self.last_say_kwargs = None
        # Note: on ne reset PAS customer_phone car c'est lié à l'appel

    def add_message(self, role: str, text: str) -> None:
        """Ajoute un message et met à jour last_agent_message / last_question_asked."""
        self.messages.append(Message(role=role, text=text, ts=datetime.utcnow()))
        self.touch()
        if role == "agent":
            self.last_agent_message = text
            # Reset last_say_key : seuls _say()/get_message() le rétablissent. Évite qu'un dernier
            # message "inline" (format_slot_early_confirm, etc.) laisse un last_say_key obsolète.
            self.last_say_key = None
            self.last_say_kwargs = {}
            # Dernière question posée (pour correction / "attendez")
            if "?" in text or any(q in text.lower() for q in ["dites", "quel", "préférez"]):
                self.last_question_asked = text

    def last_messages(self) -> List[Tuple[str, str]]:
        return [(m.role, m.text) for m in list(self.messages)]


class SessionStore:
    """
    In-memory session store V1.
    """
    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}

    def get_or_create(self, conv_id: str) -> Session:
        s = self._sessions.get(conv_id)
        if s is None:
            s = Session(conv_id=conv_id)
            self._sessions[conv_id] = s
        return s

    def get(self, conv_id: str) -> Optional[Session]:
        return self._sessions.get(conv_id)

    def delete(self, conv_id: str) -> None:
        if conv_id in self._sessions:
            del self._sessions[conv_id]
