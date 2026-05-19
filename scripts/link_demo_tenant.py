#!/usr/bin/env python3
"""
Lie le compte démo (demo@uwi.app) au numéro 09 39 24 05 75 (+33939240575)
et à l'assistant Vapi correspondant.

Usage (racine du projet) :
  python3 scripts/link_demo_tenant.py
  python3 scripts/link_demo_tenant.py --prod   # nécessite DATABASE_PUBLIC_URL ou DATABASE_URL

Variables utiles :
  DEMO_TENANT_ID (défaut 1 en local, 2 en prod si TEST_TENANT_ID=2)
  DEMO_EMAIL (défaut demo@uwi.app)
  VAPI_ASSISTANT_ID (défaut assistant lié au +33939240575 sur Vapi)
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEMO_DID = "+33939240575"
DEFAULT_VAPI_ASSISTANT_ID = "78dd0e14-337e-40ab-96d9-7dbbe92cdf95"
DEFAULT_EMAIL = "demo@uwi.app"


def _merge_params(existing: dict) -> dict:
    params = dict(existing or {})
    params.update(
        {
            "vapi_assistant_id": os.getenv("VAPI_ASSISTANT_ID", DEFAULT_VAPI_ASSISTANT_ID).strip(),
            "assistant_name": params.get("assistant_name") or "Clara",
            "phone_number": DEMO_DID,
            "contact_email": params.get("contact_email") or DEFAULT_EMAIL,
            "business_name": params.get("business_name") or "Cabinet Démo UWi",
            "client_onboarding_completed": "true",
        }
    )
    return params


def link_sqlite(tenant_id: int) -> None:
    db_path = ROOT / "agent.db"
    if not db_path.exists():
        raise SystemExit(f"Base SQLite introuvable : {db_path}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO tenants (tenant_id, name) VALUES (?, ?)", (tenant_id, "Cabinet Démo UWi"))

    row = cur.execute("SELECT params_json FROM tenant_config WHERE tenant_id = ?", (tenant_id,)).fetchone()
    existing = {}
    if row and row[0]:
        try:
            existing = json.loads(row[0])
        except Exception:
            existing = {}
    params_json = json.dumps(_merge_params(existing), ensure_ascii=False)

    if cur.execute("SELECT 1 FROM tenant_config WHERE tenant_id = ?", (tenant_id,)).fetchone():
        cur.execute("UPDATE tenant_config SET params_json = ? WHERE tenant_id = ?", (params_json, tenant_id))
    else:
        cur.execute(
            "INSERT INTO tenant_config (tenant_id, flags_json, params_json) VALUES (?, '{}', ?)",
            (tenant_id, params_json),
        )

    cur.execute(
        """
        INSERT INTO tenant_routing (channel, did_key, tenant_id, created_at)
        VALUES ('vocal', ?, ?, datetime('now'))
        ON CONFLICT(channel, did_key) DO UPDATE SET tenant_id = excluded.tenant_id
        """,
        (DEMO_DID, tenant_id),
    )
    # Évite qu'un ancien numéro de test (ex. +33123456789) s'affiche en premier (ORDER BY did_key).
    cur.execute(
        "DELETE FROM tenant_routing WHERE tenant_id = ? AND did_key != ?",
        (tenant_id, DEMO_DID),
    )
    conn.commit()
    conn.close()
    print(f"[sqlite] tenant_id={tenant_id} params + route {DEMO_DID} OK ({db_path})")


def link_postgres(tenant_id: int, create_demo_user: bool) -> None:
    url = (os.getenv("DATABASE_PUBLIC_URL") or os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise SystemExit("DATABASE_URL ou DATABASE_PUBLIC_URL requis pour --prod")

    import psycopg2

    conn = psycopg2.connect(url)
    cur = conn.cursor()

    cur.execute("SELECT params_json FROM tenant_config WHERE tenant_id = %s", (tenant_id,))
    row = cur.fetchone()
    existing = row[0] if row and row[0] else {}
    if isinstance(existing, str):
        existing = json.loads(existing)
    params = _merge_params(existing if isinstance(existing, dict) else {})

    cur.execute(
        "UPDATE tenant_config SET params_json = %s::jsonb, updated_at = now() WHERE tenant_id = %s",
        (json.dumps(params), tenant_id),
    )
    if cur.rowcount == 0:
        cur.execute(
            "INSERT INTO tenant_config (tenant_id, flags_json, params_json) VALUES (%s, '{}'::jsonb, %s::jsonb)",
            (tenant_id, json.dumps(params)),
        )

    cur.execute(
        """
        INSERT INTO tenant_routing (channel, key, tenant_id, is_active, updated_at)
        VALUES ('vocal', %s, %s, TRUE, now())
        ON CONFLICT (channel, key) DO UPDATE
        SET tenant_id = EXCLUDED.tenant_id, is_active = TRUE, updated_at = now()
        """,
        (DEMO_DID, tenant_id),
    )

    if create_demo_user:
        import bcrypt

        email = os.getenv("DEMO_EMAIL", DEFAULT_EMAIL).strip().lower()
        password = os.getenv("DEMO_PASSWORD", "demo1234")
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        cur.execute(
            """
            INSERT INTO tenant_users (tenant_id, email, role, password_hash, email_verified)
            VALUES (%s, %s, 'owner', %s, TRUE)
            ON CONFLICT (email) DO UPDATE SET
                tenant_id = EXCLUDED.tenant_id,
                role = EXCLUDED.role,
                password_hash = EXCLUDED.password_hash
            """,
            (tenant_id, email, password_hash),
        )
        print(f"[postgres] utilisateur {email} → tenant_id={tenant_id}")

    conn.commit()
    conn.close()
    print(f"[postgres] tenant_id={tenant_id} params + route {DEMO_DID} OK")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prod", action="store_true", help="Met à jour Postgres (prod/staging)")
    parser.add_argument("--tenant-id", type=int, default=None)
    parser.add_argument("--create-demo-user", action="store_true", help="Crée/met à jour demo@uwi.app (prod)")
    args = parser.parse_args()

    default_tid = 2 if args.prod else 1
    tenant_id = args.tenant_id or int(os.getenv("DEMO_TENANT_ID") or os.getenv("TEST_TENANT_ID") or default_tid)

    if args.prod:
        link_postgres(tenant_id, create_demo_user=args.create_demo_user)
    else:
        link_sqlite(tenant_id)

    print("Terminé. Redémarrez uvicorn si besoin, puis vérifiez GET /api/tenant/me (voice_number, vapi_assistant_id).")


if __name__ == "__main__":
    main()
