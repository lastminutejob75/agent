"""Lecture / écriture des demandes RDV issues des pages publiques (/p/:slug)."""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from backend.booking_code import create_unique_booking_code_pg
from backend.db import normalize_phone_number
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
    start_ts = resolve_booking_start_ts(start_iso, slot_label)
    if not start_ts:
        logger.warning(
            "public_booking insert without start_iso tenant=%s slot_label=%r",
            tenant_id,
            (slot_label or "")[:80],
        )
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


def attach_public_booking_google_event(
    tenant_id: int,
    booking_id: str,
    google_event_id: Optional[str],
) -> bool:
    ge = (google_event_id or "").strip()[:256] or None
    if not ge:
        return False
    try:
        with pg_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE public_bookings
                    SET google_event_id = %s,
                        status = 'confirmed',
                        confirmed_at = COALESCE(confirmed_at, NOW())
                    WHERE tenant_id = %s AND id = %s
                    RETURNING id
                    """,
                    (ge, tenant_id, booking_id),
                )
                row = cur.fetchone()
            conn.commit()
            return bool(row)
    except Exception as exc:
        logger.warning("attach_public_booking_google_event failed tenant=%s id=%s: %s", tenant_id, booking_id, exc)
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
    source: str = "public_page",
    call_id: Optional[str] = None,
    notify: bool = True,
) -> Optional[str]:
    req_id = str(__import__("uuid").uuid4())
    clean_source = (source or "public_page").strip()[:32] or "public_page"
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
                _ensure_callback_requests_link_columns(cur)
                cur.execute(
                    """
                    INSERT INTO callback_requests (
                      id, tenant_id, appointment_source, appointment_id, name, phone, email,
                      reason, message, source, status, unmatched, call_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'new', %s, %s)
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
                        clean_source,
                        unmatched,
                        (call_id or "").strip()[:120] or None,
                    ),
                )
            conn.commit()
        if notify and req_id:
            _notify_cabinet_callback_request(
                tenant_id=int(tenant_id or 0),
                request_id=req_id,
                name=(name or "").strip()[:200] or None,
                phone=phone,
                reason=(reason or "other").strip(),
                message=(message or "").strip() or None,
                source=clean_source,
                email=(email or "").strip() or None,
                call_id=(call_id or "").strip() or None,
            )
        return req_id
    except Exception as exc:
        logger.warning("insert_callback_request failed tenant=%s: %s", tenant_id, exc)
        return None


def _notify_cabinet_callback_request(
    *,
    tenant_id: int,
    request_id: str,
    name: Optional[str],
    phone: str,
    reason: str,
    message: Optional[str],
    source: str,
    email: Optional[str] = None,
    call_id: Optional[str] = None,
) -> None:
    if not tenant_id or not request_id:
        return
    try:
        from backend.services.callback_notifications import notify_cabinet_callback_request

        notify_cabinet_callback_request(
            tenant_id=tenant_id,
            request_id=request_id,
            name=name or "Patient",
            phone=phone,
            reason=reason,
            message=message,
            source=source,
            email=email,
            call_id=call_id,
        )
    except Exception as exc:
        logger.debug("callback notification skipped tenant=%s: %s", tenant_id, exc)


CALLBACK_REASON_LABELS = {
    "question_rdv": "Question sur un rendez-vous",
    "modifier": "Modifier un rendez-vous",
    "annuler": "Annuler un rendez-vous",
    "admin": "Question administrative",
    "ordonnance": "Ordonnance / document",
    "other": "Autre demande",
}

_HANDOFF_REASON_TO_CALLBACK = {
    "explicit_practitioner_request": "other",
    "explicit_human_request": "other",
    "urgent_non_vital_case": "admin",
    "medical_question_requires_practitioner": "ordonnance",
    "medical_sensitive": "ordonnance",
    "technical_failure": "other",
    "too_many_retries": "other",
    "identity_uncertain": "other",
    "fallback_transfer": "other",
    "start_unclear": "other",
}

_LIVE_HANDOFF_STATUSES = frozenset(
    {
        "live_attempted",
        "live_forwarding_confirmed",
        "live_connected",
        "live_failed",
        "live_unconfirmed_timeout",
    }
)


def _handoff_reason_to_callback_reason(reason: str) -> str:
    clean = (reason or "").strip().lower()
    return _HANDOFF_REASON_TO_CALLBACK.get(clean, "other")


def _handoff_status_to_callback_status(handoff_status: str) -> str:
    clean = (handoff_status or "").strip().lower()
    if clean == "processed":
        return "processed"
    if clean == "cancelled":
        return "cancelled"
    return "new"


def _callback_status_to_handoff_status(callback_status: str) -> Optional[str]:
    clean = (callback_status or "").strip().lower()
    if clean == "processed":
        return "processed"
    if clean == "cancelled":
        return "cancelled"
    return None


def _ensure_callback_requests_link_columns(cur) -> None:
    cur.execute("ALTER TABLE callback_requests ADD COLUMN IF NOT EXISTS call_id TEXT")
    cur.execute("ALTER TABLE callback_requests ADD COLUMN IF NOT EXISTS handoff_id BIGINT")


def _build_callback_message_from_handoff(handoff: Dict[str, Any]) -> Optional[str]:
    summary = str(handoff.get("summary") or "").strip()
    excerpt = str(handoff.get("transcript_excerpt") or "").strip()
    if summary and excerpt and excerpt not in summary:
        return f"{summary}\n\n{excerpt}"[:2000]
    return (summary or excerpt or "")[:2000] or None


def upsert_callback_from_handoff(tenant_id: int, handoff: Dict[str, Any]) -> Optional[str]:
    """Crée ou met à jour une demande de rappel unifiée à partir d'un handoff vocal."""
    handoff_id = int(handoff.get("id") or 0)
    if not handoff_id:
        return None
    call_id = str(handoff.get("call_id") or "").strip()
    phone = str(handoff.get("patient_phone") or "").strip()
    unmatched = False
    if not phone:
        phone = "+33000000000"
        unmatched = True
    name = str(
        handoff.get("display_name")
        or handoff.get("validated_name")
        or handoff.get("raw_name")
        or "Patient"
    ).strip()[:200]
    reason = _handoff_reason_to_callback_reason(str(handoff.get("reason") or ""))
    message = _build_callback_message_from_handoff(handoff)
    status = _handoff_status_to_callback_status(str(handoff.get("status") or ""))
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
                _ensure_callback_requests_link_columns(cur)
                cur.execute(
                    """
                    SELECT id
                    FROM callback_requests
                    WHERE tenant_id = %s AND handoff_id = %s
                    LIMIT 1
                    """,
                    (tenant_id, handoff_id),
                )
                existing = cur.fetchone()
                created_new = False
                if existing:
                    req_id = str(existing["id"])
                    cur.execute(
                        """
                        UPDATE callback_requests
                        SET name = %s,
                            phone = %s,
                            reason = %s,
                            message = %s,
                            call_id = %s,
                            status = %s,
                            unmatched = %s,
                            source = 'vocal_agent',
                            handled_at = CASE
                                WHEN %s IN ('processed', 'cancelled') AND handled_at IS NULL THEN NOW()
                                ELSE handled_at
                            END
                        WHERE tenant_id = %s AND handoff_id = %s
                        """,
                        (
                            name or None,
                            phone,
                            reason,
                            message,
                            call_id or None,
                            status,
                            unmatched,
                            status,
                            tenant_id,
                            handoff_id,
                        ),
                    )
                else:
                    req_id = str(__import__("uuid").uuid4())
                    created_new = True
                    cur.execute(
                        """
                        INSERT INTO callback_requests (
                          id, tenant_id, name, phone, reason, message, source, status,
                          unmatched, call_id, handoff_id
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, 'vocal_agent', %s, %s, %s, %s)
                        """,
                        (
                            req_id,
                            tenant_id,
                            name or None,
                            phone,
                            reason,
                            message,
                            status,
                            unmatched,
                            call_id or None,
                            handoff_id,
                        ),
                    )
            conn.commit()
        if created_new and req_id and status == "new":
            _notify_cabinet_callback_request(
                tenant_id=tenant_id,
                request_id=req_id,
                name=name or None,
                phone=phone,
                reason=reason,
                message=message,
                source="vocal_agent",
                call_id=call_id or None,
            )
        return req_id
    except Exception as exc:
        logger.warning(
            "upsert_callback_from_handoff failed tenant=%s handoff_id=%s: %s",
            tenant_id,
            handoff_id,
            exc,
        )
        return None


def sync_callback_status_from_handoff(tenant_id: int, handoff: Dict[str, Any]) -> None:
    handoff_id = int(handoff.get("id") or 0)
    if not handoff_id:
        return
    status = _handoff_status_to_callback_status(str(handoff.get("status") or ""))
    try:
        with pg_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                _ensure_callback_requests_link_columns(cur)
                cur.execute(
                    """
                    UPDATE callback_requests
                    SET status = %s,
                        handled_at = CASE
                            WHEN %s IN ('processed', 'cancelled') AND handled_at IS NULL THEN NOW()
                            ELSE handled_at
                        END
                    WHERE tenant_id = %s AND handoff_id = %s
                    """,
                    (status, status, tenant_id, handoff_id),
                )
            conn.commit()
    except Exception as exc:
        logger.debug(
            "sync_callback_status_from_handoff failed tenant=%s handoff_id=%s: %s",
            tenant_id,
            handoff_id,
            exc,
        )


def sync_handoff_status_from_callback(tenant_id: int, handoff_id: Optional[int], callback_status: str) -> None:
    if not handoff_id:
        return
    target = _callback_status_to_handoff_status(callback_status)
    if not target:
        return
    try:
        from backend.handoffs import update_handoff_status

        update_handoff_status(tenant_id, int(handoff_id), status=target)
    except Exception as exc:
        logger.debug(
            "sync_handoff_status_from_callback failed tenant=%s handoff_id=%s: %s",
            tenant_id,
            handoff_id,
            exc,
        )


def get_callback_request_by_call_id(tenant_id: int, call_id: str) -> Optional[Dict[str, Any]]:
    clean_call_id = (call_id or "").strip()
    if not clean_call_id:
        return None
    try:
        with pg_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                _ensure_callback_requests_link_columns(cur)
                cur.execute(
                    """
                    SELECT id, tenant_id, name, phone, email, reason, message, source, status,
                           unmatched, created_at, handled_at, handled_by, call_id, handoff_id
                    FROM callback_requests
                    WHERE tenant_id = %s AND call_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (tenant_id, clean_call_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception as exc:
        logger.debug("get_callback_request_by_call_id failed tenant=%s call_id=%s: %s", tenant_id, clean_call_id, exc)
        return None


def get_callback_request_by_id(tenant_id: int, request_id: str) -> Optional[Dict[str, Any]]:
    try:
        with pg_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                _ensure_callback_requests_link_columns(cur)
                cur.execute(
                    """
                    SELECT id, tenant_id, name, phone, email, reason, message, source, status,
                           unmatched, created_at, handled_at, handled_by, call_id, handoff_id
                    FROM callback_requests
                    WHERE tenant_id = %s AND id = %s
                    LIMIT 1
                    """,
                    (tenant_id, request_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception as exc:
        logger.debug("get_callback_request_by_id failed tenant=%s id=%s: %s", tenant_id, request_id, exc)
        return None


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
                _ensure_callback_requests_link_columns(cur)
                params: List[Any] = [tenant_id]
                status_sql = ""
                if status:
                    status_sql = " AND status = %s"
                    params.append(status.strip().lower())
                params.append(max(1, min(int(limit), 200)))
                try:
                    cur.execute(
                        f"""
                        SELECT cr.id, cr.tenant_id, cr.appointment_source, cr.appointment_id, cr.name, cr.phone, cr.email,
                               cr.reason, cr.message, cr.source, cr.status, cr.unmatched, cr.created_at, cr.handled_at,
                               cr.handled_by, cr.call_id, cr.handoff_id,
                               h.status AS handoff_status, h.priority AS handoff_priority, h.mode AS handoff_mode
                        FROM callback_requests cr
                        LEFT JOIN human_handoffs h
                          ON h.tenant_id = cr.tenant_id AND h.id = cr.handoff_id
                        WHERE cr.tenant_id = %s{status_sql.replace("status", "cr.status")}
                        ORDER BY cr.created_at DESC
                        LIMIT %s
                        """,
                        tuple(params),
                    )
                except Exception:
                    cur.execute(
                        f"""
                        SELECT id, tenant_id, appointment_source, appointment_id, name, phone, email,
                               reason, message, source, status, unmatched, created_at, handled_at, handled_by,
                               call_id, handoff_id
                        FROM callback_requests
                        WHERE tenant_id = %s{status_sql}
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
                      AND COALESCE(confirmed_at, created_at) >= %s::timestamptz
                      AND COALESCE(confirmed_at, created_at) < %s::timestamptz
                      AND status = ANY(%s)
                    """,
                    (tenant_id, start, end, statuses),
                )
                row = cur.fetchone()
                return int(row["c"] or 0) if row else 0
    except Exception as exc:
        logger.debug("count_public_bookings failed tenant=%s: %s", tenant_id, exc)
        return 0


def list_public_bookings_created_between(
    tenant_id: int,
    start: str,
    end: str,
    *,
    statuses: Optional[List[str]] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """RDV publics/chat enregistrés dans l'intervalle (created_at)."""
    ensure_public_bookings_schema()
    statuses = statuses or ["confirmed", "pending"]
    safe_limit = max(1, min(int(limit or 50), 100))
    try:
        with pg_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, patient_name, patient_phone, motif, slot_label, status,
                           start_iso, created_at, confirmed_at, source, booking_code
                    FROM public_bookings
                    WHERE tenant_id = %s
                      AND COALESCE(confirmed_at, created_at) >= %s::timestamptz
                      AND COALESCE(confirmed_at, created_at) < %s::timestamptz
                      AND status = ANY(%s)
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (tenant_id, start, end, statuses, safe_limit),
                )
                return [dict(r) for r in cur.fetchall()]
    except Exception as exc:
        logger.debug("list_public_bookings_created_between failed tenant=%s: %s", tenant_id, exc)
        return []


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
                lookback_start = day_start.astimezone(timezone.utc) - timedelta(days=120)
                cur.execute(
                    """
                    SELECT id, patient_name, patient_phone, motif, slot_label, status,
                           start_iso, created_at, source, booking_code, google_event_id
                    FROM public_bookings
                    WHERE tenant_id = %s
                      AND status IN ('confirmed', 'pending')
                      AND (
                        (start_iso IS NOT NULL AND start_iso >= %s AND start_iso < %s)
                        OR (start_iso IS NULL AND created_at >= %s)
                      )
                    ORDER BY COALESCE(start_iso, created_at) ASC
                    """,
                    (
                        tenant_id,
                        day_start.astimezone(timezone.utc),
                        day_end.astimezone(timezone.utc),
                        lookback_start,
                    ),
                )
                rows = [dict(r) for r in cur.fetchall()]
    except Exception as exc:
        logger.debug("fetch_public_bookings_for_agenda failed tenant=%s: %s", tenant_id, exc)
        return slots

    day_start_local = day_start.astimezone(tz) if day_start.tzinfo else day_start.replace(tzinfo=tz)
    day_end_local = day_end.astimezone(tz) if day_end.tzinfo else day_end.replace(tzinfo=tz)

    for row in rows:
        start_local = _booking_start_local(row, tz)
        if not start_local:
            continue
        if start_local < day_start_local or start_local >= day_end_local:
            continue
        if not include_past_on_date and start_local < now_local:
            continue
        _maybe_persist_booking_start_iso(row, start_local)
        end_local = start_local + timedelta(minutes=30)
        status = (row.get("status") or "pending").strip()
        raw_src = (row.get("source") or "").strip()
        booking_origin_disp = booking_origin_canonical(raw_src or "page_publique")
        google_event_id = str(row.get("google_event_id") or "").strip()
        confirmed = status == "confirmed"
        slots.append(
            {
                "date": start_local.strftime("%Y-%m-%d"),
                "hour": _format_agenda_hour(start_local),
                "start_iso": start_local.isoformat(),
                "patient": (row.get("patient_name") or "Patient").strip(),
                "patient_phone": normalize_phone_number(row.get("patient_phone") or "") or (row.get("patient_phone") or "").strip(),
                "motif": (row.get("motif") or "Consultation").strip(),
                "type": (row.get("motif") or "Consultation").strip(),
                "source": "PAGE_PUBLIQUE",
                "booking_origin": booking_origin_disp,
                "done": end_local <= now_local,
                "current": start_local <= now_local < end_local,
                "event_id": google_event_id or str(row.get("id") or ""),
                "appointment_id": None,
                "slot_id": None,
                "can_cancel": confirmed and bool(google_event_id or start_local),
                "can_reschedule": confirmed and bool(google_event_id),
                "booking_status": status,
                "slot_label": (row.get("slot_label") or "").strip(),
                "booking_code": (row.get("booking_code") or "").strip(),
                "public_booking_id": str(row.get("id") or ""),
                "google_event_id": google_event_id,
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


_FRENCH_MONTHS = {
    "janvier": 1,
    "fevrier": 2,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
    "décembre": 12,
}


def _parse_french_slot_label_date(label: str, ref_local: datetime) -> Optional[date]:
    """Extrait une date civile depuis un libellé type « Lundi 3 juin à 9h30 »."""
    raw = str(label or "").strip().lower()
    if not raw:
        return None
    if "aujourd" in raw:
        return ref_local.date()
    match = re.search(
        r"(\d{1,2})\s+(janvier|f[eé]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[eé]cembre)",
        raw,
    )
    if not match:
        return None
    day = int(match.group(1))
    month_key = (
        match.group(2)
        .replace("février", "fevrier")
        .replace("août", "aout")
        .replace("décembre", "decembre")
    )
    month = _FRENCH_MONTHS.get(month_key)
    if not month:
        return None
    year = ref_local.year
    try:
        return date(year, month, day)
    except ValueError:
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
    ref_local = datetime.now(tz)
    if isinstance(created, datetime):
        ref_local = created.astimezone(tz)

    label_raw = (row.get("slot_label") or "").strip()
    label = label_raw.lower()
    hour, minute = _parse_time_from_label(label)
    parsed_date = _parse_french_slot_label_date(label_raw, ref_local)
    if parsed_date and hour is not None:
        return datetime(parsed_date.year, parsed_date.month, parsed_date.day, hour, minute or 0, tzinfo=tz)

    base_date = ref_local.date()
    if hour is not None:
        return datetime(base_date.year, base_date.month, base_date.day, hour, minute or 0, tzinfo=tz)
    if isinstance(created, datetime):
        return created.astimezone(tz)
    return None


def resolve_booking_start_ts(
    start_iso: Optional[str],
    slot_label: Optional[str],
    tz_name: str = "Europe/Paris",
) -> Optional[datetime]:
    """Dérive start_iso à l'écriture (obligatoire pour l'agenda)."""
    start_ts = _parse_iso_ts(start_iso)
    if start_ts:
        return start_ts
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("Europe/Paris")
    row = {"slot_label": slot_label or "", "created_at": datetime.now(timezone.utc)}
    start_local = _booking_start_local(row, tz)
    if start_local:
        return start_local.astimezone(timezone.utc)
    return None


def _format_agenda_hour(start_local: datetime) -> str:
    if start_local.minute:
        return start_local.strftime("%Hh%M")
    return start_local.strftime("%Hh")


def _maybe_persist_booking_start_iso(row: Dict[str, Any], start_local: datetime) -> None:
    """Backfill start_iso pour les anciennes lignes sans date explicite."""
    if row.get("start_iso"):
        return
    booking_id = row.get("id")
    if not booking_id:
        return
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE public_bookings
                    SET start_iso = %s
                    WHERE id = %s AND start_iso IS NULL
                    """,
                    (start_local.astimezone(timezone.utc), booking_id),
                )
            conn.commit()
    except Exception as exc:
        logger.debug("persist booking start_iso skipped id=%s: %s", booking_id, exc)


def _parse_time_from_label(label: str) -> tuple[Optional[int], Optional[int]]:
    match = re.search(r"(\d{1,2})[:h](\d{2})", label)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r"(\d{1,2})h(\d{0,2})?", label)
    if match:
        minute = int(match.group(2) or 0)
        return int(match.group(1)), minute
    return None, None
