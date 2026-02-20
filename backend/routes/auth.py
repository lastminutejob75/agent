# backend/routes/auth.py
"""
Auth tenant: Magic Link + JWT ; login email+mdp (cookie uwi_session) ; Google SSO.
- POST /api/auth/request-link {email}
- GET /api/auth/verify?token=...
- POST /api/auth/login {email, password} → cookie uwi_session
- GET /api/auth/me → profil depuis cookie
- POST /api/auth/logout → supprime cookie
- GET /api/auth/google/start → { auth_url, state }
- POST /api/auth/google/callback { code, redirect_uri, state } → cookie uwi_session
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

from backend.auth_events_pg import log_auth_event
from backend.auth_pg import (
    auth_create_magic_link,
    auth_get_tenant_user_by_email,
    auth_verify_magic_link,
    pg_get_tenant_user_by_email_for_google,
    pg_get_tenant_user_by_email_for_login,
    pg_get_tenant_user_by_id,
    pg_link_google_sub,
)
from backend.services.email_service import send_magic_link_email
from backend.tenants_pg import pg_create_tenant, pg_get_tenant_full

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

JWT_SECRET = os.environ.get("JWT_SECRET") or os.environ.get("SESSION_SECRET") or ""
APP_BASE_URL = (os.environ.get("APP_BASE_URL") or "").rstrip("/")
MAGICLINK_TTL_MINUTES = int(os.environ.get("MAGICLINK_TTL_MINUTES", "15"))
ENABLE_MAGICLINK_DEBUG = (os.environ.get("ENABLE_MAGICLINK_DEBUG") or "").lower() == "true"
JWT_EXPIRES_DAYS = 7

# Session cookie (login email+mdp) — delete_cookie doit matcher secure/samesite/path
SESSION_COOKIE_NAME = os.environ.get("SESSION_COOKIE_NAME", "uwi_session")
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", str(60 * 60 * 24 * 30)))
COOKIE_SECURE = (os.environ.get("COOKIE_SECURE", "true").lower() == "true")
COOKIE_SAMESITE = os.environ.get("COOKIE_SAMESITE", "none")

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
    from_ref: Optional[str] = Field(None, alias="from", max_length=64)
    tenant_tag: Optional[str] = Field(None, alias="tenant", max_length=128)


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

    # Log support tag quand l’admin envoie le lien (from=admin + tenant=base64url)
    if body.from_ref == "admin" and body.tenant_tag:
        logger.info(
            "LOGIN_REQUEST from=admin tenant_tag=%s email=%s",
            (body.tenant_tag or "")[:64],
            email[:50] if email else "(empty)",
        )

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


@router.get("/impersonate")
def auth_impersonate_validate(token: str = ""):
    """
    Valide un token d’impersonation (émis par POST /api/admin/tenants/{id}/impersonate).
    Retourne tenant_id, tenant_name, expires_at pour que le client stocke le token et affiche le bandeau.
    """
    if not JWT_SECRET:
        raise HTTPException(503, "JWT_SECRET not configured")
    if not token:
        raise HTTPException(400, "token missing")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(400, "Token expiré")
    except jwt.InvalidTokenError:
        raise HTTPException(400, "Token invalide")
    if payload.get("scope") != "impersonate" or "tenant_id" not in payload:
        raise HTTPException(400, "Token invalide (scope)")
    tenant_id = int(payload["tenant_id"])
    exp = payload.get("exp")
    expires_at = datetime.utcfromtimestamp(exp).strftime("%Y-%m-%dT%H:%M:%SZ") if exp else None
    tenant_name = _get_tenant_name(tenant_id)
    log_auth_event(tenant_id, "impersonate", "auth_impersonate_used", None)
    return {
        "tenant_id": tenant_id,
        "tenant_name": tenant_name,
        "expires_at": expires_at,
    }


# --- Login email+mdp (cookie uwi_session) ---

class LoginBody(BaseModel):
    email: EmailStr
    password: str


def _issue_client_session(user_id: int, tenant_id: int, role: str) -> str:
    now = int(time.time())
    payload = {
        "typ": "client_session",
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role,
        "iat": now,
        "exp": now + SESSION_TTL_SECONDS,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _read_client_session_cookie(request: Request) -> Optional[dict]:
    raw = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw:
        return None
    if not JWT_SECRET:
        return None
    try:
        payload = jwt.decode(raw, JWT_SECRET, algorithms=["HS256"])
        if payload.get("typ") != "client_session":
            return None
        return payload
    except Exception:
        return None


@router.post("/login")
def auth_login(body: LoginBody, response: Response):
    """
    Login email + mot de passe. Pose le cookie uwi_session (JWT).
    Réponse neutre en cas d'échec (anti-enumération).
    """
    if not JWT_SECRET:
        raise HTTPException(503, "JWT_SECRET not configured")
    email = (body.email or "").strip().lower()
    password = (body.password or "").strip()

    row = pg_get_tenant_user_by_email_for_login(email)
    if not row or not row.get("password_hash"):
        raise HTTPException(status_code=401, detail="Identifiants invalides")

    password_hash = row["password_hash"]
    ok = False
    try:
        ok = bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        ok = False
    if not ok:
        raise HTTPException(status_code=401, detail="Identifiants invalides")

    token = _issue_client_session(
        user_id=row["user_id"],
        tenant_id=row["tenant_id"],
        role=row["role"],
    )
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
        max_age=SESSION_TTL_SECONDS,
    )
    log_auth_event(row["tenant_id"], email, "auth_login_password", None)
    return {"ok": True}


@router.get("/me")
def auth_me(request: Request):
    """
    Profil du client connecté via cookie uwi_session.
    """
    payload = _read_client_session_cookie(request)
    if not payload:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    row = pg_get_tenant_user_by_id(user_id)
    if not row:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {
        "id": str(user_id),
        "tenant_id": str(row["tenant_id"]),
        "email": row["email"],
        "role": row["role"],
    }


@router.post("/logout")
def auth_logout(response: Response):
    """Supprime le cookie (secure/samesite/path identiques à set_cookie)."""
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
    )
    return {"ok": True}


# --- Google SSO (PKCE + state signé, auto-link par email, signup via onboarding) ---

GOOGLE_CLIENT_ID = (os.environ.get("GOOGLE_CLIENT_ID") or "").strip()
GOOGLE_CLIENT_SECRET = (os.environ.get("GOOGLE_CLIENT_SECRET") or "").strip()
GOOGLE_REDIRECT_URI_DEFAULT = (os.environ.get("GOOGLE_REDIRECT_URI") or "").strip()
GOOGLE_OAUTH_SCOPES = os.environ.get("GOOGLE_OAUTH_SCOPES", "openid email profile").strip()
GOOGLE_OAUTH_STATE_TTL_SECONDS = 600  # 10 min

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _pkce_code_verifier_and_challenge() -> tuple[str, str]:
    code_verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("utf-8")
    return code_verifier, code_challenge


# Anti-replay : jti déjà utilisés (TTL 10 min). Cleans lazily on check.
_used_oauth_jtis: dict[str, float] = {}


def _issue_oauth_state() -> str:
    """State JWT : nonce (jti) + exp uniquement. Pas de code_verifier (stocké côté front)."""
    now = int(time.time())
    payload = {
        "typ": "google_oauth_state",
        "jti": secrets.token_urlsafe(16),
        "iat": now,
        "exp": now + GOOGLE_OAUTH_STATE_TTL_SECONDS,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _verify_and_consume_oauth_state(state: str) -> bool:
    """Vérifie signature + exp et consomme jti (anti-replay). Retourne True si valide et pas déjà utilisé."""
    if not state or not JWT_SECRET:
        return False
    now = time.time()
    # Purge anciens jti
    for jti, t in list(_used_oauth_jtis.items()):
        if now - t > GOOGLE_OAUTH_STATE_TTL_SECONDS:
            del _used_oauth_jtis[jti]
    try:
        payload = jwt.decode(state, JWT_SECRET, algorithms=["HS256"])
        if payload.get("typ") != "google_oauth_state":
            return False
        jti = payload.get("jti")
        if not jti or jti in _used_oauth_jtis:
            return False
        _used_oauth_jtis[jti] = now
        return True
    except Exception:
        return False


@router.get("/google/start")
def auth_google_start(redirect_uri: Optional[str] = None):
    """
    Retourne auth_url (Google), state (JWT signé sans secret), et code_verifier.
    Front : stocker code_verifier en sessionStorage, rediriger vers auth_url.
    Au retour (page callback) : POST /callback avec { code, redirect_uri, state, code_verifier }, credentials: include.
    """
    if not GOOGLE_CLIENT_ID or not JWT_SECRET:
        raise HTTPException(503, "Google SSO not configured")
    redirect = (redirect_uri or GOOGLE_REDIRECT_URI_DEFAULT).strip()
    if not redirect:
        raise HTTPException(400, "redirect_uri required (query or GOOGLE_REDIRECT_URI)")
    code_verifier, code_challenge = _pkce_code_verifier_and_challenge()
    state = _issue_oauth_state()
    params = {
        "response_type": "code",
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect,
        "scope": GOOGLE_OAUTH_SCOPES,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
    }
    qs = "&".join(f"{k}={urllib.parse.quote(v)}" for k, v in params.items())
    auth_url = f"{GOOGLE_AUTH_URL}?{qs}"
    return {"auth_url": auth_url, "state": state, "code_verifier": code_verifier}


class GoogleCallbackBody(BaseModel):
    code: str
    redirect_uri: str
    state: str
    code_verifier: str


def _exchange_code_for_tokens(code: str, redirect_uri: str, code_verifier: str) -> Optional[dict]:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "code_verifier": code_verifier,
    }
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        GOOGLE_TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.warning("Google token exchange failed: %s", e)
        return None


def _verify_google_id_token(id_token_str: str) -> Optional[dict]:
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests
        idinfo = id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
        if idinfo.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
            return None
        return idinfo
    except Exception as e:
        logger.warning("Google id_token verify failed: %s", e)
        return None


@router.post("/google/callback")
def auth_google_callback(body: GoogleCallbackBody, response: Response):
    """
    Échange code → tokens (code_verifier fourni par le front), vérifie id_token, auto-link ou signup, pose cookie uwi_session.
    redirect_uri doit être strictement identique à celle passée à /start et déclarée dans Google Console.
    """
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET or not JWT_SECRET:
        raise HTTPException(503, "Google SSO not configured")
    if not _verify_and_consume_oauth_state(body.state):
        raise HTTPException(400, "Invalid or expired state")
    code_verifier = (body.code_verifier or "").strip()
    if not code_verifier:
        raise HTTPException(400, "code_verifier required")
    redirect_uri = body.redirect_uri.strip()
    tokens = _exchange_code_for_tokens(body.code, redirect_uri, code_verifier)
    if not tokens or "id_token" not in tokens:
        raise HTTPException(400, "Token exchange failed")
    idinfo = _verify_google_id_token(tokens["id_token"])
    if not idinfo:
        raise HTTPException(401, "Invalid id_token")
    email = (idinfo.get("email") or "").strip().lower()
    email_verified = idinfo.get("email_verified") is True
    sub = idinfo.get("sub")
    if not email or not sub:
        raise HTTPException(401, "Missing email or sub in id_token")
    if not email_verified:
        raise HTTPException(403, "Email non vérifié par Google")

    row = pg_get_tenant_user_by_email_for_google(email)
    if row:
        link_result = pg_link_google_sub(row["user_id"], sub, email)
        if link_result == "conflict":
            raise HTTPException(409, "Compte déjà lié à un autre compte Google")
        tenant_id = row["tenant_id"]
        user_id = row["user_id"]
        role = row["role"]
    else:
        # Signup via onboarding : créer tenant + owner (même flow que public/onboarding).
        # En forte concurrence, idéalement transaction (create tenant + user + link) pour éviter tenants fantômes.
        company_name = (idinfo.get("name") or email.split("@")[0] or "Nouveau").strip()[:200]
        tid = pg_create_tenant(
            name=company_name,
            contact_email=email,
            calendar_provider="none",
            calendar_id="",
            timezone="Europe/Paris",
        )
        if not tid:
            raise HTTPException(500, "Création de compte échouée")
        row2 = pg_get_tenant_user_by_email_for_google(email)
        if not row2:
            raise HTTPException(500, "Création de compte échouée")
        link_result = pg_link_google_sub(row2["user_id"], sub, email)
        if link_result == "conflict":
            raise HTTPException(409, "Compte déjà lié à un autre compte Google")
        tenant_id = row2["tenant_id"]
        user_id = row2["user_id"]
        role = row2["role"]

    token = _issue_client_session(user_id=user_id, tenant_id=tenant_id, role=role)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
        max_age=SESSION_TTL_SECONDS,
    )
    log_auth_event(tenant_id, email, "auth_google_sso", None)
    return {"ok": True}
