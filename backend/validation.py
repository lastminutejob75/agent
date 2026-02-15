# backend/validation.py
"""
Validation avant TTS (pare-feu sortie).
- critical: allowlist stricte par say_key (texte EXACT depuis prompts.py)
- template: doit matcher les textes autorisés pour l'état (strict)
- ai_generated: règles longueur + interdits + pattern
Si échec → fallback technical_transfer + log VALIDATION_DEVIATION.
Ne modifie jamais la logique de retry/transfer (reason), seulement le texte émis.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from backend import prompts
from backend.validation_config import (
    DEFAULT_STATE_CONFIG,
    STATE_VALIDATION_RULES,
    validate_message as _validate_message_config,
)

logger = logging.getLogger(__name__)


def _allowed_texts_for_critical(state: str, channel: str = "vocal") -> List[str]:
    """Texte exact pour chaque say_key de l'allowlist (source prompts.py)."""
    config = STATE_VALIDATION_RULES.get(state, DEFAULT_STATE_CONFIG)
    keys = config.allowlist_say_keys or []
    out: List[str] = []
    for key in keys:
        try:
            msg = prompts.get_message(key, channel=channel)
            if msg and msg.strip():
                out.append(msg.strip())
        except Exception:
            pass
    return out


def validate_response(
    state: str,
    message_text: str,
    channel: str = "vocal",
    *,
    template_state: Optional[str] = None,
    say_key: Optional[str] = None,
    template_candidates: Optional[List[str]] = None,
) -> Tuple[bool, str]:
    """
    Valide le message agent avant TTS.
    Returns: (valid, text_to_use).
    Si valid=False, text_to_use = fallback technical_transfer (exact depuis prompts.py).
    """
    config = STATE_VALIDATION_RULES.get(state, DEFAULT_STATE_CONFIG)
    effective_state = template_state if template_state is not None else state
    text = (message_text or "").strip()

    # Critical: allowlist stricte (texte exact depuis prompts.py)
    if config.message_type == "critical":
        allowed = _allowed_texts_for_critical(effective_state, channel)
        if say_key and config.allowlist_say_keys and say_key in config.allowlist_say_keys:
            expected = prompts.get_message(say_key, channel=channel)
            if text == (expected or "").strip():
                return True, message_text
        if text in allowed:
            return True, message_text
        fallback = prompts.get_message("technical_transfer", channel=channel)
        logger.warning(
            "VALIDATION_DEVIATION",
            extra={
                "state": state,
                "template_state": template_state,
                "message_type": "critical",
                "reason": "message not in allowlist",
                "say_key": say_key,
                "text_preview": (text or "")[:100],
            },
        )
        return False, (fallback or "").strip()

    # Template: doit matcher un des candidats (strict)
    if config.message_type == "template":
        valid, reason = _validate_message_config(
            effective_state,
            text,
            say_key=say_key,
            template_candidates=template_candidates,
        )
        if valid:
            return True, message_text
        fallback = prompts.get_message("technical_transfer", channel=channel)
        logger.warning(
            "VALIDATION_DEVIATION",
            extra={
                "state": state,
                "template_state": template_state,
                "message_type": "template",
                "reason": reason or "template mismatch",
                "text_preview": (text or "")[:100],
            },
        )
        return False, (fallback or "").strip()

    # AI generated: règles souples
    if config.message_type == "ai_generated":
        valid, reason = _validate_message_config(
            effective_state,
            text,
            say_key=say_key,
            template_candidates=template_candidates,
        )
        if valid:
            return True, message_text
        fallback = prompts.get_message("technical_transfer", channel=channel)
        logger.warning(
            "VALIDATION_DEVIATION",
            extra={
                "state": state,
                "template_state": template_state,
                "message_type": "ai_generated",
                "reason": reason or "ai_rules",
                "text_preview": (text or "")[:100],
            },
        )
        return False, (fallback or "").strip()

    # Fallback safe
    fallback = prompts.get_message("technical_transfer", channel=channel)
    return False, (fallback or "").strip()
