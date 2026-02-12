#!/usr/bin/env python3
# scripts/verify_backfill_ivr_events.py
"""
Vérification post-backfill : comparaison SQLite vs Postgres.
- Comptage global sur la période
- Distribution par event (7 derniers jours)

Usage:
  python scripts/verify_backfill_ivr_events.py [--db-sqlite agent.db] [--pg-url $DATABASE_URL]
  python scripts/verify_backfill_ivr_events.py --days 7
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta


def main() -> int:
    p = argparse.ArgumentParser(description="Verify ivr_events backfill SQLite vs Postgres")
    p.add_argument(
        "--db-sqlite",
        default=os.environ.get("UWI_DB_PATH", "agent.db"),
        help="SQLite DB path",
    )
    p.add_argument(
        "--pg-url",
        default=os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL"),
        help="Postgres URL",
    )
    p.add_argument("--days", type=int, default=7, help="Période en jours (default: 7)")
    args = p.parse_args()

    if not args.pg_url:
        print("Error: --pg-url or DATABASE_URL or PG_EVENTS_URL required")
        return 1

    end = datetime.utcnow()
    start = end - timedelta(days=args.days)
    start_str = start.strftime("%Y-%m-%d %H:%M:%S")
    end_str = end.strftime("%Y-%m-%d %H:%M:%S")

    import sqlite3
    conn_sqlite = sqlite3.connect(args.db_sqlite)
    conn_sqlite.row_factory = sqlite3.Row  # accès row["c"], row["event"]

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        print("Error: psycopg required. pip install psycopg[binary]")
        return 1

    # 1) Comptage global
    q_count = """
        SELECT COUNT(*) AS c FROM ivr_events
        WHERE created_at >= ? AND created_at < ?
    """
    r_sqlite = conn_sqlite.execute(q_count, (start_str, end_str)).fetchone()
    count_sqlite = int(r_sqlite["c"])

    with psycopg.connect(args.pg_url, row_factory=dict_row) as pg:
        with pg.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS c FROM ivr_events WHERE created_at >= %s AND created_at < %s",
                (start_str, end_str),
            )
            r_pg = cur.fetchone()
    count_pg = int(r_pg["c"])

    print(f"=== Comptage global ({start_str} → {end_str}) ===")
    print(f"  SQLite:  {count_sqlite}")
    print(f"  Postgres: {count_pg}")
    diff = abs(count_sqlite - count_pg)
    if diff == 0:
        print("  OK: identique")
    else:
        print(f"  Delta: {diff} (vérifier si acceptable)")

    # 2) Distribution par event
    q_dist = """
        SELECT event, COUNT(*) AS n FROM ivr_events
        WHERE created_at >= ? AND created_at < ?
        GROUP BY event ORDER BY n DESC
    """
    rows_sqlite = conn_sqlite.execute(q_dist, (start_str, end_str)).fetchall()
    dist_sqlite = {r["event"]: r["n"] for r in rows_sqlite}

    with psycopg.connect(args.pg_url, row_factory=dict_row) as pg:
        with pg.cursor() as cur:
            cur.execute(
                "SELECT event, COUNT(*) AS n FROM ivr_events WHERE created_at >= %s AND created_at < %s GROUP BY event ORDER BY n DESC",
                (start_str, end_str),
            )
            rows_pg = cur.fetchall()
    dist_pg = {r["event"]: r["n"] for r in rows_pg}

    all_events = sorted(set(dist_sqlite.keys()) | set(dist_pg.keys()))
    print(f"\n=== Distribution par event (7 jours) ===")
    print(f"  {'event':<30} {'SQLite':>10} {'PG':>10} {'diff':>8}")
    print("  " + "-" * 60)
    for ev in all_events:
        s, p = dist_sqlite.get(ev, 0), dist_pg.get(ev, 0)
        d = s - p
        ok = "OK" if d == 0 else "!"
        print(f"  {ev:<30} {s:>10} {p:>10} {d:>+8} {ok}")

    conn_sqlite.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
