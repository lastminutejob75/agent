"""Lecture / écriture des demandes RDV issues des pages publiques (/p/:slug)."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from backend.booking_code import create_unique_booking_code_pg
from backend.pg_pool import pg_connection
from backend.pg_tenant_context import set_tenant_id_on_connection
from backend.booking_origin import canonical as booking_origin_canonical

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
                cur.execute(
                    "ALTER TABLE public_bookings ADD COLUMN IF NOT EXISTS booking_code VARCHAR(8)"
                )
                cur.execute(
                    "ALTER TABLE public_bookings ADD COLUMN IF NOT EXISTS google_event_id VARCHAR(256)"
                )
                cur.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_public_bookings_tenant_booking_code
                    ON public_bookings (tenant_id, booking_code)
                    WHERE booking_code IS NOT NULL AND booking_code <> ''
                    """
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
    booking_code: Optional[str] = None,
    google_event_id: Optional[str] = None,
) -> Dict[str, str]:
    ensure_public_bookings_schema()
    start_ts = _parse_iso_ts(start_iso)
    confirmed_at = datetime.now(timezone.utc) if status == "confirmed" else None
    stored_code = (booking_code or "").strip().upper()[:8] or None
    try:
        with pg_connection() as conn:
            if tenant_id is not None:
                set_tenant_id_on_connection(conn, int(tenant_id))
            with conn.cursor() as cur:
                ge = (google_event_id or "").strip()[:256] or None
                if not stored_code:
                    stored_code = create_unique_booking_code_pg(cur, tenant_id)
                cur.execute(
                    """
                    INSERT INTO public_bookings (
                      id, tenant_id, slot_id, slot_label, patient_name, patient_phone,
                      patient_email, motif, source, status, start_iso, created_at, confirmed_at,
                      booking_code, google_event_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s)
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
                        stored_code,
                        ge,
                    ),
                )
            conn.commit()
    except Exception as exc:
        logger.warning("public booking insert skipped: %s", exc)
        if not stored_code:
            from backend.booking_code import create_unique_booking_code_for_tenant

            stored_code = create_unique_booking_code_for_tenant(tenant_id)
    return {"id": booking_id, "booking_code": stored_code or ""}


def _contact_phone_matches(stored: Optional[str], provided: Optional[str]) -> bool:
    from backend.db import normalize_phone_number

    a = normalize_phone_number(stored or "")
    b = normalize_phone_number(provided or "")
    return bool(a and b and a == b)


def _contact_email_matches(stored: Optional[str], provided: Optional[str]) -> bool:
    a = (stored or "").strip().lower()
    b = (provided or "").strip().lower()
    return bool(a and b and a == b)


def lookup_public_bookings(
    tenant_id: int,
    *,
    booking_code: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retourne les RDV publics à venir correspondant aux critères."""
    ensure_public_bookings_schema()
    from backend.booking_code import normalize_booking_code

    code = normalize_booking_code(booking_code) if booking_code else ""
    phone_val = (phone or "").strip()
    email_val = (email or "").strip().lower()
    if not code and not phone_val and not email_val:
        return []

    rows: List[Dict[str, Any]] = []
    try:
        with pg_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                conditions = [
                    "tenant_id = %s",
                    "status IN ('confirmed', 'pending')",
                    "COALESCE(start_iso, created_at) >= NOW() - INTERVAL '1 hour'",
                ]
                params: List[Any] = [tenant_id]
                if code:
                    conditions.append("UPPER(booking_code) = %s")
                    params.append(code)
                elif phone_val or email_val:
                    contact_parts: List[str] = []
                    if phone_val:
                        from backend.db import normalize_phone_number

                        norm_phone = normalize_phone_number(phone_val)
                        contact_parts.append("patient_phone = %s")
                        params.append(norm_phone or phone_val)
                    if email_val:
                        contact_parts.append("LOWER(COALESCE(patient_email, '')) = %s")
                        params.append(email_val)
                    if contact_parts:
                        conditions.append(f"({' OR '.join(contact_parts)})")
                cur.execute(
                    f"""
                    SELECT id, patient_name, patient_phone, patient_email, motif, slot_label,
                           status, start_iso, created_at, booking_code
                    FROM public_bookings
                    WHERE {' AND '.join(conditions)}
                    ORDER BY COALESCE(start_iso, created_at) ASC
                    LIMIT 20
                    """,
                    tuple(params),
                )
                rows = [dict(r) for r in cur.fetchall()]
    except Exception as exc:
        logger.debug("lookup_public_bookings failed tenant=%s: %s", tenant_id, exc)
        return []
    return rows


def get_public_booking_by_id(tenant_id: int, booking_id: str) -> Optional[Dict[str, Any]]:
    ensure_public_bookings_schema()
    try:
        with pg_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, patient_name, patient_phone, patient_email, motif, slot_label,
                           status, start_iso, created_at, booking_code, slot_id, source,
                           google_event_id
                    FROM public_bookings
                    WHERE tenant_id = %s AND id = %s
                    LIMIT 1
                    """,
                    (tenant_id, booking_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception as exc:
        logger.debug("get_public_booking_by_id failed tenant=%s id=%s: %s", tenant_id, booking_id, exc)
        return None


def cancel_public_booking_by_id(tenant_id: int, booking_id: str) -> bool:
    ensure_public_bookings_schema()
    try:
        with pg_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE public_bookings
                    SET status = 'cancelled', cancelled_at = NOW()
                    WHERE tenant_id = %s AND id = %s
                      AND status IN ('confirmed', 'pending')
                    RETURNING id
                    """,
                    (tenant_id, booking_id),
                )
                row = cur.fetchone()
            conn.commit()
            return bool(row)
    except Exception as exc:
        logger.warning("cancel_public_booking_by_id failed tenant=%s id=%s: %s", tenant_id, booking_id, exc)
        return False


def mark_public_booking_rescheduled(tenant_id: int, booking_id: str) -> bool:
    ensure_public_bookings_schema()
    try:
        with pg_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE public_bookings
                    SET status = 'cancelled', cancelled_at = NOW()
                    WHERE tenant_id = %s AND id = %s
                      AND status IN ('confirmed', 'pending')
                    RETURNING id
                    """,
                    (tenant_id, booking_id),
                )
                row = cur.fetchone()
            conn.commit()
            return bool(row)
    except Exception as exc:
        logger.warning("mark_public_booking_rescheduled failed tenant=%s id=%s: %s", tenant_id, booking_id, exc)
        return False


def insert_callback_request(
    *,
    tenant_id: Optional[int],
    name: Optional[str],
    phone: str,
    email: Optional[str],
    reason: str,
    message: Optional[str],
    appointment_source: Optional[str] = None,
    appointment_id: Optional[str] = None,
    unmatched: bool = False,
) -> Optional[str]:
    req_id = str(__import__("uuid").uuid4())
    try:
        with pg_connection() as conn:
            if tenant_id is not None:
                set_tenant_id_on_connection(conn, int(tenant_id))
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS callback_requests (
                      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                      tenant_id BIGINT REFERENCES tenants(tenant_id) ON DELETE SET NULL,
                      appointment_source TEXT,
                      appointment_id TEXT,
                      patient_id BIGINT,
                      name TEXT,
                      phone TEXT NOT NULL,
                      email TEXT,
                      reason TEXT NOT NULL DEFAULT 'other',
                      message TEXT,
                      source TEXT NOT NULL DEFAULT 'public_page',
                      status TEXT NOT NULL DEFAULT 'new',
                      unmatched BOOLEAN NOT NULL DEFAULT FALSE,
                      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                      handled_at TIMESTAMPTZ,
                      handled_by TEXT
                    )
                    """
                )
                cur.execute(
                    """
                    INSERT INTO callback_requests (
                      id, tenant_id, appointment_source, appointment_id, name, phone, email,
                      reason, message, source, status, unmatched
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'public_page', 'new', %s)
                    """,
                    (
                        req_id,
                        tenant_id,
                        appointment_source,
                        appointment_id,
                        (name or "").strip()[:200] or None,
                        phone,
                        (email or "").strip()[:254] or None,
                        (reason or "other").strip()[:80],
                        (message or "").strip()[:2000] or None,
                        unmatched,
                    ),
                )
            conn.commit()
        return req_id
    except Exception as exc:
        logger.warning("insert_callback_request failed tenant=%s: %s", tenant_id, exc)
        return None


CALLBACK_REASON_LABELS = {
    "question_rdv": "Question sur un rendez-vous",
    "modifier": "Modifier un rendez-vous",
    "annuler": "Annuler un rendez-vous",
    "admin": "Question administrative",
    "ordonnance": "Ordonnance / document",
    "other": "Autre demande",
}


def list_callback_requests(
    tenant_id: int,
    *,
    status: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    try:
        with pg_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS callback_requests (
                      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                      tenant_id BIGINT REFERENCES tenants(tenant_id) ON DELETE SET NULL,
                      appointment_source TEXT,
                      appointment_id TEXT,
                      patient_id BIGINT,
                      name TEXT,
                      phone TEXT NOT NULL,
                      email TEXT,
                      reason TEXT NOT NULL DEFAULT 'other',
                      message TEXT,
                      source TEXT NOT NULL DEFAULT 'public_page',
                      status TEXT NOT NULL DEFAULT 'new',
                      unmatched BOOLEAN NOT NULL DEFAULT FALSE,
                      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                      handled_at TIMESTAMPTZ,
                      handled_by TEXT
                    )
                    """
                )
                params: List[Any] = [tenant_id]
                status_filter = ""
                if status:
                    status_filter = " AND status = %s"
                    params.append(status.strip().lower())
                params.append(max(1, min(int(limit), 200)))
                cur.execute(
                    f"""
                    SELECT id, tenant_id, appointment_source, appointment_id, name, phone, email,
                           reason, message, source, status, unmatched, created_at, handled_at, handled_by
                    FROM callback_requests
                    WHERE tenant_id = %s{status_filter}
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in cur.fetchall()]
    except Exception as exc:
        logger.debug("list_callback_requests failed tenant=%s: %s", tenant_id, exc)
        return []


def update_callback_request_status(
    tenant_id: int,
    request_id: str,
    *,
    status: str,
    handled_by: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    clean_status = (status or "").strip().lower()
    if clean_status not in {"processed", "cancelled", "new"}:
        return None
    try:
        with pg_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE callback_requests
                    SET status = %s,
                        handled_at = CASE WHEN %s IN ('processed', 'cancelled') THEN NOW() ELSE handled_at END,
                        handled_by = COALESCE(%s, handled_by)
                    WHERE tenant_id = %s AND id = %s
                    RETURNING id, tenant_id, name, phone, email, reason, message, source, status,
                              unmatched, created_at, handled_at, handled_by
                    """,
                    (
                        clean_status,
                        clean_status,
                        (handled_by or "").strip()[:120] or None,
                        tenant_id,
                        request_id,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
            return dict(row) if row else None
    except Exception as exc:
        logger.warning("update_callback_request_status failed tenant=%s id=%s: %s", tenant_id, request_id, exc)
        return None


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
                           start_iso, created_at, source, booking_code
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
        raw_src = (row.get("source") or "").strip()
        booking_origin_disp = booking_origin_canonical(raw_src or "page_publique")
        slots.append(
            {
                "date": start_local.strftime("%Y-%m-%d"),
                "hour": start_local.strftime("%Hh"),
                "start_iso": start_local.isoformat(),
                "patient": (row.get("patient_name") or "Patient").strip(),
                "patient_phone": (row.get("patient_phone") or "").strip(),
                "motif": (row.get("motif") or "Consultation").strip(),
                "type": (row.get("motif") or "Consultation").strip(),
                "source": "PAGE_PUBLIQUE",
                "booking_origin": booking_origin_disp,
                "done": end_local <= now_local,
                "current": start_local <= now_local < end_local,
                "event_id": str(row.get("id") or ""),
                "appointment_id": None,
                "slot_id": None,
                "can_cancel": False,
                "can_reschedule": False,
                "booking_status": status,
                "slot_label": (row.get("slot_label") or "").strip(),
                "booking_code": (row.get("booking_code") or "").strip(),
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
