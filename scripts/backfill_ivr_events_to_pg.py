#!/usr/bin/env python3
# scripts/backfill_ivr_events_to_pg.py
"""
Backfill ivr_events SQLite → Postgres (one-shot).
Usage: python scripts/backfill_ivr_events_to_pg.py [--db-sqlite agent.db] [--pg-url $DATABASE_URL]
"""
from __future__ import annotations

import argparse
import os
import sys


def main() -> int:
    p = argparse.ArgumentParser(description="Backfill ivr_events SQLite → Postgres")
    p.add_argument(
        "--db-sqlite",
        default=os.environ.get("UWI_DB_PATH", "agent.db"),
        help="SQLite DB path",
    )
    p.add_argument(
        "--pg-url",
        default=os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL"),
        help="Postgres URL (or DATABASE_URL / PG_EVENTS_URL env)",
    )
    p.add_argument("--dry-run", action="store_true", help="Count only, no insert")
    args = p.parse_args()

    if not args.pg_url:
        print("Error: --pg-url or DATABASE_URL or PG_EVENTS_URL required")
        return 1

    import sqlite3
    conn_sqlite = sqlite3.connect(args.db_sqlite)
    conn_sqlite.row_factory = sqlite3.Row

    try:
        import psycopg
    except ImportError:
        print("Error: psycopg required. pip install psycopg[binary]")
        return 1

    rows = conn_sqlite.execute(
        "SELECT client_id, call_id, event, context, reason, created_at FROM ivr_events"
    ).fetchall()

    n = len(rows)
    print(f"Found {n} rows in SQLite ivr_events")

    if n == 0:
        return 0

    if args.dry_run:
        print("Dry-run: skipping insert")
        return 0

    # ON CONFLICT DO NOTHING : idempotent (rejouable sans doublons)
    inserted = 0
    with psycopg.connect(args.pg_url) as pg:
        with pg.cursor() as cur:
            for r in rows:
                try:
                    cur.execute(
                        """
                        INSERT INTO ivr_events (client_id, call_id, event, context, reason, created_at)
                        VALUES (%s, %s, %s, %s, %s, COALESCE(%s::timestamptz, now()))
                        ON CONFLICT (client_id, call_id, event, created_at) DO NOTHING
                        """,
                        (
                            r["client_id"],
                            r["call_id"] or "",
                            r["event"],
                            r["context"],
                            r["reason"],
                            r["created_at"],
                        ),
                    )
                    inserted += cur.rowcount
                except Exception as e:
                    print(f"Error row client_id={r['client_id']} event={r['event']}: {e}")
                    raise
        pg.commit()

    print(f"Inserted: {inserted} (skipped duplicates: {n - inserted})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
