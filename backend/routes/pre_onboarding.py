# backend/routes/pre_onboarding.py — POST /api/pre-onboarding/commit (wizard "Créer votre assistante")
# E2E test: Landing → /creer-assistante → remplir wizard → commit (email + modal) → voir lead dans /admin/leads → email fondateur (FOUNDER_EMAIL/ADMIN_EMAIL). Voir landing/README.md § Test E2E Wizard Lead.
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.leads_pg import upsert_lead
from backend.pre_onboarding_rate_limit import check_pre_onboarding_commit
from backend.services.email_service import send_lead_founder_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pre-onboarding", tags=["pre_onboarding"])

VALID_VOLUME = {"<10", "10-25", "25-50", "50-100", "100+", "unknown"}
VALID_VOICE = {"female", "male"}

# Spécialités médicales (menu déroulant wizard) — ordre affichage côté front
VALID_SPECIALTIES = frozenset({
    "Médecin généraliste", "Médecin spécialiste", "Pédiatre", "Dermatologue", "Ophtalmologue",
    "Cardiologue", "Gynécologue", "Psychiatre",
    "Chirurgien-dentiste", "Orthodontiste",
    "Infirmier(e) libéral(e)", "Kinésithérapeute", "Ostéopathe", "Orthophoniste", "Psychologue", "Sage-femme",
    "Centre médical", "Clinique privée", "Cabinet de groupe", "Maison de santé",
    "Autre profession de santé",
})

# Point de douleur principal (mini-diagnostic)
VALID_PAIN_POINTS = frozenset({
    "Les appels interrompent mes consultations",
    "Mon secrétariat est débordé",
    "Je rate des appels importants",
    "La gestion des rendez-vous me prend trop de temps",
    "Je veux améliorer l'expérience patient",
    "Autre",
})


class PreOnboardingCommitBody(BaseModel):
    email: str = Field(..., min_length=1)
    medical_specialty: str = Field(..., min_length=1)
    daily_call_volume: str = Field(...)
    primary_pain_point: str = Field(default="")
    opening_hours: Dict[str, Any] = Field(default_factory=dict)
    voice_gender: str = Field(...)
    assistant_name: str = Field(..., min_length=1)
    source: str = Field(default="landing_cta")
    wants_callback: bool = False
    callback_phone: str = Field(default="")


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


@router.post("/commit")
async def commit_pre_onboarding(request: Request, body: PreOnboardingCommitBody) -> Dict[str, Any]:
    """
    Enregistre un lead pré-onboarding (wizard "Créer votre assistante").
    Retourne rapidement ; envoi email fondateur en arrière-plan.
    """
    # 0) Rate limit (anti-spam)
    try:
        check_pre_onboarding_commit(request, body.email.strip())
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))

    # 1) Validation
    if not _validate_email(body.email):
        raise HTTPException(status_code=400, detail="Email invalide")
    if body.medical_specialty not in VALID_SPECIALTIES:
        raise HTTPException(status_code=400, detail="medical_specialty invalide")
    if body.daily_call_volume not in VALID_VOLUME:
        raise HTTPException(status_code=400, detail="daily_call_volume invalide")
    if body.primary_pain_point and body.primary_pain_point not in VALID_PAIN_POINTS:
        raise HTTPException(status_code=400, detail="primary_pain_point invalide")
    if body.voice_gender not in VALID_VOICE:
        raise HTTPException(status_code=400, detail="voice_gender invalide")
    if not (body.assistant_name and body.assistant_name.strip()):
        raise HTTPException(status_code=400, detail="assistant_name requis")
    if body.wants_callback and not (body.callback_phone and body.callback_phone.strip()):
        raise HTTPException(
            status_code=400,
            detail="Numéro de téléphone requis pour être rappelé",
        )
    if not _validate_opening_hours(body.opening_hours):
        raise HTTPException(
            status_code=400,
            detail="Horaires invalides : au moins un jour doit être ouvert",
        )

    # 2) Upsert lead (déduplication : si email déjà en new/contacted → update, sinon insert)
    lead_id = upsert_lead(
        email=body.email.strip(),
        daily_call_volume=body.daily_call_volume,
        medical_specialty=body.medical_specialty.strip(),
        primary_pain_point=(body.primary_pain_point or "").strip(),
        assistant_name=body.assistant_name.strip(),
        voice_gender=body.voice_gender,
        opening_hours=body.opening_hours,
        wants_callback=body.wants_callback,
        callback_phone=(body.callback_phone or "").strip() or None,
        source=body.source or "landing_cta",
    )
    if not lead_id:
        raise HTTPException(status_code=500, detail="Erreur enregistrement lead")

    # 3) Envoi email fondateur en synchrone (v1 fiable sur Railway : pas de process recyclé avant envoi)
    dashboard_base = (
        os.environ.get("ADMIN_BASE_URL")
        or os.environ.get("FRONT_BASE_URL")
        or os.environ.get("APP_BASE_URL")
        or ""
    ).strip()
    try:
        ok, err = send_lead_founder_email(
            lead_id=lead_id,
            email=body.email,
            daily_call_volume=body.daily_call_volume,
            medical_specialty=body.medical_specialty,
            primary_pain_point=(body.primary_pain_point or "").strip(),
            assistant_name=body.assistant_name,
            voice_gender=body.voice_gender,
            opening_hours=body.opening_hours,
            wants_callback=body.wants_callback,
            callback_phone=(body.callback_phone or "").strip() or "",
            dashboard_base_url=dashboard_base,
        )
        if not ok:
            logger.warning("lead_founder_email failed: %s", err)
    except Exception as e:
        logger.exception("lead_founder_email exception: %s", e)

    out = {"ok": True, "lead_id": lead_id}
    return out
