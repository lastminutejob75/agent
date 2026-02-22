# backend/routes/pre_onboarding.py — POST /api/pre-onboarding/commit (wizard "Créer votre assistante")
from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.leads_pg import insert_lead
from backend.services.email_service import send_lead_founder_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pre-onboarding", tags=["pre_onboarding"])

VALID_VOLUME = {"<10", "10-25", "25-50", "50+", "unknown"}
VALID_VOICE = {"female", "male"}


class PreOnboardingCommitBody(BaseModel):
    email: str = Field(..., min_length=1)
    daily_call_volume: str = Field(...)
    opening_hours: Dict[str, Any] = Field(default_factory=dict)
    voice_gender: str = Field(...)
    assistant_name: str = Field(..., min_length=1)
    source: str = Field(default="landing_cta")
    wants_callback: bool = False


def _validate_email(email: str) -> bool:
    if not email or len(email) > 254:
        return False
    pat = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pat, email.strip()))


def _validate_opening_hours(oh: Dict[str, Any]) -> bool:
    if not isinstance(oh, dict):
        return False
    # At least one day must be open (not all closed)
    has_open = False
    for k, v in (oh or {}).items():
        if isinstance(v, dict) and not v.get("closed") and (v.get("start") or v.get("end")):
            has_open = True
            break
    return has_open


def _send_founder_email_async(lead_id: str, body: PreOnboardingCommitBody) -> None:
    """Run in thread so we don't block the response."""
    try:
        dashboard_base = (
            os.environ.get("FRONT_BASE_URL") or os.environ.get("APP_BASE_URL") or ""
        ).strip()
        ok, err = send_lead_founder_email(
            lead_id=lead_id,
            email=body.email,
            daily_call_volume=body.daily_call_volume,
            assistant_name=body.assistant_name,
            voice_gender=body.voice_gender,
            opening_hours=body.opening_hours,
            wants_callback=body.wants_callback,
            dashboard_base_url=dashboard_base,
        )
        if not ok:
            logger.warning("lead_founder_email failed: %s", err)
    except Exception as e:
        logger.exception("_send_founder_email_async: %s", e)


@router.post("/commit")
async def commit_pre_onboarding(body: PreOnboardingCommitBody) -> Dict[str, Any]:
    """
    Enregistre un lead pré-onboarding (wizard "Créer votre assistante").
    Retourne rapidement ; envoi email fondateur en arrière-plan.
    """
    # 1) Validation
    if not _validate_email(body.email):
        raise HTTPException(status_code=400, detail="Email invalide")
    if body.daily_call_volume not in VALID_VOLUME:
        raise HTTPException(status_code=400, detail="daily_call_volume invalide")
    if body.voice_gender not in VALID_VOICE:
        raise HTTPException(status_code=400, detail="voice_gender invalide")
    if not (body.assistant_name and body.assistant_name.strip()):
        raise HTTPException(status_code=400, detail="assistant_name requis")
    if not _validate_opening_hours(body.opening_hours):
        raise HTTPException(
            status_code=400,
            detail="Horaires invalides : au moins un jour doit être ouvert",
        )

    # 2) Insert lead
    lead_id = insert_lead(
        email=body.email.strip(),
        daily_call_volume=body.daily_call_volume,
        assistant_name=body.assistant_name.strip(),
        voice_gender=body.voice_gender,
        opening_hours=body.opening_hours,
        wants_callback=body.wants_callback,
        source=body.source or "landing_cta",
    )
    if not lead_id:
        raise HTTPException(status_code=500, detail="Erreur enregistrement lead")

    # 3) Return quickly
    out = {"ok": True, "lead_id": lead_id}
    # Optional: mock test number for v1
    # out["test_number"] = "+33900000000"

    # 4) Send founder email in background (don't block response)
    asyncio.get_event_loop().run_in_executor(
        None,
        _send_founder_email_async,
        lead_id,
        body,
    )

    return out
