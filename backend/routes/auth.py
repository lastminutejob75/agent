# backend/routes/auth.py
"""
Auth tenant: Magic Link + JWT.
- POST /api/auth/request-link {email}
- GET /api/auth/verify?token=...
"""
from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta

import jwt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.auth_events_pg import log_auth_event
from backend.auth_pg import (
    auth_create_magic_link,
    auth_get_tenant_user_by_email,
    auth_verify_magic_link,
)
from backend.services.email_service import send_magic_link_email
from backend.tenants_pg import pg_get_tenant_full

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

JWT_SECRET = os.environ.get("JWT_SECRET", "")
APP_BASE_URL = (os.environ.get("APP_BASE_URL") or "").rstrip("/")
MAGICLINK_TTL_MINUTES = int(os.environ.get("MAGICLINK_TTL_MINUTES", "15"))
ENABLE_MAGICLINK_DEBUG = (os.environ.get("ENABLE_MAGICLINK_DEBUG") or "").lower() == "true"
JWT_EXPIRES_DAYS = 7

# Rate limit: 5 req/min par clé (IP:email)
_AUTH_RATE_LIMIT: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_WINDOW = 60
_RATE_LIMIT_MAX = 5


def _rate_limit_key(ip: str, email: str) -> str:
    return f"{ip}:{email}"


def _check_rate_limit(ip: str, email: str) -> bool:
    """True si limité (rejeter)."""
    now = time.time()
    key = _rate_limit_key(ip, email)
    window_start = now - _RATE_LIMIT_WINDOW
    _AUTH_RATE_LIMIT[key] = [t for t in _AUTH_RATE_LIMIT[key] if t > window_start]
    if len(_AUTH_RATE_LIMIT[key]) >= _RATE_LIMIT_MAX:
        return True
    _AUTH_RATE_LIMIT[key].append(now)
    return False


class RequestLinkBody(BaseModel):
    email: str = Field(..., max_length=255)


def _get_tenant_name(tenant_id: int) -> str:
    d = pg_get_tenant_full(tenant_id)
    return (d.get("name") or "Tenant") if d else "Tenant"


def _create_jwt(tenant_id: int, email: str, role: str) -> tuple[str, int]:
    exp = datetime.utcnow() + timedelta(days=JWT_EXPIRES_DAYS)
    payload = {
        "sub": email,
        "tenant_id": tenant_id,
        "email": email,
        "role": role,
        "exp": exp,
        "iat": datetime.utcnow(),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return token, int((exp - datetime.utcnow()).total_seconds())


def _client_ip(request: Request) -> str:
    return (request.client.host if request.client else "") or ""


@router.post("/request-link")
def auth_request_link(body: RequestLinkBody, request: Request):
    """
    Demande un magic link. Toujours 200 {ok:true} (anti user enumeration).
    Si email connu: crée token, stocke hash, envoie email Postmark.
    Rate limit: 5/min par IP+email.
    """
    email = (body.email or "").strip().lower()
    if not email:
        return {"ok": True}

    ip = _client_ip(request)
    if _check_rate_limit(ip, email):
        logger.warning("auth_rate_limited ip=%s email=%s", ip[:20], email[:20])
        log_auth_event(None, email, "auth_rate_limited", ip)
        return {"ok": True}  # Toujours neutre, pas de leak

    log_auth_event(None, email, "auth_magic_link_requested", ip)

    user = auth_get_tenant_user_by_email(email)
    if not user:
        logger.debug("request-link: email unknown, no action")
        return {"ok": True}

    tenant_id, _, _ = user
    token = auth_create_magic_link(tenant_id, email, ttl_minutes=MAGICLINK_TTL_MINUTES)
    if not token:
        return {"ok": True}  # Toujours neutre

    log_auth_event(tenant_id, email, "auth_magic_link_sent", None)

    login_url = f"{APP_BASE_URL}/auth/callback?token={token}"
    ok, err = send_magic_link_email(email, login_url, ttl_minutes=MAGICLINK_TTL_MINUTES)
    if not ok:
        logger.warning("magic_link_email failed: %s (still return ok)", err)
        log_auth_event(tenant_id, email, "auth_magic_link_failed", err or "unknown")

    resp = {"ok": True}
    if ENABLE_MAGICLINK_DEBUG:
        resp["debug_login_url"] = login_url
    return resp


@router.get("/verify")
def auth_verify(token: str = ""):
    """
    Vérifie le token magic link, marque used, retourne JWT.
    """
    if not JWT_SECRET:
        raise HTTPException(503, "JWT_SECRET not configured")
    if not token:
        raise HTTPException(400, "token missing")

    result = auth_verify_magic_link(token)
    if not result:
        log_auth_event(None, "", "auth_magic_link_failed", "invalid_or_expired")
        raise HTTPException(400, "Token invalide, expiré ou déjà utilisé")

    tenant_id, email, role = result
    log_auth_event(tenant_id, email, "auth_magic_link_verified", None)
    access_token, expires_in = _create_jwt(tenant_id, email, role)
    tenant_name = _get_tenant_name(tenant_id)
    return {
        "access_token": access_token,
        "tenant_id": tenant_id,
        "tenant_name": tenant_name,
        "email": email,
        "expires_in": expires_in,
    }
