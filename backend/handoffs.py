from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import backend.db as db
from backend.handoff_router import resolve_handoff_decision


ALLOWED_STATUSES = {
    "new",
    "live_attempted",
    "live_connected",
    "live_failed",
    "callback_created",
    "callback_scheduled",
    "processed",
    "cancelled",
}


def _handoff_row_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": int(row.get("id") or 0),
        "tenant_id": int(row.get("tenant_id") or 0),
        "call_id": row.get("call_id") or "",
        "channel": row.get("channel") or "vocal",
        "reason": row.get("reason") or "",
        "target": row.get("target") or "assistant",
        "mode": row.get("mode") or "callback_only",
        "priority": row.get("priority") or "normal",
        "status": row.get("status") or "callback_created",
        "patient_phone": row.get("patient_phone") or "",
        "raw_name": row.get("raw_name") or "",
        "validated_name": row.get("validated_name") or "",
        "display_name": row.get("display_name") or row.get("validated_name") or row.get("raw_name") or "Patient",
        "summary": row.get("summary") or "",
        "transcript_excerpt": row.get("transcript_excerpt") or "",
        "booking_start_iso": str(row.get("booking_start_iso") or ""),
        "booking_end_iso": str(row.get("booking_end_iso") or ""),
        "booking_motif": row.get("booking_motif") or "",
        "notes": row.get("notes") or "",
        "created_at": str(row.get("created_at") or ""),
        "updated_at": str(row.get("updated_at") or ""),
        "processed_at": str(row.get("processed_at") or ""),
    }


def _normalized_phone_from_session(session: Any) -> str:
    qualif = getattr(session, "qualif_data", None)
    qualif_contact = getattr(qualif, "contact", None) if qualif else None
    qualif_type = getattr(qualif, "contact_type", None) if qualif else None
    if qualif_type == "phone":
        phone = db.normalize_phone_number(qualif_contact)
        if phone:
            return phone
    return db.normalize_phone_number(getattr(session, "customer_phone", None))


def _build_transcript_excerpt(session: Any, limit: int = 4) -> str:
    messages = list(getattr(session, "messages", None) or [])
    if not messages:
        return ""
    lines: List[str] = []
    for msg in messages[-limit:]:
        role = "Patient" if getattr(msg, "role", "") == "user" else "Assistant"
        text = str(getattr(msg, "text", "") or "").strip()
        if text:
            lines.append(f"{role}: {text}")
    return "\n".join(lines)[:800]


def _build_summary(
    *,
    target: str,
    reason: str,
    motif: str,
) -> str:
    if reason == "explicit_practitioner_request":
        return "Le patient demande explicitement à parler au praticien."
    if reason == "explicit_human_request":
        return "Le patient demande explicitement à parler à un humain."
    if reason == "urgent_non_vital_case":
        return "Le patient nécessite une reprise rapide par le praticien."
    if reason == "medical_question_requires_practitioner":
        return f"Demande médicale à reprendre par le praticien{f' : {motif}' if motif else ''}."
    if reason == "technical_failure":
        return "La conversation nécessite une reprise humaine suite à une difficulté technique."
    if reason == "too_many_retries":
        return "La conversation n'a pas pu être résolue automatiquement après plusieurs tentatives."
    role = "praticien" if target == "practitioner" else "assistante"
    return f"Demande à reprendre par le {role} du cabinet."


def build_handoff_payload(
    session: Any,
    *,
    reason: str,
    target: str,
    mode: str,
    priority: str,
) -> Dict[str, Any]:
    patient_phone = _normalized_phone_from_session(session)
    profile = db.get_cabinet_client_by_phone(getattr(session, "tenant_id", 1), patient_phone) if patient_phone else None
    qualif = getattr(session, "qualif_data", None)
    raw_name = str(getattr(qualif, "name", "") or "").strip()
    validated_name = str((profile or {}).get("validated_name") or "").strip()
    display_name = validated_name or raw_name or str((profile or {}).get("display_name") or "").strip() or "Patient"
    motif = str(getattr(qualif, "motif", "") or "").strip()
    transcript_excerpt = _build_transcript_excerpt(session)
    return {
        "tenant_id": int(getattr(session, "tenant_id", 1) or 1),
        "call_id": str(getattr(session, "conv_id", "") or "").strip(),
        "channel": str(getattr(session, "channel", "vocal") or "vocal").strip() or "vocal",
        "reason": reason,
        "target": target,
        "mode": mode,
        "priority": priority,
        "status": "callback_created",
        "patient_phone": patient_phone,
        "raw_name": raw_name,
        "validated_name": validated_name,
        "display_name": display_name,
        "summary": _build_summary(target=target, reason=reason, motif=motif),
        "transcript_excerpt": transcript_excerpt,
        "booking_start_iso": "",
        "booking_end_iso": "",
        "booking_motif": motif,
        "notes": "",
    }


def get_handoff_by_call_id(tenant_id: int, call_id: str) -> Optional[Dict[str, Any]]:
    call_id = (call_id or "").strip()
    if not call_id:
        return None
    url = db._pg_events_url()
    if url:
        try:
            import psycopg
            from psycopg.rows import dict_row

            with psycopg.connect(url, row_factory=dict_row) as conn:
                db._ensure_human_handoffs_table_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT *
                        FROM human_handoffs
                        WHERE tenant_id = %s AND call_id = %s
                        LIMIT 1
                        """,
                        (tenant_id, call_id),
                    )
                    row = cur.fetchone()
                    if row:
                        return _handoff_row_to_dict(row)
        except Exception:
            pass

    conn = db.get_conn()
    try:
        db._ensure_human_handoffs_table(conn)
        row = conn.execute(
            """
            SELECT *
            FROM human_handoffs
            WHERE tenant_id = ? AND call_id = ?
            LIMIT 1
            """,
            (tenant_id, call_id),
        ).fetchone()
        if not row:
            return None
        return _handoff_row_to_dict(dict(row))
    finally:
        conn.close()


def get_handoff_by_id(tenant_id: int, handoff_id: int) -> Optional[Dict[str, Any]]:
    url = db._pg_events_url()
    if url:
        try:
            import psycopg
            from psycopg.rows import dict_row

            with psycopg.connect(url, row_factory=dict_row) as conn:
                db._ensure_human_handoffs_table_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT * FROM human_handoffs WHERE tenant_id = %s AND id = %s LIMIT 1",
                        (tenant_id, handoff_id),
                    )
                    row = cur.fetchone()
                    if row:
                        return _handoff_row_to_dict(row)
        except Exception:
            pass

    conn = db.get_conn()
    try:
        db._ensure_human_handoffs_table(conn)
        row = conn.execute(
            "SELECT * FROM human_handoffs WHERE tenant_id = ? AND id = ? LIMIT 1",
            (tenant_id, handoff_id),
        ).fetchone()
        if not row:
            return None
        return _handoff_row_to_dict(dict(row))
    finally:
        conn.close()


def create_handoff(
    tenant_id: int,
    call_id: str,
    *,
    channel: str,
    reason: str,
    target: str,
    mode: str,
    priority: str,
    status: str,
    patient_phone: str = "",
    raw_name: str = "",
    validated_name: str = "",
    display_name: str = "",
    summary: str = "",
    transcript_excerpt: str = "",
    booking_start_iso: str = "",
    booking_end_iso: str = "",
    booking_motif: str = "",
    notes: str = "",
) -> Optional[Dict[str, Any]]:
    call_id = (call_id or "").strip()
    if not call_id:
        return None
    existing = get_handoff_by_call_id(tenant_id, call_id)
    if existing:
        return existing

    clean = {
        "channel": (channel or "vocal").strip()[:16] or "vocal",
        "reason": (reason or "fallback_transfer").strip()[:64] or "fallback_transfer",
        "target": (target or "assistant").strip()[:32] or "assistant",
        "mode": (mode or "callback_only").strip()[:32] or "callback_only",
        "priority": (priority or "normal").strip()[:32] or "normal",
        "status": (status or "callback_created").strip()[:32] or "callback_created",
        "patient_phone": db.normalize_phone_number(patient_phone)[:32],
        "raw_name": (raw_name or "").strip()[:160],
        "validated_name": (validated_name or "").strip()[:160],
        "display_name": (display_name or "").strip()[:160] or "Patient",
        "summary": (summary or "").strip()[:400],
        "transcript_excerpt": (transcript_excerpt or "").strip()[:2000],
        "booking_start_iso": (booking_start_iso or "").strip()[:64],
        "booking_end_iso": (booking_end_iso or "").strip()[:64],
        "booking_motif": (booking_motif or "").strip()[:240],
        "notes": (notes or "").strip()[:1000],
    }

    url = db._pg_events_url()
    if url:
        try:
            import psycopg

            with psycopg.connect(url) as conn:
                db._ensure_human_handoffs_table_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO human_handoffs (
                            tenant_id, call_id, channel, reason, target, mode, priority, status,
                            patient_phone, raw_name, validated_name, display_name, summary,
                            transcript_excerpt, booking_start_iso, booking_end_iso, booking_motif,
                            notes, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                        ON CONFLICT (tenant_id, call_id) DO NOTHING
                        """,
                        (
                            tenant_id,
                            call_id,
                            clean["channel"],
                            clean["reason"],
                            clean["target"],
                            clean["mode"],
                            clean["priority"],
                            clean["status"],
                            clean["patient_phone"] or None,
                            clean["raw_name"] or None,
                            clean["validated_name"] or None,
                            clean["display_name"] or None,
                            clean["summary"] or None,
                            clean["transcript_excerpt"] or None,
                            clean["booking_start_iso"] or None,
                            clean["booking_end_iso"] or None,
                            clean["booking_motif"] or None,
                            clean["notes"] or None,
                        ),
                    )
                    conn.commit()
        except Exception:
            pass

    conn = db.get_conn()
    try:
        db._ensure_human_handoffs_table(conn)
        conn.execute(
            """
            INSERT OR IGNORE INTO human_handoffs (
                tenant_id, call_id, channel, reason, target, mode, priority, status,
                patient_phone, raw_name, validated_name, display_name, summary,
                transcript_excerpt, booking_start_iso, booking_end_iso, booking_motif,
                notes, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tenant_id,
                call_id,
                clean["channel"],
                clean["reason"],
                clean["target"],
                clean["mode"],
                clean["priority"],
                clean["status"],
                clean["patient_phone"] or None,
                clean["raw_name"] or None,
                clean["validated_name"] or None,
                clean["display_name"] or None,
                clean["summary"] or None,
                clean["transcript_excerpt"] or None,
                clean["booking_start_iso"] or None,
                clean["booking_end_iso"] or None,
                clean["booking_motif"] or None,
                clean["notes"] or None,
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_handoff_by_call_id(tenant_id, call_id)


def list_handoffs(
    tenant_id: int,
    *,
    status: str | None = None,
    target: str | None = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    clean_status = (status or "").strip().lower()
    clean_target = (target or "").strip().lower()
    limit = max(1, min(int(limit or 50), 200))

    url = db._pg_events_url()
    if url:
        try:
            import psycopg
            from psycopg.rows import dict_row

            sql = "SELECT * FROM human_handoffs WHERE tenant_id = %s"
            params: List[Any] = [tenant_id]
            if clean_status:
                sql += " AND LOWER(status) = %s"
                params.append(clean_status)
            if clean_target:
                sql += " AND LOWER(target) = %s"
                params.append(clean_target)
            sql += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)
            with psycopg.connect(url, row_factory=dict_row) as conn:
                db._ensure_human_handoffs_table_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(sql, tuple(params))
                    items = [_handoff_row_to_dict(row) for row in cur.fetchall()]
                    if items:
                        return items
        except Exception:
            pass

    conn = db.get_conn()
    try:
        db._ensure_human_handoffs_table(conn)
        sql = "SELECT * FROM human_handoffs WHERE tenant_id = ?"
        params: List[Any] = [tenant_id]
        if clean_status:
            sql += " AND LOWER(status) = ?"
            params.append(clean_status)
        if clean_target:
            sql += " AND LOWER(target) = ?"
            params.append(clean_target)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, tuple(params)).fetchall()
        return [_handoff_row_to_dict(dict(row)) for row in rows]
    finally:
        conn.close()


def update_handoff_status(
    tenant_id: int,
    handoff_id: int,
    *,
    status: str,
    notes: str = "",
) -> Optional[Dict[str, Any]]:
    clean_status = (status or "").strip().lower()
    if clean_status not in ALLOWED_STATUSES:
        return None
    clean_notes = (notes or "").strip()[:1000]
    processed_at = datetime.utcnow().isoformat() if clean_status == "processed" else None

    url = db._pg_events_url()
    if url:
        try:
            import psycopg

            with psycopg.connect(url) as conn:
                db._ensure_human_handoffs_table_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE human_handoffs
                        SET status = %s,
                            notes = CASE WHEN %s = '' THEN COALESCE(notes, '') ELSE %s END,
                            processed_at = CASE WHEN %s = 'processed' THEN now() ELSE processed_at END,
                            updated_at = now()
                        WHERE tenant_id = %s AND id = %s
                        """,
                        (clean_status, clean_notes, clean_notes, clean_status, tenant_id, handoff_id),
                    )
                    conn.commit()
        except Exception:
            pass

    conn = db.get_conn()
    try:
        db._ensure_human_handoffs_table(conn)
        conn.execute(
            """
            UPDATE human_handoffs
            SET status = ?,
                notes = CASE WHEN ? = '' THEN COALESCE(notes, '') ELSE ? END,
                processed_at = CASE WHEN ? = 'processed' THEN ? ELSE processed_at END,
                updated_at = ?
            WHERE tenant_id = ? AND id = ?
            """,
            (
                clean_status,
                clean_notes,
                clean_notes,
                clean_status,
                processed_at,
                datetime.utcnow().isoformat(),
                tenant_id,
                handoff_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_handoff_by_id(tenant_id, handoff_id)


def ensure_transfer_handoff(
    session: Any,
    *,
    trigger_reason: str,
    user_text: str = "",
) -> Optional[Dict[str, Any]]:
    tenant_id = int(getattr(session, "tenant_id", 1) or 1)
    call_id = str(getattr(session, "conv_id", "") or "").strip()
    if not call_id:
        return None
    existing = get_handoff_by_call_id(tenant_id, call_id)
    if existing:
        return existing
    decision = resolve_handoff_decision(
        session,
        trigger_reason=trigger_reason,
        channel=str(getattr(session, "channel", "vocal") or "vocal"),
        user_text=user_text,
    )
    payload = build_handoff_payload(
        session,
        reason=decision["reason"],
        target=decision["target"],
        mode=decision["mode"],
        priority=decision["priority"],
    )
    return create_handoff(
        tenant_id,
        call_id,
        channel=payload["channel"],
        reason=payload["reason"],
        target=payload["target"],
        mode=payload["mode"],
        priority=payload["priority"],
        status=payload["status"],
        patient_phone=payload["patient_phone"],
        raw_name=payload["raw_name"],
        validated_name=payload["validated_name"],
        display_name=payload["display_name"],
        summary=payload["summary"],
        transcript_excerpt=payload["transcript_excerpt"],
        booking_start_iso=payload["booking_start_iso"],
        booking_end_iso=payload["booking_end_iso"],
        booking_motif=payload["booking_motif"],
        notes=payload["notes"],
    )
