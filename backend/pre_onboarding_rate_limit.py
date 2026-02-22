# backend/pre_onboarding_rate_limit.py — Rate limit POST /api/pre-onboarding/commit (in-memory)
# Anti-spam minimal : 10 req/min par IP, 3 req/min par email

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import List

logger = logging.getLogger(__name__)

_store: defaultdict[str, List[float]] = defaultdict(list)
_WINDOW_SEC = 60
_MAX_PER_IP = 10
_MAX_PER_EMAIL = 3


def _trim(key: str) -> None:
    now = time.time()
    cutoff = now - _WINDOW_SEC
    _store[key] = [t for t in _store[key] if t > cutoff]


def _inc(key: str) -> int:
    _trim(key)
    now = time.time()
    _store[key].append(now)
    return len(_store[key])


def _client_ip(request) -> str:
    forwarded = (getattr(request, "headers", None) or {}).get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if getattr(request, "client", None) and request.client:
        return request.client.host or "0.0.0.0"
    return "0.0.0.0"


def check_pre_onboarding_commit(request, email: str) -> None:
    """
    À appeler avant de traiter POST /api/pre-onboarding/commit.
    Lève RuntimeError si rate limit dépassé (à convertir en 429).
    Email normalisé (lowercase + strip) pour la clé ; si vide/malformé, on rate-limit uniquement sur IP.
    """
    ip = _client_ip(request)
    ip_key = f"preonb_ip:{ip}"
    email_key = f"preonb_email:{(email or '').strip().lower()}"
    n_ip = _inc(ip_key)
    n_email = _inc(email_key) if email else 0
    if n_ip > _MAX_PER_IP:
        logger.warning("rate_limit pre_onboarding_commit ip=%s count=%s", ip[:32], n_ip)
        raise RuntimeError("Trop de demandes. Réessayez dans une minute.")
    if email and n_email > _MAX_PER_EMAIL:
        logger.warning("rate_limit pre_onboarding_commit email count=%s", n_email)
        raise RuntimeError("Trop de demandes pour cet email. Réessayez dans une minute.")
