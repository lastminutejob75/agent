#!/usr/bin/env python3
# scripts/backfill_tenants_to_pg.py
"""
Backfill tenants, tenant_config, tenant_routing SQLite → Postgres.
Rejouable : ON CONFLICT DO UPDATE pour tenant_config et tenant_routing.
Usage: python scripts/backfill_tenants_to_pg.py [--db-sqlite agent.db] [--pg-url $DATABASE_URL]
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def main() -> int:
    p = argparse.ArgumentParser(description="Backfill tenants/config/routing SQLite → Postgres")
    p.add_argument(
        "--db-sqlite",
        default=os.environ.get("UWI_DB_PATH", "agent.db"),
        help="SQLite DB path",
    )
    p.add_argument(
        "--pg-url",
        default=os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL"),
        help="Postgres URL",
    )
    p.add_argument("--dry-run", action="store_true", help="Count only, no insert")
    args = p.parse_args()

    if not args.pg_url:
        print("Error: --pg-url or DATABASE_URL or PG_TENANTS_URL required")
        return 1

    import sqlite3
    conn = sqlite3.connect(args.db_sqlite)
    conn.row_factory = sqlite3.Row

    try:
        import psycopg
    except ImportError:
        print("Error: psycopg required. pip install psycopg[binary]")
        return 1

    tenants = conn.execute("SELECT tenant_id, name, timezone, status, created_at FROM tenants").fetchall()
    configs = conn.execute("SELECT tenant_id, flags_json, params_json, updated_at FROM tenant_config").fetchall()
    routing = conn.execute("SELECT channel, did_key, tenant_id, created_at FROM tenant_routing").fetchall()

    print(f"SQLite: {len(tenants)} tenants, {len(configs)} configs, {len(routing)} routes")

    if args.dry_run:
        print("Dry-run: skipping insert")
        return 0

    with psycopg.connect(args.pg_url) as pg:
        with pg.cursor() as cur:
            # tenants
            for r in tenants:
                cur.execute(
                    """
                    INSERT INTO tenants (tenant_id, name, timezone, status, created_at)
                    VALUES (%s, %s, %s, %s, COALESCE(%s::timestamptz, now()))
                    ON CONFLICT (tenant_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        timezone = COALESCE(EXCLUDED.timezone, tenants.timezone),
                        status = COALESCE(EXCLUDED.status, tenants.status)
                    """,
                    (
                        r["tenant_id"],
                        r["name"] or "DEFAULT",
                        r["timezone"] or "Europe/Paris",
                        r["status"] or "active",
                        r["created_at"],
                    ),
                )
            # tenant_config
            for r in configs:
                flags = r["flags_json"]
                params = r["params_json"]
                if isinstance(flags, str):
                    flags = json.loads(flags) if flags else {}
                if isinstance(params, str):
                    params = json.loads(params) if params else {}
                cur.execute(
                    """
                    INSERT INTO tenant_config (tenant_id, flags_json, params_json, updated_at)
                    VALUES (%s, %s::jsonb, %s::jsonb, COALESCE(%s::timestamptz, now()))
                    ON CONFLICT (tenant_id) DO UPDATE SET
                        flags_json = EXCLUDED.flags_json,
                        params_json = EXCLUDED.params_json,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (r["tenant_id"], json.dumps(flags), json.dumps(params), r["updated_at"]),
                )
            # tenant_routing (did_key → key en PG)
            for r in routing:
                cur.execute(
                    """
                    INSERT INTO tenant_routing (channel, key, tenant_id, is_active, created_at, updated_at)
                    VALUES (%s, %s, %s, TRUE, COALESCE(%s::timestamptz, now()), now())
                    ON CONFLICT (channel, key) DO UPDATE SET
                        tenant_id = EXCLUDED.tenant_id,
                        is_active = TRUE,
                        updated_at = now()
                    """,
                    (r["channel"], r["did_key"] or "", r["tenant_id"], r["created_at"]),
                )
        pg.commit()

    print("Backfill done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
