"""Synchronisation Google Calendar pour les actions publiques (annulation / déplacement)."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def _tenant_calendar_params(tenant_id: int) -> Dict[str, Any]:
    from backend.routes.tenant import _get_tenant_detail

    detail = _get_tenant_detail(tenant_id) or {}
    params = detail.get("params") or {}
    return {
        "detail": detail,
        "params": params,
        "calendar_provider": (params.get("calendar_provider") or "").strip(),
        "calendar_id": (params.get("calendar_id") or "").strip(),
    }


def uses_google_calendar(tenant_id: int) -> bool:
    ctx = _tenant_calendar_params(tenant_id)
    return ctx["calendar_provider"] == "google" and bool(ctx["calendar_id"])


def cancel_google_event(tenant_id: int, event_id: str, *, strict: bool = False) -> bool:
    """Annule un événement Google. Si strict=True, lève HTTPException en cas d'échec."""
    clean_id = (event_id or "").strip()
    if not clean_id:
        return True
    ctx = _tenant_calendar_params(tenant_id)
    if ctx["calendar_provider"] != "google":
        return True
    try:
        from backend.google_calendar import GoogleCalendarService

        service = GoogleCalendarService(ctx["calendar_id"])
        ok = service.cancel_appointment(clean_id)
        if not ok and strict:
            raise HTTPException(502, "Impossible d'annuler le rendez-vous sur Google Calendar.")
        return bool(ok)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("cancel_google_event failed tenant=%s event=%s: %s", tenant_id, clean_id, exc)
        if strict:
            raise HTTPException(502, "Impossible d'annuler le rendez-vous sur Google Calendar.")
        return False


def reschedule_google_event(
    tenant_id: int,
    event_id: str,
    new_start_iso: str,
    new_end_iso: str,
    *,
    timezone: str = "Europe/Paris",
) -> bool:
    clean_id = (event_id or "").strip()
    if not clean_id:
        return False
    ctx = _tenant_calendar_params(tenant_id)
    if ctx["calendar_provider"] != "google":
        return False
    try:
        from backend.google_calendar import GoogleCalendarService

        service = GoogleCalendarService(ctx["calendar_id"])
        return bool(
            service.reschedule_appointment(
                clean_id,
                new_start_iso,
                new_end_iso,
                timezone=timezone,
            )
        )
    except Exception as exc:
        logger.warning(
            "reschedule_google_event failed tenant=%s event=%s: %s",
            tenant_id,
            clean_id,
            exc,
        )
        return False


def slot_window_for_reschedule(
    tenant_id: int,
    slot_id: int,
) -> Optional[Tuple[datetime, datetime, str]]:
    from backend.cabinet_profile_pg import get_booking_rules
    from backend.routes.tenant import _get_slot_window, _get_tenant_detail, _tenant_timezone

    detail = _get_tenant_detail(tenant_id) or {}
    rules = get_booking_rules(tenant_id) or {}
    duration = int(rules.get("duration_minutes") or 15)
    tz_name = _tenant_timezone(detail)
    window = _get_slot_window(tenant_id, int(slot_id), tz_name, duration)
    if not window:
        return None
    start, end = window
    return start, end, tz_name
