"""Endpoints publics : lookup, annulation, déplacement et demande de rappel."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.db import normalize_phone_number
from backend.guards import validate_email, validate_phone
from backend.public_appointment_actions import cancel_appointment, lookup_appointments, reschedule_appointment
from backend.public_bookings_pg import insert_callback_request
from backend.public_slug_cache import tenant_id_for_slug
from backend.rate_limit import check_sliding_window, client_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/public", tags=["public_appointment_actions"])


class PublicAppointmentLookupBody(BaseModel):
    phone: Optional[str] = Field(None, max_length=40)
    email: Optional[str] = Field(None, max_length=254)
    bookingCode: Optional[str] = Field(None, max_length=16)


class PublicAppointmentCancelBody(BaseModel):
    actionToken: str = Field(..., min_length=10)
    phone: Optional[str] = Field(None, max_length=40)
    email: Optional[str] = Field(None, max_length=254)
    reason: Optional[str] = Field(None, max_length=300)


class PublicAppointmentRescheduleBody(BaseModel):
    actionToken: str = Field(..., min_length=10)
    phone: Optional[str] = Field(None, max_length=40)
    email: Optional[str] = Field(None, max_length=254)
    newSlotId: str = Field(..., min_length=1, max_length=80)
    slotLabel: Optional[str] = Field(None, max_length=140)
    startIso: Optional[str] = Field(None, max_length=64)
    endIso: Optional[str] = Field(None, max_length=64)
    slotSource: Optional[str] = Field(None, max_length=20)


class PublicCallbackRequestBody(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    phone: str = Field(..., min_length=5, max_length=40)
    email: Optional[str] = Field(None, max_length=254)
    reason: str = Field("other", max_length=80)
    message: Optional[str] = Field(None, max_length=2000)
    actionToken: Optional[str] = Field(None, max_length=2000)


def _resolve_tenant_id(slug: str) -> int:
    clean = (slug or "").strip().lower()
    if not clean:
        raise HTTPException(404, "Cabinet introuvable.")
    tenant_id = tenant_id_for_slug(clean)
    if tenant_id is None:
        raise HTTPException(404, "Cabinet introuvable.")
    return int(tenant_id)


def _rate_limit_public_action(request: Request, slug: str, prefix: str) -> None:
    ip = client_ip(request)
    try:
        check_sliding_window(f"{prefix}_ip:{ip}", limit=10, window_sec=60)
        check_sliding_window(f"{prefix}_ip:{ip}", limit=60, window_sec=3600)
        check_sliding_window(f"{prefix}_slug:{slug}", limit=30, window_sec=60)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))


def _normalize_lookup_body(body: PublicAppointmentLookupBody) -> PublicAppointmentLookupBody:
    phone_raw = (body.phone or "").strip()
    email_raw = (body.email or "").strip().lower()
    if phone_raw and not validate_phone(phone_raw):
        raise HTTPException(422, "Numero de telephone invalide.")
    if email_raw and not validate_email(email_raw):
        raise HTTPException(422, "Adresse email invalide.")
    return body.model_copy(
        update={
            "phone": normalize_phone_number(phone_raw) or phone_raw or None,
            "email": email_raw or None,
            "bookingCode": (body.bookingCode or "").strip() or None,
        }
    )


def _require_contact_verification(phone: Optional[str], email: Optional[str]) -> None:
    if not (phone or "").strip() and not (email or "").strip():
        raise HTTPException(422, "Indiquez le telephone ou l'email associe au rendez-vous.")


@router.post("/{slug}/appointments/lookup")
def public_appointments_lookup(slug: str, body: PublicAppointmentLookupBody, request: Request) -> Dict[str, Any]:
    _rate_limit_public_action(request, slug, "public_lookup")
    tenant_id = _resolve_tenant_id(slug)
    payload = _normalize_lookup_body(body)
    return lookup_appointments(
        tenant_id,
        phone=payload.phone,
        email=payload.email,
        booking_code=payload.bookingCode,
    )


@router.post("/{slug}/appointments/cancel")
def public_appointments_cancel(slug: str, body: PublicAppointmentCancelBody, request: Request) -> Dict[str, Any]:
    _rate_limit_public_action(request, slug, "public_cancel")
    _resolve_tenant_id(slug)
    phone = normalize_phone_number(body.phone or "") or (body.phone or "").strip() or None
    email = (body.email or "").strip().lower() or None
    _require_contact_verification(phone, email)
    return cancel_appointment(
        action_token=body.actionToken,
        phone=phone,
        email=email,
        reason=(body.reason or "").strip() or None,
    )


@router.post("/{slug}/appointments/reschedule")
def public_appointments_reschedule(slug: str, body: PublicAppointmentRescheduleBody, request: Request) -> Dict[str, Any]:
    _rate_limit_public_action(request, slug, "public_reschedule")
    _resolve_tenant_id(slug)
    phone = normalize_phone_number(body.phone or "") or (body.phone or "").strip() or None
    email = (body.email or "").strip().lower() or None
    _require_contact_verification(phone, email)
    return reschedule_appointment(
        action_token=body.actionToken,
        phone=phone,
        email=email,
        new_slot_id=str(body.newSlotId).strip(),
        slug=slug,
        slot_label=(body.slotLabel or "").strip() or None,
        start_iso=(body.startIso or "").strip() or None,
        end_iso=(body.endIso or "").strip() or None,
        slot_source=(body.slotSource or "").strip() or None,
    )


@router.post("/{slug}/callback-requests")
def public_callback_request(slug: str, body: PublicCallbackRequestBody, request: Request) -> Dict[str, Any]:
    _rate_limit_public_action(request, slug, "public_callback")
    tenant_id = _resolve_tenant_id(slug)
    if not validate_phone(body.phone):
        raise HTTPException(422, "Numero de telephone invalide.")
    email = (body.email or "").strip().lower()
    if email and not validate_email(email):
        raise HTTPException(422, "Adresse email invalide.")
    phone = normalize_phone_number(body.phone) or body.phone.strip()
    req_id = insert_callback_request(
        tenant_id=tenant_id,
        name=body.name.strip(),
        phone=phone,
        email=email or None,
        reason=(body.reason or "other").strip(),
        message=(body.message or "").strip() or None,
        unmatched=False,
    )
    if not req_id:
        raise HTTPException(503, "Impossible d'enregistrer votre demande pour le moment.")
    return {"ok": True, "requestId": req_id}
