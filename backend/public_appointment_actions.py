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
    insert_public_booking,
    lookup_public_bookings,
    mark_public_booking_rescheduled,
)
from backend.public_calendar_sync import (
    cancel_google_event,
    reschedule_google_event,
    slot_window_for_reschedule,
    uses_google_calendar,
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
    # Sécurité (double facteur): l'identification self-service exige le code RDV
    # ET le téléphone. Le téléphone seul n'est pas un secret (connu de l'entourage,
    # devinable), donc il ne suffit pas à retrouver/annuler un RDV. Sans code, le
    # patient est orienté vers la demande de rappel côté UI.
    if not code or not phone_val:
        raise HTTPException(
            422,
            "Pour des raisons de sécurité, indiquez votre téléphone ET votre code "
            "rendez-vous (ex. RDV-A7K3M2). Sans code, demandez à être rappelé(e).",
        )

    # On identifie le RDV par le code (identifiant unique), puis on vérifie que le
    # téléphone fourni correspond bien au même RDV (second facteur).
    public_rows = lookup_public_bookings(tenant_id, booking_code=code or None)
    internal_rows = _lookup_internal_appointments(tenant_id, booking_code=code or None)

    public_rows = [
        r for r in public_rows if _contact_phone_matches(r.get("patient_phone"), phone_val)
    ]
    internal_rows = [
        r
        for r in internal_rows
        if (r.get("contact_type") or "").strip().lower() == "phone"
        and _contact_phone_matches(r.get("contact"), phone_val)
    ]

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


def _collect_google_event_ids(tenant_id: int, record: Dict[str, Any], booking_code: str) -> List[str]:
    ids: List[str] = []
    for key in ("google_event_id",):
        val = (record.get(key) or "").strip()
        if val and val not in ids:
            ids.append(val)
    code = (booking_code or "").strip()
    if code:
        for appt in _lookup_internal_appointments(tenant_id, booking_code=code):
            ge = (appt.get("google_event_id") or "").strip()
            if ge and ge not in ids:
                ids.append(ge)
        for pb in lookup_public_bookings(tenant_id, booking_code=code):
            ge = (pb.get("google_event_id") or "").strip()
            if ge and ge not in ids:
                ids.append(ge)
    return ids


def _cancel_internal_appointment(tenant_id: int, row: Dict[str, Any], *, strict_google: bool = True) -> bool:
    appt_id = row.get("id")
    slot_id = row.get("slot_id")
    google_event_id = (row.get("google_event_id") or "").strip()
    if google_event_id:
        cancel_google_event(tenant_id, google_event_id, strict=strict_google and uses_google_calendar(tenant_id))
    ok = cancel_booking_sqlite({"id": appt_id, "slot_id": slot_id}, tenant_id=tenant_id)
    return bool(ok)


def _cancel_all_for_booking(
    tenant_id: int,
    record: Dict[str, Any],
    booking_code: str,
    *,
    strict_google: bool = True,
) -> bool:
    """Annule public_booking, appointments liés et événements Google associés."""
    cancelled_any = False
    for event_id in _collect_google_event_ids(tenant_id, record, booking_code):
        if cancel_google_event(tenant_id, event_id, strict=strict_google and uses_google_calendar(tenant_id)):
            cancelled_any = True

    source_type = record.get("source_type")
    if source_type == "public_booking":
        if cancel_public_booking_by_id(tenant_id, str(record.get("id"))):
            cancelled_any = True
    elif source_type == "appointment":
        if _cancel_internal_appointment(tenant_id, record, strict_google=False):
            cancelled_any = True

    code = (booking_code or "").strip()
    if code:
        for appt in _lookup_internal_appointments(tenant_id, booking_code=code):
            if str(appt.get("id")) != str(record.get("id")):
                if _cancel_internal_appointment(tenant_id, appt, strict_google=False):
                    cancelled_any = True
        for pb in lookup_public_bookings(tenant_id, booking_code=code):
            if str(pb.get("id")) != str(record.get("id")):
                if cancel_public_booking_by_id(tenant_id, str(pb.get("id"))):
                    cancelled_any = True
    return cancelled_any


def _reschedule_public_booking(
    tenant_id: int,
    record: Dict[str, Any],
    *,
    slug: str,
    new_slot_id: str,
    slot_label: str,
    start_iso: Optional[str],
    end_iso: Optional[str],
    slot_source: Optional[str],
) -> Dict[str, Any]:
    import uuid

    from backend.booking_code import create_unique_booking_code_for_tenant, format_booking_code
    from backend.routes.public_pages import PublicBookingRequest, _book_real_slot

    old_code = (record.get("booking_code") or "").strip()
    if not _cancel_all_for_booking(tenant_id, record, old_code, strict_google=True):
        raise HTTPException(400, "Impossible d'annuler l'ancien rendez-vous.")

    try:
        new_code = create_unique_booking_code_for_tenant(tenant_id)
    except Exception as exc:
        logger.warning("reschedule public booking code generation failed: %s", exc)
        raise HTTPException(503, "Impossible de generer un nouveau code rendez-vous.")

    payload = PublicBookingRequest(
        slug=slug,
        slotId=str(new_slot_id),
        slotLabel=slot_label or "Nouveau creneau",
        motif=(record.get("motif") or "Consultation").strip(),
        patientName=(record.get("patient_name") or "Patient").strip(),
        patientPhone=(record.get("patient_phone") or "").strip(),
        patientEmail=(record.get("patient_email") or "").strip() or None,
        source="page_publique_reschedule",
        slotSource=(slot_source or "sqlite").strip() or "sqlite",
        startIso=(start_iso or "").strip() or None,
        endIso=(end_iso or "").strip() or None,
    )
    ok, reason, google_event_id = _book_real_slot(tenant_id, payload, booking_code=new_code)
    if not ok:
        if reason == "slot_taken":
            raise HTTPException(409, "Ce creneau n'est plus disponible. Choisissez un autre horaire.")
        raise HTTPException(502, "Impossible de reserver le nouveau creneau.")

    booking_id = str(uuid.uuid4())
    insert_public_booking(
        booking_id=booking_id,
        tenant_id=tenant_id,
        slot_id=str(new_slot_id),
        slot_label=payload.slotLabel,
        patient_name=payload.patientName,
        patient_phone=payload.patientPhone,
        patient_email=payload.patientEmail,
        motif=payload.motif,
        source=payload.source,
        status="confirmed",
        start_iso=payload.startIso,
        booking_code=new_code,
        google_event_id=google_event_id,
    )
    try:
        from backend.public_action_notifications import dispatch_public_reschedule_notifications

        dispatch_public_reschedule_notifications(
            slug=slug,
            tenant_id=tenant_id,
            record=record,
            old_booking_code=old_code,
            new_booking_code=new_code,
            slot_label=payload.slotLabel,
            confirmation_id=booking_id,
        )
    except Exception as exc:
        logger.warning("public reschedule notifications failed tenant=%s: %s", tenant_id, exc)
    return {
        "ok": True,
        "rescheduled": True,
        "bookingCode": format_booking_code(new_code),
    }


def cancel_appointment(
    *,
    slug: Optional[str] = None,
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

    booking_code = (record.get("booking_code") or token_payload.get("booking_code") or "").strip()
    cancelled = _cancel_all_for_booking(
        tenant_id,
        record,
        booking_code,
        strict_google=uses_google_calendar(tenant_id),
    )

    if not cancelled:
        raise HTTPException(400, "Annulation impossible. Contactez le cabinet.")

    logger.info(
        "public_appointment_cancelled tenant=%s source=%s id=%s code=%s reason=%s",
        tenant_id,
        record.get("source_type"),
        record.get("id"),
        booking_code,
        (reason or "")[:120],
    )
    if slug:
        slot_label = str(record.get("slot_label") or "").strip()
        if not slot_label and start_dt:
            slot_label = start_dt.strftime("%A %d/%m à %H:%M")
        try:
            from backend.public_action_notifications import dispatch_public_cancel_notifications

            dispatch_public_cancel_notifications(
                slug=slug,
                tenant_id=tenant_id,
                record=record,
                booking_code=booking_code,
                slot_label=slot_label or None,
                reason=reason,
            )
        except Exception as exc:
            logger.warning("public cancel notifications failed tenant=%s: %s", tenant_id, exc)
    return {"ok": True, "cancelled": True, "bookingCode": format_booking_code(booking_code)}


def reschedule_appointment(
    *,
    slug: Optional[str] = None,
    action_token: str,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    new_slot_id: str,
    slot_label: Optional[str] = None,
    start_iso: Optional[str] = None,
    end_iso: Optional[str] = None,
    slot_source: Optional[str] = None,
) -> Dict[str, Any]:
    token_payload = decode_public_action_token(action_token)
    if not token_payload:
        raise HTTPException(401, "Session expiree. Recherchez a nouveau votre rendez-vous.")
    record = _load_record_from_token(token_payload)
    if not _verify_contact_for_record(record, phone, email):
        raise HTTPException(403, "Telephone ou email incorrect pour confirmer cette action.")

    tenant_id = int(token_payload["tenant_id"])
    start_dt = _parse_start_dt(record)
    _enforce_action_rules(tenant_id, start_dt, "reschedule")

    clean_slot_id = str(new_slot_id or "").strip()
    if not clean_slot_id:
        raise HTTPException(422, "Creneau invalide.")
    label = (slot_label or record.get("slot_label") or "").strip() or "Nouveau creneau"
    src = (slot_source or "sqlite").strip().lower()

    if record.get("source_type") == "public_booking":
        if not slug:
            raise HTTPException(400, "Contexte cabinet manquant.")
        return _reschedule_public_booking(
            tenant_id,
            record,
            slug=slug,
            new_slot_id=clean_slot_id,
            slot_label=label,
            start_iso=start_iso,
            end_iso=end_iso,
            slot_source=src,
        )

    try:
        slot_id_int = int(clean_slot_id)
    except ValueError:
        raise HTTPException(400, "Creneau invalide pour ce rendez-vous.")

    appt_id = int(record.get("id"))
    google_event_id = (record.get("google_event_id") or "").strip()
    old_slot_id = int(record.get("slot_id") or 0)

    if google_event_id and uses_google_calendar(tenant_id):
        new_window = slot_window_for_reschedule(tenant_id, slot_id_int)
        old_window = slot_window_for_reschedule(tenant_id, old_slot_id) if old_slot_id else None
        if not new_window:
            raise HTTPException(400, "Creneau introuvable.")
        new_start, new_end, tz_name = new_window
        moved = reschedule_google_event(
            tenant_id,
            google_event_id,
            new_start.isoformat(),
            new_end.isoformat(),
            timezone=tz_name,
        )
        if not moved:
            raise HTTPException(502, "Impossible de deplacer le rendez-vous sur Google Calendar.")
        from backend.slots_pg import pg_reschedule_booking_atomic

        ok = pg_reschedule_booking_atomic(tenant_id, appt_id, slot_id_int)
        if ok is not True:
            from backend.db import reschedule_booking_atomic

            ok = reschedule_booking_atomic(appt_id, slot_id_int, tenant_id=tenant_id)
        if not ok and old_window:
            old_start, old_end, _ = old_window
            reschedule_google_event(
                tenant_id,
                google_event_id,
                old_start.isoformat(),
                old_end.isoformat(),
                timezone=tz_name,
            )
            raise HTTPException(409, "Ce creneau n'est plus disponible. Choisissez un autre horaire.")
        if not ok:
            raise HTTPException(409, "Ce creneau n'est plus disponible. Choisissez un autre horaire.")
    else:
        from backend.slots_pg import pg_reschedule_booking_atomic

        ok = pg_reschedule_booking_atomic(tenant_id, appt_id, slot_id_int)
        if ok is not True:
            from backend.db import reschedule_booking_atomic

            ok = reschedule_booking_atomic(appt_id, slot_id_int, tenant_id=tenant_id)
        if not ok:
            raise HTTPException(409, "Ce creneau n'est plus disponible. Choisissez un autre horaire.")

    booking_code = (record.get("booking_code") or "").strip()
    if booking_code:
        for pb in lookup_public_bookings(tenant_id, booking_code=booking_code):
            mark_public_booking_rescheduled(tenant_id, str(pb.get("id")))

    new_code_raw = None
    try:
        from backend.slots_pg import pg_booking_code_for_slot

        new_code_raw = pg_booking_code_for_slot(tenant_id, slot_id_int)
    except Exception:
        new_code_raw = None

    if slug and new_code_raw:
        try:
            from backend.public_action_notifications import dispatch_public_reschedule_notifications

            dispatch_public_reschedule_notifications(
                slug=slug,
                tenant_id=tenant_id,
                record=record,
                old_booking_code=booking_code,
                new_booking_code=new_code_raw,
                slot_label=label,
            )
        except Exception as exc:
            logger.warning("public reschedule notifications failed tenant=%s: %s", tenant_id, exc)

    logger.info(
        "public_appointment_rescheduled tenant=%s appt_id=%s new_slot=%s",
        tenant_id,
        appt_id,
        slot_id_int,
    )
    out: Dict[str, Any] = {"ok": True, "rescheduled": True}
    if new_code_raw:
        out["bookingCode"] = format_booking_code(new_code_raw)
    return out
