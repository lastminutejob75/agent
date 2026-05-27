"""Timeline historique patient (appels, notes, documents, RDV, transferts)."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.booking_origin import display_origin_label
from backend.db import list_patient_documents, list_patient_notes, normalize_phone_number

ABSENCE_NOTE_PREFIX = "[ABSENCE-RDV]"


def _parse_dt(value: Any) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _fmt_date(dt: datetime) -> str:
    return dt.astimezone().strftime("%d/%m/%Y")


def _fmt_time(dt: datetime) -> str:
    return dt.astimezone().strftime("%H:%M")


def _booking_origin_label(code: str) -> str:
    return display_origin_label(code)


def _list_patient_past_appointments_detailed(tenant_id: int, phone_norm: str, *, limit: int = 40) -> List[Dict[str, Any]]:
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
                        SELECT a.contact, a.motif, a.contact_type, a.booking_origin, s.start_ts
                        FROM appointments a
                        JOIN slots s ON s.id = a.slot_id AND s.tenant_id = a.tenant_id
                        WHERE a.tenant_id = %s AND s.start_ts < now()
                        ORDER BY s.start_ts DESC
                        LIMIT %s
                        """,
                        (tenant_id, max(limit * 4, limit)),
                    )
                    for row in cur.fetchall() or []:
                        contact_norm = normalize_phone_number(row.get("contact") if "contact" in row else "")
                        if contact_norm and contact_norm != phone_norm:
                            continue
                        start_ts = row.get("start_ts")
                        if isinstance(start_ts, datetime):
                            start = start_ts if start_ts.tzinfo else start_ts.replace(tzinfo=timezone.utc)
                        else:
                            start = _parse_dt(start_ts)
                        if not start or start >= now:
                            continue
                        rows.append(
                            {
                                "start": start,
                                "motif": row.get("motif") or "Consultation",
                                "contact_type": row.get("contact_type") or "",
                                "booking_origin": row.get("booking_origin") or "",
                            }
                        )
                        if len(rows) >= limit:
                            break
            return rows
        except Exception:
            pass

    try:
        from backend.db import ensure_tenant_config, get_conn

        ensure_tenant_config()
        conn = get_conn()
        try:
            raw_rows = conn.execute(
                """
                SELECT a.contact, a.motif, a.contact_type, a.booking_origin, s.date, s.time
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
            try:
                start = datetime.fromisoformat(f"{row['date']}T{row['time']}:00").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if start >= now:
                continue
            rows.append(
                {
                    "start": start,
                    "motif": row["motif"] or "Consultation",
                    "contact_type": row["contact_type"] or "",
                    "booking_origin": row["booking_origin"] or "",
                }
            )
            if len(rows) >= limit:
                break
    except Exception:
        pass
    return rows


def _call_type_label(status: str) -> str:
    s = str(status or "").upper()
    if s in {"TRANSFERRED", "ABANDONED", "MISSED"}:
        return "Appel entrant"
    if s in {"CONFIRMED", "RESCHEDULED", "CANCELLED", "FAQ"}:
        return "Appel entrant"
    return "Appel entrant"


def _call_status_label(status: str, followup_state: str) -> tuple[str, str]:
    s = str(status or "").upper()
    follow = str(followup_state or "").lower()
    if s == "TRANSFERRED" or follow == "callback":
        return "Action humaine requise", "orange"
    if s in {"CONFIRMED", "RESCHEDULED"}:
        return "Traité automatiquement", "green"
    if s == "CANCELLED":
        return "Annulation traitée", "green"
    if s == "ABANDONED":
        return "Appel interrompu", "orange"
    if follow == "processed":
        return "Traité", "green"
    return "Traité automatiquement", "green"


def build_patient_history(
    tenant_id: int,
    phone: str,
    *,
    calls: Optional[List[Dict[str, Any]]] = None,
    handoffs: Optional[List[Dict[str, Any]]] = None,
    notes: Optional[List[Dict[str, Any]]] = None,
    documents: Optional[List[Dict[str, Any]]] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    phone_norm = normalize_phone_number(phone)
    note_rows = notes if notes is not None else list_patient_notes(tenant_id, phone, limit=200)
    doc_rows = documents if documents is not None else list_patient_documents(tenant_id, phone)
    call_rows = calls or []
    handoff_rows = handoffs or []
    appt_rows = _list_patient_past_appointments_detailed(tenant_id, phone_norm, limit=30)

    items: List[Dict[str, Any]] = []

    for call in call_rows:
        at = _parse_dt(call.get("started_at"))
        if not at:
            continue
        status = str(call.get("status") or "")
        follow = str(call.get("followup_state") or "")
        status_label, tone = _call_status_label(status, follow)
        summary = str(call.get("summary") or "").strip() or "Interaction téléphonique avec Clara."
        items.append(
            {
                "id": f"call-{call.get('call_id') or at.isoformat()}",
                "kind": "call",
                "at": at.isoformat(),
                "date_label": _fmt_date(at),
                "time_label": _fmt_time(at),
                "type_label": _call_type_label(status),
                "summary": summary,
                "status_label": status_label,
                "tone": tone,
            }
        )

    for handoff in handoff_rows:
        at = _parse_dt(handoff.get("created_at"))
        if not at:
            continue
        summary = str(handoff.get("summary") or handoff.get("reason") or "Transfert vers le cabinet.").strip()
        status_raw = str(handoff.get("status") or "").lower()
        if status_raw in {"processed", "cancelled", "closed"}:
            status_label, tone = "Traité", "green"
        else:
            status_label, tone = "Action humaine requise", "orange"
        items.append(
            {
                "id": f"handoff-{handoff.get('id') or at.isoformat()}",
                "kind": "handoff",
                "at": at.isoformat(),
                "date_label": _fmt_date(at),
                "time_label": _fmt_time(at),
                "type_label": "Transfert humain",
                "summary": summary,
                "status_label": status_label,
                "tone": tone,
            }
        )

    for appt in appt_rows:
        at = appt["start"]
        origin = _booking_origin_label(appt.get("booking_origin"))
        motif = str(appt.get("motif") or "Consultation")
        items.append(
            {
                "id": f"appt-{at.isoformat()}",
                "kind": "appointment",
                "at": at.isoformat(),
                "date_label": _fmt_date(at),
                "time_label": _fmt_time(at),
                "type_label": "Rendez-vous",
                "summary": f"{motif} · {_fmt_time(at)} · origine {origin}",
                "status_label": "Passé",
                "tone": "green",
            }
        )

    for note in note_rows:
        at = _parse_dt(note.get("created_at"))
        if not at:
            continue
        text = str(note.get("note_text") or note.get("text") or "").strip()
        if not text:
            continue
        if text.startswith(ABSENCE_NOTE_PREFIX):
            type_label = "Absence RDV"
            tone = "orange"
            status_label = "Noté par le cabinet"
        else:
            type_label = "Note cabinet"
            tone = "green"
            status_label = f"Par {note.get('author') or 'Cabinet'}"
        items.append(
            {
                "id": f"note-{note.get('id') or at.isoformat()}",
                "kind": "note",
                "at": at.isoformat(),
                "date_label": _fmt_date(at),
                "time_label": _fmt_time(at),
                "type_label": type_label,
                "summary": text[:240],
                "status_label": status_label,
                "tone": tone,
            }
        )

    for doc in doc_rows:
        at = _parse_dt(doc.get("created_at"))
        if not at:
            continue
        name = str(doc.get("original_name") or "Document").strip()
        items.append(
            {
                "id": f"doc-{doc.get('id') or at.isoformat()}",
                "kind": "document",
                "at": at.isoformat(),
                "date_label": _fmt_date(at),
                "time_label": _fmt_time(at),
                "type_label": "Document reçu",
                "summary": f"{name} ajouté au dossier.",
                "status_label": "Archivé",
                "tone": "green",
            }
        )

    items.sort(key=lambda row: row.get("at") or "", reverse=True)
    capped = items[: max(1, min(int(limit or 50), 100))]
    return {"items": capped, "total": len(items)}
