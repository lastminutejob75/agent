"""Tags d'insights patient (fiche cabinet) dérivés de données réelles."""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.db import get_conn, list_patient_notes, normalize_phone_number

logger = logging.getLogger(__name__)

ABSENCE_NOTE_PREFIX = "[ABSENCE-RDV]"
ABSENCE_NOTE_RE = re.compile(
    r"(no[\s-]?show|absence au rendez|absent au rendez|manqu[ée].{0,12}rdv|"
    r"pas venu|n['']est pas venu|n'a pas honor)",
    re.IGNORECASE,
)
SMS_PREF_RE = re.compile(r"\b(sms|texto|message\s+texte)\b", re.IGNORECASE)

MIN_REGULAR_APPOINTMENTS = 3
MIN_PREF_APPOINTMENTS = 2
MIN_PREF_RATIO = 0.6
NO_SHOW_RISK_ABSENCES = 2


def _parse_appointment_start(row: Dict[str, Any]) -> Optional[datetime]:
    start_ts = row.get("start_ts")
    if start_ts is not None:
        if isinstance(start_ts, datetime):
            dt = start_ts
        else:
            raw = str(start_ts).strip()
            if not raw:
                return None
            try:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    date_s = str(row.get("date") or "").strip()
    time_s = str(row.get("time") or "00:00").strip()
    if not date_s:
        return None
    try:
        dt = datetime.fromisoformat(f"{date_s}T{time_s}")
    except ValueError:
        try:
            dt = datetime.strptime(f"{date_s} {time_s[:5]}", "%Y-%m-%d %H:%M")
        except ValueError:
            return None
    return dt.replace(tzinfo=timezone.utc)


def _list_patient_past_appointments(tenant_id: int, phone_norm: str, *, limit: int = 120) -> List[Dict[str, Any]]:
    if not phone_norm:
        return []

    now = datetime.now(timezone.utc)
    rows: List[Dict[str, Any]] = []
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_SLOTS_URL")
    if url:
        try:
            import psycopg
            from psycopg.rows import dict_row

            with psycopg.connect(url, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT a.contact, a.contact_type, s.start_ts
                        FROM appointments a
                        JOIN slots s ON s.id = a.slot_id AND s.tenant_id = a.tenant_id
                        WHERE a.tenant_id = %s AND s.start_ts < now()
                        ORDER BY s.start_ts DESC
                        LIMIT %s
                        """,
                        (tenant_id, max(limit * 4, limit)),
                    )
                    for row in cur.fetchall() or []:
                        contact_norm = normalize_phone_number(row.get("contact") or "")
                        if contact_norm != phone_norm:
                            continue
                        start = _parse_appointment_start(row)
                        if not start or start >= now:
                            continue
                        rows.append(
                            {
                                "start": start,
                                "contact_type": str(row.get("contact_type") or "").lower(),
                            }
                        )
                        if len(rows) >= limit:
                            break
            return rows
        except Exception as exc:
            logger.warning("patient_insights pg failed tenant=%s: %s", tenant_id, exc)

    try:
        from backend.db import ensure_tenant_config

        ensure_tenant_config()
        conn = get_conn()
        try:
            raw_rows = conn.execute(
                """
                SELECT a.contact, a.contact_type, s.date, s.time
                FROM appointments a
                JOIN slots s ON s.id = a.slot_id AND s.tenant_id = a.tenant_id
                WHERE a.tenant_id = ?
                ORDER BY s.date DESC, s.time DESC
                LIMIT ?
                """,
                (tenant_id, max(limit * 4, limit)),
            ).fetchall()
        finally:
            conn.close()
        for row in raw_rows:
            contact_norm = normalize_phone_number(row["contact"] or "")
            if contact_norm != phone_norm:
                continue
            start = _parse_appointment_start(dict(row))
            if not start or start >= now:
                continue
            rows.append(
                {
                    "start": start,
                    "contact_type": str(row["contact_type"] or "").lower(),
                }
            )
            if len(rows) >= limit:
                break
    except Exception as exc:
        logger.warning("patient_insights sqlite failed tenant=%s: %s", tenant_id, exc)
    return rows


def _count_absence_notes(notes: List[Dict[str, Any]]) -> int:
    count = 0
    for note in notes:
        text = str(note.get("note_text") or note.get("text") or "").strip()
        if not text:
            continue
        if text.startswith(ABSENCE_NOTE_PREFIX) or ABSENCE_NOTE_RE.search(text):
            count += 1
    return count


def _note_mentions_sms(notes: List[Dict[str, Any]]) -> bool:
    for note in notes:
        text = str(note.get("note_text") or note.get("text") or "")
        if SMS_PREF_RE.search(text):
            return True
    return False


def build_absence_note_text(appointment_date: datetime) -> str:
    label = appointment_date.astimezone().strftime("%d/%m/%Y à %H:%M")
    return f"{ABSENCE_NOTE_PREFIX} Patient absent au rendez-vous du {label}."


def compute_patient_insights(
    tenant_id: int,
    phone: str,
    *,
    notes: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Construit les tags visibles sur la fiche patient à partir de RDV passés et notes."""
    phone_norm = normalize_phone_number(phone)
    note_rows = notes if notes is not None else list_patient_notes(tenant_id, phone, limit=200)
    past_appts = _list_patient_past_appointments(tenant_id, phone_norm)

    tags: List[Dict[str, str]] = []

    if len(past_appts) >= MIN_REGULAR_APPOINTMENTS:
        tags.append({"key": "regular", "label": "Patient régulier", "tone": "blue"})

    if len(past_appts) >= MIN_PREF_APPOINTMENTS:
        morning = sum(1 for appt in past_appts if appt["start"].hour < 13)
        afternoon = len(past_appts) - morning
        total = len(past_appts)
        if morning >= MIN_PREF_APPOINTMENTS and morning / total >= MIN_PREF_RATIO:
            tags.append({"key": "morning_pref", "label": "Préférence matin", "tone": "blue"})
        elif afternoon >= MIN_PREF_APPOINTMENTS and afternoon / total >= MIN_PREF_RATIO:
            tags.append({"key": "afternoon_pref", "label": "Préférence après-midi", "tone": "blue"})

    if _note_mentions_sms(note_rows):
        tags.append({"key": "sms_pref", "label": "SMS préféré", "tone": "blue"})

    absence_notes = _count_absence_notes(note_rows)
    if absence_notes >= NO_SHOW_RISK_ABSENCES:
        tags.append({"key": "no_show_risk", "label": "Risque no-show", "tone": "red"})

    recent_past = [
        {"start_iso": appt["start"].astimezone().isoformat()}
        for appt in past_appts[:12]
    ]

    return {
        "tags": tags,
        "stats": {
            "past_appointments": len(past_appts),
            "absence_notes": absence_notes,
        },
        "recent_past_appointments": recent_past,
    }
