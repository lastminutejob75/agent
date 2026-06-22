"""Health checks par service externe (audit fiabilite 2026-05).

Verifie l'accessibilite et la configuration des integrations critiques :
- PostgreSQL (DB principale)
- Vapi (assistant vocal)
- Twilio (telephonie)
- Stripe (paiement)
- Google Calendar (slots/RDV)
- SMTP / Postmark (emails sortants)

## Resultats

Chaque service retourne un dict :
```json
{
  "status": "ok|degraded|down|not_configured",
  "latency_ms": 42,
  "detail": "msg explicatif (optionnel)"
}
```

Les checks sont :
- **Bornes** : timeout 2s par defaut (configurable).
- **Caches** : 30s en memoire pour eviter de saturer les APIs externes.
- **Fail-soft** : toute exception → `degraded` avec `detail=...`. Jamais d'erreur 500.

## Usage

```python
from backend.health_checks import run_all_checks
result = run_all_checks()  # dict {service: {status, latency_ms, ...}}
```
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Callable, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

# Cache : (service_name) -> (timestamp, result_dict)
_CACHE: Dict[str, tuple] = {}
_CACHE_TTL_SECONDS = 30.0
_CACHE_LOCK = threading.Lock()

DEFAULT_TIMEOUT_S = 2.0


# ---- Statuts -----------------------------------------------------------------

STATUS_OK = "ok"
STATUS_DEGRADED = "degraded"
STATUS_DOWN = "down"
STATUS_NOT_CONFIGURED = "not_configured"


# ---- Helper cache ------------------------------------------------------------


def _cached(service: str, fn: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    """Wrap un check pour le mettre en cache pendant `_CACHE_TTL_SECONDS`."""
    now = time.monotonic()
    with _CACHE_LOCK:
        entry = _CACHE.get(service)
        if entry and (now - entry[0]) < _CACHE_TTL_SECONDS:
            return entry[1]
    # Compute (hors lock pour ne pas serialiser les network calls)
    result = fn()
    with _CACHE_LOCK:
        _CACHE[service] = (now, result)
    return result


def reset_cache() -> None:
    """Vide le cache des checks (utile pour tests)."""
    with _CACHE_LOCK:
        _CACHE.clear()


# ---- Checks individuels ------------------------------------------------------


def check_postgres(timeout: float = DEFAULT_TIMEOUT_S) -> Dict[str, Any]:
    """Verifie la connexion DB via le pool partage."""
    def _do():
        url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL") or ""
        if not url.strip():
            return {"status": STATUS_NOT_CONFIGURED, "detail": "DATABASE_URL not set"}
        t0 = time.monotonic()
        try:
            from backend.pg_pool import pg_connection
            with pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            return {
                "status": STATUS_OK,
                "latency_ms": int((time.monotonic() - t0) * 1000),
            }
        except Exception as e:
            return {
                "status": STATUS_DOWN,
                "latency_ms": int((time.monotonic() - t0) * 1000),
                "detail": str(e)[:120],
            }

    return _cached("postgres", _do)


def check_vapi(timeout: float = DEFAULT_TIMEOUT_S) -> Dict[str, Any]:
    """Verifie l'API Vapi via GET /assistant (auth requise)."""
    def _do():
        api_key = (os.environ.get("VAPI_API_KEY") or "").strip()
        if not api_key:
            return {"status": STATUS_NOT_CONFIGURED, "detail": "VAPI_API_KEY not set"}
        t0 = time.monotonic()
        try:
            with httpx.Client(timeout=timeout) as client:
                r = client.get(
                    "https://api.vapi.ai/assistant",
                    headers={"Authorization": f"Bearer {api_key}"},
                    params={"limit": 1},
                )
            latency = int((time.monotonic() - t0) * 1000)
            if r.status_code in (200, 204):
                return {"status": STATUS_OK, "latency_ms": latency}
            if r.status_code in (401, 403):
                return {
                    "status": STATUS_DEGRADED,
                    "latency_ms": latency,
                    "detail": f"auth failed (HTTP {r.status_code})",
                }
            return {
                "status": STATUS_DEGRADED,
                "latency_ms": latency,
                "detail": f"HTTP {r.status_code}",
            }
        except Exception as e:
            return {
                "status": STATUS_DOWN,
                "latency_ms": int((time.monotonic() - t0) * 1000),
                "detail": str(e)[:120],
            }

    return _cached("vapi", _do)


def check_twilio(timeout: float = DEFAULT_TIMEOUT_S) -> Dict[str, Any]:
    """Verifie l'API Twilio via GET /Accounts/{sid}.json (Basic auth)."""
    def _do():
        sid = (os.environ.get("TWILIO_ACCOUNT_SID") or "").strip()
        token = (os.environ.get("TWILIO_AUTH_TOKEN") or "").strip()
        api_key_sid = (os.environ.get("TWILIO_API_KEY_SID") or "").strip()
        api_key_secret = (os.environ.get("TWILIO_API_KEY_SECRET") or "").strip()
        # Basic auth : clés d'API (SK/secret) en priorité, sinon Account SID + Auth Token.
        if sid and api_key_sid and api_key_secret:
            auth_user, auth_pass = api_key_sid, api_key_secret
        elif sid and token:
            auth_user, auth_pass = sid, token
        else:
            return {"status": STATUS_NOT_CONFIGURED, "detail": "TWILIO_* not set"}
        t0 = time.monotonic()
        try:
            with httpx.Client(timeout=timeout, auth=(auth_user, auth_pass)) as client:
                r = client.get(f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json")
            latency = int((time.monotonic() - t0) * 1000)
            if r.status_code == 200:
                return {"status": STATUS_OK, "latency_ms": latency}
            if r.status_code in (401, 403):
                return {
                    "status": STATUS_DEGRADED,
                    "latency_ms": latency,
                    "detail": f"auth failed (HTTP {r.status_code})",
                }
            return {
                "status": STATUS_DEGRADED,
                "latency_ms": latency,
                "detail": f"HTTP {r.status_code}",
            }
        except Exception as e:
            return {
                "status": STATUS_DOWN,
                "latency_ms": int((time.monotonic() - t0) * 1000),
                "detail": str(e)[:120],
            }

    return _cached("twilio", _do)


def check_stripe(timeout: float = DEFAULT_TIMEOUT_S) -> Dict[str, Any]:
    """Verifie l'API Stripe via GET /v1/customers (auth requise)."""
    def _do():
        key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
        if not key:
            return {"status": STATUS_NOT_CONFIGURED, "detail": "STRIPE_SECRET_KEY not set"}
        t0 = time.monotonic()
        try:
            with httpx.Client(timeout=timeout) as client:
                r = client.get(
                    "https://api.stripe.com/v1/customers",
                    headers={"Authorization": f"Bearer {key}"},
                    params={"limit": 1},
                )
            latency = int((time.monotonic() - t0) * 1000)
            if r.status_code == 200:
                return {"status": STATUS_OK, "latency_ms": latency}
            if r.status_code in (401, 403):
                return {
                    "status": STATUS_DEGRADED,
                    "latency_ms": latency,
                    "detail": f"auth failed (HTTP {r.status_code})",
                }
            return {
                "status": STATUS_DEGRADED,
                "latency_ms": latency,
                "detail": f"HTTP {r.status_code}",
            }
        except Exception as e:
            return {
                "status": STATUS_DOWN,
                "latency_ms": int((time.monotonic() - t0) * 1000),
                "detail": str(e)[:120],
            }

    return _cached("stripe", _do)


def check_calendar() -> Dict[str, Any]:
    """Verifie la config Google Calendar (sans network call : juste presence credentials)."""
    def _do():
        try:
            import backend.config as config
            if not getattr(config, "GOOGLE_CALENDAR_ENABLED", False):
                reason = getattr(config, "GOOGLE_CALENDAR_DISABLE_REASON", "not configured")
                return {"status": STATUS_NOT_CONFIGURED, "detail": str(reason)[:120]}
            if not getattr(config, "GOOGLE_CALENDAR_ID", None):
                return {"status": STATUS_DEGRADED, "detail": "GOOGLE_CALENDAR_ID not set"}
            return {"status": STATUS_OK}
        except Exception as e:
            return {"status": STATUS_DEGRADED, "detail": str(e)[:120]}

    return _cached("calendar", _do)


def check_email() -> Dict[str, Any]:
    """Verifie la config SMTP / Postmark (presence des variables, pas de network)."""
    def _do():
        provider = (os.environ.get("EMAIL_PROVIDER") or "").strip().lower()
        if provider == "postmark":
            tok = (os.environ.get("POSTMARK_SERVER_TOKEN") or "").strip()
            if tok:
                return {"status": STATUS_OK, "detail": "postmark configured"}
            return {"status": STATUS_DEGRADED, "detail": "postmark provider but no token"}
        # SMTP fallback
        host = (os.environ.get("SMTP_HOST") or "").strip()
        user = (os.environ.get("SMTP_EMAIL") or "").strip()
        pwd = (os.environ.get("SMTP_PASSWORD") or "").strip()
        if host and user and pwd:
            return {"status": STATUS_OK, "detail": "smtp configured"}
        return {"status": STATUS_NOT_CONFIGURED, "detail": "no email provider configured"}

    return _cached("email", _do)


# ---- Aggregat ----------------------------------------------------------------


def run_all_checks(timeout: float = DEFAULT_TIMEOUT_S) -> Dict[str, Any]:
    """Lance tous les checks en parallele (threads) et retourne un dict consolide.

    Returns:
        ```json
        {
          "status": "ok|degraded|down",
          "checked_at": "2026-05-09T...",
          "services": {
            "postgres": {...},
            "vapi": {...},
            ...
          }
        }
        ```
    """
    from datetime import datetime, timezone

    services_to_check: Dict[str, Callable[[], Dict[str, Any]]] = {
        "postgres": lambda: check_postgres(timeout),
        "vapi": lambda: check_vapi(timeout),
        "twilio": lambda: check_twilio(timeout),
        "stripe": lambda: check_stripe(timeout),
        "calendar": check_calendar,
        "email": check_email,
    }
    results: Dict[str, Dict[str, Any]] = {}
    threads: list = []

    def _run(name, fn):
        try:
            results[name] = fn()
        except Exception as e:
            results[name] = {"status": STATUS_DEGRADED, "detail": f"check error: {str(e)[:120]}"}

    for name, fn in services_to_check.items():
        t = threading.Thread(target=_run, args=(name, fn), daemon=True, name=f"hc-{name}")
        t.start()
        threads.append(t)

    for t in threads:
        t.join(timeout=timeout + 1.0)

    overall = _aggregate_status(results)
    return {
        "status": overall,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "services": results,
    }


def _aggregate_status(services: Dict[str, Dict[str, Any]]) -> str:
    """Calcule le statut global a partir des statuts individuels.

    - any DOWN dans (postgres, vapi, twilio, stripe) → DOWN
    - any DEGRADED → DEGRADED
    - sinon → OK
    """
    critical = {"postgres", "vapi", "twilio", "stripe"}
    has_down = any(
        services.get(s, {}).get("status") == STATUS_DOWN
        for s in critical
    )
    if has_down:
        return STATUS_DOWN
    has_degraded = any(
        s.get("status") == STATUS_DEGRADED
        for s in services.values()
    )
    if has_degraded:
        return STATUS_DEGRADED
    return STATUS_OK
