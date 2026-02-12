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


def _get_dashboard_snapshot(tenant_id: int, tenant_name: str) -> dict:
    """
    Snapshot dashboard pour un tenant.
    - service_status: online si dernier event < 15 min, sinon offline
    - last_call: dernier call (7j) avec outcome prioritaire
    - last_booking: depuis appointments PG si dispo, sinon ivr_events
    - counters_7d: agrégats ivr_events
    """
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    start_7d = (now - timedelta(days=7)).strftime("%Y-%m-%d 00:00:00")
    end_7d = now.strftime("%Y-%m-%d %H:%M:%S")
    cutoff_15min = (now - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")

    url_events = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    url_slots = os.environ.get("DATABASE_URL") or os.environ.get("PG_SLOTS_URL")

    service_status = {"status": "offline", "reason": "no_recent_events", "checked_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
    last_call = None
    last_booking = None
    counters_7d = {"calls_total": 0, "bookings_confirmed": 0, "transfers": 0, "abandons": 0}

    if url_events:
        try:
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(url_events, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    # Dernier event pour service_status
                    cur.execute(
                        "SELECT MAX(created_at) as m FROM ivr_events WHERE client_id = %s",
                        (tenant_id,),
                    )
                    row = cur.fetchone()
                    last_ts = row["m"] if row and row["m"] else None
                    if last_ts:
                        try:
                            ts = last_ts
                            if hasattr(ts, "tzinfo") and ts.tzinfo:
                                ts = ts.replace(tzinfo=None)
                            elif isinstance(ts, str):
                                ts = datetime.fromisoformat(ts.replace("Z", "+00:00")[:26])
                                if hasattr(ts, "tzinfo") and ts.tzinfo:
                                    ts = ts.replace(tzinfo=None)
                            delta = now - ts
                        except Exception:
                            delta = timedelta(minutes=999)
                        if delta.total_seconds() < 900:  # 15 min
                            service_status = {"status": "online", "reason": None, "checked_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}

                    # Counters 7d
                    cur.execute(
                        "SELECT event, COUNT(*) as cnt FROM ivr_events WHERE client_id = %s AND created_at >= %s AND created_at <= %s GROUP BY event",
                        (tenant_id, start_7d, end_7d),
                    )
                    by_event = {r["event"]: r["cnt"] for r in cur.fetchall()}
                    cur.execute(
                        "SELECT COUNT(DISTINCT call_id) as n FROM ivr_events WHERE client_id = %s AND created_at >= %s AND created_at <= %s AND call_id != ''",
                        (tenant_id, start_7d, end_7d),
                    )
                    r = cur.fetchone()
                    calls_total = int(r["n"]) if r and r["n"] else 0
                    if not calls_total and by_event:
                        calls_total = sum(by_event.values())  # fallback
                    counters_7d = {
                        "calls_total": calls_total,
                        "bookings_confirmed": by_event.get("booking_confirmed", 0),
                        "transfers": by_event.get("transferred_human", 0) + by_event.get("transferred", 0),
                        "abandons": by_event.get("user_abandon", 0),
                    }

                    # last_call: dernier call_id (7j), outcome par priorité
                    cur.execute(
                        "SELECT call_id, created_at FROM ivr_events WHERE client_id = %s AND created_at >= %s AND call_id != '' ORDER BY created_at DESC LIMIT 1",
                        (tenant_id, start_7d),
                    )
                    row = cur.fetchone()
                    if row:
                        cid = row["call_id"]
                        cur.execute(
                            "SELECT event, created_at FROM ivr_events WHERE client_id = %s AND call_id = %s",
                            (tenant_id, cid),
                        )
                        evts = cur.fetchall()
                        outcome = None
                        for e in evts:
                            if e["event"] == "booking_confirmed":
                                outcome = "booking_confirmed"
                                break
                            if e["event"] in ("transferred_human", "transferred"):
                                outcome = outcome or "transferred_human"
                            if e["event"] == "user_abandon":
                                outcome = outcome or "user_abandon"
                        outcome = outcome or "unknown"
                        last_ts = max((e["created_at"] for e in evts), default=row["created_at"])
                        last_call = {
                            "call_id": cid,
                            "created_at": str(last_ts),
                            "name": None,
                            "motif": None,
                            "slot_label": None,
                            "outcome": outcome,
                        }
        except Exception as e:
            logger.warning("dashboard ivr_events failed: %s", e)
    else:
        # Fallback SQLite ivr_events
        import backend.db as db
        conn = db.get_conn()
        try:
            cur = conn.execute("SELECT MAX(created_at) FROM ivr_events WHERE client_id = ?", (tenant_id,))
            row = cur.fetchone()
            if row and row[0]:
                from datetime import datetime as dt
                try:
                    last_ts = dt.fromisoformat(str(row[0]).replace("Z", "")[:19])
                    delta = now - last_ts
                    if delta.total_seconds() < 900:
                        service_status = {"status": "online", "reason": None, "checked_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
                except Exception:
                    pass
            cur = conn.execute(
                "SELECT event, COUNT(*) FROM ivr_events WHERE client_id = ? AND created_at >= ? AND created_at <= ? GROUP BY event",
                (tenant_id, start_7d, end_7d),
            )
            by_event = {r[0]: r[1] for r in cur.fetchall()}
            cur = conn.execute(
                "SELECT COUNT(DISTINCT call_id) FROM ivr_events WHERE client_id = ? AND created_at >= ? AND created_at <= ? AND call_id != ''",
                (tenant_id, start_7d, end_7d),
            )
            r = cur.fetchone()
            calls_total = r[0] if r and r[0] else sum(by_event.values())
            counters_7d = {
                "calls_total": calls_total,
                "bookings_confirmed": by_event.get("booking_confirmed", 0),
                "transfers": by_event.get("transferred_human", 0) + by_event.get("transferred", 0),
                "abandons": by_event.get("user_abandon", 0),
            }
            cur = conn.execute(
                "SELECT call_id, created_at FROM ivr_events WHERE client_id = ? AND created_at >= ? AND call_id != '' ORDER BY created_at DESC LIMIT 1",
                (tenant_id, start_7d),
            )
            row = cur.fetchone()
            if row:
                cur2 = conn.execute("SELECT event FROM ivr_events WHERE client_id = ? AND call_id = ?", (tenant_id, row[0]))
                evts = [r[0] for r in cur2.fetchall()]
                outcome = "booking_confirmed" if "booking_confirmed" in evts else ("transferred_human" if any(e in ("transferred_human", "transferred") for e in evts) else ("user_abandon" if "user_abandon" in evts else "unknown"))
                last_call = {"call_id": row[0], "created_at": str(row[1]), "name": None, "motif": None, "slot_label": None, "outcome": outcome}
        except Exception as e:
            logger.warning("dashboard sqlite failed: %s", e)
        finally:
            conn.close()

    # last_booking: appointments PG préféré (PG a tenant_id)
    if url_slots and config.USE_PG_SLOTS:
        try:
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(url_slots, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT a.name, a.created_at, s.start_ts
                        FROM appointments a
                        JOIN slots s ON a.slot_id = s.id
                        WHERE a.tenant_id = %s
                        ORDER BY a.created_at DESC
                        LIMIT 1
                        """,
                        (tenant_id,),
                    )
                    row = cur.fetchone()
                    if row:
                        start_ts = row["start_ts"]
                        slot_label = str(start_ts)[:16].replace("T", " ") if start_ts else None
                        last_booking = {
                            "created_at": str(row["created_at"]),
                            "name": row["name"],
                            "slot_label": slot_label,
                            "source": "postgres",
                        }
        except Exception as e:
            logger.debug("dashboard appointments failed: %s", e)

    if not last_booking and last_call and last_call.get("outcome") == "booking_confirmed":
        last_booking = {
            "created_at": last_call["created_at"],
            "name": last_call.get("name"),
            "slot_label": last_call.get("slot_label"),
            "source": "ivr_events",
        }

    return {
        "tenant_id": tenant_id,
        "tenant_name": tenant_name,
        "service_status": service_status,
        "last_call": last_call,
        "last_booking": last_booking,
        "counters_7d": counters_7d,
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


@router.get("/admin/tenants/{tenant_id}/dashboard")
def admin_get_dashboard(
    tenant_id: int,
    _: None = Depends(_verify_admin),
):
    """Snapshot dashboard: service_status, last_call, last_booking, counters_7d."""
    d = _get_tenant_detail(tenant_id)
    if not d:
        raise HTTPException(404, "Tenant not found")
    return _get_dashboard_snapshot(tenant_id, d.get("name", "N/A"))


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
