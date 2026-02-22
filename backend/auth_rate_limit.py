# backend/auth_rate_limit.py — Rate limiting auth endpoints (in-memory TTL)
# Politique: forgot 5/min IP + 3/min email, reset 10/min IP, login 10/min IP

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import List

logger = logging.getLogger(__name__)

# key -> list of timestamps (epoch sec)
_store: defaultdict[str, List[float]] = defaultdict(list)
_WINDOW_SEC = 60


def _trim(key: str) -> None:
    now = time.time()
    cutoff = now - _WINDOW_SEC
    _store[key] = [t for t in _store[key] if t > cutoff]


def _inc(key: str) -> int:
    _trim(key)
    now = time.time()
    _store[key].append(now)
    return len(_store[key])


def _count(key: str) -> int:
    _trim(key)
    return len(_store[key])


def _client_ip(request) -> str:
    forwarded = (getattr(request, "headers", None) or {}).get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if getattr(request, "client", None) and request.client:
        return request.client.host or "0.0.0.0"
    return "0.0.0.0"


def check_forgot_password(request, email: str) -> None:
    """Lève pas d’exception = OK. Sinon raise une exception à convertir en 429."""
    ip = _client_ip(request)
    ip_key = f"forgot_ip:{ip}"
    email_key = f"forgot_email:{(email or '').strip().lower()}"
    n_ip = _inc(ip_key)
    n_email = _inc(email_key) if email else 0
    if n_ip > 5:
        logger.warning("rate_limit forgot_password ip=%s count=%s", ip[:32], n_ip)
        raise RuntimeError("Trop de demandes. Réessayez dans une minute.")
    if email and n_email > 3:
        logger.warning("rate_limit forgot_password email count=%s", n_email)
        raise RuntimeError("Trop de demandes pour cet email. Réessayez dans une minute.")


def check_reset_password(request) -> None:
    ip = _client_ip(request)
    key = f"reset_ip:{ip}"
    n = _inc(key)
    if n > 10:
        logger.warning("rate_limit reset_password ip=%s count=%s", ip[:32], n)
        raise RuntimeError("Trop de tentatives. Réessayez dans une minute.")


def check_login(request) -> None:
    ip = _client_ip(request)
    key = f"login_ip:{ip}"
    n = _inc(key)
    if n > 10:
        logger.warning("rate_limit login ip=%s count=%s", ip[:32], n)
        raise RuntimeError("Trop de tentatives de connexion. Réessayez dans une minute.")
