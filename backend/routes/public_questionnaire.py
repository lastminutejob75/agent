"""Questionnaire médical patient — accès public par token signé.

- GET  /api/public/patient-questionnaire/{token} → schéma + réponses pré-remplies
- POST /api/public/patient-questionnaire/{token} → soumission patient

Le token (HMAC, cf. backend.lead_tokens) encode tenant_id + téléphone. Aucun
autre identifiant n'est exposé. À la soumission, les réponses remplissent le
questionnaire de la fiche et enrichissent profil + contexte patient.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.db import get_cabinet_client_by_phone
from backend.patient_questionnaire import (
    FILLED_BY_PATIENT,
    STATUS_COMPLETED,
    apply_answers_to_patient,
    get_questionnaire,
    merge_profile_into_answers,
    parse_questionnaire_token,
    questionnaire_schema,
    sanitize_answers,
    save_questionnaire,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/public/patient-questionnaire", tags=["public_questionnaire"])


class PublicQuestionnaireSubmitBody(BaseModel):
    answers: Dict[str, Any] = Field(default_factory=dict)


def _resolve_token(token: str) -> Dict[str, Any]:
    ref = parse_questionnaire_token(token)
    if not ref:
        raise HTTPException(404, "Lien invalide ou expiré.")
    return ref


def _cabinet_label(tenant_id: int) -> str:
    try:
        from backend.tenants_pg import pg_get_tenant_full

        tenant = pg_get_tenant_full(tenant_id)
        if tenant:
            return str(tenant.get("name") or "").strip() or "Votre cabinet"
    except Exception:
        logger.debug("public questionnaire cabinet label lookup failed", exc_info=True)
    return "Votre cabinet"


@router.get("/{token}")
def public_get_questionnaire(token: str):
    ref = _resolve_token(token)
    tenant_id = ref["tenant_id"]
    phone = ref["phone"]
    profile = get_cabinet_client_by_phone(tenant_id, phone)
    if not profile:
        raise HTTPException(404, "Fiche introuvable.")
    state = get_questionnaire(tenant_id, phone)
    patient_name = (
        profile.get("display_name") or profile.get("validated_name") or profile.get("raw_name") or ""
    ).strip()
    # Pré-remplissage côté patient avec ce que la fiche connaît déjà.
    answers = merge_profile_into_answers(profile, state.get("answers"))
    return {
        "ok": True,
        "cabinet_name": _cabinet_label(tenant_id),
        "patient_name": patient_name,
        "schema": questionnaire_schema(),
        "answers": answers,
        "already_completed": state.get("status") == STATUS_COMPLETED,
    }


@router.post("/{token}")
def public_submit_questionnaire(token: str, body: PublicQuestionnaireSubmitBody):
    ref = _resolve_token(token)
    tenant_id = ref["tenant_id"]
    phone = ref["phone"]
    profile = get_cabinet_client_by_phone(tenant_id, phone)
    if not profile:
        raise HTTPException(404, "Fiche introuvable.")

    answers = sanitize_answers(body.answers)
    save_questionnaire(
        tenant_id,
        phone,
        answers=answers,
        status=STATUS_COMPLETED,
        filled_by=FILLED_BY_PATIENT,
        mark_completed=True,
    )
    apply_answers_to_patient(
        tenant_id,
        phone,
        answers,
        source_label="rempli par le patient",
        add_context_note=True,
    )
    return {"ok": True}
