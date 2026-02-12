#!/usr/bin/env python3
"""
Backfill tenant_users depuis tenant_config.params_json->contact_email.
Pour les tenants existants créés avant la migration 007.
Usage: python scripts/backfill_tenant_users.py
       railway run python scripts/backfill_tenant_users.py
       python scripts/backfill_tenant_users.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
_env = _root / ".env"
if _env.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env)
    except ImportError:
        pass


def main() -> int:
    p = argparse.ArgumentParser(description="Backfill tenant_users from tenant_config.contact_email")
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

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        print("Error: psycopg required. pip install psycopg[binary]")
        return 1

    try:
        with psycopg.connect(args.pg_url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                # tenant_config.params_json->>'contact_email'
                cur.execute(
                    """
                    SELECT t.tenant_id, t.name,
                           tc.params_json->>'contact_email' as contact_email
                    FROM tenants t
                    JOIN tenant_config tc ON tc.tenant_id = t.tenant_id
                    WHERE tc.params_json->>'contact_email' IS NOT NULL
                      AND TRIM(tc.params_json->>'contact_email') != ''
                    """
                )
                rows = cur.fetchall()

                print(f"Found {len(rows)} tenants with contact_email")
                if not rows:
                    return 0

                for r in rows:
                    email = (r["contact_email"] or "").strip().lower()
                    if not email:
                        continue
                    tid = r["tenant_id"]
                    name = r["name"] or "?"
                    print(f"  tenant_id={tid} ({name}) -> {email}")

                if args.dry_run:
                    print("Dry-run: skipping insert")
                    return 0

                inserted = 0
                for r in rows:
                    email = (r["contact_email"] or "").strip().lower()
                    if not email:
                        continue
                    tid = r["tenant_id"]
                    cur.execute(
                        """
                        INSERT INTO tenant_users (tenant_id, email, role)
                        VALUES (%s, %s, 'owner')
                        ON CONFLICT (email) DO NOTHING
                        """,
                        (tid, email),
                    )
                    if cur.rowcount > 0:
                        inserted += 1

                conn.commit()
                print(f"Inserted {inserted} tenant_users")

        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
