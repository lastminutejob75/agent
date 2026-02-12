# backend/calendar_adapter.py
"""
Interface calendrier par tenant.
Provider par tenant (google/none) avec fallback sur config global.
Ne pas imposer Google Calendar : tenant peut avoir provider=none.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol

from backend import config
from backend.tenant_config import get_params

logger = logging.getLogger(__name__)

# Schéma params_json : {"calendar_provider": "google"|"none", "calendar_id": "xxx@..."}
CALENDAR_PROVIDER_KEY = "calendar_provider"
CALENDAR_ID_KEY = "calendar_id"


# Sentinel pour provider=none (pas d'accès agenda)
PROVIDER_NONE_SENTINEL = {"provider": "none"}


class CalendarAdapter(Protocol):
    """Interface minimale pour un provider calendrier."""

    def get_free_slots(
        self,
        date: datetime,
        duration_minutes: int = 15,
        start_hour: int = 9,
        end_hour: int = 18,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """Retourne les créneaux libres pour une date."""
        ...

    def book_appointment(
        self,
        start_time: str,
        end_time: str,
        patient_name: str,
        patient_contact: str,
        motif: str,
    ) -> Optional[str]:
        """Crée un RDV. Retourne event_id ou None."""
        ...

    def can_propose_slots(self) -> bool:
        """True si le provider peut proposer des créneaux (pas provider=none)."""
        ...

    def find_booking_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Recherche un RDV par nom. Retourne dict ou None (ou PROVIDER_NONE_SENTINEL si none)."""
        ...

    def cancel_booking(self, event_id: str) -> bool:
        """Annule un RDV. Retourne True si succès."""
        ...


class _GoogleCalendarAdapter:
    """Wrapper autour de GoogleCalendarService."""

    def __init__(self, calendar_id: str, tenant_id: int = 1):
        self._calendar_id = calendar_id
        self._tenant_id = tenant_id
        self._service = None

    def _get_service(self):
        if self._service is not None:
            return self._service
        try:
            from backend.google_calendar import GoogleCalendarService
            self._service = GoogleCalendarService(self._calendar_id)
            return self._service
        except Exception as e:
            logger.error("GoogleCalendarAdapter init: %s", e)
            return None

    def get_free_slots(
        self,
        date: datetime,
        duration_minutes: int = 15,
        start_hour: int = 9,
        end_hour: int = 18,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        svc = self._get_service()
        if not svc:
            return []
        return svc.get_free_slots(
            date=date,
            duration_minutes=duration_minutes,
            start_hour=start_hour,
            end_hour=end_hour,
            limit=limit,
        )

    def book_appointment(
        self,
        start_time: str,
        end_time: str,
        patient_name: str,
        patient_contact: str,
        motif: str,
    ) -> Optional[str]:
        svc = self._get_service()
        if not svc:
            return None
        return svc.book_appointment(
            start_time=start_time,
            end_time=end_time,
            patient_name=patient_name,
            patient_contact=patient_contact,
            motif=motif,
        )

    def can_propose_slots(self) -> bool:
        return True

    def find_booking_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        svc = self._get_service()
        if not svc:
            return None
        try:
            events = svc.list_upcoming_events(days=30)
            name_lower = name.lower()
            for event in events:
                summary = (event.get("summary") or "").lower()
                description = (event.get("description") or "").lower()
                if name_lower in summary or name_lower in description:
                    start = event.get("start", {}).get("dateTime", "")
                    label = "votre rendez-vous"
                    if start:
                        try:
                            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                            days_fr = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
                            months_fr = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
                            label = f"{days_fr[dt.weekday()]} {dt.day} {months_fr[dt.month - 1]} à {dt.hour}h{dt.minute:02d}"
                        except Exception:
                            pass
                    logger.info("find_booking_by_name tenant_id=%s calendar_id=%s name=%s found", self._tenant_id, self._calendar_id[:20] + "...", name[:20])
                    return {
                        "event_id": event.get("id"),
                        "label": label,
                        "start": start,
                        "end": event.get("end", {}).get("dateTime", ""),
                        "summary": event.get("summary", ""),
                    }
            logger.info("find_booking_by_name tenant_id=%s calendar_id=%s name=%s not_found", self._tenant_id, self._calendar_id[:20] + "...", name[:20])
            return None
        except Exception as e:
            logger.error("find_booking_by_name tenant_id=%s: %s", self._tenant_id, e)
            return None

    def cancel_booking(self, event_id: str) -> bool:
        svc = self._get_service()
        if not svc:
            return False
        ok = svc.cancel_appointment(event_id)
        if ok:
            logger.info("cancel_booking tenant_id=%s calendar_id=%s event_id=%s", self._tenant_id, self._calendar_id[:20] + "...", event_id[:20] + "..." if len(event_id) > 20 else event_id)
        return ok


class _NoneCalendarAdapter:
    """
    Provider "none" : pas d'agenda connecté.
    Ne propose pas de créneaux, ne book pas.
    UX : collecte demande + transfert humain (flow séparé).
    """

    def get_free_slots(
        self,
        date: datetime,
        duration_minutes: int = 15,
        start_hour: int = 9,
        end_hour: int = 18,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        return []

    def book_appointment(
        self,
        start_time: str,
        end_time: str,
        patient_name: str,
        patient_contact: str,
        motif: str,
    ) -> Optional[str]:
        return None

    def can_propose_slots(self) -> bool:
        return False

    def find_booking_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        return PROVIDER_NONE_SENTINEL

    def cancel_booking(self, event_id: str) -> bool:
        return False


def get_calendar_adapter(session: Any) -> Optional[CalendarAdapter]:
    """
    Retourne l'adapter calendrier pour le tenant de la session.
    Migration sans downtime : fallback sur config global si tenant sans params.

    Returns:
        _GoogleCalendarAdapter | _NoneCalendarAdapter | None
        - GoogleAdapter : provider=google ou pas de config (legacy)
        - NoneAdapter : provider=none
        - None : pas de credentials Google (SQLite fallback)
    """
    tenant_id = getattr(session, "tenant_id", None) or config.DEFAULT_TENANT_ID
    params = get_params(tenant_id)

    provider = (params.get(CALENDAR_PROVIDER_KEY) or "").strip().lower()
    calendar_id = (params.get(CALENDAR_ID_KEY) or "").strip()

    # provider=none : pas de créneaux, pas de booking
    if provider == "none":
        logger.info("[CAL_ADAPTER] tenant_id=%s provider=none calendar_id=n/a", tenant_id)
        return _NoneCalendarAdapter()

    # provider=google ou pas de config (legacy)
    if not calendar_id:
        calendar_id = getattr(config, "GOOGLE_CALENDAR_ID", None) or ""

    if not calendar_id or not getattr(config, "SERVICE_ACCOUNT_FILE", None):
        return None  # SQLite fallback (comportement actuel)

    cal_short = calendar_id[:24] + "..." if len(calendar_id) > 24 else calendar_id
    logger.info("[CAL_ADAPTER] tenant_id=%s provider=google calendar_id=%s", tenant_id, cal_short)
    return _GoogleCalendarAdapter(calendar_id, tenant_id)
