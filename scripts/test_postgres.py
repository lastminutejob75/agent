#!/usr/bin/env python3
"""
Teste la connexion Postgres (DATABASE_URL ou PG_TENANTS_URL).
Usage: python scripts/test_postgres.py
       DATABASE_URL=postgres://... python scripts/test_postgres.py
       railway run python scripts/test_postgres.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Charger .env si présent
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
        print("❌ DATABASE_URL ou PG_TENANTS_URL requis")
        print("   railway run python scripts/test_postgres.py")
        return 1

    # Masquer le mot de passe dans l'affichage
    safe_url = url.split("@")[-1] if "@" in url else url[:50] + "..."
    print(f"🔗 Connexion à Postgres... ({safe_url})")

    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        print("✅ Postgres OK (SELECT 1 réussi)")

        # Vérifier les tables auth
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name IN ('tenant_users', 'magic_links', 'auth_events')
                    ORDER BY table_name
                """)
                tables = [r[0] for r in cur.fetchall()]
        if tables:
            print(f"   Tables auth: {', '.join(tables)}")
        else:
            print("   ⚠️ Tables auth absentes (migrations 007/008 à exécuter)")

        return 0
    except ImportError:
        print("❌ psycopg requis: pip install psycopg[binary]")
        return 1
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
