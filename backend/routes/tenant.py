# backend/routes/tenant.py
"""
API tenant (client): dashboard, technical-status, me, params, agenda.
Protégé par cookie uwi_session uniquement (require_tenant_auth).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from backend.auth_pg import pg_get_tenant_user_by_id
from backend.config import get_service_account_email
from backend.db import ensure_tenant_config, get_conn
from backend.google_calendar import GoogleCalendarPermissionError, GoogleCalendarService
from backend.routes.admin import (
    _get_dashboard_snapshot,
    _get_kpis_daily,
    _get_rgpd_extended,
    _get_technical_status,
    _get_tenant_detail,
)
from backend.services.email_service import send_agenda_contact_request_email
from backend.tenants_pg import pg_update_tenant_params

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tenant", tags=["tenant"])

JWT_SECRET = os.environ.get("JWT_SECRET", "")
SESSION_COOKIE_NAME = os.environ.get("SESSION_COOKIE_NAME", "uwi_session")


def _decode_jwt(token: str) -> Optional[Dict[str, Any]]:
    if not JWT_SECRET or not token:
        return None
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None


def _auth_from_cookie(request: Request) -> Optional[Dict[str, Any]]:
    raw = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw:
        return None
    payload = _decode_jwt(raw)
    if not payload or payload.get("typ") != "client_session":
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    row = pg_get_tenant_user_by_id(user_id)
    if not row:
        return None
    return {
        "tenant_id": row["tenant_id"],
        "email": row["email"],
        "role": row["role"],
        "sub": str(user_id),
    }


def _auth_from_bearer(request: Request) -> Optional[Dict[str, Any]]:
    """Même JWT que le cookie, envoyé en Authorization: Bearer (pour mobile où les cookies tiers sont bloqués)."""
    auth_h = request.headers.get("Authorization")
    if not auth_h or not auth_h.startswith("Bearer "):
        return None
    raw = auth_h[7:].strip()
    if not raw:
        return None
    payload = _decode_jwt(raw)
    if not payload or payload.get("typ") != "client_session":
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    row = pg_get_tenant_user_by_id(user_id)
    if not row:
        return None
    return {
        "tenant_id": row["tenant_id"],
        "email": row["email"],
        "role": row["role"],
        "sub": str(user_id),
    }


def require_tenant_auth(request: Request) -> Dict[str, Any]:
    """
    Authentification par cookie uwi_session ou Bearer (même JWT). Bearer permet mobile quand les cookies tiers sont bloqués.
    """
    if not JWT_SECRET:
        raise HTTPException(503, "JWT_SECRET not configured")
    auth = _auth_from_cookie(request) or _auth_from_bearer(request)
    if auth:
        return auth
    raise HTTPException(401, "Missing or invalid token")


@router.get("/me")
def tenant_me(auth: dict = Depends(require_tenant_auth)):
    """Profil du tenant connecté."""
    tenant_id = auth["tenant_id"]
    d = _get_tenant_detail(tenant_id)
    if not d:
        raise HTTPException(404, "Tenant not found")
    params = d.get("params") or {}
    return {
        "tenant_id": tenant_id,
        "tenant_name": d.get("name", "N/A"),
        "email": auth.get("email"),
        "role": auth.get("role", "owner"),
        "contact_email": params.get("contact_email", ""),
        "timezone": params.get("timezone", "Europe/Paris"),
        "calendar_id": params.get("calendar_id", ""),
        "calendar_provider": params.get("calendar_provider", "none"),
    }


def _safe_dashboard_snapshot(tenant_id: int, tenant_name: str) -> dict:
    """Retourne le snapshot dashboard ou un fallback minimal en cas d'erreur (évite 500)."""
    try:
        return _get_dashboard_snapshot(tenant_id, tenant_name)
    except Exception as e:
        logger.warning("dashboard snapshot failed for tenant_id=%s: %s", tenant_id, e)
        from datetime import datetime, timezone
        return {
            "tenant_id": tenant_id,
            "tenant_name": tenant_name or "N/A",
            "service_status": {"status": "offline", "reason": "error", "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
            "last_call": None,
            "last_booking": None,
            "counters_7d": {"calls_total": 0, "bookings_confirmed": 0, "transfers": 0, "abandons": 0},
            "transfer_reasons": [],
        }


@router.get("/dashboard")
def tenant_dashboard(auth: dict = Depends(require_tenant_auth)):
    """Snapshot dashboard (même payload que admin/tenants/{id}/dashboard)."""
    tenant_id = auth["tenant_id"]
    d = _get_tenant_detail(tenant_id)
    if not d:
        raise HTTPException(404, "Tenant not found")
    return _safe_dashboard_snapshot(tenant_id, d.get("name", "N/A"))


@router.get("/kpis")
def tenant_kpis(auth: dict = Depends(require_tenant_auth), days: int = Query(7, ge=1, le=30)):
    """KPIs par jour + trend vs semaine précédente (graphique 7j)."""
    tenant_id = auth["tenant_id"]
    return _get_kpis_daily(tenant_id, days=days)


@router.get("/rgpd")
def tenant_rgpd(auth: dict = Depends(require_tenant_auth)):
    """RGPD côté client : consent_rate 7j + derniers consent_obtained."""
    from datetime import datetime, timedelta
    tenant_id = auth["tenant_id"]
    now = datetime.utcnow()
    start = (now - timedelta(days=7)).strftime("%Y-%m-%d 00:00:00")
    end = now.strftime("%Y-%m-%d %H:%M:%S")
    return _get_rgpd_extended(tenant_id, start, end)


@router.get("/technical-status")
def tenant_technical_status(auth: dict = Depends(require_tenant_auth)):
    """Statut technique (DID, routing, calendar, service agent)."""
    tenant_id = auth["tenant_id"]
    status = _get_technical_status(tenant_id)
    if not status:
        raise HTTPException(404, "Tenant not found")
    return status


@router.patch("/params")
def tenant_patch_params(
    body: Dict[str, str],
    auth: dict = Depends(require_tenant_auth),
):
    """
    Met à jour params (whitelist: contact_email, calendar_provider, calendar_id, timezone, consent_mode).
    """
    allowed = {"contact_email", "calendar_provider", "calendar_id", "timezone", "consent_mode"}
    params = {k: str(v) for k, v in (body or {}).items() if k in allowed and v is not None}
    if not params:
        return {"ok": True}
    tenant_id = auth["tenant_id"]
    ok = pg_update_tenant_params(tenant_id, params)
    if not ok:
        raise HTTPException(500, "Failed to update params")
    return {"ok": True}


# --- Agenda setup (client) ---


class VerifyGoogleBody(BaseModel):
    calendar_id: str


class ContactRequestBody(BaseModel):
    software: str
    software_other: Optional[str] = None


@router.get("/agenda/config")
def tenant_agenda_config(auth: dict = Depends(require_tenant_auth)):
    """Retourne service_account_email pour les instructions partage Google Calendar."""
    return {"service_account_email": get_service_account_email()}


@router.post("/agenda/verify-google")
def tenant_agenda_verify_google(
    body: VerifyGoogleBody,
    auth: dict = Depends(require_tenant_auth),
):
    """
    Vérifie l'accès au calendrier Google (get_free_slots test).
    Si OK : sauvegarde calendar_provider=google, calendar_id.
    """
    calendar_id = (body.calendar_id or "").strip()
    if not calendar_id:
        return {"ok": False, "reason": "calendar_id_required"}
    tenant_id = auth["tenant_id"]
    try:
        svc = GoogleCalendarService(calendar_id)
        slots = svc.get_free_slots(datetime.now(), duration_minutes=15, limit=1)
        pg_update_tenant_params(tenant_id, {"calendar_provider": "google", "calendar_id": calendar_id})
        logger.info("agenda_verify_google ok tenant_id=%s calendar_id=%s", tenant_id, calendar_id[:50])
        return {"ok": True}
    except GoogleCalendarPermissionError:
        return {"ok": False, "reason": "permission"}
    except Exception as e:
        logger.warning("agenda_verify_google failed tenant_id=%s: %s", tenant_id, e)
        return {"ok": False, "reason": "error"}


@router.post("/agenda/contact-request")
def tenant_agenda_contact_request(
    body: ContactRequestBody,
    auth: dict = Depends(require_tenant_auth),
):
    """Enregistre la demande de connexion agenda (logiciel métier) et envoie email admin."""
    tenant_id = auth["tenant_id"]
    software = (body.software or "").strip() or "autre"
    software_other = (body.software_other or "").strip()
    d = _get_tenant_detail(tenant_id)
    if not d:
        raise HTTPException(404, "Tenant not found")
    tenant_name = d.get("name", "N/A")
    tenant_email = auth.get("email", "") or (d.get("params") or {}).get("contact_email", "")
    ensure_tenant_config()
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO agenda_contact_requests (tenant_id, software, software_other) VALUES (?, ?, ?)",
            (tenant_id, software, software_other),
        )
        conn.commit()
    finally:
        conn.close()
    send_agenda_contact_request_email(tenant_name, tenant_email, software, software_other)
    return {"ok": True}


@router.post("/agenda/activate-none")
def tenant_agenda_activate_none(auth: dict = Depends(require_tenant_auth)):
    """Active le mode sans agenda externe (l'assistant gère les RDV dans son propre système)."""
    tenant_id = auth["tenant_id"]
    pg_update_tenant_params(tenant_id, {"calendar_provider": "none", "calendar_id": ""})
    return {"ok": True}
