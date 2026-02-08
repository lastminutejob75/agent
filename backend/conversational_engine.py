# backend/conversational_engine.py
"""
Mode conversationnel P0 : uniquement en état START.
Réponse naturelle LLM avec placeholders, validation stricte, fallback FSM inchangée.
"""
from __future__ import annotations

import hashlib
import logging
from typing import List, Optional

from backend import config, prompts
from backend.cabinet_data import CabinetData
from backend.engine import Event, detect_strong_intent
from backend.placeholders import replace_placeholders
from backend.llm_conversation import (
    FAIL_INVALID_JSON,
    FAIL_VALIDATION_REJECTED,
    complete_conversation,
)
from backend.session import Session

logger = logging.getLogger(__name__)

# Raisons pour métriques conv_p0_start (reason)
REASON_LLM_OK = "LLM_OK"
REASON_LOW_CONF = "LOW_CONF"
REASON_STRONG_INTENT = "STRONG_INTENT"
# INVALID_JSON, VALIDATION_REJECTED, LLM_ERROR viennent de llm_conversation


def _stable_bucket(conv_id: str) -> int:
    """Bucket 0-99 déterministe et stable (SHA256) pour canary rollout."""
    h = hashlib.sha256(conv_id.encode("utf-8")).hexdigest()
    return int(h[:8], 16) % 100


def _is_canary(conv_id: str) -> bool:
    """
    Canary:
    - 0  => disabled
    - 1..99 => percent rollout
    - 100 => enabled for all
    """
    percent = int(getattr(config, "CONVERSATIONAL_CANARY_PERCENT", 0) or 0)
    if percent <= 0:
        return False
    if percent >= 100:
        return True
    return _stable_bucket(conv_id) < percent


def _session_history_for_llm(session: Session, max_turns: int = 6) -> List[dict]:
    """Derniers tours (role, text) pour le prompt LLM."""
    out = []
    if not session.messages:
        return out
    for m in list(session.messages)[-max_turns * 2 :]:
        out.append({"role": m.role, "text": (m.text or "")[:200]})
    return out


def _start_turn(session: Session) -> int:
    """Numéro du tour utilisateur courant (1-based)."""
    return 1 + sum(1 for m in session.messages if getattr(m, "role", None) == "user")


def _log_conv_p0_start(
    conv_id: str,
    session: Session,
    reason: str,
    *,
    next_mode: Optional[str] = None,
    start_turn: Optional[int] = None,
    confidence: Optional[float] = None,
    llm_used: bool = False,
) -> None:
    """Un log structuré par décision (ou non-décision) canary en START."""
    extra = {"conv_id": conv_id, "reason": reason, "start_turn": start_turn if start_turn is not None else _start_turn(session)}
    if next_mode is not None:
        extra["next_mode"] = next_mode
    if confidence is not None:
        extra["confidence"] = round(confidence, 3)
    if llm_used:
        extra["llm_used"] = True
    logger.info("conv_p0_start", extra=extra)


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
            _log_conv_p0_start(conv_id, session, reason=REASON_STRONG_INTENT)
            logger.info("[CONV] strong_intent=%s → FSM", strong)
            return self.fsm_engine.handle_message(conv_id, user_text)

        history = _session_history_for_llm(session)
        conv_result, fail_reason = complete_conversation(
            self.cabinet_data,
            session.state,
            user_text or "",
            history,
            self.llm_client,
        )
        min_conf = float(getattr(config, "CONVERSATIONAL_MIN_CONFIDENCE", 0.75) or 0.75)
        start_turn = 1 + sum(1 for m in session.messages if getattr(m, "role", None) == "user")

        if conv_result is None:
            # INVALID_JSON / VALIDATION_REJECTED = on a appelé le LLM mais rejeté la sortie
            llm_called_but_rejected = fail_reason in (FAIL_INVALID_JSON, FAIL_VALIDATION_REJECTED)
            _log_conv_p0_start(
                conv_id,
                session,
                reason=fail_reason or "LLM_ERROR",
                start_turn=start_turn,
                llm_used=llm_called_but_rejected,
            )
            logger.info("[CONV] no result or low confidence → FSM")
            return self.fsm_engine.handle_message(conv_id, user_text)
        if conv_result.confidence < min_conf:
            _log_conv_p0_start(
                conv_id,
                session,
                reason=REASON_LOW_CONF,
                start_turn=start_turn,
                confidence=conv_result.confidence,
            )
            logger.info("[CONV] no result or low confidence → FSM")
            return self.fsm_engine.handle_message(conv_id, user_text)

        response_text = conv_result.response_text
        next_mode = conv_result.next_mode
        _log_conv_p0_start(
            conv_id,
            session,
            reason=REASON_LLM_OK,
            next_mode=next_mode,
            start_turn=start_turn,
            confidence=conv_result.confidence,
            llm_used=True,
        )

        if next_mode == "FSM_FAQ":
            response_text = replace_placeholders(
                response_text,
                self.faq_store,
                self.cabinet_data,
            )

        # FSM_FALLBACK : réponse LLM validée (sans placeholder) → retourner ce texte, state reste START
        if next_mode == "FSM_FALLBACK":
            session.add_message("user", user_text)
            session.add_message("agent", response_text)
            session.last_agent_message = response_text
            self.fsm_engine._save_session(session)
            return [Event("final", response_text, conv_state=session.state)]

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
