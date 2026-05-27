"""
Garde-fous sécurité (données médicales / multi-tenant).
"""
from __future__ import annotations

import hmac
import logging
import os
import time
from typing import Any, Dict, Optional, Set
from urllib.parse import urlparse

import jwt
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

_LEAD_TOKEN_TYP = "lead_access"
_LEAD_TOKEN_TTL_SECONDS = int(os.environ.get("LEAD_ACCESS_TOKEN_TTL_SECONDS", str(7 * 24 * 3600)))
_USED_IMPERSONATE_JTIS: Dict[str, float] = {}
_IMPERSONATE_JTI_TTL_SECONDS = 600


def is_production() -> bool:
    env = (os.environ.get("ENV") or os.environ.get("RAILWAY_ENVIRONMENT") or "").strip().lower()
    return env in ("production", "prod")


def debug_routes_enabled() -> bool:
    # Flag principal attendu par les tests/ops.
    flag = (os.environ.get("ENABLE_DEBUG_ENDPOINTS") or "").strip().lower()
    if not flag:
        # Compat legacy.
        flag = (os.environ.get("ENABLE_DEBUG_ROUTES") or "").strip().lower()
    if flag in ("true", "1", "yes", "on"):
        return True
    if flag in ("false", "0", "no", "off"):
        return False
    # Secure by default: fermé tant que non explicitement activé.
    return False


def require_strict_tenant_key() -> bool:
    if is_production():
        return True
    from backend import config

    return config.is_multi_tenant_mode()


def _jwt_secret() -> str:
    return (os.environ.get("JWT_SECRET") or os.environ.get("LEAD_ACCESS_SECRET") or "").strip()


def _normalize_origin(url: str) -> str:
    u = (url or "").strip().rstrip("/")
    if not u:
        return ""
    try:
        p = urlparse(u)
        if p.scheme and p.netloc:
            return f"{p.scheme}://{p.netloc}".rstrip("/")
    except Exception:
        pass
    return u


def google_redirect_allowed(redirect_uri: str) -> bool:
    redirect = (redirect_uri or "").strip()
    if not redirect:
        return False
    allowlist: Set[str] = set()
    for key in (
        "GOOGLE_REDIRECT_URI",
        "GOOGLE_REDIRECT_URI_DEFAULT",
        "FRONT_BASE_URL",
        "APP_BASE_URL",
    ):
        origin = _normalize_origin(os.environ.get(key) or "")
        if origin:
            allowlist.add(origin)
    cors_raw = (os.environ.get("CORS_ORIGINS") or "").strip()
    for part in cors_raw.split(","):
        origin = _normalize_origin(part)
        if origin:
            allowlist.add(origin)
    extra = (os.environ.get("GOOGLE_REDIRECT_URI_ALLOWLIST") or "").strip()
    for part in extra.split(","):
        origin = _normalize_origin(part)
        if origin:
            allowlist.add(origin)
    candidate = _normalize_origin(redirect)
    if candidate in allowlist:
        return True
    if not is_production():
        return redirect.startswith("http://localhost") or redirect.startswith("http://127.0.0.1")
    logger.warning("google_redirect_rejected uri=%s allowlist_size=%d", redirect[:120], len(allowlist))
    return False


def assert_google_redirect_allowed(redirect_uri: str) -> None:
    if not google_redirect_allowed(redirect_uri):
        raise HTTPException(400, "redirect_uri non autorisée")


def verify_vapi_webhook(request: Request) -> bool:
    secret = (os.environ.get("VAPI_WEBHOOK_SECRET") or "").strip()
    if not secret:
        if is_production():
            logger.error("VAPI_WEBHOOK_SECRET manquant en production")
            return False
        return True
    provided = (request.headers.get("x-vapi-secret") or request.headers.get("X-Vapi-Secret") or "").strip()
    if not provided:
        auth = (request.headers.get("authorization") or "").strip()
        if auth.lower().startswith("bearer "):
            provided = auth[7:].strip()
    return bool(provided) and hmac.compare_digest(provided, secret)


def assert_vapi_webhook(request: Request) -> None:
    if not verify_vapi_webhook(request):
        raise HTTPException(401, "Webhook Vapi non autorisé")


def issue_lead_access_token(lead_id: str) -> str:
    secret = _jwt_secret()
    if not secret:
        raise RuntimeError("JWT_SECRET required for lead access tokens")
    now = int(time.time())
    payload = {
        "typ": _LEAD_TOKEN_TYP,
        "lead_id": str(lead_id),
        "iat": now,
        "exp": now + _LEAD_TOKEN_TTL_SECONDS,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def verify_lead_access_token(lead_id: str, token: Optional[str]) -> bool:
    secret = _jwt_secret()
    if not secret or not token:
        return False
    try:
        payload = jwt.decode(str(token).strip(), secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return False
    if payload.get("typ") != _LEAD_TOKEN_TYP:
        return False
    return str(payload.get("lead_id") or "") == str(lead_id)


def assert_lead_access(lead_id: str, token: Optional[str]) -> None:
    if verify_lead_access_token(lead_id, token):
        return
    if is_production():
        raise HTTPException(403, "Accès refusé à cette ressource lead")
    logger.warning("lead_access_token_missing_or_invalid lead_id=%s (autorisé hors prod)", (lead_id or "")[:36])


def _purge_impersonate_jtis() -> None:
    now = time.time()
    expired = [jti for jti, ts in _USED_IMPERSONATE_JTIS.items() if now - ts > _IMPERSONATE_JTI_TTL_SECONDS]
    for jti in expired:
        _USED_IMPERSONATE_JTIS.pop(jti, None)


def register_impersonate_jti(jti: str) -> bool:
    """Retourne False si le jti a déjà été consommé (usage unique)."""
    if not jti:
        return True
    _purge_impersonate_jtis()
    if jti in _USED_IMPERSONATE_JTIS:
        return False
    _USED_IMPERSONATE_JTIS[jti] = time.time()
    return True


def admin_session_secret() -> str:
    admin_only = (os.environ.get("ADMIN_SESSION_SECRET") or "").strip()
    shared = (os.environ.get("JWT_SECRET") or "").strip()
    if is_production() and not admin_only:
        logger.warning(
            "ADMIN_SESSION_SECRET non défini en production — utiliser un secret admin dédié (≠ JWT_SECRET)"
        )
    return admin_only or shared
