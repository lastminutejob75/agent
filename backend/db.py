# backend/db.py
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional

DB_PATH = "agent.db"

SLOT_TIMES = ["10:00", "14:00", "16:00"]
TARGET_MIN_SLOTS = 15  # 5 jours ouvrés * 3 slots
MAX_DAYS_AHEAD = 30  # Limite de sécurité pour éviter boucle infinie


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_ivr_tables(conn: sqlite3.Connection) -> None:
    """Crée les tables ivr_events et calls si absentes (rapport quotidien IVR)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            call_id TEXT NOT NULL,
            outcome TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ivr_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            call_id TEXT,
            event TEXT NOT NULL,
            context TEXT,
            reason TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ivr_events_client_date ON ivr_events(client_id, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ivr_events_client_event_date ON ivr_events(client_id, event, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_calls_client_date ON calls(client_id, created_at)")


def create_ivr_event(
    client_id: int,
    call_id: str,
    event: str,
    context: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    """
    Insertion simple dans ivr_events (persistance pour rapport quotidien).
    Noms canoniques: booking_confirmed, transfer_human, abandon, intent_router_trigger,
    recovery_step, anti_loop_trigger, empty_message.
    """
    conn = get_conn()
    try:
        _ensure_ivr_tables(conn)
        conn.execute(
            """INSERT INTO ivr_events (client_id, call_id, event, context, reason)
               VALUES (?, ?, ?, ?, ?)""",
            (client_id, call_id or "", event, context or None, reason or None),
        )
        conn.commit()
    finally:
        conn.close()


def init_db(days: int = 7) -> None:
    conn = get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                is_booked INTEGER DEFAULT 0,
                UNIQUE(date, time)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                contact TEXT NOT NULL,
                contact_type TEXT NOT NULL,
                motif TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(slot_id) REFERENCES slots(id)
            )
        """)
        _ensure_ivr_tables(conn)
        
        # Seed slots (SKIP WEEKENDS)
        for day in range(1, days + 1):
            target_date = datetime.now() + timedelta(days=day)
            
            # Skip weekends
            if target_date.weekday() < 5:  # Lundi-Vendredi
                d = target_date.strftime("%Y-%m-%d")
                for t in SLOT_TIMES:
                    conn.execute(
                        "INSERT OR IGNORE INTO slots (date, time) VALUES (?, ?)",
                        (d, t)
                    )

        conn.commit()
    finally:
        conn.close()


def cleanup_old_slots() -> None:
    """
    Supprime les slots passés et garantit au moins TARGET_MIN_SLOTS slots futurs
    (lundi-vendredi uniquement).
    
    Logique :
    - Supprime tous les slots dont date < aujourd'hui
    - Compte les slots futurs restants
    - Crée de nouveaux slots (weekdays only) jusqu'à atteindre TARGET_MIN_SLOTS
    - Utilise BEGIN IMMEDIATE pour éviter race conditions
    
    Raises:
        Exception: Si erreur DB (rollback automatique)
    """
    conn = get_conn()
    try:
        # Lock write transaction (évite race)
        conn.execute("BEGIN IMMEDIATE")

        today = datetime.now().strftime("%Y-%m-%d")

        # Supprimer les slots passés
        conn.execute("DELETE FROM slots WHERE date < ?", (today,))

        # Compter les slots futurs (tous, pas seulement libres, car on veut garantir le nombre total)
        cur = conn.execute("SELECT COUNT(*) as c FROM slots WHERE date >= ?", (today,))
        count = int(cur.fetchone()["c"])

        missing = max(0, TARGET_MIN_SLOTS - count)
        if missing == 0:
            conn.commit()
            return

        day_offset = 1
        added = 0

        while added < missing:
            # Sécurité : évite boucle infinie (ne devrait jamais arriver avec 15 slots max)
            if day_offset > MAX_DAYS_AHEAD:
                break

            target_date = datetime.now() + timedelta(days=day_offset)

            # Weekdays only
            if target_date.weekday() < 5:
                d = target_date.strftime("%Y-%m-%d")

                for t in SLOT_TIMES:
                    if added >= missing:
                        break

                    before = conn.total_changes
                    conn.execute(
                        "INSERT OR IGNORE INTO slots (date, time) VALUES (?, ?)",
                        (d, t),
                    )
                    # On incrémente seulement si INSERT a vraiment changé qqch
                    if conn.total_changes > before:
                        added += 1

            day_offset += 1

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def count_free_slots(limit: int = 1000) -> int:
    cleanup_old_slots()  # Nettoyer avant de compter
    conn = get_conn()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        cur = conn.execute("SELECT COUNT(*) AS c FROM slots WHERE is_booked=0 AND date >= ?", (today,))
        return int(cur.fetchone()["c"])
    finally:
        conn.close()


def list_free_slots(limit: int = 3, pref: Optional[str] = None) -> List[Dict]:
    """
    Liste les créneaux libres.
    pref: "matin" (avant 12h), "après-midi" (14h-18h), "soir" (>=18h) — filtre pour cohérence avec la préférence user.
    """
    cleanup_old_slots()
    conn = get_conn()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        # Filtre horaire selon préférence (éviter 10h quand user a dit "je finis à 17h")
        time_condition = ""
        if pref == "matin":
            time_condition = " AND time < '12:00'"
        elif pref == "après-midi":
            time_condition = " AND time >= '14:00' AND time < '18:00'"
        elif pref == "soir":
            time_condition = " AND time >= '18:00'"
        params = (today, limit)
        cur = conn.execute(
            f"""
            SELECT id, date, time 
            FROM slots 
            WHERE is_booked=0 AND date >= ?{time_condition}
            ORDER BY date ASC, time ASC 
            LIMIT ?
            """,
            params
        )
        out = []
        for r in cur.fetchall():
            out.append({"id": int(r["id"]), "date": r["date"], "time": r["time"]})
        return out
    finally:
        conn.close()


def book_slot_atomic(
    slot_id: int,
    name: str,
    contact: str,
    contact_type: str,
    motif: str
) -> bool:
    """
    Book atomique.
    Returns False if slot already booked.
    """
    conn = get_conn()
    try:
        conn.execute("BEGIN")
        conn.execute(
            "UPDATE slots SET is_booked=1 WHERE id=? AND is_booked=0",
            (slot_id,)
        )
        if conn.total_changes == 0:
            conn.rollback()
            return False

        conn.execute(
            """
            INSERT INTO appointments (slot_id, name, contact, contact_type, motif, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (slot_id, name, contact, contact_type, motif, datetime.utcnow().isoformat())
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def find_booking_by_name(name: str) -> Optional[Dict]:
    """
    Recherche un RDV SQLite par nom du patient (insensible à la casse).
    Returns:
        Dict avec id (appointment id), slot_id, date, time, name, contact, contact_type, motif
        ou None si non trouvé.
    """
    if not name or not name.strip():
        return None
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT a.id, a.slot_id, a.name, a.contact, a.contact_type, a.motif, s.date, s.time
            FROM appointments a
            JOIN slots s ON s.id = a.slot_id
            WHERE LOWER(TRIM(a.name)) = LOWER(TRIM(?))
            ORDER BY a.created_at DESC
            LIMIT 1
            """,
            (name.strip(),),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "slot_id": row["slot_id"],
            "name": row["name"],
            "contact": row["contact"],
            "contact_type": row["contact_type"],
            "motif": row["motif"],
            "date": row["date"],
            "time": row["time"],
        }
    finally:
        conn.close()


def cancel_booking_sqlite(booking: Dict) -> bool:
    """
    Annule un RDV SQLite : supprime l'appointment et libère le slot.
    booking doit contenir au moins slot_id (ou id de l'appointment).
    Returns True si annulation effectuée.
    """
    slot_id = booking.get("slot_id")
    appt_id = booking.get("id")
    conn = get_conn()
    try:
        conn.execute("BEGIN")
        if slot_id is not None:
            conn.execute("DELETE FROM appointments WHERE slot_id = ?", (slot_id,))
        elif appt_id is not None:
            cur = conn.execute("SELECT slot_id FROM appointments WHERE id = ?", (appt_id,))
            r = cur.fetchone()
            if not r:
                conn.rollback()
                return False
            slot_id = r["slot_id"]
            conn.execute("DELETE FROM appointments WHERE id = ?", (appt_id,))
        else:
            conn.rollback()
            return False
        if conn.total_changes == 0:
            conn.rollback()
            return False
        conn.execute("UPDATE slots SET is_booked = 0 WHERE id = ?", (slot_id,))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_daily_report_data(client_id: int, date_str: str) -> Dict:
    """
    Métriques IVR pour le rapport quotidien (email).
    Source: ivr_events + calls uniquement (pas appointments: pas de client_id/status).
    Booked = event 'booking_confirmed' dans ivr_events.

    date_str: "YYYY-MM-DD"
    Fenêtre: [day 00:00:00, day+1 00:00:00) pour éviter les soucis de format ISO.

    Events attendus (à persister depuis l'engine): booking_confirmed, recovery_step,
    intent_router_trigger, anti_loop_trigger, empty_message, transfer/transferred/transfer_human,
    abandon/hangup/user_hangup.
    """
    conn = get_conn()
    try:
        _ensure_ivr_tables(conn)
        day = date_str[:10]
        start_ts = day + " 00:00:00"

        # 1) Calls total (par client)
        cur = conn.execute(
            """SELECT COUNT(*) AS calls_total
               FROM calls
               WHERE client_id = ?
                 AND created_at >= ?
                 AND created_at < datetime(? || ' 00:00:00', '+1 day')""",
            (client_id, start_ts, day),
        )
        row = cur.fetchone()
        calls_total = row["calls_total"] or 0

        # 2) Booked / Transfers / Abandons (ivr_events)
        cur = conn.execute(
            """SELECT COUNT(*) AS booked
               FROM ivr_events
               WHERE client_id = ? AND event = 'booking_confirmed'
                 AND created_at >= ? AND created_at < datetime(? || ' 00:00:00', '+1 day')""",
            (client_id, start_ts, day),
        )
        booked = cur.fetchone()["booked"] or 0

        cur = conn.execute(
            """SELECT COUNT(*) AS transfers
               FROM ivr_events
               WHERE client_id = ? AND event IN ('transfer', 'transferred', 'transfer_human')
                 AND created_at >= ? AND created_at < datetime(? || ' 00:00:00', '+1 day')""",
            (client_id, start_ts, day),
        )
        transfers = cur.fetchone()["transfers"] or 0

        cur = conn.execute(
            """SELECT COUNT(*) AS abandons
               FROM ivr_events
               WHERE client_id = ? AND event IN ('abandon', 'hangup', 'user_hangup')
                 AND created_at >= ? AND created_at < datetime(? || ' 00:00:00', '+1 day')""",
            (client_id, start_ts, day),
        )
        abandons = cur.fetchone()["abandons"] or 0

        # 3) Santé agent: intent_router / recovery / anti_loop (une requête)
        cur = conn.execute(
            """SELECT
                 SUM(CASE WHEN event = 'intent_router_trigger' THEN 1 ELSE 0 END) AS intent_router_count,
                 SUM(CASE WHEN event = 'recovery_step'         THEN 1 ELSE 0 END) AS recovery_count,
                 SUM(CASE WHEN event = 'anti_loop_trigger'   THEN 1 ELSE 0 END) AS anti_loop_count
               FROM ivr_events
               WHERE client_id = ?
                 AND created_at >= ? AND created_at < datetime(? || ' 00:00:00', '+1 day')""",
            (client_id, start_ts, day),
        )
        r = cur.fetchone()
        intent_router_count = r["intent_router_count"] or 0
        recovery_count = r["recovery_count"] or 0
        anti_loop_count = r["anti_loop_count"] or 0

        # 4) Silences répétés (empty_message >= 2 dans un call)
        cur = conn.execute(
            """SELECT COUNT(*) AS silent_calls
               FROM (
                 SELECT call_id
                 FROM ivr_events
                 WHERE client_id = ? AND event = 'empty_message'
                   AND created_at >= ? AND created_at < datetime(? || ' 00:00:00', '+1 day')
                   AND call_id IS NOT NULL AND call_id != ''
                 GROUP BY call_id
                 HAVING COUNT(*) >= 2
               ) t""",
            (client_id, start_ts, day),
        )
        empty_silence_calls = cur.fetchone()["silent_calls"] or 0

        # 5) Top 3 contexts (recovery_step)
        cur = conn.execute(
            """SELECT COALESCE(context, 'unknown') AS context, COUNT(*) AS cnt
               FROM ivr_events
               WHERE client_id = ? AND event = 'recovery_step'
                 AND created_at >= ? AND created_at < datetime(? || ' 00:00:00', '+1 day')
               GROUP BY COALESCE(context, 'unknown')
               ORDER BY cnt DESC
               LIMIT 3""",
            (client_id, start_ts, day),
        )
        top_contexts = [{"context": row["context"], "count": row["cnt"]} for row in cur.fetchall()]

        # 6) Qualité booking: direct / after recovery / after intent_router
        cur = conn.execute(
            """SELECT COUNT(*) AS direct_booking
               FROM (
                 SELECT DISTINCT e.call_id
                 FROM ivr_events e
                 WHERE e.client_id = ? AND e.event = 'booking_confirmed'
                   AND e.created_at >= ? AND e.created_at < datetime(? || ' 00:00:00', '+1 day')
                   AND e.call_id IS NOT NULL AND e.call_id != ''
                   AND NOT EXISTS (
                     SELECT 1 FROM ivr_events r
                     WHERE r.client_id = e.client_id AND r.call_id = e.call_id AND r.event = 'recovery_step'
                   )
                   AND NOT EXISTS (
                     SELECT 1 FROM ivr_events ir
                     WHERE ir.client_id = e.client_id AND ir.call_id = e.call_id AND ir.event = 'intent_router_trigger'
                   )
               ) t""",
            (client_id, start_ts, day),
        )
        direct_booking = cur.fetchone()["direct_booking"] or 0

        cur = conn.execute(
            """SELECT COUNT(*) AS booking_after_recovery
               FROM (
                 SELECT DISTINCT e.call_id
                 FROM ivr_events e
                 WHERE e.client_id = ? AND e.event = 'booking_confirmed'
                   AND e.created_at >= ? AND e.created_at < datetime(? || ' 00:00:00', '+1 day')
                   AND e.call_id IS NOT NULL AND e.call_id != ''
                   AND EXISTS (
                     SELECT 1 FROM ivr_events r
                     WHERE r.client_id = e.client_id AND r.call_id = e.call_id AND r.event = 'recovery_step'
                   )
               ) t""",
            (client_id, start_ts, day),
        )
        booking_after_recovery = cur.fetchone()["booking_after_recovery"] or 0

        cur = conn.execute(
            """SELECT COUNT(*) AS booking_after_intent_router
               FROM (
                 SELECT DISTINCT e.call_id
                 FROM ivr_events e
                 WHERE e.client_id = ? AND e.event = 'booking_confirmed'
                   AND e.created_at >= ? AND e.created_at < datetime(? || ' 00:00:00', '+1 day')
                   AND e.call_id IS NOT NULL AND e.call_id != ''
                   AND EXISTS (
                     SELECT 1 FROM ivr_events ir
                     WHERE ir.client_id = e.client_id AND ir.call_id = e.call_id AND ir.event = 'intent_router_trigger'
                   )
               ) t""",
            (client_id, start_ts, day),
        )
        booking_after_intent_router = cur.fetchone()["booking_after_intent_router"] or 0

        # Total events (pour footer debug admin)
        cur = conn.execute(
            """SELECT COUNT(*) AS events_count
               FROM ivr_events
               WHERE client_id = ?
                 AND created_at >= ? AND created_at < datetime(? || ' 00:00:00', '+1 day')""",
            (client_id, start_ts, day),
        )
        events_count = cur.fetchone()["events_count"] or 0

        return {
            "calls_total": calls_total,
            "booked": booked,
            "transfers": transfers,
            "abandons": abandons,
            "intent_router_count": intent_router_count,
            "recovery_count": recovery_count,
            "anti_loop_count": anti_loop_count,
            "empty_silence_calls": empty_silence_calls,
            "top_contexts": top_contexts,
            "direct_booking": direct_booking,
            "booking_after_recovery": booking_after_recovery,
            "booking_after_intent_router": booking_after_intent_router,
            "events_count": events_count,
        }
    finally:
        conn.close()
