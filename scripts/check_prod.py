#!/usr/bin/env python3
"""
Vérifie qu'une instance UWi (prod ou locale) est correctement configurée.
Usage:
  export BASE_URL=https://ton-app.railway.app
  python scripts/check_prod.py
Sans BASE_URL, utilise http://localhost:8000
"""
from __future__ import annotations
import os
import sys
import urllib.request
import urllib.error
import json
from typing import Optional, Tuple

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")


def get(path: str) -> Tuple[Optional[dict], Optional[str]]:
    """GET JSON; returns (data, error)."""
    url = f"{BASE_URL}{path}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode()), None
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode()
            return None, f"HTTP {e.code}: {body[:200]}"
        except Exception:
            return None, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return None, str(e.reason) if getattr(e, "reason", None) else str(e)
    except Exception as e:
        return None, str(e)


def main():
    print(f"Base URL: {BASE_URL}\n")
    ok_count = 0
    total = 0

    # 1. GET /health
    total += 1
    data, err = get("/health")
    if err:
        print(f"  [KO] GET /health -> {err}")
    else:
        status = data.get("status") == "ok"
        creds = data.get("credentials_loaded", False)
        cal = data.get("calendar_id_set", False)
        if status:
            ok_count += 1
            print("  [OK] GET /health -> status=ok")
        else:
            print("  [KO] GET /health -> status != ok")
        print(f"       credentials_loaded={creds}, calendar_id_set={cal}")
        if not creds:
            print("       -> Vérifier GOOGLE_SERVICE_ACCOUNT_BASE64")
        if not cal:
            print("       -> Vérifier GOOGLE_CALENDAR_ID")

    # 2. GET /api/vapi/health
    total += 1
    data, err = get("/api/vapi/health")
    if err:
        print(f"  [KO] GET /api/vapi/health -> {err}")
    else:
        if data.get("status") == "ok" and data.get("service") == "voice":
            ok_count += 1
            print("  [OK] GET /api/vapi/health -> status=ok, service=voice")
        else:
            print(f"  [KO] GET /api/vapi/health -> {data}")

    # 3. GET /api/vapi/test (optionnel, vérifie que l'engine répond)
    total += 1
    data, err = get("/api/vapi/test")
    if err:
        print(f"  [KO] GET /api/vapi/test -> {err}")
    else:
        if data.get("status") == "ok" and data.get("response"):
            ok_count += 1
            print("  [OK] GET /api/vapi/test -> engine répond")
        else:
            print(f"  [KO] GET /api/vapi/test -> {data}")

    print()
    if ok_count == total:
        print(f"Résultat: {ok_count}/{total} vérifications OK. Prêt pour test client.")
        return 0
    print(f"Résultat: {ok_count}/{total} OK. Corriger les éléments KO avant test client.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
