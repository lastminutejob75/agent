# backend/slots_pg.py
"""
Postgres slots + appointments (PG-first, SQLite fallback).
tenant_id pour isolation multi-tenant.
start_ts remplace (date, time).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SLOT_TIMES = ["10:00", "14:00", "16:00"]
TARGET_MIN_SLOTS = 15
MAX_DAYS_AHEAD = 30


def _pg_url() -> Optional[str]:
    return os.environ.get("DATABASE_URL") or os.environ.get("PG_SLOTS_URL")


def _is_transient(e: Exception) -> bool:
    msg = str(e).lower()
    return any(x in msg for x in ("connection", "timeout", "refused", "could not connect"))


def _start_ts_to_date_time(start_ts: Any) -> tuple[str, str]:
    """Convertit start_ts PostgreSQL en (date, time) pour compat SlotDisplay."""
    if start_ts is None:
        return ("", "09:00")
    s = str(start_ts)
    if " " in s:
        date_part, time_part = s.split(" ", 1)
        t = time_part[:5] if len(time_part) >= 5 else "09:00"
        return (date_part[:10], t)
    return (s[:10] if len(s) >= 10 else "", "09:00")


def pg_list_free_slots(
    tenant_id: int,
    limit: int = 3,
    pref: Optional[str] = None,
) -> Optional[List[Dict[str, Any]]]:
    """
    Liste les créneaux libres depuis PG.
    Returns [{"id", "date", "time", "start_ts"}, ...] ou None si échec.
    """
    url = _pg_url()
    if not url:
        return None

    time_cond = ""
    if pref == "matin":
        time_cond = " AND EXTRACT(HOUR FROM start_ts AT TIME ZONE 'Europe/Paris') < 12"
    elif pref == "après-midi":
        time_cond = " AND EXTRACT(HOUR FROM start_ts AT TIME ZONE 'Europe/Paris') >= 14 AND EXTRACT(HOUR FROM start_ts AT TIME ZONE 'Europe/Paris') < 18"
    elif pref == "soir":
        time_cond = " AND EXTRACT(HOUR FROM start_ts AT TIME ZONE 'Europe/Paris') >= 18"

    def _query() -> Optional[List[Dict[str, Any]]]:
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, start_ts
                    FROM slots
                    WHERE tenant_id = %s AND is_booked = FALSE
                      AND start_ts >= CURRENT_DATE + INTERVAL '1 day'
                      {time_cond}
                    ORDER BY start_ts ASC
                    LIMIT %s
                    """,
                    (tenant_id, limit),
                )
                rows = cur.fetchall()
                out = []
                for r in rows:
                    date_s, time_s = _start_ts_to_date_time(r["start_ts"])
                    out.append({
                        "id": int(r["id"]),
                        "date": date_s,
                        "time": time_s,
                        "start_ts": r["start_ts"],
                    })
                return out

    try:
        return _query()
    except Exception as e:
        if _is_transient(e):
            try:
                return _query()
            except Exception:
                pass
        return None


def pg_find_slot_id_by_datetime(
    date_str: str,
    time_str: str,
    tenant_id: int = 1,
) -> Optional[int]:
    """
    Trouve l'id d'un slot libre par date et heure (ex: "2026-02-16", "09:00").
    Retourne None si non trouvé ou déjà réservé.
    """
    url = _pg_url()
    if not url:
        return None
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                # start_ts format: timestamp, on compare date+time
                cur.execute(
                    """
                    SELECT id FROM slots
                    WHERE tenant_id = %s AND is_booked = FALSE
                      AND start_ts::date = %s::date
                      AND to_char(start_ts, 'HH24:MI') = %s
                    LIMIT 1
                    """,
                    (tenant_id, date_str[:10], (time_str or "09:00")[:5]),
                )
                row = cur.fetchone()
                return int(row[0]) if row else None
    except Exception as e:
        logger.debug("pg_find_slot_id_by_datetime failed: %s", e)
        return None


def pg_count_free_slots(tenant_id: int) -> Optional[int]:
    """Compte les créneaux libres (après cleanup)."""
    url = _pg_url()
    if not url:
        return None

    def _query() -> Optional[int]:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM slots
                    WHERE tenant_id = %s AND is_booked = FALSE
                      AND start_ts >= CURRENT_DATE + INTERVAL '1 day'
                    """,
                    (tenant_id,),
                )
                row = cur.fetchone()
                return int(row[0]) if row else 0

    try:
        return _query()
    except Exception as e:
        if _is_transient(e):
            try:
                return _query()
            except Exception:
                pass
        return None


def pg_book_slot_atomic(
    tenant_id: int,
    slot_id: int,
    name: str,
    contact: str,
    contact_type: str,
    motif: str,
) -> Optional[bool]:
    """
    Booking atomique : UPDATE slots SET is_booked=TRUE WHERE id=? AND is_booked=FALSE RETURNING id.
    Returns True si succès, False si déjà pris, None si échec PG.
    """
    url = _pg_url()
    if not url:
        return None

    def _do() -> Optional[bool]:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE slots SET is_booked = TRUE
                    WHERE tenant_id = %s AND id = %s AND is_booked = FALSE
                    RETURNING id
                    """,
                    (tenant_id, slot_id),
                )
                row = cur.fetchone()
                if not row:
                    conn.rollback()
                    return False
                cur.execute(
                    """
                    INSERT INTO appointments (tenant_id, slot_id, name, contact, contact_type, motif)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (tenant_id, slot_id, name, contact, contact_type, motif),
                )
                conn.commit()
                return True

    try:
        return _do()
    except Exception as e:
        if _is_transient(e):
            try:
                return _do()
            except Exception:
                pass
        return None


def pg_find_booking_by_name(tenant_id: int, name: str) -> Optional[Dict[str, Any]]:
    """Recherche RDV par nom (insensible à la casse)."""
    if not name or not str(name).strip():
        return None
    url = _pg_url()
    if not url:
        return None

    def _query() -> Optional[Dict[str, Any]]:
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT a.id, a.slot_id, a.name, a.contact, a.contact_type, a.motif,
                           s.start_ts
                    FROM appointments a
                    JOIN slots s ON s.id = a.slot_id
                    WHERE a.tenant_id = %s AND LOWER(TRIM(a.name)) = LOWER(TRIM(%s))
                    ORDER BY a.created_at DESC
                    LIMIT 1
                    """,
                    (tenant_id, name.strip()),
                )
                row = cur.fetchone()
                if not row:
                    return None
                date_s, time_s = _start_ts_to_date_time(row["start_ts"])
                return {
                    "id": row["id"],
                    "slot_id": row["slot_id"],
                    "name": row["name"],
                    "contact": row["contact"],
                    "contact_type": row["contact_type"],
                    "motif": row["motif"],
                    "date": date_s,
                    "time": time_s,
                }

    try:
        return _query()
    except Exception as e:
        if _is_transient(e):
            try:
                return _query()
            except Exception:
                pass
        return None


def pg_cancel_booking(tenant_id: int, booking: Dict[str, Any]) -> Optional[bool]:
    """Annule un RDV (supprime appointment, libère slot)."""
    slot_id = booking.get("slot_id")
    appt_id = booking.get("id")
    if slot_id is None and appt_id is None:
        return False
    url = _pg_url()
    if not url:
        return None

    def _do() -> Optional[bool]:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                sid = slot_id
                if sid is None and appt_id is not None:
                    cur.execute(
                        "SELECT slot_id FROM appointments WHERE tenant_id = %s AND id = %s",
                        (tenant_id, appt_id),
                    )
                    r = cur.fetchone()
                    if not r:
                        return False
                    sid = r[0]
                if sid is None:
                    return False
                if appt_id is not None:
                    cur.execute(
                        "DELETE FROM appointments WHERE tenant_id = %s AND id = %s",
                        (tenant_id, appt_id),
                    )
                else:
                    cur.execute(
                        "DELETE FROM appointments WHERE tenant_id = %s AND slot_id = %s",
                        (tenant_id, sid),
                    )
                if cur.rowcount == 0:
                    conn.rollback()
                    return False
                cur.execute(
                    "UPDATE slots SET is_booked = FALSE WHERE tenant_id = %s AND id = %s",
                    (tenant_id, sid),
                )
                conn.commit()
                return True

    try:
        return _do()
    except Exception as e:
        if _is_transient(e):
            try:
                return _do()
            except Exception:
                pass
        return None


def pg_cleanup_and_ensure_slots(tenant_id: int) -> Optional[bool]:
    """
    Supprime slots passés, garantit TARGET_MIN_SLOTS futurs (weekdays).
    Returns True si succès, None si échec.
    """
    url = _pg_url()
    if not url:
        return None

    def _do() -> Optional[bool]:
        import psycopg
        from datetime import timedelta
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM slots WHERE tenant_id = %s AND start_ts < CURRENT_DATE + INTERVAL '1 day'",
                    (tenant_id,),
                )
                cur.execute(
                    "SELECT COUNT(*) FROM slots WHERE tenant_id = %s AND start_ts >= CURRENT_DATE + INTERVAL '1 day'",
                    (tenant_id,),
                )
                count = int(cur.fetchone()[0])
                missing = max(0, TARGET_MIN_SLOTS - count)
                day_offset = 1
                added = 0
                while added < missing and day_offset <= MAX_DAYS_AHEAD:
                    target = datetime.utcnow() + timedelta(days=day_offset)
                    if target.weekday() < 5:  # Lundi-Vendredi
                        for t in SLOT_TIMES:
                            if added >= missing:
                                break
                            h, m = map(int, t.split(":"))
                            start_ts = target.replace(hour=h, minute=m, second=0, microsecond=0)
                            cur.execute(
                                """
                                INSERT INTO slots (tenant_id, start_ts)
                                VALUES (%s, %s)
                                ON CONFLICT (tenant_id, start_ts) DO NOTHING
                                """,
                                (tenant_id, start_ts),
                            )
                            if cur.rowcount > 0:
                                added += 1
                    day_offset += 1
                conn.commit()
                return True

    try:
        return _do()
    except Exception as e:
        if _is_transient(e):
            try:
                return _do()
            except Exception:
                pass
        return None
