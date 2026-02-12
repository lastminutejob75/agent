#!/usr/bin/env python3
# scripts/verify_backfill_tenants.py
"""
Vérification post-backfill tenants : comparaison SQLite vs Postgres.
- Comptage tenants, configs, routes
- Diff flags/params pour tenant_id=1
- Diff routing (channel, key)
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def main() -> int:
    p = argparse.ArgumentParser(description="Verify tenants backfill SQLite vs Postgres")
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
    args = p.parse_args()

    if not args.pg_url:
        print("Error: --pg-url or DATABASE_URL or PG_TENANTS_URL required")
        return 1

    import sqlite3
    conn = sqlite3.connect(args.db_sqlite)
    conn.row_factory = sqlite3.Row

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        print("Error: psycopg required. pip install psycopg[binary]")
        return 1

    # Comptage
    n_tenants_s = conn.execute("SELECT COUNT(*) AS c FROM tenants").fetchone()["c"]
    n_configs_s = conn.execute("SELECT COUNT(*) AS c FROM tenant_config").fetchone()["c"]
    n_routes_s = conn.execute("SELECT COUNT(*) AS c FROM tenant_routing").fetchone()["c"]

    with psycopg.connect(args.pg_url, row_factory=dict_row) as pg:
        with pg.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM tenants")
            n_tenants_p = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM tenant_config")
            n_configs_p = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM tenant_routing")
            n_routes_p = cur.fetchone()["c"]

    print("=== Comptage ===")
    print(f"  {'':20} {'SQLite':>10} {'PG':>10} {'diff':>8}")
    print(f"  {'tenants':20} {n_tenants_s:>10} {n_tenants_p:>10} {n_tenants_p - n_tenants_s:>+8}")
    print(f"  {'tenant_config':20} {n_configs_s:>10} {n_configs_p:>10} {n_configs_p - n_configs_s:>+8}")
    print(f"  {'tenant_routing':20} {n_routes_s:>10} {n_routes_p:>10} {n_routes_p - n_routes_s:>+8}")

    # Diff flags/params tenant_id=1
    print("\n=== tenant_config (tenant_id=1) ===")
    row_s = conn.execute(
        "SELECT flags_json, params_json FROM tenant_config WHERE tenant_id = 1"
    ).fetchone()
    with psycopg.connect(args.pg_url, row_factory=dict_row) as pg:
        with pg.cursor() as cur:
            cur.execute("SELECT flags_json, params_json FROM tenant_config WHERE tenant_id = 1")
            row_p = cur.fetchone()

    if row_s and row_p:
        flags_s = json.loads(row_s["flags_json"]) if row_s["flags_json"] else {}
        params_s = json.loads(row_s["params_json"]) if row_s["params_json"] else {}
        flags_p = dict(row_p["flags_json"]) if row_p["flags_json"] else {}
        params_p = dict(row_p["params_json"]) if row_p["params_json"] else {}
        flags_ok = flags_s == flags_p
        params_ok = params_s == params_p
        print(f"  flags match: {flags_ok}")
        print(f"  params match: {params_ok}")

    # Diff routing
    print("\n=== tenant_routing (sample) ===")
    routes_s = conn.execute(
        "SELECT channel, did_key, tenant_id FROM tenant_routing"
    ).fetchall()
    with psycopg.connect(args.pg_url, row_factory=dict_row) as pg:
        with pg.cursor() as cur:
            cur.execute("SELECT channel, key, tenant_id FROM tenant_routing")
            routes_p = cur.fetchall()

    set_s = {(r["channel"], r["did_key"], r["tenant_id"]) for r in routes_s}
    set_p = {(r["channel"], r["key"], r["tenant_id"]) for r in routes_p}
    only_s = set_s - set_p
    only_p = set_p - set_s
    print(f"  SQLite routes: {len(set_s)}")
    print(f"  PG routes: {len(set_p)}")
    if only_s:
        print(f"  Only in SQLite: {len(only_s)} {list(only_s)[:3]}...")
    if only_p:
        print(f"  Only in PG: {len(only_p)} {list(only_p)[:3]}...")
    if not only_s and not only_p:
        print("  OK: routing identical")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
