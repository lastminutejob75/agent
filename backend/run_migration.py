#!/usr/bin/env python3
"""
Exécute une migration SQL sur Postgres.
Usage: python -m backend.run_migration 007
       python backend/run_migration.py 007
       DATABASE_URL=postgres://... make migrate
Charge .env si présent.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Charger .env à la racine (parent de backend/)
_root = Path(__file__).resolve().parent.parent
_env = _root / ".env"
if _env.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env)
    except ImportError:
        pass


def main() -> int:
    p = argparse.ArgumentParser(description="Run Postgres migration")
    p.add_argument("migration", help="Migration number (ex: 007) or filename")
    p.add_argument(
        "--pg-url",
        default=os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL"),
        help="Postgres URL (default: DATABASE_URL or PG_TENANTS_URL)",
    )
    p.add_argument("--dry-run", action="store_true", help="Print SQL only, do not run")
    args = p.parse_args()

    if not args.pg_url and not args.dry_run:
        print("Error: --pg-url or DATABASE_URL or PG_TENANTS_URL required")
        return 1

    root = Path(__file__).resolve().parent.parent
    migrations_dir = root / "migrations"

    # Find migration file
    mig = args.migration.strip()
    if not mig.endswith(".sql"):
        # 007 -> 007_*.sql or 007*.sql
        prefix = mig if mig.startswith("0") else f"0{mig}" if len(mig) <= 2 else mig
        candidates = sorted(migrations_dir.glob(f"{prefix}*.sql"))
        if not candidates:
            candidates = sorted(migrations_dir.glob(f"*{mig}*.sql"))
        if not candidates:
            print(f"Error: no migration file matching '{args.migration}' in migrations/")
            return 1
        if len(candidates) > 1:
            # Prefer exact prefix match
            exact = [c for c in candidates if c.name.startswith(prefix)]
            path = exact[0] if exact else candidates[0]
        else:
            path = candidates[0]
    else:
        path = migrations_dir / mig
        if not path.exists():
            path = Path(mig)
        if not path.exists():
            print(f"Error: file not found: {path}")
            return 1

    sql = path.read_text(encoding="utf-8")
    print(f"Migration: {path.name}")
    if args.dry_run:
        print("-- DRY RUN --")
        print(sql[:500] + "..." if len(sql) > 500 else sql)
        return 0

    try:
        import psycopg
    except ImportError:
        print("Error: psycopg required. pip install psycopg[binary]")
        return 1

    try:
        with psycopg.connect(args.pg_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
        print("OK")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
