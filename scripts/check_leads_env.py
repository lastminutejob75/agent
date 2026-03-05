#!/usr/bin/env python3
"""
Vérifie la config pour les leads pré-onboarding (wizard + emails).
Usage: python scripts/check_leads_env.py
       ou: API_URL=https://api.uwiapp.com python scripts/check_leads_env.py  # vérifier le backend déployé
Charge .env à la racine si présent. N'affiche jamais les valeurs.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
env_file = ROOT / ".env"
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip("'\"")
                    if key and key not in os.environ:
                        os.environ[key] = value


def main() -> int:
    print("Config leads pré-onboarding\n")

    # DB
    db_url = (os.getenv("DATABASE_URL") or os.getenv("PG_TENANTS_URL") or "").strip()
    db_ok = bool(db_url)
    print(f"  {'OK' if db_ok else 'MANQUANT':8}  DATABASE_URL ou PG_TENANTS_URL  (base des leads)")

    # Destinataire email
    to_vars = ["FOUNDER_EMAIL", "ADMIN_EMAIL", "ADMIN_ALERT_EMAIL", "REPORT_EMAIL", "SMTP_EMAIL"]
    to_ok = any((os.getenv(k) or "").strip() for k in to_vars)
    print(f"  {'OK' if to_ok else 'MANQUANT':8}  FOUNDER_EMAIL / ADMIN_EMAIL / ADMIN_ALERT_EMAIL / REPORT_EMAIL / SMTP_EMAIL  (destinataire)")

    # Envoi
    postmark = (
        (os.getenv("POSTMARK_SERVER_TOKEN") or "").strip()
        and (os.getenv("EMAIL_FROM") or os.getenv("POSTMARK_FROM_EMAIL") or os.getenv("SMTP_EMAIL") or "").strip()
    )
    smtp = (os.getenv("SMTP_EMAIL") or "").strip() and (os.getenv("SMTP_PASSWORD") or "").strip()
    send_ok = postmark or smtp
    print(f"  {'OK' if send_ok else 'MANQUANT':8}  Postmark ou SMTP  (envoi)")

    print()
    if db_ok and to_ok and send_ok:
        print("  Config OK. Si leads introuvables : vérifier VITE_UWI_API_BASE_URL (Vercel) = même URL que le backend.")
        return 0
    print("  Config incomplète. Sur Railway : DATABASE_URL, FOUNDER_EMAIL (ou REPORT_EMAIL), Postmark ou SMTP.")
    print("  Diagnostic backend : curl https://TON_API/api/pre-onboarding/config")
    return 1


if __name__ == "__main__":
    sys.exit(main())
