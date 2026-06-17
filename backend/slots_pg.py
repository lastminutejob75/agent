# backend/slots_pg.py
"""
Postgres slots + appointments (PG-first, SQLite fallback).
tenant_id pour isolation multi-tenant.
start_ts remplace (date, time).
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
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


def _apply_tenant_rls(conn, tenant_id: Optional[int]) -> None:
    """Pose le contexte tenant RLS (``app.current_tenant_id``) sur la connexion.

    Les tables ``slots`` et ``appointments`` ont RLS activé (policy
    ``app_tenant_matches(tenant_id)`` en USING **et** WITH CHECK). Sans ce
    contexte, les lectures renvoient 0 ligne et les écritures sont rejetées
    ("new row violates row-level security policy"). On utilise ``set_config(..,
    false)`` (niveau session) pour que le contexte survive aux commits internes.
    """
    try:
        tid = int(tenant_id)
    except (TypeError, ValueError):
        return
    if tid < 1:
        return
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (str(tid),))


@contextmanager
def _connect_pg(url: str, tenant_id: Optional[int] = None, *, row_factory=None):
    """Ouvre une connexion PG et applique immédiatement le contexte tenant RLS.

    Remplace les ``psycopg.connect(url)`` bruts qui ne posaient pas le contexte
    RLS et cassaient lectures/écritures sur slots/appointments.
    """
    import psycopg

    kwargs: Dict[str, Any] = {}
    if row_factory is not None:
        kwargs["row_factory"] = row_factory
    with psycopg.connect(url, **kwargs) as conn:
        _apply_tenant_rls(conn, tenant_id)
        yield conn


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
        with _connect_pg(url, tenant_id, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, start_ts
                    FROM slots
                    WHERE tenant_id = %s AND is_booked = FALSE
                      AND start_ts >= (NOW() AT TIME ZONE 'Europe/Paris') + INTERVAL '30 minutes'
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
        with _connect_pg(url, tenant_id) as conn:
            with conn.cursor() as cur:
                # start_ts format: timestamp, on compare date+time
                cur.execute(
                    """
                    SELECT id FROM slots
                    WHERE tenant_id = %s AND is_booked = FALSE
                      AND (start_ts AT TIME ZONE 'Europe/Paris')::date = %s::date
                      AND to_char(start_ts AT TIME ZONE 'Europe/Paris', 'HH24:MI') = %s
                    LIMIT 1
                    """,
                    (tenant_id, date_str[:10], (time_str or "09:00")[:5]),
                )
                row = cur.fetchone()
                return int(row[0]) if row else None
    except Exception as e:
        logger.debug("pg_find_slot_id_by_datetime failed: %s", e)
        return None


def pg_list_free_slots_for_date(
    tenant_id: int,
    date_str: str,
) -> Optional[List[Dict[str, Any]]]:
    """Créneaux libres pour une date (déplacement RDV)."""
    url = _pg_url()
    if not url:
        return None

    def _query() -> Optional[List[Dict[str, Any]]]:
        import psycopg
        from psycopg.rows import dict_row

        with _connect_pg(url, tenant_id, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, start_ts
                    FROM slots
                    WHERE tenant_id = %s
                      AND is_booked = FALSE
                      AND start_ts::date = %s::date
                    ORDER BY start_ts ASC
                    """,
                    (tenant_id, date_str[:10]),
                )
                rows = cur.fetchall()
                out: List[Dict[str, Any]] = []
                for row in rows:
                    date_s, time_s = _start_ts_to_date_time(row.get("start_ts"))
                    out.append({
                        "id": int(row.get("id") or 0),
                        "date": date_s,
                        "time": time_s,
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
        logger.debug("pg_list_free_slots_for_date failed: %s", e)
        return None


def pg_count_free_slots_by_month(tenant_id: int, month: str) -> Optional[Dict[str, int]]:
    """Nombre de créneaux libres par jour pour un mois (calendrier déplacement)."""
    url = _pg_url()
    if not url:
        return None
    month_key = str(month or "")[:7]
    if len(month_key) != 7:
        return None

    def _query() -> Optional[Dict[str, int]]:
        import psycopg

        with _connect_pg(url, tenant_id) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT to_char(start_ts AT TIME ZONE 'Europe/Paris', 'YYYY-MM-DD') AS d,
                           COUNT(*)::int AS cnt
                    FROM slots
                    WHERE tenant_id = %s
                      AND is_booked = FALSE
                      AND to_char(start_ts AT TIME ZONE 'Europe/Paris', 'YYYY-MM') = %s
                      AND start_ts::date >= CURRENT_DATE
                    GROUP BY 1
                    ORDER BY 1
                    """,
                    (tenant_id, month_key),
                )
                return {str(row[0]): int(row[1]) for row in cur.fetchall() if row[0]}

    try:
        return _query()
    except Exception as e:
        if _is_transient(e):
            try:
                return _query()
            except Exception:
                pass
        logger.debug("pg_count_free_slots_by_month failed: %s", e)
        return None


def pg_count_free_slots_horizon(
    tenant_id: int,
    days: int = 7,
    tz_name: str = "Europe/Paris",
) -> Optional[Dict[str, int]]:
    """Créneaux libres par jour sur N jours civils à partir d'aujourd'hui (sans cleanup)."""
    url = _pg_url()
    if not url:
        return None
    safe_days = max(1, min(int(days or 7), 31))
    tz_key = (tz_name or "Europe/Paris").strip() or "Europe/Paris"

    def _query() -> Optional[Dict[str, int]]:
        import psycopg

        with _connect_pg(url, tenant_id) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT to_char(start_ts AT TIME ZONE %s, 'YYYY-MM-DD') AS d,
                           COUNT(*)::int AS cnt
                    FROM slots
                    WHERE tenant_id = %s
                      AND is_booked = FALSE
                      AND (start_ts AT TIME ZONE %s)::date >= (CURRENT_TIMESTAMP AT TIME ZONE %s)::date
                      AND (start_ts AT TIME ZONE %s)::date
                          < (CURRENT_TIMESTAMP AT TIME ZONE %s)::date + %s
                    GROUP BY 1
                    ORDER BY 1
                    """,
                    (tz_key, tenant_id, tz_key, tz_key, tz_key, tz_key, safe_days),
                )
                return {str(row[0]): int(row[1]) for row in cur.fetchall() if row[0]}

    try:
        return _query()
    except Exception as e:
        if _is_transient(e):
            try:
                return _query()
            except Exception:
                pass
        logger.debug("pg_count_free_slots_horizon failed: %s", e)
        return None


def pg_ensure_slot_id_by_datetime(
    date_str: str,
    time_str: str,
    tenant_id: int = 1,
) -> Optional[int]:
    """
    Garantit l'existence d'un slot pour une date/heure donnée et retourne son id.
    Utilisé pour mirrorer un RDV Google dans l'agenda interne UWI.
    """
    url = _pg_url()
    if not url:
        return None

    def _do() -> Optional[int]:
        import psycopg
        with _connect_pg(url, tenant_id) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id FROM slots
                    WHERE tenant_id = %s
                      AND (start_ts AT TIME ZONE 'Europe/Paris')::date = %s::date
                      AND to_char(start_ts AT TIME ZONE 'Europe/Paris', 'HH24:MI') = %s
                    ORDER BY id ASC
                    LIMIT 1
                    """,
                    (tenant_id, date_str[:10], (time_str or "09:00")[:5]),
                )
                row = cur.fetchone()
                if row:
                    conn.commit()
                    return int(row[0])

                # Certaines bases historiques n'ont pas la contrainte UNIQUE
                # (tenant_id, start_ts). Eviter ON CONFLICT rend le miroir
                # dashboard -> agenda interne robuste sur ces schémas.
                cur.execute(
                    """
                    INSERT INTO slots (tenant_id, start_ts)
                    VALUES (%s, (%s::timestamp AT TIME ZONE 'Europe/Paris'))
                    RETURNING id
                    """,
                    (tenant_id, f"{date_str[:10]}T{(time_str or '09:00')[:5]}:00"),
                )
                row = cur.fetchone()
                conn.commit()
                return int(row[0]) if row else None

    try:
        return _do()
    except Exception as e:
        if _is_transient(e):
            try:
                return _do()
            except Exception:
                pass
        logger.warning("pg_ensure_slot_id_by_datetime failed tenant_id=%s: %s", tenant_id, e)
        return None


def pg_count_free_slots(tenant_id: int) -> Optional[int]:
    """Compte les créneaux libres (après cleanup)."""
    url = _pg_url()
    if not url:
        return None

    def _query() -> Optional[int]:
        import psycopg
        with _connect_pg(url, tenant_id) as conn:
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


def pg_attach_google_event_id(
    tenant_id: int,
    google_event_id: str,
    *,
    appointment_id: Optional[int] = None,
    slot_id: Optional[int] = None,
) -> Optional[bool]:
    """Associe un événement Google à un RDV miroir local."""
    event_id = str(google_event_id or "").strip()
    if not event_id or (not appointment_id and not slot_id):
        return False
    url = _pg_url()
    if not url:
        return None

    def _do() -> Optional[bool]:
        import psycopg

        with _connect_pg(url, tenant_id) as conn:
            with conn.cursor() as cur:
                if appointment_id:
                    cur.execute(
                        """
                        UPDATE appointments
                        SET google_event_id = %s
                        WHERE tenant_id = %s AND id = %s
                        """,
                        (event_id[:256], tenant_id, appointment_id),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE appointments
                        SET google_event_id = %s
                        WHERE tenant_id = %s AND slot_id = %s
                        """,
                        (event_id[:256], tenant_id, slot_id),
                    )
                if cur.rowcount == 0:
                    conn.rollback()
                    return False
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
        logger.debug("pg_attach_google_event_id failed tenant_id=%s err=%s", tenant_id, e)
        return None


def pg_book_slot_atomic(
    tenant_id: int,
    slot_id: int,
    name: str,
    contact: str,
    contact_type: str,
    motif: str,
    booking_origin: Optional[str] = None,
    google_event_id: Optional[str] = None,
    booking_code: Optional[str] = None,
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
        with _connect_pg(url, tenant_id) as conn:
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
                bo = (booking_origin or "").strip()[:40] or None
                ge = (google_event_id or "").strip()[:256] or None
                from backend.booking_code import create_unique_booking_code_pg

                stored_code = (booking_code or "").strip().upper()[:8] or None
                if not stored_code:
                    stored_code = create_unique_booking_code_pg(cur, tenant_id)
                cur.execute(
                    """
                    INSERT INTO appointments (
                        tenant_id, slot_id, name, contact, contact_type, motif,
                        booking_origin, google_event_id, booking_code
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (tenant_id, slot_id, name, contact, contact_type, motif, bo, ge, stored_code),
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
        logger.warning("pg_book_slot_atomic failed tenant_id=%s slot_id=%s: %s", tenant_id, slot_id, e)
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
        with _connect_pg(url, tenant_id, row_factory=dict_row) as conn:
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
        with _connect_pg(url, tenant_id) as conn:
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


def pg_reschedule_booking_atomic(tenant_id: int, appt_id: int, new_slot_id: int) -> Optional[bool]:
    """Déplace un RDV local vers un nouveau slot PG dans une seule transaction."""
    if not appt_id or not new_slot_id:
        return False
    url = _pg_url()
    if not url:
        return None

    def _do() -> Optional[bool]:
        import psycopg
        with _connect_pg(url, tenant_id) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT slot_id, name, contact, contact_type, motif, booking_origin, google_event_id
                    FROM appointments
                    WHERE tenant_id = %s AND id = %s
                    FOR UPDATE
                    """,
                    (tenant_id, appt_id),
                )
                row = cur.fetchone()
                if not row:
                    conn.rollback()
                    return False
                old_slot_id, name, contact, contact_type, motif, booking_origin, google_event_id = row
                if int(old_slot_id) == int(new_slot_id):
                    conn.rollback()
                    return False

                cur.execute(
                    """
                    UPDATE slots SET is_booked = TRUE
                    WHERE tenant_id = %s AND id = %s AND is_booked = FALSE
                    RETURNING id
                    """,
                    (tenant_id, new_slot_id),
                )
                locked = cur.fetchone()
                if not locked:
                    conn.rollback()
                    return False

                bo = ((booking_origin or "").strip()[:40] if booking_origin else None)
                ge = ((google_event_id or "").strip()[:256] if google_event_id else None)
                from backend.booking_code import create_unique_booking_code_pg

                new_code = create_unique_booking_code_pg(cur, tenant_id)
                cur.execute(
                    """
                    INSERT INTO appointments (
                        tenant_id, slot_id, name, contact, contact_type, motif,
                        booking_origin, google_event_id, booking_code
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (tenant_id, new_slot_id, name, contact, contact_type, motif, bo, ge, new_code),
                )
                cur.execute(
                    "DELETE FROM appointments WHERE tenant_id = %s AND id = %s",
                    (tenant_id, appt_id),
                )
                cur.execute(
                    "UPDATE slots SET is_booked = FALSE WHERE tenant_id = %s AND id = %s",
                    (tenant_id, old_slot_id),
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
        logger.debug("pg_reschedule_booking_atomic failed: %s", e)
        return None


def pg_booking_code_for_slot(tenant_id: int, slot_id: int) -> Optional[str]:
    """Code RDV de l'appointment actif sur un slot (après déplacement)."""
    if not slot_id:
        return None
    url = _pg_url()
    if not url:
        return None
    try:
        import psycopg
        from psycopg.rows import dict_row

        with _connect_pg(url, tenant_id, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT booking_code
                    FROM appointments
                    WHERE tenant_id = %s AND slot_id = %s
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (tenant_id, int(slot_id)),
                )
                row = cur.fetchone()
                code = str((row or {}).get("booking_code") or "").strip()
                return code or None
    except Exception as exc:
        logger.debug("pg_booking_code_for_slot failed tenant=%s slot=%s: %s", tenant_id, slot_id, exc)
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
        with _connect_pg(url, tenant_id) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM slots s
                    WHERE s.tenant_id = %s
                      AND s.start_ts < CURRENT_DATE + INTERVAL '1 day'
                      AND NOT EXISTS (SELECT 1 FROM appointments a WHERE a.slot_id = s.id)
                    """,
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
