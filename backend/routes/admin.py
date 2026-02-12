# backend/routes/admin.py
"""
API admin / onboarding pour uwi-landing (Vite SPA).
- POST /public/onboarding (public)
- GET/PATCH /admin/* (protégé Bearer ADMIN_API_TOKEN)
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from backend import config
from backend.tenants_pg import (
    pg_add_routing,
    pg_create_tenant,
    pg_fetch_tenants,
    pg_get_tenant_full,
    pg_get_tenant_flags,
    pg_get_tenant_params,
    pg_get_routing_for_tenant,
    pg_update_tenant_flags,
    pg_update_tenant_params,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["admin"])
_security = HTTPBearer(auto_error=False)

ADMIN_TOKEN = os.environ.get("ADMIN_API_TOKEN", "")


def _verify_admin(credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security)) -> None:
    if not ADMIN_TOKEN:
        raise HTTPException(503, "Admin API not configured (ADMIN_API_TOKEN missing)")
    if not credentials or credentials.credentials != ADMIN_TOKEN:
        raise HTTPException(401, "Invalid or missing admin token")


# --- Schemas ---


class OnboardingRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=200)
    email: str = Field(..., max_length=255)
    calendar_provider: str = Field(default="none", pattern="^(google|none)$")
    calendar_id: str = Field(default="", max_length=500)
    sector: Optional[str] = Field(default=None, max_length=100)


class OnboardingResponse(BaseModel):
    tenant_id: int
    message: str
    admin_setup_token: Optional[str] = None  # P0: same as ADMIN_API_TOKEN for internal use


class RoutingCreate(BaseModel):
    channel: str = Field(default="vocal", pattern="^(vocal|whatsapp)$")
    key: str = Field(..., min_length=1)  # DID E.164 ou widget_key
    tenant_id: int


class FlagsUpdate(BaseModel):
    flags: Dict[str, bool] = Field(default_factory=dict)


class ParamsUpdate(BaseModel):
    params: Dict[str, str] = Field(default_factory=dict)


# --- Helpers ---


def _get_tenant_list(include_inactive: bool = False) -> List[dict]:
    """Liste tenants (PG-first, fallback SQLite)."""
    if config.USE_PG_TENANTS:
        result = pg_fetch_tenants(include_inactive=include_inactive)
        if result:
            return result[0]
    # Fallback SQLite
    import backend.db as db
    db.ensure_tenant_config()
    conn = db.get_conn()
    try:
        if include_inactive:
            rows = conn.execute("SELECT tenant_id, name, status FROM tenants ORDER BY tenant_id").fetchall()
        else:
            rows = conn.execute(
                "SELECT tenant_id, name, status FROM tenants WHERE COALESCE(status,'active')='active' ORDER BY tenant_id"
            ).fetchall()
        return [{"tenant_id": r[0], "name": r[1], "status": r[2]} for r in rows]
    finally:
        conn.close()


def _get_tenant_detail(tenant_id: int) -> Optional[dict]:
    """Détail tenant (PG-first)."""
    if config.USE_PG_TENANTS:
        d = pg_get_tenant_full(tenant_id)
        if d:
            return d
    # Fallback SQLite
    import backend.db as db
    db.ensure_tenant_config()
    conn = db.get_conn()
    try:
        r = conn.execute("SELECT tenant_id, name, timezone, status, created_at FROM tenants WHERE tenant_id = ?", (tenant_id,)).fetchone()
        if not r:
            return None
        cfg = conn.execute("SELECT flags_json, params_json FROM tenant_config WHERE tenant_id = ?", (tenant_id,)).fetchone()
        flags = json.loads(cfg[0]) if cfg and cfg[0] else {}
        params = json.loads(cfg[1]) if cfg and cfg[1] else {}
        routes = conn.execute("SELECT channel, did_key FROM tenant_routing WHERE tenant_id = ?", (tenant_id,)).fetchall()
        routing = [{"channel": r[0], "key": r[1], "is_active": True} for r in routes]  # key = did_key
        return {
            "tenant_id": r[0],
            "name": r[1],
            "timezone": r[2],
            "status": r[3],
            "created_at": r[4],
            "flags": flags,
            "params": params,
            "routing": routing,
        }
    finally:
        conn.close()


def _get_kpis_weekly(tenant_id: int, start: str, end: str) -> dict:
    """Aggrège ivr_events pour la période (PG ou SQLite)."""
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    if url:
        try:
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(url, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT event, COUNT(*) as cnt
                        FROM ivr_events
                        WHERE client_id = %s AND created_at >= %s AND created_at < %s
                        GROUP BY event
                        """,
                        (tenant_id, start, end),
                    )
                    rows = cur.fetchall()
                    by_event = {r["event"]: r["cnt"] for r in rows}
        except Exception as e:
            logger.warning("pg kpis failed: %s", e)
            by_event = {}
    else:
        import backend.db as db
        conn = db.get_conn()
        try:
            rows = conn.execute(
                """
                SELECT event, COUNT(*) as cnt FROM ivr_events
                WHERE client_id = ? AND created_at >= ? AND created_at < ?
                GROUP BY event
                """,
                (tenant_id, start, end),
            ).fetchall()
            by_event = {r[0]: r[1] for r in rows}
        finally:
            conn.close()
    calls = by_event.get("call_started", 0) or by_event.get("call_start", 0)
    if not calls:
        calls = sum(by_event.values())  # fallback
    return {
        "tenant_id": tenant_id,
        "start": start,
        "end": end,
        "calls_total": calls,
        "booking_confirmed": by_event.get("booking_confirmed", 0),
        "transferred_human": by_event.get("transferred_human", 0) + by_event.get("transferred", 0),
        "user_abandon": by_event.get("user_abandon", 0),
        "contact_captured_phone": by_event.get("contact_captured_phone", 0),
        "contact_captured_email": by_event.get("contact_captured_email", 0),
        "contact_confirmed": by_event.get("contact_confirmed", 0),
        "contact_failed_transfer": by_event.get("contact_failed_transfer", 0),
    }


def _get_rgpd(tenant_id: int, start: str, end: str) -> dict:
    """RGPD: consent_obtained, consent_rate."""
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    if url:
        try:
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(url, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT event, COUNT(*) as cnt
                        FROM ivr_events
                        WHERE client_id = %s AND created_at >= %s AND created_at < %s
                        AND event IN ('consent_obtained', 'call_started', 'call_start')
                        GROUP BY event
                        """,
                        (tenant_id, start, end),
                    )
                    rows = cur.fetchall()
                    by_event = {r["event"]: r["cnt"] for r in rows}
        except Exception as e:
            logger.warning("pg rgpd failed: %s", e)
            by_event = {}
    else:
        import backend.db as db
        conn = db.get_conn()
        try:
            rows = conn.execute(
                """
                SELECT event, COUNT(*) FROM ivr_events
                WHERE client_id = ? AND created_at >= ? AND created_at < ?
                AND event IN ('consent_obtained', 'call_started', 'call_start')
                GROUP BY event
                """,
                (tenant_id, start, end),
            ).fetchall()
            by_event = {r[0]: r[1] for r in rows}
        finally:
            conn.close()
    consent = by_event.get("consent_obtained", 0)
    calls = by_event.get("call_started", 0) or by_event.get("call_start", 0) or 1
    return {
        "tenant_id": tenant_id,
        "start": start,
        "end": end,
        "consent_obtained": consent,
        "calls_total": calls,
        "consent_rate": round(consent / calls, 2) if calls else 0,
    }


# --- Routes ---


@router.post("/public/onboarding", response_model=OnboardingResponse)
def public_onboarding(body: OnboardingRequest):
    """Crée un tenant + config. Public (pas de auth)."""
    if config.USE_PG_TENANTS:
        tid = pg_create_tenant(
            name=body.company_name,
            contact_email=body.email,
            calendar_provider=body.calendar_provider,
            calendar_id=body.calendar_id,
            timezone="Europe/Paris",
        )
        if tid:
            return OnboardingResponse(
                tenant_id=tid,
                message="Onboarding créé. Vous pouvez configurer le tenant depuis l'admin.",
                admin_setup_token=ADMIN_TOKEN if ADMIN_TOKEN else None,
            )
    # Fallback SQLite
    import backend.db as db
    db.ensure_tenant_config()
    conn = db.get_conn()
    try:
        conn.execute(
            "INSERT INTO tenants (name, status) VALUES (?, 'active')",
            (body.company_name or "Nouveau",),
        )
        row = conn.execute("SELECT last_insert_rowid()").fetchone()
        tid = row[0] if row else None
        if not tid:
            conn.rollback()
            raise HTTPException(500, "Failed to create tenant")
        params = json.dumps({
            "calendar_provider": body.calendar_provider,
            "calendar_id": body.calendar_id,
            "contact_email": body.email,
        })
        conn.execute(
            "INSERT INTO tenant_config (tenant_id, flags_json, params_json) VALUES (?, '{}', ?)",
            (tid, params),
        )
        conn.commit()
        return OnboardingResponse(
            tenant_id=tid,
            message="Onboarding créé.",
            admin_setup_token=ADMIN_TOKEN if ADMIN_TOKEN else None,
        )
    except Exception as e:
        conn.rollback()
        logger.exception("onboarding failed")
        raise HTTPException(500, str(e))
    finally:
        conn.close()


@router.get("/admin/tenants")
def admin_list_tenants(
    include_inactive: bool = Query(False),
    _: None = Depends(_verify_admin),
):
    """Liste tous les tenants."""
    items = _get_tenant_list(include_inactive=include_inactive)
    return {"tenants": items}


@router.get("/admin/tenants/{tenant_id}")
def admin_get_tenant(
    tenant_id: int,
    _: None = Depends(_verify_admin),
):
    """Détail tenant (config + routing)."""
    d = _get_tenant_detail(tenant_id)
    if not d:
        raise HTTPException(404, "Tenant not found")
    return d


@router.patch("/admin/tenants/{tenant_id}/flags")
def admin_patch_flags(
    tenant_id: int,
    body: FlagsUpdate,
    _: None = Depends(_verify_admin),
):
    """Met à jour les flags (merge)."""
    if config.USE_PG_TENANTS:
        ok = pg_update_tenant_flags(tenant_id, body.flags)
        if ok:
            return {"ok": True}
    from backend.tenant_config import set_flags
    set_flags(tenant_id, body.flags)
    return {"ok": True}


@router.patch("/admin/tenants/{tenant_id}/params")
def admin_patch_params(
    tenant_id: int,
    body: ParamsUpdate,
    _: None = Depends(_verify_admin),
):
    """Met à jour les params (merge)."""
    if config.USE_PG_TENANTS:
        ok = pg_update_tenant_params(tenant_id, body.params)
        if ok:
            return {"ok": True}
    from backend.tenant_config import set_params
    set_params(tenant_id, body.params)
    return {"ok": True}


@router.post("/admin/routing")
def admin_add_routing(
    body: RoutingCreate,
    _: None = Depends(_verify_admin),
):
    """Ajoute une route DID → tenant."""
    if config.USE_PG_TENANTS:
        ok = pg_add_routing(body.channel, body.key, body.tenant_id)
        if ok:
            return {"ok": True}
    from backend.tenant_routing import add_route
    add_route(body.channel, body.key, body.tenant_id)
    return {"ok": True}


@router.get("/admin/kpis/weekly")
def admin_kpis_weekly(
    tenant_id: int = Query(..., description="tenant_id"),
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
    _: None = Depends(_verify_admin),
):
    """KPIs hebdo pour un tenant."""
    if len(start) == 10:
        start = start + " 00:00:00"
    if len(end) == 10:
        end = end + " 23:59:59"
    return _get_kpis_weekly(tenant_id, start, end)


@router.get("/admin/rgpd")
def admin_rgpd(
    tenant_id: int = Query(..., description="tenant_id"),
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
    _: None = Depends(_verify_admin),
):
    """RGPD: consent_rate + consent_obtained."""
    if len(start) == 10:
        start = start + " 00:00:00"
    if len(end) == 10:
        end = end + " 23:59:59"
    return _get_rgpd(tenant_id, start, end)
