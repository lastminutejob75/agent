"""Questionnaires V2 — accès public par token (usage unique)."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.questionnaire_v2 import public_questionnaire_payload, submit_questionnaire_response
from backend.tenants_pg import pg_get_tenant_full

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/q", tags=["public_questionnaire_v2"])


class PublicQuestionnaireSubmitBody(BaseModel):
    answers: Dict[str, Any] = Field(default_factory=dict)
    consent_given: bool = False


def _cabinet_label(tenant_id: int) -> str:
    try:
        tenant = pg_get_tenant_full(tenant_id)
        if tenant:
            return str(tenant.get("name") or "").strip() or "Votre cabinet"
    except Exception:
        logger.debug("public q cabinet label lookup failed", exc_info=True)
    return "Votre cabinet"


@router.get("/{token}")
def public_get_questionnaire_v2(token: str):
    try:
        payload = public_questionnaire_payload(token)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return {
        "ok": True,
        "cabinet_name": _cabinet_label(payload["tenant_id"]),
        "patient_name": payload.get("patient_name") or "",
        "template": payload["template"],
        "expires_at": payload.get("expires_at") or "",
        "medical_upload_message": (
            None
            if payload["template"].get("medical_upload_allowed")
            else "Pour transmettre un document médical, merci d'utiliser le canal habituel du cabinet."
        ),
    }


@router.post("/{token}/submit")
def public_submit_questionnaire_v2(token: str, body: PublicQuestionnaireSubmitBody):
    try:
        result = submit_questionnaire_response(
            token,
            body.answers,
            consent_given=body.consent_given,
            has_uploads=False,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, **result}
