#!/usr/bin/env python3
"""Supprime tous les leads (table pre_onboarding_leads). Remise à zéro liste / cockpit.

Usage (depuis la racine du dépôt) :
  python3 scripts/delete_all_pre_onboarding_leads.py --confirm

Charge automatiquement les variables depuis .env si présent (DATABASE_URL ou PG_TENANTS_URL).

ATTENTION : irréversible. À n'exécuter que sur la base voulue.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def preload_env():
    env_path = REPO / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def main() -> int:
    parser = argparse.ArgumentParser(description="Supprime tous les lignes pre_onboarding_leads")
    parser.add_argument("--confirm", action="store_true", required=True, help="Confirme la suppression définitive")
    args = parser.parse_args()

    preload_env()

    sys.path.insert(0, str(REPO))
    os.chdir(REPO)

    from backend.leads_pg import delete_all_pre_onboarding_leads

    if not os.environ.get("DATABASE_URL") and not os.environ.get("PG_TENANTS_URL"):
        print("DATABASE_URL ou PG_TENANTS_URL manquant (.env ou environnement)", file=sys.stderr)
        return 1

    n = delete_all_pre_onboarding_leads()
    print(f"Supprimé {n} ligne(s) dans pre_onboarding_leads.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
