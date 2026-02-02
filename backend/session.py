# backend/session.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Deque, Dict, List, Optional, Tuple
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
    transfer_logged: bool = False  # idempotence: n'écrire qu'une fois transfer_human par call
    last_seen_at: datetime = field(default_factory=datetime.utcnow)
    messages: Deque[Message] = field(default_factory=lambda: deque(maxlen=config.MAX_MESSAGES_HISTORY))

    # PRD counters
    no_match_turns: int = 0
    confirm_retry_count: int = 0
    contact_retry_count: int = 0
    
    # Accumulation des chiffres du téléphone (vocal)
    partial_phone_digits: str = ""

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
    
    # CANCEL/MODIFY pending
    pending_cancel_slot: Optional[Dict] = None  # RDV à annuler/modifier

    # Production-grade V3 (PRODUCTION_GRADE_SPEC_V3)
    last_intent: Optional[str] = None  # Anti-boucle intent override
    consecutive_questions: int = 0  # Max 3 puis action concrète
    last_question_asked: Optional[str] = None  # Rejouer si "attendez"
    global_recovery_fails: int = 0  # Échecs globaux → INTENT_ROUTER si >= 2
    correction_count: int = 0  # Corrections répétées → INTENT_ROUTER si >= 2
    pending_preference: Optional[str] = None  # Préférence inférée (PREFERENCE_CONFIRM)
    empty_message_count: int = 0  # IVR Principe 3 : messages vides répétés → INTENT_ROUTER si >= 2
    turn_count: int = 0  # Nombre de tours (user+agent) → anti-loop si > 25 (spec V3)

    # Recovery par contexte (analytics + tuning fin — AJOUT_COMPTEURS_RECOVERY)
    slot_choice_fails: int = 0
    name_fails: int = 0
    phone_fails: int = 0
    preference_fails: int = 0
    contact_confirm_fails: int = 0
    cancel_name_fails: int = 0  # Flow CANCEL : RDV non trouvé (vérifier/humain puis INTENT_ROUTER)
    cancel_rdv_not_found_count: int = 0  # CANCEL : nb fois "RDV pas trouvé" (alternatives puis transfert)
    modify_name_fails: int = 0  # Flow MODIFY : RDV non trouvé (vérifier/humain puis INTENT_ROUTER)
    modify_rdv_not_found_count: int = 0  # MODIFY : nb fois "RDV pas trouvé"
    faq_fails: int = 0  # FAQ : question pas comprise (reformulation → exemples → INTENT_ROUTER)

    MAX_CONSECUTIVE_QUESTIONS = 3  # Limite cognitive (spec V3)
    MAX_TURNS_ANTI_LOOP = 25  # Garde-fou : >25 tours sans DONE/TRANSFERRED → INTENT_ROUTER
    MAX_CONTEXT_FAILS = 3  # Échecs sur un même contexte → escalade INTENT_ROUTER

    def touch(self) -> None:
        self.last_seen_at = datetime.utcnow()

    def is_expired(self) -> bool:
        ttl = timedelta(minutes=config.SESSION_TTL_MINUTES)
        return datetime.utcnow() - self.last_seen_at > ttl

    def reset(self) -> None:
        self.state = "START"
        self.no_match_turns = 0
        self.confirm_retry_count = 0
        self.contact_retry_count = 0
        self.partial_phone_digits = ""
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
        self.pending_cancel_slot = None
        self.last_intent = None
        self.consecutive_questions = 0
        self.last_question_asked = None
        self.global_recovery_fails = 0
        self.correction_count = 0
        self.pending_preference = None
        self.empty_message_count = 0
        self.turn_count = 0
        self.slot_choice_fails = 0
        self.name_fails = 0
        self.phone_fails = 0
        self.preference_fails = 0
        self.cancel_name_fails = 0
        self.cancel_rdv_not_found_count = 0
        self.modify_name_fails = 0
        self.modify_rdv_not_found_count = 0
        self.faq_fails = 0
        self.contact_confirm_fails = 0
        self.client_id = None
        self.transfer_logged = False
        # Note: on ne reset PAS customer_phone car c'est lié à l'appel

    def add_message(self, role: str, text: str) -> None:
        self.messages.append(Message(role=role, text=text, ts=datetime.utcnow()))
        self.touch()

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
