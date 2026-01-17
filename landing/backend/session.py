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
    last_seen_at: datetime = field(default_factory=datetime.utcnow)
    messages: Deque[Message] = field(default_factory=lambda: deque(maxlen=config.MAX_MESSAGES_HISTORY))

    # PRD counters
    no_match_turns: int = 0
    confirm_retry_count: int = 0
    contact_retry_count: int = 0  # ✅ NOUVEAU

    # Qualification
    qualif_step: str = "name"
    qualif_data: QualifData = field(default_factory=QualifData)
    motif_help_used: bool = False  # NEW: utilisé pour empêcher la boucle sur le motif

    # Booking pending
    pending_slot_ids: List[int] = field(default_factory=list)
    pending_slot_labels: List[str] = field(default_factory=list)

    def touch(self) -> None:
        self.last_seen_at = datetime.utcnow()

    def is_expired(self) -> bool:
        ttl = timedelta(minutes=config.SESSION_TTL_MINUTES)
        return datetime.utcnow() - self.last_seen_at > ttl

    def reset(self) -> None:
        self.state = "START"
        self.no_match_turns = 0
        self.confirm_retry_count = 0
        self.contact_retry_count = 0  # ✅ NOUVEAU
        self.qualif_step = "name"
        self.qualif_data = QualifData()
        self.motif_help_used = False
        self.pending_slot_ids = []
        self.pending_slot_labels = []

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
