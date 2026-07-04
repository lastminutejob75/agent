"""
Reformulation LLM du motif patient (niveau B — fiche consultation UWI).

POST /api/tenant/consultations/reformulate-motif
  { raw_motif, patient_age? } -> { suggestions: [..], source: "llm" }

Derrière ENABLE_CONSULTATION_MOTIF_REFORMULATE_LLM=true.
Timeout applicatif 2 s — le front garde le niveau A en fallback silencieux.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from backend.llm_provider import create_chat_client

logger = logging.getLogger(__name__)

MOTIF_REFORMULATE_TIMEOUT_MS = 2000

SYSTEM_PROMPT = (
    "Tu reformules un motif déclaré par un patient en formulations médicales courtes "
    "pour un praticien de médecine générale.\n"
    "Règles strictes:\n"
    "- Maximum 3 suggestions\n"
    "- Formulations courtes (5 à 10 mots)\n"
    "- Terminologie médicale professionnelle\n"
    "- JAMAIS de diagnostic affirmé: utilise « à explorer », « à caractériser », "
    "« à évaluer », « — évaluation »\n"
    "- Ne rien inventer au-delà du verbatim patient\n"
    'Réponds en JSON strict uniquement: {"suggestions":["...","..."]}'
)


class MotifReformulateRequest(BaseModel):
    raw_motif: str = Field(min_length=1)
    patient_age: Optional[int] = Field(default=None, ge=0, le=130)

    @field_validator("raw_motif")
    @classmethod
    def strip_raw_motif(cls, value: str) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            raise ValueError("raw_motif requis")
        return cleaned


class MotifReformulateResponse(BaseModel):
    suggestions: list[str]
    source: str = "llm"


def is_motif_reformulate_llm_enabled() -> bool:
    return (os.getenv("ENABLE_CONSULTATION_MOTIF_REFORMULATE_LLM") or "").strip().lower() in (
        "true",
        "1",
        "yes",
    )


def _parse_json_payload(text: str) -> dict:
    raw = str(text or "").strip()
    if not raw:
        return {}
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw, flags=re.IGNORECASE)
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(raw[start : end + 1])
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}
        return {}


def sanitize_motif_suggestions(items: list) -> list[str]:
    out: list[str] = []
    for item in items or []:
        text = str(item or "").strip()
        if not text or len(text) > 120:
            continue
        out.append(text)
        if len(out) >= 3:
            break
    return out


def reformulate_motif_with_llm(raw_motif: str, patient_age: Optional[int] = None) -> list[str]:
    if not is_motif_reformulate_llm_enabled():
        raise RuntimeError("motif reformulate LLM disabled")

    client = create_chat_client(
        purpose="assist",
        provider_env_key="LLM_MOTIF_REFORMULATE_PROVIDER",
    ) or create_chat_client(
        purpose="assist",
        provider_env_key="LLM_ASSIST_PROVIDER",
    )
    if not client:
        raise RuntimeError("LLM client unavailable")

    age_hint = f"Âge patient: {patient_age} ans." if patient_age is not None else ""
    user = f'Motif patient: «{raw_motif.strip()}». {age_hint}'.strip()

    raw = client.complete(SYSTEM_PROMPT, user, MOTIF_REFORMULATE_TIMEOUT_MS)
    parsed = _parse_json_payload(raw)
    suggestions = sanitize_motif_suggestions(parsed.get("suggestions") or [])
    if not suggestions:
        raise RuntimeError("empty suggestions from LLM")
    return suggestions


def build_motif_reformulate_response(raw_motif: str, patient_age: Optional[int] = None) -> MotifReformulateResponse:
    suggestions = reformulate_motif_with_llm(raw_motif, patient_age)
    return MotifReformulateResponse(suggestions=suggestions, source="llm")
