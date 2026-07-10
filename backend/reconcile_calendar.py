"""
Réconciliation périodique entre Google Calendar (source de vérité) et le miroir
local UWI (`appointments` + `slots`).

Objectif : détecter et corriger les divergences silencieuses qui peuvent apparaître
quand l'écriture miroir échoue après un succès Google (ex : annulation depuis le
dashboard où Google OK + DB locale KO).

Principes :
- **Conservateur** : on ne touche jamais à Google depuis le job, uniquement au miroir local
- **Idempotent** : peut être relancé autant de fois que voulu sans effet de bord
- **Multi-tenant** : itère sur tous les tenants ayant `calendar_provider=google`
- **Fenêtre glissante** : aujourd'hui → +30 jours par défaut

Cas couverts :
1. **Miroir orphelin** : un `appointment` UWI existe mais aucun event Google
   correspondant (par date+contact) → on supprime le miroir et libère le slot.
   Cause typique : annulation depuis le dashboard avec écriture local KO,
   ou suppression manuelle dans Google par le praticien.

2. **Event Google `RDV - ` orphelin** (sans miroir UWI) : on logue uniquement.
   On ne tente pas de recréer le miroir car on n'a pas toutes les infos
   (slot_id UWI requis, contact_type...).

Usage :
    from backend.reconcile_calendar import reconcile_all_tenants, start_background_job
    # Manuel
    report = reconcile_all_tenants(window_days=30)
    # Automatique (au démarrage de l'app)
    start_background_job(interval_seconds=600)  # toutes les 10 min
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_JOB_THREAD: Optional[threading.Thread] = None
_JOB_STOP_EVENT = threading.Event()


def _get_google_tenants() -> List[int]:
    """Retourne les tenant_id ayant calendar_provider=google configuré."""
    try:
        from backend.tenants_pg import pg_fetch_tenants, pg_get_tenant_params
    except Exception as e:
        logger.warning("reconcile_calendar: cannot import tenants_pg: %s", e)
        return [1]

    tenants_result = pg_fetch_tenants(include_inactive=False)
    if not tenants_result:
        return [1]
    tenants_list, _ = tenants_result
    google_tenants: List[int] = []
    for t in tenants_list or []:
        tid = int(t.get("tenant_id") or 0)
        if not tid:
            continue
        try:
            params_tuple = pg_get_tenant_params(tid)
            params = (params_tuple[0] if params_tuple else {}) or {}
            if str(params.get("calendar_provider") or "").strip().lower() == "google":
                google_tenants.append(tid)
        except Exception as e:
            logger.debug("reconcile_calendar: skip tenant %s params error: %s", tid, e)
    return google_tenants


def _list_google_events(tenant_id: int, calendar_id: str, day_start: datetime, day_end: datetime) -> List[Dict[str, Any]]:
    """Liste les événements Google sur la fenêtre. Retourne [] en cas d'erreur."""
    try:
        from backend.google_calendar import GoogleCalendarService
        service = GoogleCalendarService(calendar_id)
        result = service.service.events().list(
            calendarId=calendar_id,
            timeMin=day_start.isoformat(),
            timeMax=day_end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            fields="items(id,summary,description,start,end)",
        ).execute()
        return result.get("items", []) or []
    except Exception as e:
        logger.warning("reconcile_calendar: list_events failed tenant_id=%s err=%s", tenant_id, e)
        return []


def _list_local_mirror_appointments(tenant_id: int, day_start: datetime, day_end: datetime, tz_name: str) -> Dict[str, List[Dict[str, Any]]]:
    """Réutilise l'index existant dans routes.tenant pour rester cohérent."""
    try:
        from backend.routes.tenant import _load_local_appointments_for_window
        return _load_local_appointments_for_window(tenant_id, day_start, day_end, tz_name)
    except Exception as e:
        logger.warning("reconcile_calendar: load mirror failed tenant_id=%s err=%s", tenant_id, e)
        return {}


def _build_google_lookup(tenant_id: int, events: List[Dict[str, Any]], tz_name: str) -> Dict[str, List[Dict[str, Any]]]:
    """Index Google events par clé (YYYY-MM-DDTHH:MM)."""
    try:
        from backend.routes.tenant import _appointment_lookup_key, _parse_dt, _get_zoneinfo, _extract_google_description_line
        from backend.db import normalize_phone_number
    except Exception as e:
        logger.warning("reconcile_calendar: cannot import helpers: %s", e)
        return {}

    tz = _get_zoneinfo(tz_name)
    index: Dict[str, List[Dict[str, Any]]] = {}
    for event in events:
        raw_start = (event.get("start") or {}).get("dateTime") or (event.get("start") or {}).get("date")
        start_dt = _parse_dt(raw_start, tz_name)
        if not start_dt:
            continue
        start_local = start_dt.astimezone(tz)
        summary = (event.get("summary") or "").strip()
        description = (event.get("description") or "").strip()
        is_uwi = summary.startswith("RDV - ") or "Patient:" in description
        contact = _extract_google_description_line(description, "Contact") if is_uwi else ""
        name = summary.replace("RDV - ", "", 1).strip() if summary.startswith("RDV - ") else summary
        key = _appointment_lookup_key(start_local)
        if not key:
            continue
        index.setdefault(key, []).append({
            "event_id": event.get("id") or "",
            "summary": summary,
            "is_uwi": is_uwi,
            "contact": normalize_phone_number(contact) if contact else "",
            "raw_contact": contact,
            "name": name,
            "motif": _extract_google_description_line(description, "Motif") if is_uwi else "",
            "start_iso": start_local.isoformat(),
        })
    return index


def _matches(google_entry: Dict[str, Any], local_appt: Dict[str, Any]) -> bool:
    """Match un event Google et un appointment local par contact ou nom."""
    try:
        from backend.db import normalize_phone_number
    except Exception:
        normalize_phone_number = lambda x: str(x or "").strip()

    g_contact = google_entry.get("contact") or ""
    a_contact = normalize_phone_number(local_appt.get("contact") or "")
    if g_contact and a_contact and g_contact == a_contact:
        return True
    g_name = (google_entry.get("name") or "").strip().lower()
    a_name = (local_appt.get("name") or "").strip().lower()
    if g_name and a_name and (g_name in a_name or a_name in g_name):
        return True
    return False


def reconcile_tenant(tenant_id: int, window_days: int = 30, dry_run: bool = False) -> Dict[str, Any]:
    """
    Réconcilie un tenant Google.

    Returns:
        dict avec stats : { "tenant_id", "google_events", "local_mirrors",
                            "orphan_mirrors_removed", "orphan_google_events", "errors" }
    """
    report: Dict[str, Any] = {
        "tenant_id": tenant_id,
        "google_events": 0,
        "local_mirrors": 0,
        "orphan_mirrors_removed": 0,
        "orphan_google_events": 0,
        "orphan_google_mirrors_recreated": 0,
        "errors": [],
        "dry_run": dry_run,
    }

    try:
        from backend.routes.admin import _get_tenant_detail
        from backend.routes.tenant import _tenant_timezone, _get_zoneinfo
        from backend.db import cancel_booking_sqlite
    except Exception as e:
        report["errors"].append(f"import_failed: {e}")
        return report

    detail = _get_tenant_detail(tenant_id)
    if not detail:
        report["errors"].append("tenant_not_found")
        return report

    params = (detail.get("params") or {})
    if (params.get("calendar_provider") or "").strip() != "google":
        report["errors"].append("not_google_provider")
        return report
    calendar_id = (params.get("calendar_id") or "").strip()
    if not calendar_id:
        report["errors"].append("missing_calendar_id")
        return report

    tz_name = _tenant_timezone(detail)
    tz = _get_zoneinfo(tz_name)
    now_local = datetime.now(tz)
    day_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=max(1, int(window_days)))

    google_events = _list_google_events(tenant_id, calendar_id, day_start, day_end)
    google_lookup = _build_google_lookup(tenant_id, google_events, tz_name)
    local_index = _list_local_mirror_appointments(tenant_id, day_start, day_end, tz_name)

    report["google_events"] = sum(len(v) for v in google_lookup.values())
    report["local_mirrors"] = sum(len(v) for v in local_index.values())

    # 1. Miroirs orphelins : appointments UWI sans event Google correspondant
    for key, local_appts in local_index.items():
        google_entries = google_lookup.get(key, [])
        for appt in local_appts:
            matched = any(_matches(g, appt) for g in google_entries)
            if matched:
                continue
            logger.warning(
                "[RECONCILE] orphan_mirror tenant_id=%s appt_id=%s slot_id=%s key=%s contact=%s dry_run=%s",
                tenant_id, appt.get("id"), appt.get("slot_id"), key, appt.get("contact"), dry_run,
            )
            if dry_run:
                report["orphan_mirrors_removed"] += 1
                continue
            try:
                ok = cancel_booking_sqlite(
                    {"id": int(appt.get("id") or 0), "slot_id": int(appt.get("slot_id") or 0)},
                    tenant_id=tenant_id,
                )
                if ok:
                    report["orphan_mirrors_removed"] += 1
                else:
                    report["errors"].append(f"cancel_failed_appt_{appt.get('id')}")
            except Exception as e:
                report["errors"].append(f"cancel_exception_appt_{appt.get('id')}: {e}")

    # 2. Events Google UWI orphelins : présents dans Google mais pas dans le miroir local
    for key, google_entries in google_lookup.items():
        local_appts = local_index.get(key, [])
        for g in google_entries:
            if not g.get("is_uwi"):
                continue
            matched = any(_matches(g, a) for a in local_appts)
            if matched:
                continue
            report["orphan_google_events"] += 1
            logger.info(
                "[RECONCILE] orphan_google_event tenant_id=%s event_id=%s key=%s name=%s contact=%s",
                tenant_id, g.get("event_id"), key, g.get("name"), g.get("contact"),
            )
            if dry_run:
                continue
            try:
                from backend import tools_booking

                event_id = str(g.get("event_id") or "").strip()
                start_iso = str(g.get("start_iso") or "").strip()
                if not event_id or not start_iso:
                    continue
                contact = str(g.get("raw_contact") or g.get("contact") or "").strip()
                session = SimpleNamespace(
                    tenant_id=tenant_id,
                    conv_id="calendar-reconciliation",
                    booking_origin=None,
                    booking_code=None,
                    qualif_data=SimpleNamespace(
                        name=str(g.get("name") or "Client"),
                        contact=contact,
                        contact_type="email" if "@" in contact else "phone",
                        motif=str(g.get("motif") or "Consultation"),
                    ),
                )
                if tools_booking._mirror_google_booking_to_internal(session, start_iso, event_id):
                    report["orphan_google_mirrors_recreated"] += 1
                else:
                    report["errors"].append(f"mirror_recreate_failed_event_{event_id}")
            except Exception as e:
                report["errors"].append(f"mirror_recreate_exception_event_{g.get('event_id')}: {e}")

    return report


def reconcile_all_tenants(window_days: int = 30, dry_run: bool = False) -> List[Dict[str, Any]]:
    """Réconcilie tous les tenants Google-connected. Renvoie la liste des reports."""
    reports: List[Dict[str, Any]] = []
    tenants = _get_google_tenants()
    if not tenants:
        logger.info("[RECONCILE] no google tenants to process")
        return reports
    for tid in tenants:
        try:
            r = reconcile_tenant(tid, window_days=window_days, dry_run=dry_run)
            reports.append(r)
            logger.info(
                "[RECONCILE] tenant_id=%s google=%s local=%s orphan_mirrors_removed=%s orphan_google=%s errors=%s",
                tid, r["google_events"], r["local_mirrors"],
                r["orphan_mirrors_removed"], r["orphan_google_events"], len(r["errors"]),
            )
        except Exception as e:
            logger.error("[RECONCILE] tenant_id=%s failed: %s", tid, e, exc_info=True)
            reports.append({"tenant_id": tid, "errors": [str(e)]})
    return reports


def _job_loop(interval_seconds: int, window_days: int, dry_run: bool) -> None:
    logger.info("[RECONCILE] background job started interval=%ss window_days=%s dry_run=%s",
                interval_seconds, window_days, dry_run)
    while not _JOB_STOP_EVENT.is_set():
        try:
            reconcile_all_tenants(window_days=window_days, dry_run=dry_run)
        except Exception as e:
            logger.error("[RECONCILE] job iteration failed: %s", e, exc_info=True)
        if _JOB_STOP_EVENT.wait(timeout=interval_seconds):
            break
    logger.info("[RECONCILE] background job stopped")


def start_background_job(interval_seconds: int = 600, window_days: int = 30, dry_run: bool = False) -> bool:
    """Démarre le thread daemon de réconciliation. No-op si déjà démarré."""
    global _JOB_THREAD
    if _JOB_THREAD is not None and _JOB_THREAD.is_alive():
        logger.info("[RECONCILE] background job already running")
        return False
    if os.environ.get("UWI_RECONCILE_DISABLED", "").strip() in ("1", "true", "yes"):
        logger.info("[RECONCILE] disabled via UWI_RECONCILE_DISABLED")
        return False
    _JOB_STOP_EVENT.clear()
    _JOB_THREAD = threading.Thread(
        target=_job_loop,
        args=(interval_seconds, window_days, dry_run),
        daemon=True,
        name="reconcile-calendar",
    )
    _JOB_THREAD.start()
    return True


def stop_background_job() -> None:
    """Arrête le thread daemon (utile pour les tests)."""
    _JOB_STOP_EVENT.set()
