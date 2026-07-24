"""Routes authentifiées de la section consulaire."""
from __future__ import annotations

from typing import Any, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.consular_pg import (
    get_application,
    get_post_for_account,
    list_applications,
    list_counter_slots,
)
from backend.routes.tenant import require_tenant_auth


router = APIRouter(prefix="/api/post", tags=["consular"])


ApplicationStatus = Literal[
    "new",
    "incomplete",
    "complete",
    "scheduled",
    "escalated",
    "closed",
]


class PostSummary(BaseModel):
    post_id: UUID
    name: str
    country_code: str
    host_country_code: str
    reference_prefix: str
    timezone: str
    status: str


class ApplicationSummary(BaseModel):
    id: UUID
    reference: str
    channel: Literal["phone", "chat", "whatsapp"]
    lang: Literal["bg", "fr", "en", "ar"]
    purpose: Optional[str] = None
    visa_category: Optional[Literal["A", "C", "D"]] = None
    reclassified_from: Optional[Literal["A", "C", "D"]] = None
    applicant_name: Optional[str] = None
    applicant_phone: Optional[str] = None
    residence: Optional[str] = None
    travel_window: Optional[str] = None
    duration_days: Optional[int] = None
    passport_ok: Optional[bool] = None
    host_nationality: Optional[str] = None
    fee_exempt: bool
    is_minor: bool
    is_first_application: Optional[bool] = None
    schengen_history: Optional[bool] = None
    previous_refusal: bool
    status: ApplicationStatus
    created_at: Any
    qualified_at: Optional[Any] = None


class CounterSlotSummary(BaseModel):
    post_id: UUID
    slot_start: str
    slot_end: str
    visa_category_filter: Optional[Literal["A", "C", "D"]] = None


def _account_id(auth: dict[str, Any]) -> int:
    return int(auth["tenant_id"])


@router.get("/me", response_model=PostSummary)
def post_me(auth: dict[str, Any] = Depends(require_tenant_auth)):
    post = get_post_for_account(_account_id(auth))
    if not post:
        raise HTTPException(404, "Aucun poste consulaire lié à ce compte")
    return post


@router.get("/applications", response_model=list[ApplicationSummary])
def applications_list(
    status: Optional[ApplicationStatus] = None,
    limit: int = Query(100, ge=1, le=500),
    auth: dict[str, Any] = Depends(require_tenant_auth),
):
    return list_applications(_account_id(auth), status=status, limit=limit)


@router.get("/applications/{application_id}")
def application_detail(
    application_id: UUID,
    auth: dict[str, Any] = Depends(require_tenant_auth),
):
    application = get_application(_account_id(auth), application_id)
    if not application:
        raise HTTPException(404, "Demande introuvable")
    return application


@router.get("/counter-slots", response_model=list[CounterSlotSummary])
def counter_slots_list(
    visa_category: Optional[Literal["A", "C", "D"]] = None,
    limit: int = Query(100, ge=1, le=500),
    auth: dict[str, Any] = Depends(require_tenant_auth),
):
    return list_counter_slots(
        _account_id(auth),
        visa_category=visa_category,
        limit=limit,
    )
