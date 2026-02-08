# backend/conversational_engine.py
"""
Conversational Engine - P0 (START state only)

Natural LLM-generated responses with strict safety via:
1. Placeholders for factual data
2. Post-validation (no digits, no forbidden words)
3. Fallback to FSM if validation fails

IMPORTANT: This is a wrapper around the existing Engine.
All booking/qualification flows remain in engine.py (FSM).
"""

from __future__ import annotations
import logging
from typing import List, Optional, TYPE_CHECKING

from backend.cabinet_data import CabinetData, DEFAULT_CABINET_DATA
from backend.llm_conversation import (
    LLMClient,
    ConvResult,
    build_system_prompt,
    build_user_prompt,
)
from backend.placeholders import replace_placeholders, validate_placeholders
from backend.response_validator import full_validate
from backend.session import Session
from backend.tools_faq import FaqStore

if TYPE_CHECKING:
    from backend.engine import Engine, Event


logger = logging.getLogger(__name__)


# Minimum confidence to accept LLM response
MIN_CONFIDENCE_THRESHOLD = 0.75


class ConversationalEngine:
    """
    Wrapper engine that adds natural LLM responses in START state.
    Delegates to FSM engine for all other states and fallback.
    """

    def __init__(
        self,
        fsm_engine: "Engine",
        llm_client: LLMClient,
        faq_store: FaqStore,
        cabinet_data: CabinetData = DEFAULT_CABINET_DATA,
    ):
        """
        Initialize the conversational engine.

        Args:
            fsm_engine: The existing deterministic FSM engine
            llm_client: LLM client for natural responses
            faq_store: FAQ store for placeholder resolution
            cabinet_data: Business ground truth data
        """
        self.fsm_engine = fsm_engine
        self.llm_client = llm_client
        self.faq_store = faq_store
        self.cabinet_data = cabinet_data

    def handle_message(self, conv_id: str, user_text: str) -> List["Event"]:
        """
        Handle a user message with conversational mode.

        P0 Scope:
        - Only uses LLM in START state
        - All other states delegate to FSM

        Args:
            conv_id: Conversation ID
            user_text: User message

        Returns:
            List of Event objects
        """
        from backend.engine import Event, detect_strong_intent

        # Get or create session
        session = self.fsm_engine.session_store.get_or_create(conv_id)

        # P0: Only use conversational mode in START state
        if session.state != "START":
            logger.debug(f"[{conv_id}] State={session.state}, delegating to FSM")
            return self.fsm_engine.handle_message(conv_id, user_text)

        # Check for strong intents that bypass LLM
        strong_intent = detect_strong_intent(user_text)
        if strong_intent:
            logger.info(f"[{conv_id}] Strong intent detected: {strong_intent}, bypassing LLM")
            return self.fsm_engine.handle_message(conv_id, user_text)

        # Try conversational LLM
        try:
            result = self._try_llm_response(session, user_text)
            if result is None:
                # LLM failed or rejected, fallback to FSM
                logger.info(f"[{conv_id}] LLM response rejected, falling back to FSM")
                return self.fsm_engine.handle_message(conv_id, user_text)

            # Process successful LLM result
            return self._process_conv_result(session, user_text, result)

        except Exception as e:
            logger.error(f"[{conv_id}] Conversational error: {e}", exc_info=True)
            return self.fsm_engine.handle_message(conv_id, user_text)

    def _try_llm_response(
        self,
        session: Session,
        user_text: str,
    ) -> Optional[ConvResult]:
        """
        Try to get a valid LLM response.

        Returns:
            ConvResult if valid, None if rejected
        """
        # Build prompts
        history = session.last_messages()

        # Call LLM
        raw_output = self.llm_client.complete(
            user_message=user_text,
            conversation_history=history,
            state=session.state,
            cabinet_data=self.cabinet_data,
        )

        logger.debug(f"[{session.conv_id}] LLM raw output: {raw_output[:200]}...")

        # Validate
        is_valid, parsed_data, rejection_reason = full_validate(raw_output)

        if not is_valid:
            logger.warning(f"[{session.conv_id}] LLM response rejected: {rejection_reason}")
            return None

        # Check confidence
        confidence = parsed_data.get("confidence", 0)
        if confidence < MIN_CONFIDENCE_THRESHOLD:
            logger.warning(f"[{session.conv_id}] Low confidence: {confidence}")
            return None

        # Validate placeholders
        response_text = parsed_data.get("response_text", "")
        placeholders_valid, invalid_placeholders = validate_placeholders(response_text)
        if not placeholders_valid:
            logger.warning(f"[{session.conv_id}] Invalid placeholders: {invalid_placeholders}")
            return None

        return ConvResult(
            response_text=response_text,
            next_mode=parsed_data.get("next_mode", "FSM_FALLBACK"),
            extracted=parsed_data.get("extracted"),
            confidence=confidence,
            raw_output=raw_output,
        )

    def _process_conv_result(
        self,
        session: Session,
        user_text: str,
        result: ConvResult,
    ) -> List["Event"]:
        """
        Process a validated ConvResult and route appropriately.

        Args:
            session: Current session
            user_text: Original user message
            result: Validated ConvResult from LLM

        Returns:
            List of Event objects
        """
        from backend.engine import Event

        # Replace placeholders with actual FAQ answers
        final_text, all_replaced = replace_placeholders(
            result.response_text,
            self.faq_store,
            self.cabinet_data,
        )

        if not all_replaced:
            logger.warning(f"[{session.conv_id}] Some placeholders not replaced, using partial text")

        # Store extracted entities if present
        if result.extracted:
            self._apply_extracted_entities(session, result.extracted)

        # Route based on next_mode
        return self._route_next_mode(session, user_text, final_text, result.next_mode)

    def _apply_extracted_entities(self, session: Session, extracted: dict) -> None:
        """Apply extracted entities to session."""
        if extracted.get("name"):
            session.qualif_data.name = extracted["name"]
            session.extracted_name = True

        if extracted.get("motif"):
            session.qualif_data.motif = extracted["motif"]
            session.extracted_motif = True

        if extracted.get("pref"):
            session.qualif_data.pref = extracted["pref"]
            session.extracted_pref = True

        if extracted.get("contact"):
            session.qualif_data.contact = extracted["contact"]

    def _route_next_mode(
        self,
        session: Session,
        user_text: str,
        response_text: str,
        next_mode: str,
    ) -> List["Event"]:
        """
        Route to appropriate flow based on next_mode.

        Args:
            session: Current session
            user_text: Original user message
            response_text: Final response text (placeholders replaced)
            next_mode: Where to route (FSM_BOOKING, FSM_FAQ, etc.)

        Returns:
            List of Event objects
        """
        from backend.engine import Event

        conv_id = session.conv_id
        logger.info(f"[{conv_id}] Routing to {next_mode}")

        # Add messages to history
        session.add_message("user", user_text)
        session.add_message("agent", response_text)

        if next_mode == "FSM_BOOKING":
            # Transition to booking flow
            session.state = "QUALIF_NAME"
            session.last_question_asked = response_text
            self._save_session(session)
            return [Event("final", response_text, conv_state="QUALIF_NAME")]

        elif next_mode == "FSM_FAQ":
            # Stay in FAQ/START flow
            session.state = "FAQ_ANSWERED"
            self._save_session(session)
            return [Event("final", response_text, conv_state="FAQ_ANSWERED")]

        elif next_mode == "FSM_TRANSFER":
            # Trigger transfer
            session.state = "TRANSFERRED"
            self._save_session(session)
            return [Event("transfer", response_text, conv_state="TRANSFERRED")]

        else:  # FSM_FALLBACK
            # Keep in START, let FSM handle next turn
            self._save_session(session)
            return [Event("final", response_text, conv_state="START")]

    def _save_session(self, session: Session) -> None:
        """Save session if store supports it."""
        if hasattr(self.fsm_engine.session_store, "save"):
            self.fsm_engine.session_store.save(session)


def create_conversational_engine(
    fsm_engine: "Engine",
    llm_client: LLMClient,
    faq_store: Optional[FaqStore] = None,
    cabinet_data: Optional[CabinetData] = None,
) -> ConversationalEngine:
    """
    Factory function to create a ConversationalEngine.

    Args:
        fsm_engine: The existing FSM engine
        llm_client: LLM client for natural responses
        faq_store: Optional FAQ store (uses engine's if not provided)
        cabinet_data: Optional cabinet data (uses default if not provided)

    Returns:
        Configured ConversationalEngine
    """
    return ConversationalEngine(
        fsm_engine=fsm_engine,
        llm_client=llm_client,
        faq_store=faq_store or fsm_engine.faq_store,
        cabinet_data=cabinet_data or DEFAULT_CABINET_DATA,
    )
