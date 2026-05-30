"""Logique métier : lookup / annulation / déplacement / rappel depuis la page publique."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from backend.booking_code import format_booking_code, normalize_booking_code
from backend.db import cancel_booking_sqlite, normalize_phone_number
from backend.public_action_tokens import decode_public_action_token, issue_public_action_token
from backend.public_bookings_pg import (
    _contact_email_matches,
    _contact_phone_matches,
    cancel_public_booking_by_id,
    get_public_booking_by_id,
    lookup_public_bookings,
    mark_public_booking_rescheduled,
)

logger = logging.getLogger(__name__)

ActionKind = Literal["cancel", "reschedule"]


def _pg_url() -> Optional[str]:
    from backend.slots_pg import _pg_url as url

    return url()


def _phone_hint(phone: str) -> str:
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if len(digits) >= 4:
        return f"{'•' * max(0, len(digits) - 2)}{digits[-2:]}"
    return "••••"


def _parse_start_dt(row: Dict[str, Any], tz_name: str = "Europe/Paris") -> Optional[datetime]:
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("Europe/Paris")
    raw = row.get("start_iso") or row.get("start_ts")
    if isinstance(raw, datetime):
        return raw.astimezone(tz)
    if raw:
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(tz)
        except Exception:
            pass
    created = row.get("created_at")
    if isinstance(created, datetime):
        return created.astimezone(tz)
    return None


def _lookup_internal_appointments(
    tenant_id: int,
    *,
    booking_code: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
) -> List[Dict[str, Any]]:
    code = normalize_booking_code(booking_code) if booking_code else ""
    phone_norm = normalize_phone_number(phone or "")
    email_val = (email or "").strip().lower()
    if not code and not phone_norm and not email_val:
        return []
    url = _pg_url()
    if not url:
        return []

    conditions = ["a.tenant_id = %s", "s.start_ts >= NOW() - INTERVAL '1 hour'"]
    params: List[Any] = [tenant_id]
    if code:
        conditions.append("UPPER(a.booking_code) = %s")
        params.append(code)
    else:
        contact_parts: List[str] = []
        if phone_norm:
            contact_parts.append("(a.contact_type = 'phone' AND a.contact = %s)")
            params.append(phone_norm)
        if email_val:
            contact_parts.append("(a.contact_type = 'email' AND LOWER(a.contact) = %s)")
            params.append(email_val)
        if contact_parts:
            conditions.append(f"({' OR '.join(contact_parts)})")

    try:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT a.id, a.slot_id, a.name, a.contact, a.contact_type, a.motif,
                           a.booking_code, a.google_event_id, s.start_ts
                    FROM appointments a
                    JOIN slots s ON s.id = a.slot_id AND s.tenant_id = a.tenant_id
                    WHERE {' AND '.join(conditions)}
                    ORDER BY s.start_ts ASC
                    LIMIT 20
                    """,
                    tuple(params),
                )
                return [dict(r) for r in cur.fetchall()]
    except Exception as exc:
        logger.debug("lookup internal appointments failed tenant=%s: %s", tenant_id, exc)
        return []


def _get_internal_appointment(tenant_id: int, appt_id: int) -> Optional[Dict[str, Any]]:
    url = _pg_url()
    if not url:
        return None
    try:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT a.id, a.slot_id, a.name, a.contact, a.contact_type, a.motif,
                           a.booking_code, a.google_event_id, s.start_ts
                    FROM appointments a
                    JOIN slots s ON s.id = a.slot_id AND s.tenant_id = a.tenant_id
                    WHERE a.tenant_id = %s AND a.id = %s
                    LIMIT 1
                    """,
                    (tenant_id, appt_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception as exc:
        logger.debug("get internal appointment failed tenant=%s id=%s: %s", tenant_id, appt_id, exc)
        return None


def _get_booking_rules(tenant_id: int) -> Dict[str, Any]:
    try:
        from backend.cabinet_profile_pg import get_booking_rules

        rules = get_booking_rules(tenant_id) or {}
    except Exception:
        rules = {}
    return {
        "appointment_cancel_allowed": bool(rules.get("appointment_cancel_allowed", True)),
        "appointment_cancel_notice_hours": int(rules.get("appointment_cancel_notice_hours") or 24),
        "appointment_reschedule_allowed": bool(rules.get("appointment_reschedule_allowed", True)),
        "appointment_reschedule_notice_hours": int(rules.get("appointment_reschedule_notice_hours") or 24),
    }


def _enforce_action_rules(tenant_id: int, start_dt: Optional[datetime], action: ActionKind) -> None:
    rules = _get_booking_rules(tenant_id)
    if action == "cancel":
        if not rules["appointment_cancel_allowed"]:
            raise HTTPException(403, "L'annulation en ligne n'est pas autorisee pour ce cabinet.")
        notice = rules["appointment_cancel_notice_hours"]
    else:
        if not rules["appointment_reschedule_allowed"]:
            raise HTTPException(403, "La modification en ligne n'est pas autorisee pour ce cabinet.")
        notice = rules["appointment_reschedule_notice_hours"]
    if start_dt is None:
        return
    now = datetime.now(start_dt.tzinfo or timezone.utc)
    if start_dt - now < timedelta(hours=max(0, notice)):
        raise HTTPException(
            403,
            f"Cette action doit etre effectuee au moins {notice} h avant le rendez-vous.",
        )


def _serialize_public_row(row: Dict[str, Any], tenant_id: int) -> Dict[str, Any]:
    start_dt = _parse_start_dt(row)
    phone = (row.get("patient_phone") or "").strip()
    booking_code = (row.get("booking_code") or "").strip()
    token = issue_public_action_token(
        tenant_id=tenant_id,
        source_type="public_booking",
        source_id=str(row.get("id") or ""),
        booking_code=booking_code,
    )
    return {
        "actionToken": token,
        "sourceType": "public_booking",
        "date": start_dt.strftime("%Y-%m-%d") if start_dt else None,
        "time": start_dt.strftime("%H:%M") if start_dt else None,
        "slotLabel": (row.get("slot_label") or "").strip(),
        "motif": (row.get("motif") or "Consultation").strip(),
        "patientName": (row.get("patient_name") or "").strip(),
        "phoneHint": _phone_hint(phone),
        "bookingCode": format_booking_code(booking_code),
        "status": (row.get("status") or "pending").strip(),
    }


def _serialize_internal_row(row: Dict[str, Any], tenant_id: int) -> Dict[str, Any]:
    start_dt = _parse_start_dt(row)
    phone = row.get("contact") if (row.get("contact_type") or "") == "phone" else ""
    booking_code = (row.get("booking_code") or "").strip()
    token = issue_public_action_token(
        tenant_id=tenant_id,
        source_type="appointment",
        source_id=str(row.get("id") or ""),
        booking_code=booking_code,
    )
    return {
        "actionToken": token,
        "sourceType": "appointment",
        "date": start_dt.strftime("%Y-%m-%d") if start_dt else None,
        "time": start_dt.strftime("%H:%M") if start_dt else None,
        "slotLabel": start_dt.strftime("%A %d/%m à %H:%M") if start_dt else "",
        "motif": (row.get("motif") or "Consultation").strip(),
        "patientName": (row.get("name") or "").strip(),
        "phoneHint": _phone_hint(str(phone or "")),
        "bookingCode": format_booking_code(booking_code),
        "status": "confirmed",
    }


def lookup_appointments(
    tenant_id: int,
    *,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    booking_code: Optional[str] = None,
) -> Dict[str, Any]:
    code = normalize_booking_code(booking_code) if booking_code else ""
    phone_val = (phone or "").strip()
    email_val = (email or "").strip()
    if not code and not phone_val and not email_val:
        raise HTTPException(422, "Renseignez votre telephone, email ou code rendez-vous.")

    public_rows = lookup_public_bookings(
        tenant_id,
        booking_code=code or None,
        phone=phone_val or None,
        email=email_val or None,
    )
    internal_rows = _lookup_internal_appointments(
        tenant_id,
        booking_code=code or None,
        phone=phone_val or None,
        email=email_val or None,
    )

    seen_codes: set[str] = set()
    appointments: List[Dict[str, Any]] = []
    for row in public_rows:
        bc = (row.get("booking_code") or "").strip().upper()
        key = f"pb:{row.get('id')}"
        if bc:
            seen_codes.add(bc)
        appointments.append(_serialize_public_row(row, tenant_id))
    for row in internal_rows:
        bc = (row.get("booking_code") or "").strip().upper()
        if bc and bc in seen_codes:
            continue
        appointments.append(_serialize_internal_row(row, tenant_id))

    rules = _get_booking_rules(tenant_id)
    if not appointments:
        return {"status": "not_found", "appointments": [], "rules": rules}
    return {
        "status": "found" if len(appointments) == 1 else "multiple",
        "appointments": appointments,
        "rules": rules,
    }


def _verify_contact_for_record(record: Dict[str, Any], phone: Optional[str], email: Optional[str]) -> bool:
    source_type = record.get("source_type") or record.get("sourceType")
    if source_type == "public_booking":
        return _contact_phone_matches(record.get("patient_phone"), phone) or _contact_email_matches(
            record.get("patient_email"), email
        )
    contact_type = (record.get("contact_type") or "").strip().lower()
    if contact_type == "phone":
        return _contact_phone_matches(record.get("contact"), phone)
    if contact_type == "email":
        return _contact_email_matches(record.get("contact"), email)
    return _contact_phone_matches(record.get("contact"), phone) or _contact_email_matches(
        record.get("contact"), email
    )


def _load_record_from_token(token_payload: Dict[str, Any]) -> Dict[str, Any]:
    tenant_id = int(token_payload["tenant_id"])
    source_type = token_payload["source_type"]
    source_id = token_payload["source_id"]
    if source_type == "public_booking":
        row = get_public_booking_by_id(tenant_id, source_id)
        if not row:
            raise HTTPException(404, "Rendez-vous introuvable.")
        row["source_type"] = "public_booking"
        return row
    if source_type == "appointment":
        try:
            appt_id = int(source_id)
        except (TypeError, ValueError):
            raise HTTPException(400, "Token invalide.")
        row = _get_internal_appointment(tenant_id, appt_id)
        if not row:
            raise HTTPException(404, "Rendez-vous introuvable.")
        row["source_type"] = "appointment"
        return row
    raise HTTPException(400, "Token invalide.")


def _cancel_internal_appointment(tenant_id: int, row: Dict[str, Any]) -> bool:
    appt_id = row.get("id")
    slot_id = row.get("slot_id")
    google_event_id = (row.get("google_event_id") or "").strip()
    if google_event_id:
        try:
            from backend.google_calendar import GoogleCalendarService
            from backend.routes.tenant import _get_tenant_detail

            detail = _get_tenant_detail(tenant_id) or {}
            params = detail.get("params") or {}
            calendar_id = (params.get("calendar_id") or "").strip()
            service = GoogleCalendarService(calendar_id)
            service.cancel_appointment(google_event_id)
        except Exception as exc:
            logger.warning("public cancel google failed tenant=%s event=%s: %s", tenant_id, google_event_id, exc)
    ok = cancel_booking_sqlite({"id": appt_id, "slot_id": slot_id}, tenant_id=tenant_id)
    return bool(ok)


def cancel_appointment(
    *,
    action_token: str,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    token_payload = decode_public_action_token(action_token)
    if not token_payload:
        raise HTTPException(401, "Session expiree. Recherchez a nouveau votre rendez-vous.")
    record = _load_record_from_token(token_payload)
    if not _verify_contact_for_record(record, phone, email):
        raise HTTPException(403, "Telephone ou email incorrect pour confirmer cette action.")

    tenant_id = int(token_payload["tenant_id"])
    start_dt = _parse_start_dt(record)
    _enforce_action_rules(tenant_id, start_dt, "cancel")

    cancelled = False
    source_type = record.get("source_type")
    booking_code = (record.get("booking_code") or token_payload.get("booking_code") or "").strip()

    if source_type == "public_booking":
        cancelled = cancel_public_booking_by_id(tenant_id, str(record.get("id")))
        if booking_code:
            for appt in _lookup_internal_appointments(tenant_id, booking_code=booking_code):
                _cancel_internal_appointment(tenant_id, appt)
    else:
        cancelled = _cancel_internal_appointment(tenant_id, record)
        if booking_code:
            for pb in lookup_public_bookings(tenant_id, booking_code=booking_code):
                cancel_public_booking_by_id(tenant_id, str(pb.get("id")))

    if not cancelled:
        raise HTTPException(400, "Annulation impossible. Contactez le cabinet.")

    logger.info(
        "public_appointment_cancelled tenant=%s source=%s id=%s code=%s reason=%s",
        tenant_id,
        source_type,
        record.get("id"),
        booking_code,
        (reason or "")[:120],
    )
    return {"ok": True, "cancelled": True, "bookingCode": format_booking_code(booking_code)}


def reschedule_appointment(
    *,
    action_token: str,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    new_slot_id: int,
) -> Dict[str, Any]:
    token_payload = decode_public_action_token(action_token)
    if not token_payload:
        raise HTTPException(401, "Session expiree. Recherchez a nouveau votre rendez-vous.")
    record = _load_record_from_token(token_payload)
    if record.get("source_type") != "appointment":
        raise HTTPException(400, "Ce rendez-vous ne peut pas etre deplace automatiquement. Demandez a etre rappele.")
    if not _verify_contact_for_record(record, phone, email):
        raise HTTPException(403, "Telephone ou email incorrect pour confirmer cette action.")

    tenant_id = int(token_payload["tenant_id"])
    start_dt = _parse_start_dt(record)
    _enforce_action_rules(tenant_id, start_dt, "reschedule")

    appt_id = int(record.get("id"))
    from backend.slots_pg import pg_reschedule_booking_atomic

    ok = pg_reschedule_booking_atomic(tenant_id, appt_id, int(new_slot_id))
    if ok is not True:
        from backend.db import reschedule_booking_atomic

        ok = reschedule_booking_atomic(appt_id, int(new_slot_id), tenant_id=tenant_id)
    if not ok:
        raise HTTPException(409, "Ce creneau n'est plus disponible. Choisissez un autre horaire.")

    booking_code = (record.get("booking_code") or "").strip()
    if booking_code:
        for pb in lookup_public_bookings(tenant_id, booking_code=booking_code):
            mark_public_booking_rescheduled(tenant_id, str(pb.get("id")))

    logger.info(
        "public_appointment_rescheduled tenant=%s appt_id=%s new_slot=%s",
        tenant_id,
        appt_id,
        new_slot_id,
    )
    return {"ok": True, "rescheduled": True}
