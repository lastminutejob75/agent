# backend/routes/tenant.py
"""
API tenant (client): dashboard, technical-status, me, params.
Protégé par cookie uwi_session uniquement (require_tenant_auth).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.auth_pg import pg_get_tenant_user_by_id
from backend.routes.admin import (
    _get_dashboard_snapshot,
    _get_kpis_daily,
    _get_rgpd_extended,
    _get_technical_status,
    _get_tenant_detail,
)
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


def require_tenant_auth(request: Request) -> Dict[str, Any]:
    """
    Authentification par cookie uwi_session uniquement (typ=client_session).
    """
    if not JWT_SECRET:
        raise HTTPException(503, "JWT_SECRET not configured")
    auth = _auth_from_cookie(request)
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


@router.get("/dashboard")
def tenant_dashboard(auth: dict = Depends(require_tenant_auth)):
    """Snapshot dashboard (même payload que admin/tenants/{id}/dashboard)."""
    tenant_id = auth["tenant_id"]
    d = _get_tenant_detail(tenant_id)
    if not d:
        raise HTTPException(404, "Tenant not found")
    return _get_dashboard_snapshot(tenant_id, d.get("name", "N/A"))


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
