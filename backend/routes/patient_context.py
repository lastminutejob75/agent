"""Routes V2 : résumé IA patient + questionnaires structurés."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.db import get_cabinet_client_by_phone, get_conn
from backend.questionnaire_v2 import (
    create_questionnaire_request,
    ensure_default_medical_template,
    get_questionnaire_response,
    integrate_response,
    list_patient_questionnaire_requests,
)
from backend.routes.tenant import require_tenant_auth
from backend.services.patient_summary import get_or_generate_summary, log_health_access
from backend.services.email_service import send_patient_admin_form_email, send_patient_questionnaire_email
from backend.tenant_capabilities import get_tenant_capabilities, requester_from_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tenant", tags=["patient_context_v2"])


class CreateQuestionnaireBody(BaseModel):
    template_id: Optional[str] = None
    template_type: Optional[str] = None  # "admin" | "medical"
    sent_to_email: Optional[str] = None
    sent_to_phone: Optional[str] = None
    appointment_id: Optional[str] = None
    send_email: bool = True


def _tenant_detail(tenant_id: int) -> Dict[str, Any]:
    try:
        from backend.tenants_pg import pg_get_tenant_full

        return pg_get_tenant_full(tenant_id) or {}
    except Exception:
        return {}


def _public_v2_link(raw_token: str) -> str:
    base = (os.environ.get("PUBLIC_BASE_URL") or "https://www.uwiapp.com").rstrip("/")
    return f"{base}/q/{raw_token}"


def _require_health_questionnaire_access(auth: dict, tenant_id: int, phone: str, is_health: bool) -> None:
    """Bloque l'accès aux réponses santé sans HDS + profil soignant."""
    if not is_health:
        return
    detail = _tenant_detail(tenant_id)
    caps = get_tenant_capabilities(tenant_id, detail)
    requester = requester_from_auth(auth)
    if "hds_enabled" not in caps:
        raise HTTPException(403, "Données de santé : HDS requis pour consulter cette réponse.")
    if not requester.is_soignant:
        raise HTTPException(403, "Accès réservé aux profils soignants.")
    log_health_access(tenant_id, phone, requester, action="view_questionnaire_health")


@router.get("/patients/{phone}/summary")
def tenant_get_patient_summary(
    phone: str,
    auth: dict = Depends(require_tenant_auth),
    refresh: bool = False,
):
    """Résumé IA de fiche patient (cache hash, régénération si inputs changent)."""
    tenant_id = auth["tenant_id"]
    profile = get_cabinet_client_by_phone(tenant_id, phone)
    if not profile:
        raise HTTPException(404, "Fiche patient introuvable.")

    detail = _tenant_detail(tenant_id)
    caps = get_tenant_capabilities(tenant_id, detail)
    requester = requester_from_auth(auth)
    conn = get_conn()
    try:
        summary = get_or_generate_summary(
            conn,
            tenant_id,
            phone,
            caps,
            requester,
            force_refresh=refresh,
        )
    finally:
        conn.close()
    return {
        "ok": True,
        "summary": {
            "sections_json": summary.get("sections_json") or {},
            "generated_at": summary.get("generated_at") or "",
            "from_cache": bool(summary.get("from_cache")),
            "is_health": bool(summary.get("is_health")),
            "model": summary.get("model") or "",
            "access_limited": bool(summary.get("access_limited")),
        },
    }


@router.post("/patients/{phone}/questionnaires")
def tenant_create_questionnaire_request(
    phone: str,
    body: CreateQuestionnaireBody,
    auth: dict = Depends(require_tenant_auth),
):
    """Crée et envoie un questionnaire V2 (token usage unique)."""
    tenant_id = auth["tenant_id"]
    profile = get_cabinet_client_by_phone(tenant_id, phone)
    if not profile:
        raise HTTPException(404, "Fiche patient introuvable.")

    email = (body.sent_to_email or profile.get("email") or "").strip()
    if body.send_email and not email:
        raise HTTPException(400, "Aucune adresse email pour envoyer le questionnaire.")

    template_id = body.template_id
    template_type = (body.template_type or "admin").strip().lower()
    if not template_id and template_type == "medical":
        try:
            template_id = ensure_default_medical_template(tenant_id)["id"]
        except ValueError as e:
            raise HTTPException(400, str(e)) from e

    try:
        req, raw_token = create_questionnaire_request(
            tenant_id,
            phone,
            template_id=template_id,
            sent_by_user_id=str(auth.get("sub") or ""),
            sent_to_email=email,
            sent_to_phone=body.sent_to_phone or phone,
            appointment_id=body.appointment_id or "",
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    link = _public_v2_link(raw_token)
    email_sent = False
    if body.send_email and email:
        try:
            cabinet_name = str(_tenant_detail(tenant_id).get("name") or "Votre cabinet")
            patient_name = profile.get("display_name") or profile.get("validated_name") or "Patient"
            if template_type == "medical":
                send_patient_questionnaire_email(
                    to_email=email,
                    patient_name=patient_name,
                    cabinet_name=cabinet_name,
                    questionnaire_url=link,
                )
            else:
                send_patient_admin_form_email(
                    to_email=email,
                    patient_name=patient_name,
                    cabinet_name=cabinet_name,
                    questionnaire_url=link,
                )
            email_sent = True
        except Exception:
            logger.warning("questionnaire v2 email failed", exc_info=True)

    return {
        "ok": True,
        "request": req,
        "questionnaire_url": link,
        "email_sent": email_sent,
    }


@router.get("/patients/{phone}/questionnaires-v2")
def tenant_list_questionnaire_requests(
    phone: str,
    auth: dict = Depends(require_tenant_auth),
    template_type: Optional[str] = None,
):
    tenant_id = auth["tenant_id"]
    if not get_cabinet_client_by_phone(tenant_id, phone):
        raise HTTPException(404, "Fiche patient introuvable.")
    tt = (template_type or "").strip().lower() or None
    items = list_patient_questionnaire_requests(tenant_id, phone, template_type=tt)
    return {"ok": True, "requests": items}


@router.get("/questionnaires-v2/{response_id}")
def tenant_get_questionnaire_response(
    response_id: str,
    auth: dict = Depends(require_tenant_auth),
):
    tenant_id = auth["tenant_id"]
    try:
        response = get_questionnaire_response(tenant_id, response_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    _require_health_questionnaire_access(
        auth,
        tenant_id,
        str(response.get("patient_phone") or ""),
        bool(response.get("is_health")),
    )
    return {"ok": True, "response": response}


@router.post("/questionnaires-v2/{response_id}/integrate")
def tenant_integrate_questionnaire_response(
    response_id: str,
    auth: dict = Depends(require_tenant_auth),
):
    tenant_id = auth["tenant_id"]
    try:
        preview = get_questionnaire_response(tenant_id, response_id)
        _require_health_questionnaire_access(
            auth,
            tenant_id,
            str(preview.get("patient_phone") or ""),
            bool(preview.get("is_health")),
        )
        result = integrate_response(tenant_id, response_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return result
