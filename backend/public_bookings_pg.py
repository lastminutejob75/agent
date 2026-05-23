"""Lecture / écriture des demandes RDV issues des pages publiques (/p/:slug)."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from backend.pg_pool import pg_connection
from backend.pg_tenant_context import set_tenant_id_on_connection

logger = logging.getLogger(__name__)

_SCHEMA_READY = False


def ensure_public_bookings_schema() -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS public_bookings (
                      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                      tenant_id BIGINT REFERENCES tenants(tenant_id) ON DELETE SET NULL,
                      slot_id VARCHAR(80),
                      slot_label VARCHAR(140),
                      patient_name VARCHAR(200) NOT NULL,
                      patient_phone VARCHAR(40) NOT NULL,
                      patient_email VARCHAR(254),
                      motif VARCHAR(120),
                      status VARCHAR(20) NOT NULL DEFAULT 'pending',
                      source VARCHAR(40) DEFAULT 'page_publique',
                      start_iso TIMESTAMPTZ,
                      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                      confirmed_at TIMESTAMPTZ,
                      cancelled_at TIMESTAMPTZ
                    )
                    """
                )
                cur.execute(
                    "ALTER TABLE public_bookings ADD COLUMN IF NOT EXISTS patient_email VARCHAR(254)"
                )
                cur.execute(
                    "ALTER TABLE public_bookings ADD COLUMN IF NOT EXISTS start_iso TIMESTAMPTZ"
                )
                cur.execute(
                    "ALTER TABLE public_bookings ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'pending'"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_public_bookings_tenant_created "
                    "ON public_bookings (tenant_id, created_at DESC)"
                )
            conn.commit()
        _SCHEMA_READY = True
    except Exception as exc:
        logger.warning("public_bookings schema ensure skipped: %s", exc)


def insert_public_booking(
    *,
    booking_id: str,
    tenant_id: Optional[int],
    slot_id: str,
    slot_label: str,
    patient_name: str,
    patient_phone: str,
    patient_email: Optional[str],
    motif: str,
    source: str,
    status: str,
    start_iso: Optional[str],
) -> str:
    ensure_public_bookings_schema()
    start_ts = _parse_iso_ts(start_iso)
    confirmed_at = datetime.now(timezone.utc) if status == "confirmed" else None
    try:
        with pg_connection() as conn:
            if tenant_id is not None:
                set_tenant_id_on_connection(conn, int(tenant_id))
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public_bookings (
                      id, tenant_id, slot_id, slot_label, patient_name, patient_phone,
                      patient_email, motif, source, status, start_iso, created_at, confirmed_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s)
                    """,
                    (
                        booking_id,
                        tenant_id,
                        slot_id,
                        slot_label,
                        patient_name,
                        patient_phone,
                        (patient_email or "").strip()[:254] or None,
                        motif,
                        source,
                        status,
                        start_ts,
                        confirmed_at,
                    ),
                )
            conn.commit()
    except Exception as exc:
        logger.warning("public booking insert skipped: %s", exc)
    return booking_id


def count_public_bookings(
    tenant_id: int,
    start: str,
    end: str,
    *,
    statuses: Optional[List[str]] = None,
) -> int:
    ensure_public_bookings_schema()
    statuses = statuses or ["confirmed", "pending"]
    try:
        with pg_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM public_bookings
                    WHERE tenant_id = %s
                      AND created_at >= %s::timestamptz
                      AND created_at <= %s::timestamptz
                      AND status = ANY(%s)
                    """,
                    (tenant_id, start, end, statuses),
                )
                row = cur.fetchone()
                return int(row["c"] or 0) if row else 0
    except Exception as exc:
        logger.debug("count_public_bookings failed tenant=%s: %s", tenant_id, exc)
        return 0


def latest_public_booking(tenant_id: int) -> Optional[Dict[str, Any]]:
    ensure_public_bookings_schema()
    try:
        with pg_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT patient_name, slot_label, status, created_at, start_iso
                    FROM public_bookings
                    WHERE tenant_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (tenant_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception as exc:
        logger.debug("latest_public_booking failed tenant=%s: %s", tenant_id, exc)
        return None


def fetch_public_bookings_for_agenda(
    tenant_id: int,
    day_start: datetime,
    day_end: datetime,
    tz_name: str,
    now_local: datetime,
    *,
    include_past_on_date: bool,
) -> List[Dict[str, Any]]:
    """Convertit public_bookings en slots agenda (page publique + chat)."""
    ensure_public_bookings_schema()
    slots: List[Dict[str, Any]] = []
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("Europe/Paris")
    try:
        with pg_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, patient_name, patient_phone, motif, slot_label, status,
                           start_iso, created_at
                    FROM public_bookings
                    WHERE tenant_id = %s
                      AND status IN ('confirmed', 'pending')
                      AND COALESCE(start_iso, created_at) >= %s
                      AND COALESCE(start_iso, created_at) < %s
                    ORDER BY COALESCE(start_iso, created_at) ASC
                    """,
                    (
                        tenant_id,
                        day_start.astimezone(timezone.utc),
                        day_end.astimezone(timezone.utc),
                    ),
                )
                rows = [dict(r) for r in cur.fetchall()]
    except Exception as exc:
        logger.debug("fetch_public_bookings_for_agenda failed tenant=%s: %s", tenant_id, exc)
        return slots

    for row in rows:
        start_local = _booking_start_local(row, tz)
        if not start_local:
            continue
        if not include_past_on_date and start_local < now_local:
            continue
        end_local = start_local + timedelta(minutes=30)
        status = (row.get("status") or "pending").strip()
        slots.append(
            {
                "hour": start_local.strftime("%Hh"),
                "patient": (row.get("patient_name") or "Patient").strip(),
                "patient_phone": (row.get("patient_phone") or "").strip(),
                "type": (row.get("motif") or "Consultation").strip(),
                "source": "PAGE_PUBLIQUE",
                "done": end_local <= now_local,
                "current": start_local <= now_local < end_local,
                "event_id": str(row.get("id") or ""),
                "appointment_id": None,
                "slot_id": None,
                "can_cancel": False,
                "can_reschedule": False,
                "booking_status": status,
                "slot_label": (row.get("slot_label") or "").strip(),
            }
        )
    return slots


def _parse_iso_ts(raw: Optional[str]) -> Optional[datetime]:
    value = (raw or "").strip()
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _booking_start_local(row: Dict[str, Any], tz: ZoneInfo) -> Optional[datetime]:
    start_iso = row.get("start_iso")
    if start_iso:
        if isinstance(start_iso, datetime):
            dt = start_iso
        else:
            dt = _parse_iso_ts(str(start_iso))
        if dt:
            return dt.astimezone(tz)

    created = row.get("created_at")
    base_date = None
    if isinstance(created, datetime):
        base_date = created.astimezone(tz).date()
    elif created:
        try:
            base_date = datetime.fromisoformat(str(created).replace("Z", "+00:00")).astimezone(tz).date()
        except Exception:
            base_date = None

    label = (row.get("slot_label") or "").strip().lower()
    hour, minute = _parse_time_from_label(label)
    if base_date and hour is not None:
        return datetime(base_date.year, base_date.month, base_date.day, hour, minute or 0, tzinfo=tz)
    if isinstance(created, datetime):
        return created.astimezone(tz)
    return None


def _parse_time_from_label(label: str) -> tuple[Optional[int], Optional[int]]:
    match = re.search(r"(\d{1,2})[:h](\d{2})", label)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r"(\d{1,2})h(\d{0,2})?", label)
    if match:
        minute = int(match.group(2) or 0)
        return int(match.group(1)), minute
    return None, None
