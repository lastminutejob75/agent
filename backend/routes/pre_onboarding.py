# backend/routes/pre_onboarding.py — POST /api/pre-onboarding/commit (wizard "Créer votre assistante")
# E2E test: Landing → /creer-assistante → remplir wizard → commit (email + modal) → voir lead dans /admin/leads → email fondateur (FOUNDER_EMAIL/ADMIN_EMAIL). Voir landing/README.md § Test E2E Wizard Lead.
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.leads_pg import count_leads_total, get_lead, lead_exists, update_lead, update_lead_callback_booking, upsert_lead
from backend.pre_onboarding_rate_limit import check_pre_onboarding_commit
from backend.services.email_service import (
    send_lead_founder_email,
    send_pre_onboarding_admin_notification_email,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pre-onboarding", tags=["pre_onboarding"])

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
    total_leads = count_leads_total() if db_ok else -1
    backend_hint = (os.environ.get("RAILWAY_PUBLIC_DOMAIN") or os.environ.get("VERCEL_URL") or "unknown")[:64]
    return {
        "db_configured": db_ok,
        "email_recipient_configured": email_recipient_ok,
        "email_sender_configured": email_sender_ok,
        "leads_ok": db_ok,
        "emails_ok": email_recipient_ok and email_sender_ok,
        "total_leads_in_db": total_leads,
        "backend_hint": backend_hint,
    }
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

    # Notification interne dédiée pour l'équipe UWI : nouveau lead à traiter depuis le wizard.
    try:
        admin_base = (
            os.environ.get("ADMIN_BASE_URL")
            or os.environ.get("FRONT_BASE_URL")
            or os.environ.get("APP_BASE_URL")
            or ""
        ).strip().rstrip("/")
        opening_hours_pretty = json.dumps(body.opening_hours, ensure_ascii=False)
        admin_lead_url = f"{admin_base}/admin/leads/{lead_id}" if admin_base else ""
        ok, err = send_pre_onboarding_admin_notification_email(
            assistant_name=body.assistant_name.strip(),
            medical_specialty_label=(body.medical_specialty_label or "").strip() or body.medical_specialty.strip(),
            email=email,
            callback_phone=callback_phone,
            opening_hours_pretty=opening_hours_pretty,
            source=body.source or "landing_cta",
            admin_lead_url=admin_lead_url,
        )
        if not ok:
            logger.warning("pre_onboarding_admin_notification failed: %s", err)
    except Exception as e:
        logger.exception("pre_onboarding_admin_notification exception: %s", e)

    out = {"ok": True, "lead_id": lead_id}
    return out




@router.get("/leads/{lead_id}/email")
async def get_lead_email_for_create_account(lead_id: str) -> Dict[str, Any]:
    """
    Retourne l'email du lead pour le flux create-account (préremplissage).
    Ne retourne l'email que si le lead existe et en a un.
    """
    lead = get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "Lead introuvable")
    email = (lead.get("email") or "").strip()
    return {"email": email or None}


@router.get("/leads/{lead_id}/check")
async def check_lead_exists(lead_id: str) -> Dict[str, Any]:
    """
    Vérifie si un lead existe (pour diagnostic : landing vs backend même env ?).
    Utilise lead_exists (requête minimale) pour éviter les faux 404 si get_lead échoue (schema).
    Retourne 200 si existe, 404 sinon.
    """
    if lead_exists(lead_id):
        return {"exists": True}
    total = count_leads_total()
    lead = get_lead(lead_id)
    if lead:
        return {"exists": True}
    # lead_exists=False et get_lead=None → lead absent ou DB différente
    logger.warning(
        "check_lead_404",
        extra={
            "lead_id": (lead_id or "")[:36],
            "total_leads_in_db": total,
            "hint": "0 leads → commits vont peut-être vers un autre backend (VITE_UWI_API_BASE_URL)" if total == 0 else "lead_id absent de cette base",
        },
    )
    raise HTTPException(status_code=404, detail="Lead introuvable")


@router.post("/leads/{lead_id}/callback-booking")
async def callback_booking(lead_id: str, body: CallbackBookingBody) -> Dict[str, Any]:
    """
    Enregistre le créneau de rappel choisi (écran finalisation UWI).
    Met à jour le lead puis envoie l'email recap lead au fondateur (un seul email, avec créneau).
    """
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

    # Envoi email avec le RDV (créneau de rappel) — un seul email par lead
    dashboard_base = (
        os.environ.get("ADMIN_BASE_URL")
        or os.environ.get("FRONT_BASE_URL")
        or os.environ.get("APP_BASE_URL")
        or ""
    ).strip()
    lead_after = get_lead(lead_id) or lead
    email_sent = False
    email_error = None
    try:
        oh = lead_after.get("opening_hours")
        if isinstance(oh, str):
            import json
            try:
                oh = json.loads(oh) if oh else {}
            except Exception:
                oh = {}
        if not isinstance(oh, dict):
            oh = {}
        logger.info("callback_booking: attempting lead_founder_email", extra={"lead_id": lead_id})
        ok, err = send_lead_founder_email(
            lead_id=lead_id,
            email=(lead_after.get("email") or "").strip(),
            daily_call_volume=lead_after.get("daily_call_volume") or "",
            medical_specialty=lead_after.get("medical_specialty") or "",
            medical_specialty_label=(lead_after.get("medical_specialty_label") or "").strip() or "",
            specialty_other=(lead_after.get("specialty_other") or "").strip() or "",
            primary_pain_point=(lead_after.get("primary_pain_point") or "").strip() or "",
            assistant_name=(lead_after.get("assistant_name") or "").strip() or "",
            voice_gender=lead_after.get("voice_gender") or "",
            opening_hours=oh,
            wants_callback=bool(lead_after.get("callback_phone") or phone),
            callback_phone=(lead_after.get("callback_phone") or phone or "").strip() or "",
            is_enterprise=lead_after.get("is_enterprise") is True,
            dashboard_base_url=dashboard_base,
            source=(lead_after.get("source") or "landing_cta").strip() or "landing_cta",
            callback_booking_date=date_str,
            callback_booking_slot=slot,
        )
        email_sent = ok
        if not ok:
            email_error = err or "unknown"
            logger.warning("lead_founder_email after callback_booking failed: %s", err)
        else:
            logger.info("lead_founder_email after callback_booking sent ok", extra={"lead_id": lead_id})
    except Exception as e:
        email_error = str(e)
        logger.exception("lead_founder_email after callback_booking exception: %s", e)

    return {"ok": True, "email_sent": email_sent, "email_error": email_error}


class CreateAccountBody(BaseModel):
    """Corps pour création compte self-serve depuis un lead. email optionnel si le lead a déjà un email."""
    email: Optional[str] = Field(None, min_length=3, max_length=255)


@router.post("/leads/{lead_id}/create-account")
async def create_account_from_lead(lead_id: str, body: CreateAccountBody) -> Dict[str, Any]:
    """
    Crée un tenant + compte client depuis un lead (parcours self-serve).
    Le prospect peut créer son compte sans passer par l'admin.
    Envoie l'email de bienvenue avec mot de passe temporaire.
    Met à jour le lead (status=converted, tenant_id, notes_log).
    """
    from backend import config
    from backend.auth_pg import pg_create_tenant_user, pg_get_tenant_user_by_email
    from backend.tenant_config import convert_opening_hours_to_booking_rules, derive_horaires_text
    from backend.tenants_pg import pg_create_tenant, pg_update_tenant_flags, pg_update_tenant_params
    from backend.services.email_service import send_welcome_email

    if not config.USE_PG_TENANTS:
        raise HTTPException(503, "Création compte self-serve requiert Postgres (USE_PG_TENANTS)")

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

    if not pg_create_tenant_user(tid, email, role="owner", password=temp_password):
        raise HTTPException(500, "Impossible de créer l'utilisateur")

    if not pg_update_tenant_flags(tid, {"ENABLE_BOOKING": True, "ENABLE_TRANSFER": True, "ENABLE_FAQ": True, "ENABLE_ANTI_LOOP": True}):
        raise HTTPException(500, "Erreur configuration")

    params_payload = {
        "assistant_name": assistant_name,
        "sector": sector,
        "contact_email": email,
        "specialty_label": (lead.get("medical_specialty_label") or "").strip(),
        "client_onboarding_completed": False,
        "lead_id": lead_id,
        "lead_source": lead.get("source") or "landing_cta",
    }
    if not pg_update_tenant_params(tid, params_payload):
        raise HTTPException(500, "Erreur paramètres")

    opening_hours = lead.get("opening_hours")
    if isinstance(opening_hours, dict):
        try:
            rules = convert_opening_hours_to_booking_rules(opening_hours)
            rules["horaires"] = derive_horaires_text(rules)
            if not pg_update_tenant_params(tid, rules):
                logger.warning("create_account_from_lead: horaires update failed tenant_id=%s", tid)
        except Exception as e:
            logger.warning("create_account_from_lead: horaires conversion failed: %s", e)

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
