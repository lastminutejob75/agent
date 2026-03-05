#!/usr/bin/env python3
"""
Extrait le client_email du Service Account Google.
Sources : GOOGLE_SERVICE_ACCOUNT_BASE64 (env) ou credentials/service-account.json
"""
import base64
import json
import os
from pathlib import Path

# Charger .env si présent
_env = Path(__file__).resolve().parent.parent / ".env"
if _env.exists():
    from dotenv import load_dotenv
    load_dotenv(_env)

b64 = os.getenv("GOOGLE_SERVICE_ACCOUNT_BASE64")
if b64:
    try:
        data = json.loads(base64.b64decode(b64).decode())
        email = (data.get("client_email") or "").strip()
        if email:
            print(email)
        else:
            print("client_email non trouvé dans le JSON")
    except Exception as e:
        print(f"Erreur décodage: {e}")
else:
    # Fallback : fichier local
    for path in ["credentials/service-account.json", "credentials/uwi-agent-service-account.json"]:
        p = Path(__file__).resolve().parent.parent / path
        if p.exists():
            try:
                data = json.loads(p.read_text())
                email = (data.get("client_email") or "").strip()
                if email:
                    print(email)
                    break
            except Exception as e:
                print(f"Erreur lecture {path}: {e}")
    else:
        print("GOOGLE_SERVICE_ACCOUNT_BASE64 non défini et aucun fichier credentials trouvé")
