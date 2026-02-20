#!/usr/bin/env python3
"""
Envoie un email de test via POST /api/admin/email/test.
Usage:
  API_URL=https://ton-backend.railway.app ADMIN_API_TOKEN=xxx python3 scripts/test_email_send.py ton@email.com
  ou avec .env à la racine (API_URL ou VITE_UWI_API_BASE_URL, ADMIN_API_TOKEN) :
  EMAIL=ton@email.com python3 scripts/test_email_send.py
"""
from __future__ import annotations

import os
import sys

def main() -> int:
    # Charger .env si présent
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(root, ".env")
    if os.path.exists(env_path):
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
        except ImportError:
            pass

    api_url = (os.environ.get("API_URL") or os.environ.get("VITE_UWI_API_BASE_URL") or "").rstrip("/")
    token = (os.environ.get("ADMIN_API_TOKEN") or "").strip()
    email = (os.environ.get("EMAIL") or (sys.argv[1] if len(sys.argv) > 1 else "") or "").strip()

    if not api_url:
        print("Erreur: définir API_URL ou VITE_UWI_API_BASE_URL (URL du backend, ex. https://xxx.railway.app)")
        return 1
    if not token:
        print("Erreur: définir ADMIN_API_TOKEN")
        return 1
    if not email:
        print("Usage: EMAIL=ton@email.com python3 scripts/test_email_send.py")
        print("   ou: python3 scripts/test_email_send.py ton@email.com")
        print("   ou: make test-email EMAIL=ton@email.com  (avec API_URL et ADMIN_API_TOKEN dans .env)")
        return 1

    url = f"{api_url}/api/admin/email/test"
    try:
        import urllib.request
        import json
        req = urllib.request.Request(
            url,
            data=json.dumps({"to": email}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode()
            print(body)
            data = json.loads(body) if body else {}
            if data.get("ok"):
                print("\n✅ Si tu as reçu l'email 'Test UWi', c'est bon.")
                return 0
            print("\n❌ Réponse inattendue.")
            return 1
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"HTTP {e.code}: {body}")
        return 1
    except Exception as e:
        print(f"Erreur: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
