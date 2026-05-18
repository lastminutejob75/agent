from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Query

from backend.routes.tenant import (
    AppointmentReasonBody,
    AssistantSettingsBody,
    AvailabilitySettingsBody,
    BillingChangePlanBody,
    BookingRulesBody,
    OpeningHoursBody,
    PreviewMessageBody,
    TenantProfileBody,
    require_tenant_auth,
    tenant_assistant_preview,
    tenant_billing_change_plan,
    tenant_billing_invoices,
    tenant_billing_portal_session,
    tenant_billing_summary,
    tenant_calendar_status,
    tenant_create_appointment_reason,
    tenant_delete_appointment_reason,
    tenant_get_appointment_reasons,
    tenant_get_assistant_settings,
    tenant_get_availability_settings,
    tenant_get_booking_rules,
    tenant_get_opening_hours,
    tenant_get_profile,
    tenant_patch_appointment_reason,
    tenant_patch_assistant_settings,
    tenant_patch_availability_settings,
    tenant_patch_booking_rules,
    tenant_patch_opening_hours,
    tenant_patch_profile,
    tenant_profile_summary,
    tenant_test_booking_rule,
)

router = APIRouter(prefix="/api/client", tags=["client"])


@router.get("/profile-summary")
def client_profile_summary(auth: dict = Depends(require_tenant_auth)):
    return tenant_profile_summary(auth)


@router.get("/profile")
def client_get_profile(auth: dict = Depends(require_tenant_auth)):
    return tenant_get_profile(auth)


@router.patch("/profile")
def client_patch_profile(body: TenantProfileBody, auth: dict = Depends(require_tenant_auth)):
    return tenant_patch_profile(body, auth)


@router.get("/opening-hours")
def client_get_opening_hours(auth: dict = Depends(require_tenant_auth)):
    return tenant_get_opening_hours(auth)


@router.patch("/opening-hours")
def client_patch_opening_hours(body: OpeningHoursBody, auth: dict = Depends(require_tenant_auth)):
    return tenant_patch_opening_hours(body, auth)


@router.get("/availability-settings")
def client_get_availability_settings(auth: dict = Depends(require_tenant_auth)):
    return tenant_get_availability_settings(auth)


@router.patch("/availability-settings")
def client_patch_availability_settings(body: AvailabilitySettingsBody, auth: dict = Depends(require_tenant_auth)):
    return tenant_patch_availability_settings(body, auth)


@router.get("/booking-rules")
def client_get_booking_rules(auth: dict = Depends(require_tenant_auth)):
    return tenant_get_booking_rules(auth)


@router.patch("/booking-rules")
def client_patch_booking_rules(body: BookingRulesBody, auth: dict = Depends(require_tenant_auth)):
    return tenant_patch_booking_rules(body, auth)


@router.get("/appointment-reasons")
def client_get_appointment_reasons(auth: dict = Depends(require_tenant_auth)):
    return tenant_get_appointment_reasons(auth)


@router.post("/appointment-reasons")
def client_create_appointment_reason(body: AppointmentReasonBody, auth: dict = Depends(require_tenant_auth)):
    return tenant_create_appointment_reason(body, auth)


@router.patch("/appointment-reasons/{reason_id}")
def client_patch_appointment_reason(reason_id: str, body: Dict[str, Any], auth: dict = Depends(require_tenant_auth)):
    return tenant_patch_appointment_reason(reason_id, body, auth)


@router.delete("/appointment-reasons/{reason_id}")
def client_delete_appointment_reason(reason_id: str, auth: dict = Depends(require_tenant_auth)):
    return tenant_delete_appointment_reason(reason_id, auth)


@router.get("/assistant-settings")
def client_get_assistant_settings(auth: dict = Depends(require_tenant_auth)):
    return tenant_get_assistant_settings(auth)


@router.patch("/assistant-settings")
def client_patch_assistant_settings(body: AssistantSettingsBody, auth: dict = Depends(require_tenant_auth)):
    return tenant_patch_assistant_settings(body, auth)


@router.post("/assistant-preview")
def client_assistant_preview(body: PreviewMessageBody, auth: dict = Depends(require_tenant_auth)):
    return tenant_assistant_preview(body, auth)


@router.post("/test-booking-rule")
def client_test_booking_rule(body: PreviewMessageBody, auth: dict = Depends(require_tenant_auth)):
    return tenant_test_booking_rule(body, auth)


@router.get("/calendar/status")
def client_calendar_status(auth: dict = Depends(require_tenant_auth)):
    return tenant_calendar_status(auth)


@router.get("/billing/summary")
def client_billing_summary(auth: dict = Depends(require_tenant_auth)):
    return tenant_billing_summary(auth)


@router.get("/billing/invoices")
def client_billing_invoices(
    auth: dict = Depends(require_tenant_auth),
    limit: int = Query(10, ge=1, le=50),
):
    return tenant_billing_invoices(auth, limit)


@router.post("/billing/portal-session")
def client_billing_portal_session(auth: dict = Depends(require_tenant_auth)):
    return tenant_billing_portal_session(auth)


@router.post("/billing/change-plan")
def client_billing_change_plan(body: BillingChangePlanBody, auth: dict = Depends(require_tenant_auth)):
    return tenant_billing_change_plan(body, auth)
