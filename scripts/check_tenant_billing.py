#!/usr/bin/env python3
"""
Vérifie tenant_billing après paiement Stripe (TEST 2).
Usage: python scripts/check_tenant_billing.py [tenant_id]
       DATABASE_URL=... python scripts/check_tenant_billing.py
       railway run python scripts/check_tenant_billing.py
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
    tenant_id = sys.argv[1] if len(sys.argv) > 1 else "1"
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL")
    if not url:
        print("❌ DATABASE_URL ou PG_TENANTS_URL requis")
        print("   railway run python scripts/check_tenant_billing.py 1")
        return 1

    try:
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT tenant_id, plan_key, stripe_customer_id, stripe_subscription_id, stripe_metered_item_id, updated_at
                    FROM tenant_billing
                    WHERE tenant_id = %s
                """, (tenant_id,))
                row = cur.fetchone()
        if not row:
            print(f"❌ Aucune ligne tenant_billing pour tenant_id={tenant_id}")
            return 1
        print("tenant_id              :", row["tenant_id"])
        print("plan_key               :", row["plan_key"])
        print("stripe_customer_id     :", row["stripe_customer_id"] or "(vide)")
        print("stripe_subscription_id :", row["stripe_subscription_id"] or "(vide)")
        print("stripe_metered_item_id :", row["stripe_metered_item_id"] or "(vide)")
        print("updated_at            :", row["updated_at"])
        print()
        ok = (
            row["plan_key"] == "growth"
            and (row["stripe_subscription_id"] or "").startswith("sub_")
            and bool(row["stripe_metered_item_id"] or "").strip()
        )
        if ok:
            print("✅ TEST 2 OK — webhook a bien rempli tenant_billing")
        else:
            print("❌ TEST 2 — vérifier plan_key, stripe_subscription_id, stripe_metered_item_id")
        return 0 if ok else 1
    except ImportError:
        print("❌ psycopg requis: pip install psycopg[binary]")
        return 1
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
