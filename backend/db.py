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


def _ensure_tenants_tables(conn: sqlite3.Connection) -> None:
    """Crée les tables tenants + tenant_config (feature flags par tenant)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tenants (
            tenant_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            timezone TEXT DEFAULT 'Europe/Paris',
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tenant_config (
            tenant_id INTEGER PRIMARY KEY,
            flags_json TEXT NOT NULL DEFAULT '{}',
            params_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tenant_status ON tenants(status)")

    # Migration: ajouter params_json si absente (schéma legacy)
    try:
        cur = conn.execute("PRAGMA table_info(tenant_config)")
        cols = [row[1] for row in cur.fetchall()]
        if "params_json" not in cols:
            conn.execute("ALTER TABLE tenant_config ADD COLUMN params_json TEXT NOT NULL DEFAULT '{}'")
    except Exception:
        pass

    # Seed minimal (INSERT OR IGNORE = ne pas écraser config existant)
    conn.execute("INSERT OR IGNORE INTO tenants (tenant_id, name) VALUES (1, 'DEFAULT')")
    conn.execute(
        "INSERT OR IGNORE INTO tenant_config (tenant_id, flags_json, params_json, updated_at) VALUES (1, '{}', '{}', datetime('now'))"
    )

    # tenant_routing (DID → tenant_id)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tenant_routing (
            channel TEXT NOT NULL DEFAULT 'vocal',
            did_key TEXT NOT NULL,
            tenant_id INTEGER NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (channel, did_key),
            FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tenant_routing_lookup ON tenant_routing(channel, did_key)")


def ensure_tenant_config() -> None:
    """Garantit que les tables tenants/tenant_config existent."""
    conn = get_conn()
    try:
        _ensure_tenants_tables(conn)
        conn.commit()
    finally:
        conn.close()


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


def consent_obtained_exists(client_id: int, call_id: str) -> bool:
    """True si consent_obtained déjà persisté pour ce call (idempotence retry)."""
    call_id_norm = (call_id or "").strip()
    if not call_id_norm:
        return False
    try:
        from backend import config
        if config.USE_PG_EVENTS:
            from backend.ivr_events_pg import consent_obtained_exists_pg
            if consent_obtained_exists_pg(client_id, call_id_norm):
                return True
    except Exception:
        pass
    conn = get_conn()
    try:
        _ensure_ivr_tables(conn)
        row = conn.execute(
            "SELECT 1 FROM ivr_events WHERE client_id = ? AND call_id = ? AND event = 'consent_obtained' LIMIT 1",
            (client_id, call_id_norm),
        ).fetchone()
        return row is not None
    except Exception:
        return False
    finally:
        conn.close()


def create_ivr_event(
    client_id: int,
    call_id: str,
    event: str,
    context: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    """
    Insertion dans ivr_events (rapport quotidien).
    Dual-write : SQLite + Postgres si USE_PG_EVENTS=true.
    created_at partagé pour idempotence PG (ON CONFLICT DO NOTHING sur retry).
    """
    created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:26]  # microsec
    call_id_norm = call_id or ""

    conn = get_conn()
    try:
        _ensure_ivr_tables(conn)
        conn.execute(
            """INSERT INTO ivr_events (client_id, call_id, event, context, reason, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (client_id, call_id_norm, event, context or None, reason or None, created_at),
        )
        conn.commit()
    finally:
        conn.close()

    # Dual-write Postgres (silencieux si échec)
    try:
        from backend import config
        if config.USE_PG_EVENTS:
            from backend.ivr_events_pg import create_ivr_event_pg
            create_ivr_event_pg(
                client_id, call_id_norm, event, context, reason, created_at=created_at
            )
    except Exception:
        pass


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
        _ensure_tenants_tables(conn)

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
    (lundi-vendredi uniquement). SQLite uniquement.
    """
    from backend import config
    config._sqlite_guard("db.cleanup_old_slots")
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


def count_free_slots(limit: int = 1000, tenant_id: int = 1) -> int:
    """PG-first puis SQLite. tenant_id pour isolation multi-tenant."""
    from backend import config
    if config.USE_PG_SLOTS:
        try:
            from backend.slots_pg import pg_cleanup_and_ensure_slots, pg_count_free_slots
            pg_cleanup_and_ensure_slots(tenant_id)
            n = pg_count_free_slots(tenant_id)
            if n is not None:
                return n
        except Exception:
            pass
    config._sqlite_guard("db.count_free_slots")
    cleanup_old_slots()
    conn = get_conn()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        cur = conn.execute("SELECT COUNT(*) AS c FROM slots WHERE is_booked=0 AND date >= ?", (today,))
        return int(cur.fetchone()["c"])
    finally:
        conn.close()


def list_free_slots(limit: int = 3, pref: Optional[str] = None, tenant_id: int = 1) -> List[Dict]:
    """
    Liste les créneaux libres. PG-first puis SQLite.
    pref: "matin" (avant 12h), "après-midi" (14h-18h), "soir" (>=18h).
    """
    from backend import config
    if config.USE_PG_SLOTS:
        try:
            from backend.slots_pg import pg_cleanup_and_ensure_slots, pg_list_free_slots
            pg_cleanup_and_ensure_slots(tenant_id)
            raw = pg_list_free_slots(tenant_id, limit=limit, pref=pref)
            if raw is not None:
                return [{"id": r["id"], "date": r["date"], "time": r["time"]} for r in raw]
        except Exception:
            pass
    config._sqlite_guard("db.list_free_slots")
    cleanup_old_slots()
    conn = get_conn()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        time_condition = ""
        if pref == "matin":
            time_condition = " AND time < '12:00'"
        elif pref == "après-midi":
            time_condition = " AND time >= '14:00' AND time < '18:00'"
        elif pref == "soir":
            time_condition = " AND time >= '18:00'"
        cur = conn.execute(
            f"""
            SELECT id, date, time 
            FROM slots 
            WHERE is_booked=0 AND date >= ?{time_condition}
            ORDER BY date ASC, time ASC 
            LIMIT ?
            """,
            (today, limit),
        )
        out = []
        for r in cur.fetchall():
            out.append({"id": int(r["id"]), "date": r["date"], "time": r["time"]})
        return out
    finally:
        conn.close()


def find_slot_id_by_datetime(date_str: str, time_str: str) -> Optional[int]:
    """
    Trouve l'id d'un slot libre par date et heure (ex: "2026-02-16", "09:00").
    Retourne None si non trouvé ou déjà réservé. SQLite uniquement (pas de branche PG).
    """
    from backend import config
    config._sqlite_guard("db.find_slot_id_by_datetime")
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT id FROM slots WHERE date=? AND time=? AND is_booked=0 LIMIT 1",
            (date_str[:10], time_str[:5] if time_str else "09:00"),
        )
        row = cur.fetchone()
        return int(row["id"]) if row else None
    finally:
        conn.close()


def book_slot_atomic(
    slot_id: int,
    name: str,
    contact: str,
    contact_type: str,
    motif: str,
    tenant_id: int = 1,
) -> bool:
    """
    Book atomique. PG-first puis SQLite.
    Returns False if slot already booked.
    """
    from backend import config
    if config.USE_PG_SLOTS:
        try:
            from backend.slots_pg import pg_book_slot_atomic
            result = pg_book_slot_atomic(tenant_id, slot_id, name, contact, contact_type, motif)
            if result is not None:
                return result
        except Exception:
            pass
    config._sqlite_guard("db.book_slot_atomic")
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


def find_booking_by_name(name: str, tenant_id: int = 1) -> Optional[Dict]:
    """
    Recherche un RDV par nom. PG-first puis SQLite.
    """
    if not name or not name.strip():
        return None
    from backend import config
    if config.USE_PG_SLOTS:
        try:
            from backend.slots_pg import pg_find_booking_by_name
            r = pg_find_booking_by_name(tenant_id, name.strip())
            if r is not None:
                return r
        except Exception:
            pass
    config._sqlite_guard("db.find_booking_by_name")
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


def cancel_booking_sqlite(booking: Dict, tenant_id: int = 1) -> bool:
    """
    Annule un RDV local : supprime l'appointment et libère le slot. PG-first puis SQLite.
    """
    slot_id = booking.get("slot_id")
    appt_id = booking.get("id")
    from backend import config
    if config.USE_PG_SLOTS:
        try:
            from backend.slots_pg import pg_cancel_booking
            result = pg_cancel_booking(tenant_id, booking)
            if result is not None:
                return result
        except Exception:
            pass
    config._sqlite_guard("db.cancel_booking_sqlite")
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
    Source: ivr_events uniquement (table calls dépréciée: calls_total = COUNT DISTINCT call_id).
    Booked = event 'booking_confirmed' dans ivr_events.

    date_str: "YYYY-MM-DD"
    Fenêtre: [day 00:00:00, day+1 00:00:00) pour éviter les soucis de format ISO.

    Events attendus (à persister depuis l'engine): booking_confirmed, recovery_step,
    intent_router_trigger, anti_loop_trigger, empty_message, transferred_human,
    user_abandon, repeat_used, yes_ambiguous_router.
    """
    conn = get_conn()
    try:
        _ensure_ivr_tables(conn)
        day = date_str[:10]
        start_ts = day + " 00:00:00"

        # 1) Calls total = COUNT(DISTINCT call_id) dans ivr_events (dépréciation table calls)
        cur = conn.execute(
            """SELECT COUNT(DISTINCT COALESCE(NULLIF(TRIM(call_id), ''), 'UNKNOWN')) AS calls_total
               FROM ivr_events
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
               WHERE client_id = ? AND event IN ('transfer', 'transferred', 'transfer_human', 'transferred_human')
                 AND created_at >= ? AND created_at < datetime(? || ' 00:00:00', '+1 day')""",
            (client_id, start_ts, day),
        )
        transfers = cur.fetchone()["transfers"] or 0

        cur = conn.execute(
            """SELECT COUNT(*) AS abandons
               FROM ivr_events
               WHERE client_id = ? AND event IN ('abandon', 'hangup', 'user_hangup', 'user_abandon')
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
