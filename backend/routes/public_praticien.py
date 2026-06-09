"""
Fiche publique du praticien.
- GET /api/public/praticiens/{slug} → profil + horaires + motifs de RDV
- POST /api/public/praticiens/{slug}/chat → même moteur que /frontend (widget)
- GET /api/public/praticiens/{slug}/stream/{conv_id} → SSE réponses Clara
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.booking_origin import PUBLIC_PAGE
from backend.cabinet_profile_pg import (
    get_assistant_settings as pg_get_assistant_settings,
    get_booking_rules as pg_get_booking_rules,
    get_opening_hours as pg_get_opening_hours,
    get_public_profile_bundle,
    list_appointment_reasons as pg_list_appointment_reasons,
)
from backend.public_slug_cache import remember_slug_tenant, tenant_id_for_slug
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/public/praticiens", tags=["public_praticien"])


class PublicChatBody(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    conversation_id: Optional[str] = None
    tenant_id: Optional[int] = Field(None, description="Hint depuis la fiche (évite une résolution slug→tenant à chaque message)")


def _slug_safe(slug: str) -> str:
    return "".join(c for c in (slug or "").strip().lower() if c.isalnum() or c in ("-", "_"))[:120]


def _opening_hours_from_params(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = params.get("opening_hours_json") if isinstance(params, dict) else None
    if isinstance(raw, dict) and isinstance(raw.get("opening_hours"), list):
        return raw["opening_hours"]
    if isinstance(raw, list):
        return raw
    return []


def _public_reasons(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Liste réduite aux motifs publics (enabled=True)."""
    out: List[Dict[str, Any]] = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        if not it.get("enabled", True):
            continue
        out.append(
            {
                "label": str(it.get("label") or "").strip(),
                "duration_minutes": int(it.get("duration_minutes") or 30),
                "description": str(it.get("description") or "").strip(),
                "allowed_for_new_patients": bool(it.get("allowed_for_new_patients", True)),
            }
        )
    return [r for r in out if r["label"]]


@router.get("/{slug}")
def public_get_praticien(slug: str) -> Dict[str, Any]:
    """
    Retourne la fiche publique du cabinet/praticien.
    Pas d'auth, pas d'infos sensibles (pas de billing, pas de Vapi, etc.).
    """
    safe = _slug_safe(slug)
    if not safe:
        raise HTTPException(404, "Praticien introuvable")

    tenant_id = tenant_id_for_slug(safe)
    if not tenant_id:
        raise HTTPException(404, "Praticien introuvable")

    remember_slug_tenant(safe, int(tenant_id))
    bundle = get_public_profile_bundle(tenant_id)
    profile = bundle.get("profile") or {}
    params = bundle.get("params") or {}
    if not isinstance(params, dict):
        params = {}

    rules = pg_get_booking_rules(tenant_id) or {}
    opening = pg_get_opening_hours(tenant_id) or _opening_hours_from_params(params)
    assistant = pg_get_assistant_settings(tenant_id) or {}
    reasons = pg_list_appointment_reasons(tenant_id) or []

    cabinet_name = profile.get("cabinet_name") or params.get("business_name") or ""
    practitioner_name = profile.get("practitioner_name") or params.get("practitioner_name") or ""
    if not cabinet_name and not practitioner_name:
        # Profil pas encore initialisé : on évite d'exposer une page vide trompeuse.
        raise HTTPException(404, "Praticien introuvable")

    accepts_new_patients = profile.get("accepts_new_patients")
    if accepts_new_patients is None:
        accepts_new_patients = rules.get("accepts_new_patients", True)

    return {
        "slug": safe,
        "tenant_id": int(tenant_id),
        "cabinet_name": cabinet_name,
        "practitioner_name": practitioner_name,
        "specialty": profile.get("specialty") or params.get("specialty_label") or "",
        "phone": profile.get("phone") or params.get("phone_number") or "",
        "email": profile.get("email") or params.get("contact_email") or "",
        "address_line": profile.get("address_line") or params.get("address_line1") or "",
        "postal_code": profile.get("postal_code") or params.get("postal_code") or "",
        "city": profile.get("city") or params.get("city") or "",
        "website_url": profile.get("website_url") or params.get("website_url") or "",
        "languages": profile.get("languages") or [],
        "practitioner_photo_url": profile.get("practitioner_photo_url") or "",
        "accepts_new_patients": bool(accepts_new_patients),
        "opening_hours": opening,
        "appointment_reasons": _public_reasons(reasons),
        "access_instructions": assistant.get("access_instructions") or params.get("access_instructions") or "",
        "parking_info": assistant.get("parking_info") or params.get("parking_info") or "",
        "pmr_access": bool(assistant.get("pmr_access") or params.get("pmr_access") or False),
        "payment_methods": assistant.get("payment_methods") or params.get("payment_methods") or "",
        "welcome_message": assistant.get("welcome_message") or params.get("welcome_message") or "",
        "assistant_name": assistant.get("assistant_name") or params.get("assistant_name") or "Clara",
    }


def _tenant_id_for_slug(slug: str, hint: Optional[int] = None) -> int:
    safe = _slug_safe(slug)
    if not safe:
        raise HTTPException(404, "Praticien introuvable")
    tenant_id = tenant_id_for_slug(safe, hint)
    if not tenant_id:
        raise HTTPException(404, "Praticien introuvable")
    return int(tenant_id)


@router.get("/{slug}/patient-hint")
async def public_patient_hint(
    request: Request,
    slug: str,
    phone: str = "",
    email: str = "",
) -> Dict[str, Any]:
    """
    Reconnaissance patient connue (téléphone ou email) pour préremplir le formulaire RDV.
    Ne renvoie que le strict nécessaire (pas d'historique médical).

    Rate-limit IP strict (anti-énumération RGPD) : sans ça, un attaquant
    pourrait scanner tous les numéros français pour découvrir qui est patient
    de ce cabinet.
    """
    from backend.db import find_cabinet_client
    from backend.guards import validate_email, validate_phone
    from backend.rate_limit import check_sliding_window, client_ip

    ip = client_ip(request)
    try:
        check_sliding_window(f"patient_hint_ip:{ip}", limit=20, window_sec=60)
        check_sliding_window(f"patient_hint_ip:{ip}", limit=200, window_sec=3600)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))

    tenant_id = _tenant_id_for_slug(slug, None)
    phone_s = (phone or "").strip()
    email_s = (email or "").strip()
    phone_ok = bool(phone_s and validate_phone(phone_s))
    email_ok = bool(email_s and validate_email(email_s))
    if not phone_ok and not email_ok:
        return {"found": False}

    profile = find_cabinet_client(tenant_id, phone=phone_s, email=email_s)
    if not profile:
        return {"found": False}

    display = (
        (profile.get("display_name") or "").strip()
        or (profile.get("validated_name") or "").strip()
        or (profile.get("raw_name") or "").strip()
    )
    return {
        "found": True,
        "displayName": display,
        "name": display,
        "email": (profile.get("email") or "").strip(),
        "phone": (profile.get("phone") or "").strip(),
    }


@router.post("/{slug}/chat")
async def public_praticien_chat(slug: str, body: PublicChatBody) -> Dict[str, Any]:
    """
    Chat public (fiche praticien) : même engine que le widget /frontend,
    tenant résolu par le slug public (pas de X-Tenant-Key exposé au navigateur).
    """
    from backend.web_chat import start_web_chat

    tenant_id = _tenant_id_for_slug(slug, body.tenant_id)
    return await start_web_chat(
        tenant_id,
        message=body.message.strip(),
        conversation_id=body.conversation_id,
        channel="web",
        booking_origin=PUBLIC_PAGE,
    )


@router.get("/{slug}/stream/{conv_id}")
async def public_praticien_chat_stream(slug: str, conv_id: str):
    """
    SSE des réponses assistant.
    Pré-enregistre la session (conv_id peut arriver avant le premier POST, comme le widget /frontend).
    """
    from backend.engine import ENGINE
    from backend.web_chat import _register_web_conv_tenant, ensure_stream, web_chat_stream

    tenant_id = _tenant_id_for_slug(slug)
    cid = (conv_id or "").strip()
    if not cid:
        raise HTTPException(status_code=400, detail="conversation_id invalide")

    session = ENGINE.session_store.get_or_create(cid)
    session.tenant_id = tenant_id
    session.channel = "web"
    session.booking_origin = PUBLIC_PAGE
    _register_web_conv_tenant(tenant_id, cid)
    ensure_stream(cid)
    return await web_chat_stream(cid, expected_tenant_id=tenant_id)
