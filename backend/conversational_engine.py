# backend/conversational_engine.py
"""
Mode conversationnel P0 : uniquement en état START.
Réponse naturelle LLM avec placeholders, validation stricte, fallback FSM inchangée.
"""
from __future__ import annotations

import logging
from typing import List

from backend import config, prompts
from backend.cabinet_data import CabinetData
from backend.engine import Event, detect_strong_intent
from backend.placeholders import replace_placeholders
from backend.llm_conversation import complete_conversation
from backend.session import Session

logger = logging.getLogger(__name__)


def _is_canary(conv_id: str) -> bool:
    """
    Canary rollout : 0 = disabled (personne), 1-99 = % du trafic (hash conv_id), 100 = full.
    Convention explicite pour éviter en prod : 0 = 0% (désactivé), pas 100%.
    """
    percent = getattr(config, "CONVERSATIONAL_CANARY_PERCENT", 0)
    if percent <= 0:
        return False
    if percent >= 100:
        return True
    h = hash(conv_id) % 100
    return h < percent


def _session_history_for_llm(session: Session, max_turns: int = 6) -> List[dict]:
    """Derniers tours (role, text) pour le prompt LLM."""
    out = []
    if not session.messages:
        return out
    for m in list(session.messages)[-max_turns * 2 :]:
        out.append({"role": m.role, "text": (m.text or "")[:200]})
    return out


class ConversationalEngine:
    """
    Enveloppe le moteur FSM : en START + flag + canary, tente une réponse LLM naturelle
    (placeholders uniquement) ; sinon délègue à l'engine FSM.
    """

    def __init__(
        self,
        cabinet_data: CabinetData,
        faq_store,
        llm_client,  # LLMConvClient
        fsm_engine,
    ):
        self.cabinet_data = cabinet_data
        self.faq_store = faq_store
        self.llm_client = llm_client
        self.fsm_engine = fsm_engine

    def handle_message(self, conv_id: str, user_text: str) -> List:
        """Même signature que Engine.handle_message : retourne List[Event]."""
        enabled = getattr(config, "CONVERSATIONAL_MODE_ENABLED", False)
        if not enabled or not _is_canary(conv_id):
            return self.fsm_engine.handle_message(conv_id, user_text)

        session = self.fsm_engine.session_store.get_or_create(conv_id)
        if session.state != "START":
            return self.fsm_engine.handle_message(conv_id, user_text)

        # Strong intent → FSM direct (pas d'appel LLM)
        strong = detect_strong_intent(user_text or "")
        if strong in ("CANCEL", "MODIFY", "TRANSFER", "ABANDON", "ORDONNANCE"):
            logger.info("[CONV] strong_intent=%s → FSM", strong)
            return self.fsm_engine.handle_message(conv_id, user_text)

        history = _session_history_for_llm(session)
        conv_result = complete_conversation(
            self.cabinet_data,
            session.state,
            user_text or "",
            history,
            self.llm_client,
        )
        min_conf = getattr(config, "CONVERSATIONAL_MIN_CONFIDENCE", 0.75)
        if conv_result is None or conv_result.confidence < min_conf:
            logger.info("[CONV] no result or low confidence → FSM")
            return self.fsm_engine.handle_message(conv_id, user_text)

        # Remplacer placeholders
        response_text = replace_placeholders(
            conv_result.response_text,
            self.faq_store,
            self.cabinet_data,
        )
        next_mode = conv_result.next_mode

        # FSM_FALLBACK : ne pas ajouter le message user ici, laisser la FSM le faire
        if next_mode == "FSM_FALLBACK":
            return self.fsm_engine.handle_message(conv_id, user_text)

        session.add_message("user", user_text)
        session.add_message("agent", response_text)
        session.last_agent_message = response_text

        if next_mode == "FSM_BOOKING":
            session.state = "QUALIF_NAME"
            extracted = conv_result.extracted or {}
            if isinstance(extracted.get("name"), str) and extracted["name"].strip():
                session.qualif_data.name = extracted["name"].strip().title()
                session.extracted_name = True
            if isinstance(extracted.get("pref"), str) and extracted["pref"].strip():
                session.qualif_data.pref = extracted["pref"].strip()
                session.extracted_pref = True
            if isinstance(extracted.get("contact"), str) and extracted["contact"].strip():
                session.qualif_data.contact = extracted["contact"].strip()
            self.fsm_engine._save_session(session)
            return [Event("final", response_text, conv_state=session.state)]

        if next_mode == "FSM_FAQ":
            session.state = "POST_FAQ"
            self.fsm_engine._save_session(session)
            return [Event("final", response_text, conv_state=session.state)]

        if next_mode == "FSM_TRANSFER":
            session.state = "TRANSFERRED"
            msg = prompts.MSG_TRANSFER
            session.add_message("agent", msg)
            session.last_agent_message = msg
            self.fsm_engine._save_session(session)
            return [Event("final", msg, conv_state=session.state)]

        # Autre (normalement pas atteint si validate_conv_result est strict)
        session.state = "START"
        self.fsm_engine._save_session(session)
        return [Event("final", response_text, conv_state=session.state)]
