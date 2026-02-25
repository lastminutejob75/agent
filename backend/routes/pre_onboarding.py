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

# Spécialités médicales (step 1 : slugs normalisés)
VALID_SPECIALTIES = frozenset({
    "medecin_generaliste", "dentiste", "kinesitherapeute", "infirmier_liberal", "osteopathe", "centre_medical",
    "pediatre", "dermatologue", "gynecologue", "ophtalmologue", "cardiologue", "orl", "psychiatre",
    "neurologue", "rhumatologue", "gastro_enterologue",
    "orthophoniste", "sage_femme", "psychologue", "pedicure_podologue", "ergotherapeute", "dieteticien",
    "cabinet_de_groupe", "clinique_privee", "imagerie_labo", "pharmacie",
    "autre",
})

# Point de douleur principal (step 6 — quelle situation vous arrive le plus souvent)
VALID_PAIN_POINTS = frozenset({
    "Je suis interrompu(e) en consultation par les appels",
    "On me laisse beaucoup de messages à rappeler",
    "Mon secrétariat n'arrive pas à suivre",
    "Je passe trop de temps à gérer les rendez-vous",
    "Je veux mieux orienter les patients (infos, consignes, urgence)",
    "Autre",
})


class PreOnboardingCommitBody(BaseModel):
    email: str = Field(default="")  # optionnel si callback_phone fourni
    medical_specialty: str = Field(..., min_length=1)  # slug (ex: kinesitherapeute)
    medical_specialty_label: Optional[str] = Field(default=None)  # label affiché (ex: Kinésithérapeute)
    specialty_other: Optional[str] = Field(default=None)  # précision si medical_specialty=autre
    daily_call_volume: str = Field(...)
    primary_pain_point: str = Field(default="")
    opening_hours: Dict[str, Any] = Field(default_factory=dict)
    voice_gender: str = Field(...)
    assistant_name: str = Field(..., min_length=1)
    source: str = Field(default="landing_cta")
    wants_callback: bool = False
    callback_phone: str = Field(default="")  # optionnel si email fourni ; au moins un des deux requis


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
    email = (body.email or "").strip()
    callback_phone = (body.callback_phone or "").strip()
    if not email and not callback_phone:
        raise HTTPException(
            status_code=400,
            detail="Indiquez au moins un email ou un numéro de téléphone",
        )
    if email and not _validate_email(email):
        raise HTTPException(status_code=400, detail="Email invalide")

    # 0) Rate limit (anti-spam) — clé = email ou téléphone
    try:
        check_pre_onboarding_commit(request, email or callback_phone)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))

    # 1) Validation
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
    if not _validate_opening_hours(body.opening_hours):
        raise HTTPException(
            status_code=400,
            detail="Horaires invalides : au moins un jour doit être ouvert",
        )

    # 2) Upsert lead (déduplication par email si fourni ; sinon insert)
    lead_id = upsert_lead(
        email=email or None,
        daily_call_volume=body.daily_call_volume,
        medical_specialty=body.medical_specialty.strip(),
        primary_pain_point=(body.primary_pain_point or "").strip(),
        assistant_name=body.assistant_name.strip(),
        voice_gender=body.voice_gender,
        opening_hours=body.opening_hours,
        wants_callback=bool(callback_phone),
        callback_phone=callback_phone or None,
        specialty_other=(body.specialty_other or "").strip() or None,
        medical_specialty_label=(body.medical_specialty_label or "").strip() or None,
        source=body.source or "landing_cta",
    )
    if not lead_id:
        raise HTTPException(status_code=500, detail="Erreur enregistrement lead")

    # 3) Envoi email fondateur en synchrone si email fourni (pas d'envoi si lead téléphone seul)
    if email:
        dashboard_base = (
            os.environ.get("ADMIN_BASE_URL")
            or os.environ.get("FRONT_BASE_URL")
            or os.environ.get("APP_BASE_URL")
            or ""
        ).strip()
        try:
            is_enterprise = body.daily_call_volume == "100+"
            ok, err = send_lead_founder_email(
                lead_id=lead_id,
                email=email,
                daily_call_volume=body.daily_call_volume,
                medical_specialty=body.medical_specialty,
                medical_specialty_label=(body.medical_specialty_label or "").strip() or "",
                specialty_other=(body.specialty_other or "").strip() or "",
                primary_pain_point=(body.primary_pain_point or "").strip(),
                assistant_name=body.assistant_name,
                voice_gender=body.voice_gender,
                opening_hours=body.opening_hours,
                wants_callback=bool(callback_phone),
                callback_phone=callback_phone or "",
                is_enterprise=is_enterprise,
                dashboard_base_url=dashboard_base,
                source=body.source or "landing_cta",
            )
            if not ok:
                logger.warning("lead_founder_email failed: %s", err)
        except Exception as e:
            logger.exception("lead_founder_email exception: %s", e)

    out = {"ok": True, "lead_id": lead_id}
    return out
