#!/usr/bin/env python3
"""
Affiche stripe_usage_push_log pour diagnostic.
Usage: railway run python scripts/query_stripe_usage_push_log.py
       DATABASE_URL=... python scripts/query_stripe_usage_push_log.py
"""
from __future__ import annotations

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
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL")
    if not url:
        print("❌ DATABASE_URL requis. railway run python scripts/query_stripe_usage_push_log.py")
        return 1
    tenant_id = int(os.environ.get("TENANT_ID", "1"))
    try:
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tenant_id, date_utc, status, quantity_minutes, error_short, stripe_usage_record_id, pushed_at
                    FROM stripe_usage_push_log
                    WHERE tenant_id = %s
                    ORDER BY date_utc DESC
                    LIMIT 10
                    """,
                    (tenant_id,),
                )
                rows = cur.fetchall()
        if not rows:
            print(f"Aucune ligne pour tenant_id={tenant_id}")
            return 0
        for r in rows:
            print(r)
        return 0
    except Exception as e:
        print(f"❌ {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
