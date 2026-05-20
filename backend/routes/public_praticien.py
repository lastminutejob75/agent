"""
Fiche publique du praticien.
- GET /api/public/praticiens/{slug} → profil + horaires + motifs de RDV
- POST /api/public/praticiens/{slug}/chat → même moteur que /frontend (widget)
- GET /api/public/praticiens/{slug}/stream/{conv_id} → SSE réponses Clara
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.cabinet_profile_pg import (
    get_assistant_settings as pg_get_assistant_settings,
    get_booking_rules as pg_get_booking_rules,
    get_opening_hours as pg_get_opening_hours,
    get_public_profile_bundle,
    get_tenant_id_by_public_slug,
    list_appointment_reasons as pg_list_appointment_reasons,
)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/public/praticiens", tags=["public_praticien"])


class PublicChatBody(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    conversation_id: Optional[str] = None


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

    tenant_id = get_tenant_id_by_public_slug(safe)
    if not tenant_id:
        raise HTTPException(404, "Praticien introuvable")

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


def _tenant_id_for_slug(slug: str) -> int:
    safe = _slug_safe(slug)
    if not safe:
        raise HTTPException(404, "Praticien introuvable")
    tenant_id = get_tenant_id_by_public_slug(safe)
    if not tenant_id:
        raise HTTPException(404, "Praticien introuvable")
    return int(tenant_id)


@router.post("/{slug}/chat")
async def public_praticien_chat(slug: str, body: PublicChatBody) -> Dict[str, Any]:
    """
    Chat public (fiche praticien) : même engine que le widget /frontend,
    tenant résolu par le slug public (pas de X-Tenant-Key exposé au navigateur).
    """
    from backend.web_chat import start_web_chat

    tenant_id = _tenant_id_for_slug(slug)
    return await start_web_chat(
        tenant_id,
        message=body.message.strip(),
        conversation_id=body.conversation_id,
        channel="web",
    )


@router.get("/{slug}/stream/{conv_id}")
async def public_praticien_chat_stream(slug: str, conv_id: str):
    """SSE des réponses assistant pour une conversation démarrée via POST …/chat."""
    from backend.web_chat import web_chat_stream

    tenant_id = _tenant_id_for_slug(slug)
    return await web_chat_stream(conv_id, expected_tenant_id=tenant_id)
