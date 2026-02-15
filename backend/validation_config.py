# backend/validation_config.py
"""
Règles de validation des messages agent par état (critical / template / ai_generated).
À brancher sur le moteur qui émet les réponses (engine, Bland, etc.).
Pour les états UWi (backend/fsm.py), adapter les clés si besoin (ex: WAIT_CONFIRM vs CONFIRM_BOOKING).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Pattern
import re

MessageType = Literal["critical", "template", "ai_generated"]


@dataclass(frozen=True)
class AiRules:
    """
    Règles appliquées aux messages générés par IA (non-template).
    """
    max_length: int = 180
    forbidden_substrings: List[str] = field(default_factory=list)
    required_pattern: Optional[Pattern[str]] = None


@dataclass(frozen=True)
class StateValidationConfig:
    """
    - critical: allowlist stricte par say_key (texte EXACT issu de prompts.py)
    - template: doit matcher PROMPTS[state]["question"] (strict ou normalisé)
    - ai_generated: règles souples (longueur, interdits, pattern)
    """
    message_type: MessageType
    strict: bool = True

    # critical
    allowlist_say_keys: Optional[List[str]] = None

    # ai
    ai_rules: Optional[AiRules] = None


# -----------------------
# AI rules (COLLECT_REASON / motif)
# -----------------------
# Tu peux durcir progressivement (pattern, mots interdits) selon les retours terrain.
AI_RULES_COLLECT_REASON = AiRules(
    max_length=220,
    forbidden_substrings=[
        # Interdits métier / dérives (à adapter)
        "diagnostic",
        "urgence vitale",
        "arrêtez le traitement",
        "je vous prescris",
        "prescription",
        "posologie",
        "gratuit",
        # Ajoute ici vos interdits spécifiques
    ],
    # Phrase simple (évite les sorties bizarres). Permissif mais utile.
    required_pattern=re.compile(r"^.{1,}$"),
)


# -----------------------
# STATE VALIDATION RULES
# -----------------------
# Aligné avec états UWi (backend/fsm.py) + noms optionnels d’autres flows (PROPOSE_SLOTS, COLLECT_REASON).
# Pour "template", l’état passé à validate_message() doit être le "template_state" réellement utilisé.
STATE_VALIDATION_RULES: Dict[str, StateValidationConfig] = {
    # ----- Templates stricts (questions/phrases structurées) -----
    "START": StateValidationConfig(message_type="template", strict=True),
    "QUALIF_NAME": StateValidationConfig(message_type="template", strict=True),
    "QUALIF_MOTIF": StateValidationConfig(message_type="ai_generated", strict=False, ai_rules=AI_RULES_COLLECT_REASON),
    "QUALIF_PREF": StateValidationConfig(message_type="template", strict=True),
    "QUALIF_CONTACT": StateValidationConfig(message_type="template", strict=True),
    "PROPOSE_SLOTS": StateValidationConfig(message_type="template", strict=True),
    "WAIT_CONFIRM": StateValidationConfig(message_type="template", strict=True),
    "CONTACT_CONFIRM": StateValidationConfig(message_type="template", strict=True),
    "CONFIRM_BOOKING": StateValidationConfig(message_type="template", strict=True),

    # ----- AI flexible (motif) -----
    "COLLECT_REASON": StateValidationConfig(
        message_type="ai_generated",
        strict=False,
        ai_rules=AI_RULES_COLLECT_REASON,
    ),

    # ----- Critiques (allowlist stricte par say_key) -----
    "TRANSFER": StateValidationConfig(
        message_type="critical",
        strict=True,
        allowlist_say_keys=[
            "transfer_generic",
            "transfer",
            "no_slots_transfer",
            "technical_transfer",
            "permission_error_transfer",
        ],
    ),
    "TRANSFERRED": StateValidationConfig(
        message_type="critical",
        strict=True,
        allowlist_say_keys=[
            "transfer_generic",
            "transfer",
            "no_slots_transfer",
            "technical_transfer",
            "permission_error_transfer",
        ],
    ),
    "NO_SLOTS_TRANSFER": StateValidationConfig(
        message_type="critical",
        strict=True,
        allowlist_say_keys=[
            "no_slots_transfer",
        ],
    ),
    "TECHNICAL_ERROR": StateValidationConfig(
        message_type="critical",
        strict=True,
        allowlist_say_keys=[
            "technical_transfer",
        ],
    ),
    "PERMISSION_ERROR": StateValidationConfig(
        message_type="critical",
        strict=True,
        allowlist_say_keys=[
            "permission_error_transfer",
            "technical_transfer",
        ],
    ),

    # ----- Retries / edge cases -----
    "SLOT_TAKEN": StateValidationConfig(message_type="template", strict=True),
    "UNCLEAR_INPUT": StateValidationConfig(message_type="template", strict=True),
    "CLARIFY": StateValidationConfig(message_type="template", strict=True),

    # ----- Terminal -----
    "CONFIRMED": StateValidationConfig(message_type="template", strict=True),
    "ABANDONED": StateValidationConfig(message_type="template", strict=True),
}


# -----------------------
# DEFAULTS (safe)
# -----------------------
DEFAULT_STATE_CONFIG = StateValidationConfig(
    message_type="critical",
    strict=True,
    allowlist_say_keys=["technical_transfer"],
)


# -----------------------
# API de validation
# -----------------------
def validate_message(
    state: str,
    message_text: str,
    *,
    say_key: Optional[str] = None,
    template_candidates: Optional[List[str]] = None,
) -> tuple[bool, Optional[str]]:
    """
    Valide qu'un message agent est conforme à la config de l'état.
    Returns: (valid, reason_if_invalid).
    """
    config = STATE_VALIDATION_RULES.get(state, DEFAULT_STATE_CONFIG)
    text = (message_text or "").strip()

    if config.message_type == "critical":
        keys = config.allowlist_say_keys or []
        if say_key and say_key in keys:
            return True, None
        if say_key:
            return False, f"say_key '{say_key}' not in allowlist for state {state}"
        return False, f"critical state {state} requires say_key in {keys}"

    if config.message_type == "template":
        if not template_candidates:
            return True, None  # pas de liste fournie => pas de vérif stricte
        if text in template_candidates:
            return True, None
        if config.strict:
            return False, f"message not in template list for state {state}"
        text_norm = text.lower().strip()
        cand_norm = [c.lower().strip() for c in template_candidates]
        if text_norm in cand_norm:
            return True, None
        return False, f"message does not match template for state {state}"

    if config.message_type == "ai_generated" and config.ai_rules:
        r = config.ai_rules
        if len(text) > r.max_length:
            return False, f"message length {len(text)} > max {r.max_length}"
        text_lower = text.lower()
        for forbidden in r.forbidden_substrings:
            if forbidden.lower() in text_lower:
                return False, f"forbidden substring: {forbidden!r}"
        if r.required_pattern and not r.required_pattern.search(text):
            return False, "message does not match required pattern"
    return True, None
