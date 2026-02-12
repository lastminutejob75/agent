#!/usr/bin/env python3
"""
Ajoute un utilisateur (email) à un tenant pour tester le dashboard.
Usage: python scripts/add_tenant_user.py ton-email@exemple.com
       python scripts/add_tenant_user.py ton-email@exemple.com --tenant-id 2
"""
from __future__ import annotations

import argparse
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
    p = argparse.ArgumentParser(description="Add tenant user for testing")
    p.add_argument("email", help="Email to add")
    p.add_argument("--tenant-id", type=int, default=1, help="Tenant ID (default: 1)")
    p.add_argument(
        "--pg-url",
        default=os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL"),
        help="Postgres URL",
    )
    args = p.parse_args()

    if not args.pg_url:
        print("Error: --pg-url or DATABASE_URL required")
        return 1

    email = (args.email or "").strip().lower()
    if not email:
        print("Error: email required")
        return 1

    try:
        import psycopg
    except ImportError:
        print("Error: psycopg required. pip install psycopg[binary]")
        return 1

    try:
        with psycopg.connect(args.pg_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tenant_users (tenant_id, email, role)
                    VALUES (%s, %s, 'owner')
                    ON CONFLICT (email) DO UPDATE SET tenant_id = EXCLUDED.tenant_id
                    """,
                    (args.tenant_id, email),
                )
            conn.commit()
        print(f"OK: {email} ajouté au tenant {args.tenant_id}")
        print("  → Va sur /login, entre ton email, clique sur le lien Magic Link")
        print("  → Ou active ENABLE_MAGICLINK_DEBUG=true pour voir le lien direct")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
