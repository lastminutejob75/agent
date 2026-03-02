#!/usr/bin/env python3
"""
Insère des données de test dans vapi_call_usage pour tenant 1 (hier UTC).
Usage: DATABASE_URL=... python scripts/run_insert_test_usage.py
       railway run python scripts/run_insert_test_usage.py
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
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
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    if not url:
        print("❌ DATABASE_URL ou PG_EVENTS_URL requis")
        return 1

    now = datetime.now(timezone.utc)
    yesterday_start = (now.date() - timedelta(days=1))
    start_ts = datetime(yesterday_start.year, yesterday_start.month, yesterday_start.day, 10, 0, 0, tzinfo=timezone.utc)
    end_ts_1 = start_ts + timedelta(minutes=15)
    start_ts_2 = start_ts + timedelta(hours=4)
    end_ts_2 = start_ts_2 + timedelta(minutes=20)
    start_ts_3 = start_ts + timedelta(hours=6)
    end_ts_3 = start_ts_3 + timedelta(minutes=20)

    rows = [
        (1, f"test-usage-{uuid.uuid4()}", start_ts, end_ts_1, 900, 0.05),
        (1, f"test-usage-{uuid.uuid4()}", start_ts_2, end_ts_2, 1200, 0.07),
        (1, f"test-usage-{uuid.uuid4()}", start_ts_3, end_ts_3, 1200, 0.07),
    ]

    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                for tenant_id, vapi_call_id, s, e, dur, cost in rows:
                    cur.execute(
                        """
                        INSERT INTO vapi_call_usage (tenant_id, vapi_call_id, started_at, ended_at, duration_sec, cost_usd, cost_currency)
                        VALUES (%s, %s, %s, %s, %s, %s, 'USD')
                        ON CONFLICT (tenant_id, vapi_call_id) DO NOTHING
                        """,
                        (tenant_id, vapi_call_id, s, e, dur, cost),
                    )
                conn.commit()
        print(f"✅ Inséré {len(rows)} lignes (55 min total) pour tenant 1, hier UTC")
        return 0
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
