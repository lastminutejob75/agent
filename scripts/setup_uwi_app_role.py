#!/usr/bin/env python3
"""
Crée le rôle PostgreSQL uwi_app sur Railway (ou toute instance Postgres).

Railway fournit en général DATABASE_URL avec l'utilisateur postgres (superuser).
Ce script :
  1. Se connecte avec DATABASE_URL (postgres)
  2. Crée ou met à jour uwi_app (LOGIN, non superuser, pas de BYPASSRLS)
  3. Applique les GRANT (migration 035)
  4. Affiche la nouvelle URL à mettre dans Railway pour le service backend

Usage (depuis votre machine, URL prod) :
  DATABASE_URL='postgresql://postgres:...@...railway.app:5432/railway' \\
    python scripts/setup_uwi_app_role.py

Sur Railway (CLI) :
  railway link
  railway run python scripts/setup_uwi_app_role.py

Variables :
  DATABASE_URL          Connexion admin (postgres) — obligatoire
  UWI_APP_PASSWORD      Mot de passe uwi_app (sinon généré aléatoirement)
  UWI_APP_ROLE          Nom du rôle (défaut: uwi_app)
"""
from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path
from urllib.parse import quote_plus, urlparse, urlunparse

_root = Path(__file__).resolve().parent.parent
_env = _root / ".env"
if _env.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(_env)
    except ImportError:
        pass


def _admin_url() -> str:
    url = (
        os.environ.get("DATABASE_URL_MIGRATE")
        or os.environ.get("DATABASE_URL")
        or os.environ.get("PG_TENANTS_URL")
        or ""
    ).strip()
    if not url:
        print("Erreur: définissez DATABASE_URL (utilisateur postgres Railway).", file=sys.stderr)
        sys.exit(1)
    return url


def _build_app_url(admin_url: str, role: str, password: str) -> str:
    p = urlparse(admin_url)
    # Normaliser schéma pour psycopg / Railway
    scheme = p.scheme or "postgresql"
    if scheme == "postgres":
        scheme = "postgresql"
    user = quote_plus(role)
    pwd = quote_plus(password)
    host = p.hostname or "localhost"
    port = p.port or 5432
    db = (p.path or "/railway").lstrip("/") or "railway"
    netloc = f"{user}:{pwd}@{host}"
    if port:
        netloc += f":{port}"
    return urlunparse((scheme, netloc, f"/{db}", "", "", ""))


def main() -> int:
    parser = argparse.ArgumentParser(description="Créer le rôle PostgreSQL uwi_app (Railway)")
    parser.add_argument(
        "--password",
        default=(os.environ.get("UWI_APP_PASSWORD") or "").strip(),
        help="Mot de passe uwi_app (sinon généré)",
    )
    parser.add_argument(
        "--role",
        default=(os.environ.get("UWI_APP_ROLE") or "uwi_app").strip(),
        help="Nom du rôle (défaut: uwi_app)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Afficher le plan sans modifier la base")
    args = parser.parse_args()

    role = args.role or "uwi_app"
    if not role.replace("_", "").isalnum():
        print("Erreur: nom de rôle invalide", file=sys.stderr)
        return 1

    password = args.password or secrets.token_urlsafe(24)

    grants_path = _root / "migrations" / "035_uwi_app_role_grants.sql"
    if not grants_path.exists():
        print(f"Erreur: fichier introuvable {grants_path}", file=sys.stderr)
        return 1
    grants_sql = grants_path.read_text(encoding="utf-8")

    if args.dry_run:
        print(f"Rôle: {role}")
        print("Étapes: CREATE ROLE → GRANT (035) → afficher DATABASE_URL uwi_app pour Railway")
        return 0

    admin_url = _admin_url()

    try:
        import psycopg
    except ImportError:
        print("pip install psycopg[binary]", file=sys.stderr)
        return 1

    # Vérifier migration RLS
    try:
        with psycopg.connect(admin_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM pg_proc WHERE proname = 'app_current_tenant_id' LIMIT 1"
                )
                if not cur.fetchone():
                    print(
                        "Attention: migration 034 (RLS) non détectée. "
                        "Lancez d'abord: python scripts/run_migration.py 034",
                        file=sys.stderr,
                    )
    except Exception as e:
        print(f"Note: impossible de vérifier la migration 034: {e}", file=sys.stderr)

    try:
        import psycopg.sql as sql

        with psycopg.connect(admin_url) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
                exists = cur.fetchone() is not None
                ident = sql.Identifier(role)
                if exists:
                    cur.execute(
                        sql.SQL(
                            "ALTER ROLE {} WITH LOGIN PASSWORD %s "
                            "NOSUPERUSER NOCREATEDB NOCREATEROLE"
                        ).format(ident),
                        (password,),
                    )
                else:
                    cur.execute(
                        sql.SQL(
                            "CREATE ROLE {} LOGIN PASSWORD %s "
                            "NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT"
                        ).format(ident),
                        (password,),
                    )
                print(f"OK — rôle {role} créé ou mis à jour")
            conn.autocommit = False

            with conn.cursor() as cur:
                cur.execute(grants_sql)
            conn.commit()
            print("OK — droits appliqués (035_uwi_app_role_grants.sql)")
    except Exception as e:
        print(f"Erreur: {e}", file=sys.stderr)
        return 1

    app_url = _build_app_url(admin_url, role, password)

    print()
    print("=" * 60)
    print("Railway — variables à configurer")
    print("=" * 60)
    print()
    print("1) Renommez l’URL postgres actuelle (réserve admin / migrations) :")
    print("   DATABASE_URL_MIGRATE = <votre DATABASE_URL postgres actuelle>")
    print()
    print("2) Remplacez DATABASE_URL du service backend par :")
    print()
    print(f"   DATABASE_URL={app_url}")
    print()
    print(f"   PG_TENANTS_URL={app_url}")
    print("   (même valeur si vous utilisez PG_TENANTS_URL)")
    print()
    print("3) Redéployez le backend Railway.")
    print()
    print("4) Migrations futures : utilisez DATABASE_URL_MIGRATE (postgres) :")
    print("   railway run python scripts/run_migration.py <num>")
    print()
    print("Mot de passe uwi_app (conservez-le en lieu sûr) :")
    print(f"   {password}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
