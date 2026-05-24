# backend/routes/pre_onboarding.py — POST /api/pre-onboarding/commit (wizard « Créer mon assistant »)
# E2E: commit → lead admin + email interne fondateur + confirmation prospect ; callback-booking → emails fondateur + prospect.
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Header, Query, Request, BackgroundTasks
from pydantic import BaseModel, Field

from backend.leads_pg import count_leads_total, get_lead, lead_exists, update_lead, update_lead_callback_booking, upsert_lead
from backend.pre_onboarding_rate_limit import check_pre_onboarding_commit
from backend.services.email_service import send_lead_founder_email, send_lead_prospect_confirmation_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pre-onboarding", tags=["pre_onboarding"])
public_router = APIRouter(prefix="/api/public", tags=["public_leads"])

VALID_VOLUME = {"<10", "10-25", "25-50", "50-100", "100+", "unknown"}


def _append_lead_note(existing_notes_log: Any, text: str, action: str) -> str:
    entries = []
    try:
        if isinstance(existing_notes_log, str) and existing_notes_log.strip():
            entries = json.loads(existing_notes_log)
        elif isinstance(existing_notes_log, list):
            entries = list(existing_notes_log)
    except Exception:
        entries = []
    entries.append({
        "text": text,
        "action": action,
        "created_at": datetime.utcnow().isoformat() + "Z",
    })
    return json.dumps(entries, ensure_ascii=False)


@router.get("/config")
async def pre_onboarding_config() -> Dict[str, Any]:
    """
    Diagnostic : vérifie que la config Railway est OK pour leads + emails.
    Sans secrets. À appeler pour débug (ex. curl https://api.uwiapp.com/api/pre-onboarding/config).
    """
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL") or ""
    db_ok = bool(db_url.strip())
    to_email = (
        (os.environ.get("FOUNDER_EMAIL") or "").strip()
        or (os.environ.get("ADMIN_EMAIL") or "").strip()
        or (os.environ.get("ADMIN_ALERT_EMAIL") or "").strip()
        or (os.environ.get("REPORT_EMAIL") or "").strip()
        or (os.environ.get("SMTP_EMAIL") or "").strip()
    )
    email_recipient_ok = bool(to_email)
    postmark = bool((os.environ.get("POSTMARK_SERVER_TOKEN") or "").strip())
    smtp = bool((os.environ.get("SMTP_EMAIL") or "").strip() and (os.environ.get("SMTP_PASSWORD") or "").strip())
    email_sender_ok = postmark or smtp
    from backend.security import is_production

    backend_hint = (os.environ.get("RAILWAY_PUBLIC_DOMAIN") or os.environ.get("VERCEL_URL") or "unknown")[:64]
    out = {
        "db_configured": db_ok,
        "email_recipient_configured": email_recipient_ok,
        "email_sender_configured": email_sender_ok,
        "leads_ok": db_ok,
        "emails_ok": email_recipient_ok and email_sender_ok,
    }
    if not is_production():
        out["total_leads_in_db"] = count_leads_total() if db_ok else -1
        out["backend_hint"] = backend_hint
    return out


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


class CallbackBookingBody(BaseModel):
    date: str = Field(..., min_length=10)  # YYYY-MM-DD
    slot: str = Field(..., min_length=1)
    phone: str = Field(default="")


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


class PublicLeadBody(BaseModel):
    source: str = Field(default="landing_create_assistant")
    landing_path: str = Field(default="/creer-assistante")
    cabinet_name: str = Field(default="")
    contact_name: str = Field(default="")
    email: str = Field(default="")
    phone: str = Field(default="")
    profession: str = Field(default="")
    specialty: str = Field(default="")
    city: str = Field(default="")
    tenant_type: str = Field(default="")
    calls_per_day: str = Field(default="unknown")
    has_assistant: Optional[bool] = None
    assistant_name: str = Field(default="")
    pain_point: str = Field(default="")
    desired_channel: str = Field(default="")
    message: str = Field(default="")
    consent: bool = False
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    referrer: Optional[str] = None
    gclid: Optional[str] = None
    fbclid: Optional[str] = None
    honeypot: str = Field(default="")


def _public_calls_to_internal(value: str) -> str:
    raw = (value or "").strip()
    if raw in VALID_VOLUME:
        return raw
    if raw in {"0-10", "0_10"}:
        return "<10"
    if raw in {"10-25", "25-50", "50-100", "100+"}:
        return raw
    return "unknown"


def _public_profession_to_internal_slug(profession: str, specialty: str) -> str:
    p = (profession or "").strip().lower()
    s = (specialty or "").strip().lower()
    merged = f"{p} {s}"
    if "dent" in merged:
        return "dentiste"
    if "kine" in merged or "kiné" in merged:
        return "kinesitherapeute"
    if "infirm" in merged:
        return "infirmier_liberal"
    if "centre" in merged or "maison de santé" in merged:
        return "centre_medical"
    if "général" in merged or "generaliste" in merged or "médecin" in merged or "medecin" in merged:
        return "medecin_generaliste"
    return "autre"


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

    # Diagnostic express (logs Railway) : à comparer avec callback_booking_diagnostic (même deployment_id + db_hash ?)
    _db_url = os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL") or ""
    _db_hash = hashlib.sha256(_db_url.encode()).hexdigest()[:8] if _db_url else "none"
    _deploy_id = os.environ.get("RAILWAY_DEPLOYMENT_ID") or os.environ.get("RAILWAY_REPLICA_ID") or "n/a"
    logger.info(
        "commit_pre_onboarding_diagnostic",
        extra={"lead_id": lead_id, "deployment_id": _deploy_id, "db_hash": _db_hash},
    )

    # Envoi d'un email récap lead dès le commit (comme avant), sans attendre le choix du créneau.
    # Cela garantit qu'un email est bien reçu même si la confirmation de rappel échoue côté infra (lead introuvable, etc.).
    try:
        dashboard_base = (
            os.environ.get("ADMIN_BASE_URL")
            or os.environ.get("FRONT_BASE_URL")
            or os.environ.get("APP_BASE_URL")
            or ""
        ).strip()
        logger.info("commit_pre_onboarding: attempting lead_founder_email", extra={"lead_id": lead_id})
        ok, err = send_lead_founder_email(
            lead_id=lead_id,
            email=email,
            daily_call_volume=body.daily_call_volume,
            medical_specialty=body.medical_specialty.strip(),
            medical_specialty_label=(body.medical_specialty_label or "").strip() or "",
            specialty_other=(body.specialty_other or "").strip() or "",
            primary_pain_point=(body.primary_pain_point or "").strip() or "",
            assistant_name=body.assistant_name.strip(),
            voice_gender=body.voice_gender,
            opening_hours=body.opening_hours,
            wants_callback=bool(callback_phone),
            callback_phone=(callback_phone or "").strip() or "",
            is_enterprise=(body.daily_call_volume == "100+"),
            dashboard_base_url=dashboard_base,
            source=body.source or "landing_cta",
            callback_booking_date=None,
            callback_booking_slot=None,
        )
        if not ok:
            logger.warning("lead_founder_email on commit failed: %s", err)
    except Exception as e:
        logger.exception("lead_founder_email on commit exception: %s", e)

    if email:
        try:
            ok_prospect, err_prospect = send_lead_prospect_confirmation_email(
                to_email=email,
                assistant_name=body.assistant_name.strip(),
            )
            if not ok_prospect:
                logger.warning("lead_prospect_confirmation on commit failed: %s", err_prospect)
        except Exception as e:
            logger.exception("lead_prospect_confirmation on commit exception: %s", e)

    token_out = ""
    try:
        from backend.security import issue_lead_access_token

        token_out = issue_lead_access_token(lead_id)
    except Exception as e:
        logger.warning("issue_lead_access_token failed (JWT_SECRET?): %s", e)

    out: Dict[str, Any] = {"ok": True, "lead_id": lead_id}
    if token_out:
        out["token"] = token_out
    return out


@public_router.post("/leads")
async def public_leads_create(request: Request, body: PublicLeadBody) -> Dict[str, Any]:
    """Endpoint public landing -> CRM leads admin."""
    if (body.honeypot or "").strip():
        raise HTTPException(status_code=400, detail="Requête invalide")
    if not body.consent:
        raise HTTPException(status_code=400, detail="consent requis")

    email = (body.email or "").strip().lower()
    phone = (body.phone or "").strip()
    if not email and not phone:
        raise HTTPException(status_code=400, detail="email ou phone requis")
    if email and not _validate_email(email):
        raise HTTPException(status_code=400, detail="email invalide")

    cabinet_name = (body.cabinet_name or "").strip()
    contact_name = (body.contact_name or "").strip()
    if not cabinet_name and not contact_name:
        raise HTTPException(status_code=400, detail="cabinet_name ou contact_name requis")

    # Anti-spam / rate limit partagé avec le wizard.
    check_pre_onboarding_commit(request, email or phone)

    internal_calls = _public_calls_to_internal(body.calls_per_day)
    specialty_slug = _public_profession_to_internal_slug(body.profession, body.specialty)
    specialty_label = (body.specialty or body.profession or "").strip() or "Cabinet médical"
    assistant_name = (body.assistant_name or "").strip() or ("Assistante" if body.has_assistant is True else "none")
    pain = (body.pain_point or body.message or "Lead landing").strip()
    opening_hours_default = {
        "monday": {"start": "09:00", "end": "18:00", "closed": False},
        "tuesday": {"start": "09:00", "end": "18:00", "closed": False},
        "wednesday": {"start": "09:00", "end": "18:00", "closed": False},
        "thursday": {"start": "09:00", "end": "18:00", "closed": False},
        "friday": {"start": "09:00", "end": "18:00", "closed": False},
        "saturday": {"start": "09:00", "end": "12:00", "closed": True},
        "sunday": {"start": "09:00", "end": "12:00", "closed": True},
    }

    source = (body.source or "landing_create_assistant").strip() or "landing_create_assistant"
    lead_id = upsert_lead(
        email=email or None,
        daily_call_volume=internal_calls,
        medical_specialty=specialty_slug,
        medical_specialty_label=specialty_label,
        specialty_other=(body.specialty or "").strip() or None,
        primary_pain_point=pain[:400],
        assistant_name=assistant_name[:80] or "none",
        voice_gender="female",
        opening_hours=opening_hours_default,
        wants_callback=bool(phone),
        callback_phone=phone or None,
        source=source,
    )
    if not lead_id:
        raise HTTPException(status_code=500, detail="Erreur création lead")

    try:
        lead = get_lead(lead_id)
        existing_log = lead.get("notes_log") if lead else None
        entries = []
        if isinstance(existing_log, str) and existing_log.strip():
            entries = json.loads(existing_log)
        elif isinstance(existing_log, list):
            entries = list(existing_log)
        entries.append(
            {
                "text": f"Lead public: {cabinet_name or contact_name} · source={source}",
                "action": "lead_created_from_landing",
                "created_at": datetime.utcnow().isoformat() + "Z",
                "meta": {
                    "landing_path": body.landing_path,
                    "contact_name": contact_name,
                    "city": body.city,
                    "tenant_type": body.tenant_type,
                    "desired_channel": body.desired_channel,
                    "utm_source": body.utm_source,
                    "utm_medium": body.utm_medium,
                    "utm_campaign": body.utm_campaign,
                    "utm_content": body.utm_content,
                    "utm_term": body.utm_term,
                    "referrer": body.referrer,
                    "gclid": body.gclid,
                    "fbclid": body.fbclid,
                },
            }
        )
        update_lead(lead_id, notes_log=json.dumps(entries, ensure_ascii=False))
    except Exception as e:
        logger.warning("public_leads_create notes_log failed lead_id=%s err=%s", lead_id, e)

    if email:
        try:
            ok_prospect, err_prospect = send_lead_prospect_confirmation_email(
                to_email=email,
                assistant_name=assistant_name[:80] or "votre assistante",
                contact_name=cabinet_name or contact_name,
            )
            if not ok_prospect:
                logger.warning("lead_prospect_confirmation on public_leads failed: %s", err_prospect)
        except Exception as e:
            logger.warning("lead_prospect_confirmation on public_leads exception: %s", e)

    return {"ok": True, "lead_id": lead_id, "message": "Votre demande a bien été reçue."}




def _lead_token_from_request(
    request: Request,
    x_lead_token: Optional[str] = Header(None, alias="X-Lead-Token"),
    token: Optional[str] = Query(None),
) -> Optional[str]:
    return (x_lead_token or token or request.headers.get("x-lead-token") or "").strip() or None


@router.get("/leads/{lead_id}/email")
async def get_lead_email_for_create_account(
    lead_id: str,
    request: Request,
    x_lead_token: Optional[str] = Header(None, alias="X-Lead-Token"),
    token: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """
    Retourne l'email du lead pour le flux create-account (préremplissage).
    Ne retourne l'email que si le lead existe et en a un.
    """
    from backend.security import assert_lead_access

    assert_lead_access(lead_id, _lead_token_from_request(request, x_lead_token, token))
    lead = get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "Lead introuvable")
    email = (lead.get("email") or "").strip()
    return {"email": email or None}


@router.get("/leads/{lead_id}/check")
async def check_lead_exists(
    lead_id: str,
    request: Request,
    x_lead_token: Optional[str] = Header(None, alias="X-Lead-Token"),
    token: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """
    Vérifie si un lead existe (pour diagnostic : landing vs backend même env ?).
    Utilise lead_exists (requête minimale) pour éviter les faux 404 si get_lead échoue (schema).
    Retourne 200 si existe, 404 sinon.
    """
    from backend.security import assert_lead_access, is_production

    assert_lead_access(lead_id, _lead_token_from_request(request, x_lead_token, token))
    if lead_exists(lead_id):
        return {"exists": True}
    lead = get_lead(lead_id)
    if lead:
        return {"exists": True}
    logger.warning("check_lead_404", extra={"lead_id": (lead_id or "")[:36]})
    detail = "Lead introuvable"
    if not is_production():
        total = count_leads_total()
        detail = (
            f"Lead introuvable (total_leads_in_db={total}). "
            "Vérifiez VITE_UWI_API_BASE_URL si total=0."
        )
    raise HTTPException(status_code=404, detail=detail)


def _send_callback_booking_emails_task(
    lead_id: str,
    assistant_name: str,
    date_str: str,
    slot: str,
    phone: str,
    lead_email: str,
    dashboard_base: str,
) -> None:
    """Emails callback-booking en arrière-plan (ne bloque pas la réponse HTTP)."""
    try:
        from backend.services.email_service import (
            send_lead_callback_booking_email,
            send_lead_prospect_confirmation_email,
        )

        ok_founder, err_founder = send_lead_callback_booking_email(
            lead_id=lead_id,
            assistant_name=assistant_name,
            callback_date_iso=date_str,
            callback_slot=slot,
            callback_phone=phone,
            dashboard_base_url=dashboard_base,
        )
        if not ok_founder:
            logger.warning("lead_callback_booking_email failed lead_id=%s: %s", lead_id, err_founder)
    except Exception as e:
        logger.warning("lead_callback_booking_email exception lead_id=%s: %s", lead_id, e)

    if not (lead_email or "").strip():
        return
    try:
        ok_prospect, err_prospect = send_lead_prospect_confirmation_email(
            to_email=lead_email,
            assistant_name=assistant_name,
            callback_date_iso=date_str,
            callback_slot=slot,
            callback_phone=phone,
        )
        if not ok_prospect:
            logger.warning("lead_prospect_callback_confirmation failed lead_id=%s: %s", lead_id, err_prospect)
    except Exception as e:
        logger.warning("lead_prospect_callback_confirmation exception lead_id=%s: %s", lead_id, e)


@router.post("/leads/{lead_id}/callback-booking")
async def callback_booking(
    lead_id: str,
    body: CallbackBookingBody,
    request: Request,
    background_tasks: BackgroundTasks,
    x_lead_token: Optional[str] = Header(None, alias="X-Lead-Token"),
    token: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """
    Enregistre le créneau de rappel choisi (écran finalisation UWI).
    Envoie un email interne (fondateur) + confirmation prospect si email connu.
    """
    from backend.security import assert_lead_access

    assert_lead_access(lead_id, _lead_token_from_request(request, x_lead_token, token))
    # Diagnostic express (logs Railway) : même instance + même DB que commit ?
    _db_url = os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL") or ""
    _db_hash = hashlib.sha256(_db_url.encode()).hexdigest()[:8] if _db_url else "none"
    _deploy_id = os.environ.get("RAILWAY_DEPLOYMENT_ID") or os.environ.get("RAILWAY_REPLICA_ID") or "n/a"
    logger.info(
        "callback_booking_diagnostic",
        extra={
            "lead_id": lead_id,
            "deployment_id": _deploy_id,
            "db_hash": _db_hash,
        },
    )
    import re
    date_str = (body.date or "").strip()[:10]
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        raise HTTPException(status_code=400, detail="date invalide (attendu YYYY-MM-DD)")
    slot = (body.slot or "").strip()
    if not slot:
        raise HTTPException(status_code=400, detail="slot requis")
    phone = (body.phone or "").strip().replace(" ", "")

    lead = get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead introuvable")

    ok = update_lead_callback_booking(lead_id, callback_booking_date=date_str, callback_booking_slot=slot, callback_phone=phone or None)
    if not ok:
        raise HTTPException(status_code=500, detail="Erreur enregistrement créneau")
    try:
        lead_after_booking = get_lead(lead_id) or lead
        update_lead(
            lead_id,
            notes_log=_append_lead_note(
                lead_after_booking.get("notes_log"),
                f"Rappel réservé : {date_str} à {slot}",
                "callback_booking",
            ),
        )
    except Exception as e:
        logger.warning("callback_booking notes_log update failed lead_id=%s: %s", lead_id, e)

    assistant_name = (lead.get("assistant_name") or "Emma").strip()
    lead_email = (lead.get("email") or "").strip().lower()
    dashboard_base = (
        os.environ.get("ADMIN_BASE_URL")
        or os.environ.get("FRONT_BASE_URL")
        or os.environ.get("APP_BASE_URL")
        or ""
    ).strip()
    background_tasks.add_task(
        _send_callback_booking_emails_task,
        lead_id,
        assistant_name,
        date_str,
        slot,
        phone,
        lead_email,
        dashboard_base,
    )

    out: Dict[str, Any] = {"ok": True}
    if lead_email:
        out["prospect_email_sent"] = True
    return out


class CreateAccountBody(BaseModel):
    """Corps pour création compte self-serve depuis un lead. email optionnel si le lead a déjà un email."""
    email: Optional[str] = Field(None, min_length=3, max_length=255)


@router.post("/leads/{lead_id}/create-account")
async def create_account_from_lead(
    lead_id: str,
    body: CreateAccountBody,
    request: Request,
    x_lead_token: Optional[str] = Header(None, alias="X-Lead-Token"),
    token: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """
    Crée un tenant + compte client depuis un lead (parcours self-serve).
    Le prospect peut créer son compte sans passer par l'admin.
    Envoie l'email de bienvenue avec mot de passe temporaire.
    Met à jour le lead (status=converted, tenant_id, notes_log).
    """
    from backend import config
    from backend.auth_pg import pg_create_tenant_user, pg_get_tenant_user_by_email
    from backend.cabinet_profile_pg import (
        sync_normalized_from_params,
        sync_opening_hours_from_booking_rules,
    )
    from backend.tenant_config import convert_opening_hours_to_booking_rules, derive_horaires_text
    from backend.tenants_pg import pg_create_tenant, pg_update_tenant_flags, pg_update_tenant_params
    from backend.services.email_service import send_welcome_email

    if not config.USE_PG_TENANTS:
        raise HTTPException(503, "Création compte self-serve requiert Postgres (USE_PG_TENANTS)")

    from backend.security import assert_lead_access

    assert_lead_access(lead_id, _lead_token_from_request(request, x_lead_token, token))

    lead = get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "Lead introuvable")

    lead_email = (lead.get("email") or "").strip().lower()
    body_email = (body.email or "").strip().lower() if body.email else ""
    if lead_email:
        if body_email and body_email != lead_email:
            raise HTTPException(400, "L'email doit correspondre à celui du lead")
        email = lead_email
    elif body_email:
        email = body_email
    else:
        raise HTTPException(400, "email requis (le lead n'a pas d'email enregistré)")

    existing = pg_get_tenant_user_by_email(email)
    if existing:
        raise HTTPException(409, "Cet email est déjà rattaché à un compte client")

    cabinet_name = (email.split("@")[0] or "Cabinet").strip()[:120]
    sector = (lead.get("medical_specialty") or "medecin_generaliste").strip()
    assistant_name = (lead.get("assistant_name") or "sophie").strip().lower()

    import secrets
    temp_password = secrets.token_urlsafe(10)

    tid = pg_create_tenant(
        name=cabinet_name,
        contact_email=email,
        calendar_provider="none",
        calendar_id="",
        timezone="Europe/Paris",
        status="active",
        plan_key="growth",
    )
    if not tid:
        raise HTTPException(500, "Impossible de créer le compte")

    if not pg_create_tenant_user(
        tid,
        email,
        role="owner",
        password=temp_password,
        must_change_password=True,
    ):
        raise HTTPException(500, "Impossible de créer l'utilisateur")

    if not pg_update_tenant_flags(tid, {"ENABLE_BOOKING": True, "ENABLE_TRANSFER": True, "ENABLE_FAQ": True, "ENABLE_ANTI_LOOP": True}):
        raise HTTPException(500, "Erreur configuration")

    params_payload = {
        "assistant_name": assistant_name,
        "business_name": cabinet_name,
        "sector": sector,
        "contact_email": email,
        "specialty_label": (lead.get("medical_specialty_label") or "").strip(),
        "city": (lead.get("city") or "").strip(),
        "phone_number": (lead.get("callback_phone") or "").strip(),
        "client_onboarding_completed": False,
        "lead_id": lead_id,
        "lead_source": lead.get("source") or "landing_cta",
    }
    if not pg_update_tenant_params(tid, params_payload):
        raise HTTPException(500, "Erreur paramètres")

    booking_rules_final: Dict[str, Any] = {}
    opening_hours = lead.get("opening_hours")
    if isinstance(opening_hours, dict):
        try:
            booking_rules_final = convert_opening_hours_to_booking_rules(opening_hours)
            booking_rules_final["horaires"] = derive_horaires_text(booking_rules_final)
            if not pg_update_tenant_params(tid, booking_rules_final):
                logger.warning("create_account_from_lead: horaires update failed tenant_id=%s", tid)
        except Exception as e:
            logger.warning("create_account_from_lead: horaires conversion failed: %s", e)
            booking_rules_final = {}

    # Init des tables normalisées "Mon cabinet" (non bloquant)
    try:
        sync_normalized_from_params(tid, params_payload)
    except Exception as e:
        logger.warning("create_account_from_lead: sync_normalized_from_params failed tenant_id=%s: %s", tid, e)
    if booking_rules_final:
        try:
            sync_opening_hours_from_booking_rules(tid, booking_rules_final)
        except Exception as e:
            logger.warning("create_account_from_lead: sync_opening_hours failed tenant_id=%s: %s", tid, e)

    ok, err = send_welcome_email(
        email=email,
        client_name=cabinet_name,
        assistant_id=assistant_name,
        plan_key="growth",
        phone_number="",
        temp_password=temp_password,
    )
    if not ok:
        logger.warning("create_account_from_lead welcome email failed: %s", err)

    base_url = (
        os.getenv("CLIENT_APP_ORIGIN") or os.getenv("VITE_UWI_APP_URL") or os.getenv("VITE_SITE_URL") or "https://www.uwiapp.com"
    ).strip().rstrip("/")
    login_url = f"{base_url}/login?email={email}&welcome=1"

    try:
        existing_log = lead.get("notes_log")
        parsed = []
        if isinstance(existing_log, str) and existing_log.strip():
            parsed = json.loads(existing_log)
        elif isinstance(existing_log, list):
            parsed = list(existing_log)
        parsed.append({
            "text": f"Compte créé (self-serve) : {cabinet_name} (id: {tid})",
            "action": "conversion_self_serve",
            "created_at": datetime.utcnow().isoformat() + "Z",
        })
        update_lead(lead_id, status="converted", tenant_id=tid, notes_log=json.dumps(parsed, ensure_ascii=False))
    except Exception as e:
        logger.warning("create_account_from_lead lead sync failed: %s", e)

    return {
        "ok": True,
        "tenant_id": tid,
        "login_url": login_url,
        "message": "Compte créé. Consultez votre email pour le mot de passe temporaire.",
    }
