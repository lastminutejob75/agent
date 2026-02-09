#!/usr/bin/env python3
"""
Vérifie la présence des variables d'environnement pour le rapport quotidien (email).
Usage: python scripts/check_report_env.py
       ou depuis la racine: python -m scripts.check_report_env
Charge .env à la racine du projet si présent (python-dotenv optionnel).
N'affiche jamais les valeurs, seulement OK / MANQUANT.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Charger .env depuis la racine du projet
ROOT = Path(__file__).resolve().parent.parent
env_file = ROOT / ".env"
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        # Sans python-dotenv, parser .env à la main (lignes KEY=VALUE)
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip("'\"")
                    if key and key not in os.environ:
                        os.environ[key] = value

# Variables requises pour le rapport quotidien
REPORT_VARS = [
    ("REPORT_EMAIL", "Adresse qui reçoit le rapport"),
    ("OWNER_EMAIL", "Alternative à REPORT_EMAIL (reçoit le rapport)"),
    ("REPORT_SECRET", "Secret partagé avec GitHub Actions"),
    ("SMTP_EMAIL", "Compte qui envoie l'email (ex. Gmail)"),
    ("SMTP_PASSWORD", "Mot de passe d'application SMTP"),
    ("SMTP_HOST", "Ex. smtp.gmail.com (défaut si vide)"),
    ("SMTP_PORT", "Ex. 587 (défaut si vide)"),
]

# Au moins une des deux pour la réception
RECIPIENT_VARS = ["REPORT_EMAIL", "OWNER_EMAIL"]


def main() -> int:
    print("Variables d'environnement — Rapport quotidien (email)\n")
    print(f"Source: .env = {env_file} ({'trouvé' if env_file.exists() else 'absent'}), puis os.environ\n")

    ok_count = 0
    for key, desc in REPORT_VARS:
        value = os.getenv(key)
        if value and value.strip():
            status = "OK"
            ok_count += 1
            detail = f"({len(value)} car.)"
        else:
            status = "MANQUANT"
            detail = ""
        print(f"  {status:8}  {key:20}  {desc} {detail}")

    # Règle métier : au moins un destinataire
    has_recipient = any(os.getenv(k) and os.getenv(k).strip() for k in RECIPIENT_VARS)
    print()
    if has_recipient:
        print("  Destinataire rapport: OK (REPORT_EMAIL ou OWNER_EMAIL défini)")
    else:
        print("  Destinataire rapport: MANQUANT — définir REPORT_EMAIL ou OWNER_EMAIL sur Railway")

    # Envoi possible si SMTP configuré
    smtp_ok = (os.getenv("SMTP_EMAIL") or "").strip() and (os.getenv("SMTP_PASSWORD") or "").strip()
    if smtp_ok:
        print("  Envoi SMTP: OK (SMTP_EMAIL + SMTP_PASSWORD définis)")
    else:
        print("  Envoi SMTP: MANQUANT — définir SMTP_EMAIL et SMTP_PASSWORD sur Railway (mot de passe d'application Gmail)")

    print()
    if not has_recipient or not smtp_ok:
        print("Rappel: sur Railway, ajouter les variables dans le service (Variables).")
        print("Test après déploiement: curl -s -X POST \"https://TON_APP.railway.app/api/reports/daily\" -H \"X-Report-Secret: TON_SECRET\"")
        return 1
    print("Configuration minimale OK. Déploie et teste le curl pour confirmer l'envoi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
