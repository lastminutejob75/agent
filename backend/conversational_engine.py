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

        strong_threshold = float(getattr(config, "FAQ_STRONG_MATCH_THRESHOLD", 0.90) or 0.90)

        def _fallback_or_fsm() -> List:
            """Si le message matche fortement une FAQ ou une demande de RDV, déléguer à la FSM ; sinon fallback conv + CLARIFY."""
            txt = (user_text or "").strip().lower()
            faq_result = self.faq_store.search(txt, include_low=False)
            if faq_result.match and faq_result.score >= strong_threshold:
                logger.info("[CONV] LLM failed/low_conf but strong FAQ match (%.2f) → FSM", faq_result.score)
                return self.fsm_engine.handle_message(conv_id, user_text)
            # Réponse courte type "un rdv" / "rendez-vous" après la proposition → la FSM gère le booking
            if any(m in txt for m in ("rdv", "rendez-vous", "réserver", "prendre rendez-vous")):
                logger.info("[CONV] LLM failed/low_conf but booking cue → FSM")
                return self.fsm_engine.handle_message(conv_id, user_text)
            msg = prompts.MSG_CONV_FALLBACK
            session.add_message("user", user_text)
            session.add_message("agent", msg)
            session.last_agent_message = msg
            session.state = "CLARIFY"
            session.confirm_retry_count = 0
            self.fsm_engine._save_session(session)
            return [Event("final", msg, conv_state=session.state)]

        # 1) LLM failed (invalid json / rejected / error)
        if conv_result is None:
            _log_conv_p0_start(
                conv_id,
                session,
                reason=fail_reason or "LLM_ERROR",
                start_turn=start_turn,
                llm_used=fail_reason in (FAIL_INVALID_JSON, FAIL_VALIDATION_REJECTED),
                confidence=None,
                next_mode=None,
            )
            logger.info("[CONV] no result in START → fallback or FSM (si forte FAQ)")
            return _fallback_or_fsm()

        # 2) LLM low confidence
        if float(conv_result.confidence) < float(min_conf):
            _log_conv_p0_start(
                conv_id,
                session,
                reason=REASON_LOW_CONF,
                start_turn=start_turn,
                confidence=float(conv_result.confidence),
                next_mode=None,
                llm_used=True,
            )
            logger.info("[CONV] low confidence in START → fallback or FSM (si forte FAQ)")
            return _fallback_or_fsm()

        response_text = conv_result.response_text
        next_mode = conv_result.next_mode

        # Ne faire confiance à FSM_FAQ que si le message matche vraiment une FAQ (score fort).
        # Évite faux positifs type "pizza" → paiement sans liste de mots en dur.
        if next_mode == "FSM_FAQ":
            faq_result = self.faq_store.search(user_text or "", include_low=False)
            try:
                strong = float(getattr(config, "FAQ_STRONG_MATCH_THRESHOLD", 0.90) or 0.90)
            except (TypeError, ValueError):
                strong = 0.90
            score_val = getattr(faq_result, "score", 0)
            if not isinstance(score_val, (int, float)):
                score_val = 0.0
            if not faq_result.match or score_val < strong:
                next_mode = "FSM_FALLBACK"
                response_text = prompts.MSG_CONV_FALLBACK
                logger.info("[CONV] FSM_FAQ overridden to FSM_FALLBACK (score %.2f < %.2f)", score_val, strong)

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

        # FSM_FALLBACK : si le message matche en fait une FAQ (ex. "adresse" en START), répondre par la FAQ au lieu du cadrage.
        if next_mode == "FSM_FALLBACK":
            try:
                strong = float(getattr(config, "FAQ_STRONG_MATCH_THRESHOLD", 0.90) or 0.90)
            except (TypeError, ValueError):
                strong = 0.90
            faq_result = self.faq_store.search(user_text or "", include_low=False)
            score_val = getattr(faq_result, "score", 0) if getattr(faq_result, "match", False) else 0
            if isinstance(score_val, (int, float)) and faq_result.match and score_val >= strong:
                channel = getattr(session, "channel", "web")
                response = prompts.format_faq_response(faq_result.answer, faq_result.faq_id, channel=channel)
                if channel == "vocal":
                    response = response + " " + getattr(prompts, "VOCAL_FAQ_FOLLOWUP", "Souhaitez-vous autre chose ?")
                else:
                    response = response + "\n\n" + getattr(prompts, "MSG_FAQ_FOLLOWUP_WEB", "Souhaitez-vous autre chose ?")
                session.add_message("user", user_text)
                session.add_message("agent", response)
                session.last_agent_message = response
                session.state = "POST_FAQ"
                self.fsm_engine._save_session(session)
                return [Event("final", response, conv_state=session.state)]
            session.add_message("user", user_text)
            session.add_message("agent", response_text)
            session.last_agent_message = response_text
            session.state = "CLARIFY"
            session.confirm_retry_count = 0  # pas de compte de relance au premier choix
            self.fsm_engine._save_session(session)
            return [Event("final", response_text, conv_state=session.state)]

        session.add_message("user", user_text)
        session.add_message("agent", response_text)
        session.last_agent_message = response_text

        if next_mode in ("FSM_BOOKING", "FSM_BOOKING_PRELUDE"):
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
