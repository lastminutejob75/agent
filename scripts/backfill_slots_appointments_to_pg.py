#!/usr/bin/env python3
# scripts/backfill_slots_appointments_to_pg.py
"""
Backfill slots + appointments SQLite → Postgres (tenant_id=1).
Usage: python scripts/backfill_slots_appointments_to_pg.py [--db-sqlite agent.db] [--pg-url $DATABASE_URL]
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime


def main() -> int:
    p = argparse.ArgumentParser(description="Backfill slots/appointments SQLite → Postgres (tenant 1)")
    p.add_argument(
        "--db-sqlite",
        default=os.environ.get("UWI_DB_PATH", "agent.db"),
        help="SQLite DB path",
    )
    p.add_argument(
        "--pg-url",
        default=os.environ.get("DATABASE_URL") or os.environ.get("PG_SLOTS_URL"),
        help="Postgres URL",
    )
    p.add_argument("--dry-run", action="store_true", help="Count only, no insert")
    args = p.parse_args()

    if not args.pg_url:
        print("Error: --pg-url or DATABASE_URL or PG_SLOTS_URL required")
        return 1

    TENANT_ID = 1

    import sqlite3
    conn = sqlite3.connect(args.db_sqlite)
    conn.row_factory = sqlite3.Row

    try:
        import psycopg
    except ImportError:
        print("Error: psycopg required. pip install psycopg[binary]")
        return 1

    slots = conn.execute("SELECT id, date, time, is_booked FROM slots").fetchall()
    today = datetime.now().strftime("%Y-%m-%d")
    slots_future = [s for s in slots if (s["date"] or "") >= today]
    print(f"SQLite: {len(slots)} slots total, {len(slots_future)} futurs")

    appointments = conn.execute(
        "SELECT a.id, a.slot_id, a.name, a.contact, a.contact_type, a.motif, a.created_at "
        "FROM appointments a JOIN slots s ON s.id = a.slot_id WHERE s.date >= ?",
        (today,),
    ).fetchall()
    print(f"SQLite: {len(appointments)} appointments (slots futurs)")

    if args.dry_run:
        print("Dry-run: skipping insert")
        return 0

    with psycopg.connect(args.pg_url) as pg:
        with pg.cursor() as cur:
            # Map SQLite slot (date, time) -> PG slot id
            sqlite_to_pg_slot: dict[tuple[str, str], int] = {}
            for s in slots_future:
                date_s = s["date"] or ""
                time_s = s["time"] or "09:00"
                start_ts = f"{date_s} {time_s}:00"
                try:
                    cur.execute(
                        """
                        INSERT INTO slots (tenant_id, start_ts, is_booked, created_at)
                        VALUES (%s, %s::timestamptz, %s, now())
                        ON CONFLICT (tenant_id, start_ts) DO UPDATE SET is_booked = slots.is_booked
                        RETURNING id
                        """,
                        (TENANT_ID, start_ts, bool(s["is_booked"])),
                    )
                    row = cur.fetchone()
                    if row:
                        sqlite_to_pg_slot[(date_s, time_s)] = row[0]
                except Exception as e:
                    print(f"Error slot {date_s} {time_s}: {e}")
                    raise

            # Appointments : besoin du mapping slot_id SQLite -> PG
            sqlite_slots = conn.execute(
                "SELECT id, date, time FROM slots WHERE date >= ?", (today,)
            ).fetchall()
            sqlite_slot_id_to_pg = {}
            for s in sqlite_slots:
                key = (s["date"], s["time"])
                if key in sqlite_to_pg_slot:
                    sqlite_slot_id_to_pg[s["id"]] = sqlite_to_pg_slot[key]

            for a in appointments:
                pg_slot_id = sqlite_slot_id_to_pg.get(a["slot_id"])
                if pg_slot_id is None:
                    continue
                try:
                    cur.execute(
                        """
                        INSERT INTO appointments (tenant_id, slot_id, name, contact, contact_type, motif)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (tenant_id, slot_id) DO NOTHING
                        """,
                        (
                            TENANT_ID,
                            pg_slot_id,
                            a["name"] or "",
                            a["contact"] or "",
                            a["contact_type"] or "",
                            a["motif"] or "",
                        ),
                    )
                except Exception as e:
                    print(f"Error appointment {a['id']}: {e}")
                    # Pas de ON CONFLICT sur appointments - on skip les doublons
            pg.commit()

    print("Backfill done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
