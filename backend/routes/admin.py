# backend/routes/admin.py
"""
API admin / onboarding pour uwi-landing (Vite SPA).
- POST /public/onboarding (public)
- POST /api/admin/auth/login, GET /api/admin/auth/me, POST /api/admin/auth/logout (cookie session)
- GET/PATCH /admin/* (protégé cookie session OU Bearer ADMIN_API_TOKEN)
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import jwt
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from backend import config
from backend.deps import validate_tenant_id
from backend.auth_pg import pg_add_tenant_user, pg_create_tenant_user, pg_get_tenant_user_by_email
from backend.billing_pg import (
    get_tenant_billing,
    set_force_active,
    set_stripe_customer_id,
    set_tenant_suspended,
    set_tenant_unsuspended,
    tenant_id_by_stripe_customer_id,
)
from backend.tenants_pg import (
    pg_add_routing,
    pg_create_tenant,
    pg_deactivate_tenant,
    pg_fetch_tenants,
    pg_get_tenant_full,
    pg_get_tenant_flags,
    pg_get_tenant_params,
    pg_get_routing_for_tenant,
    pg_update_tenant_flags,
    pg_update_tenant_params,
)

logger = logging.getLogger(__name__)

# Convention produit : ivr_events.client_id = tenant_id (même entité). RLS/audit futur possible
# si migration ivr_events.client_id → tenant_id (ou vue SQL). Toutes les requêtes stats filtrent
# ivr_events par client_id = tenant_id (input).
def _ivr_client_id(tenant_id: int) -> int:
    """Résolution tenant → clé ivr_events. Actuellement client_id = tenant_id."""
    return tenant_id

# Minutes : plafond 6h par session pour éviter les outliers (sessions ouvertes / bug updated_at).
MAX_SESSION_MINUTES = 6 * 60  # 360


def _get_vapi_usage_for_window(
    url: Optional[str], start: str, end: str, tenant_id: Optional[int] = None
) -> tuple:
    """
    Agrège vapi_call_usage sur la fenêtre (ended_at). Retourne (minutes_total, cost_usd) ou (None, None) si table absente/erreur.
    Vapi = source de vérité conso ; utilisé en priorité dans les stats admin.
    """
    if not url:
        return (None, None)
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                if tenant_id is not None:
                    cur.execute(
                        """
                        SELECT COALESCE(SUM(duration_sec), 0) / 60.0 AS mins, COALESCE(SUM(cost_usd), 0) AS cost
                        FROM vapi_call_usage
                        WHERE tenant_id = %s AND ended_at IS NOT NULL AND ended_at >= %s AND ended_at <= %s
                        """,
                        (tenant_id, start, end),
                    )
                else:
                    cur.execute(
                        """
                        SELECT COALESCE(SUM(duration_sec), 0) / 60.0 AS mins, COALESCE(SUM(cost_usd), 0) AS cost
                        FROM vapi_call_usage
                        WHERE ended_at IS NOT NULL AND ended_at >= %s AND ended_at <= %s
                        """,
                        (start, end),
                    )
                row = cur.fetchone()
                if row and (row[0] or row[1]):
                    return (float(row[0] or 0), float(row[1] or 0))
                return (None, None)
    except Exception as e:
        if "does not exist" not in str(e).lower() and "vapi_call_usage" not in str(e).lower():
            logger.debug("vapi_usage agg: %s", e)
        return (None, None)


router = APIRouter(prefix="/api", tags=["admin"])
_security = HTTPBearer(auto_error=False)

ADMIN_TOKEN = (os.environ.get("ADMIN_API_TOKEN") or "").strip()
# Rotation : plusieurs tokens valides (ADMIN_API_TOKENS=tok1,tok2)
_ADMIN_TOKENS_EXTRA = [t.strip() for t in (os.environ.get("ADMIN_API_TOKENS") or "").split(",") if t.strip()]
_ADMIN_VALID_TOKENS = frozenset([ADMIN_TOKEN] + _ADMIN_TOKENS_EXTRA) if ADMIN_TOKEN else frozenset(_ADMIN_TOKENS_EXTRA)

# Auth admin par email + mot de passe → cookie session (HttpOnly)
ADMIN_EMAIL = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()
ADMIN_PASSWORD = (os.environ.get("ADMIN_PASSWORD") or "").strip()  # Déprécié : préférer ADMIN_PASSWORD_HASH
ADMIN_PASSWORD_HASH = (os.environ.get("ADMIN_PASSWORD_HASH") or "").strip()  # bcrypt hash (recommandé en prod)
ADMIN_SESSION_COOKIE = "uwi_admin_session"
JWT_SECRET_ADMIN = (os.environ.get("JWT_SECRET") or os.environ.get("ADMIN_SESSION_SECRET") or "").strip()
ADMIN_SESSION_EXPIRES_HOURS = int(os.environ.get("ADMIN_SESSION_EXPIRES_HOURS") or "8")
# Cross-domain (front uwiapp.com / API Railway) : SameSite=None; Secure. Même domaine (api.uwiapp.com) : Lax.
ADMIN_COOKIE_SAMESITE = (os.environ.get("ADMIN_COOKIE_SAMESITE") or "").strip().lower() or None


def _get_admin_email_from_cookie(request: Request) -> Optional[str]:
    """Lit et valide le JWT admin depuis le cookie. Retourne l'email si valide, sinon None."""
    if not JWT_SECRET_ADMIN:
        return None
    raw = request.cookies.get(ADMIN_SESSION_COOKIE)
    if not raw:
        return None
    try:
        payload = jwt.decode(raw, JWT_SECRET_ADMIN, algorithms=["HS256"])
        if payload.get("scope") != "admin":
            return None
        email = (payload.get("sub") or payload.get("email") or "").strip().lower()
        if email and email == ADMIN_EMAIL:
            return email
    except jwt.ExpiredSignatureError:
        pass
    except jwt.InvalidTokenError:
        pass
    return None


def require_admin(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> None:
    """
    Accès admin : 1) cookie uwi_admin_session (JWT scope=admin), 2) Bearer ADMIN_API_TOKEN (legacy).
    - 503 : aucune méthode configurée (ADMIN_EMAIL+ADMIN_PASSWORD ou ADMIN_API_TOKEN)
    - 401 : pas authentifié (cookie invalide/expiré ou Bearer manquant/invalide).
    """
    # 1) Cookie session
    if JWT_SECRET_ADMIN and ADMIN_EMAIL:
        email = _get_admin_email_from_cookie(request)
        if email:
            logger.info("admin_access path=%s client=%s auth=cookie", request.url.path, request.client.host if request.client else None)
            return
    # 2) Bearer legacy
    if not _ADMIN_VALID_TOKENS and not (ADMIN_EMAIL and (ADMIN_PASSWORD or ADMIN_PASSWORD_HASH)):
        raise HTTPException(503, "Admin API not configured (ADMIN_EMAIL + ADMIN_PASSWORD_HASH or ADMIN_API_TOKEN)")
    if not credentials or not (credentials.credentials or "").strip():
        raise HTTPException(401, "Missing credentials (cookie or Bearer required)")
    token = credentials.credentials.strip()
    if token not in _ADMIN_VALID_TOKENS:
        raise HTTPException(401, "Invalid or expired token")
    token_fingerprint = hashlib.sha256(token.encode()).hexdigest()[:8]
    logger.info(
        "admin_access path=%s client=%s user_agent=%s token_fp=%s",
        request.url.path,
        request.client.host if request.client else None,
        (request.headers.get("user-agent") or "")[:200],
        token_fingerprint,
    )


# Alias pour compatibilité existante
_verify_admin = require_admin


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


class AdminLoginBody(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=1)


class RoutingCreate(BaseModel):
    channel: str = Field(default="vocal", pattern="^(vocal|whatsapp|web)$")
    key: str = Field(..., min_length=1)  # DID E.164, numéro WhatsApp ou clé API web (X-Tenant-Key)
    tenant_id: int


class FlagsUpdate(BaseModel):
    flags: Dict[str, bool] = Field(default_factory=dict)


class ParamsUpdate(BaseModel):
    params: Dict[str, str] = Field(default_factory=dict)


class AdminTenantUserCreate(BaseModel):
    email: str = Field(..., max_length=255)
    role: str = Field(default="owner", pattern="^(owner|member)$")


class TenantCreateIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    contact_email: str = Field(..., max_length=255)
    timezone: str = Field(default="Europe/Paris", max_length=64)
    business_type: Optional[str] = Field(default=None, max_length=64)
    notes: Optional[str] = Field(default=None, max_length=2000)


class TenantOut(BaseModel):
    tenant_id: int
    name: str
    contact_email: str
    timezone: str
    business_type: Optional[str] = None
    created_at: str


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

    transfer_reasons = _get_transfer_reasons(tenant_id, days=7)

    return {
        "tenant_id": tenant_id,
        "tenant_name": tenant_name,
        "service_status": service_status,
        "last_call": last_call,
        "last_booking": last_booking,
        "counters_7d": counters_7d,
        "transfer_reasons": transfer_reasons,
    }


def _format_ago(ts) -> str:
    """Retourne 'il y a X min' ou 'jamais'."""
    if not ts:
        return "jamais"
    try:
        if hasattr(ts, "tzinfo") and ts.tzinfo:
            ts = ts.replace(tzinfo=None)
        elif isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00")[:26])
            if hasattr(ts, "tzinfo") and ts.tzinfo:
                ts = ts.replace(tzinfo=None)
        delta = datetime.utcnow() - ts
        s = int(delta.total_seconds())
        if s < 60:
            return "à l'instant"
        if s < 3600:
            return f"il y a {s // 60} min"
        if s < 86400:
            return f"il y a {s // 3600} h"
        return f"il y a {s // 86400} j"
    except Exception:
        return "—"


def _get_technical_status(tenant_id: int) -> Optional[dict]:
    """
    Statut technique pour affichage admin.
    - did: numéro vocal (routing channel=vocal)
    - routing_status: active | incomplete | not_configured
    - calendar_provider, calendar_id, calendar_status
    - service_agent: online | offline
    - last_event_at, last_event_ago
    """
    d = _get_tenant_detail(tenant_id)
    if not d:
        return None

    params = d.get("params") or {}
    routing = d.get("routing") or []
    vocal_routes = [r for r in routing if r.get("channel") == "vocal" and r.get("is_active", True)]
    did = vocal_routes[0]["key"] if vocal_routes else None

    # Routing status
    if vocal_routes:
        routing_status = "active"
    else:
        routing_status = "not_configured"

    # Calendar
    provider = (params.get("calendar_provider") or "none").lower()
    cal_id = (params.get("calendar_id") or "").strip()
    if provider == "google" and cal_id:
        calendar_status = "connected"
    elif provider == "google" and not cal_id:
        calendar_status = "incomplete"
    else:
        calendar_status = "not_configured"

    # Service agent + last event (réutilise logique dashboard)
    now = datetime.utcnow()
    service_agent = "offline"
    last_event_at = None
    last_event_ago = "jamais"

    url_events = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    if url_events:
        try:
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(url_events, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT MAX(created_at) as m FROM ivr_events WHERE client_id = %s",
                        (tenant_id,),
                    )
                    row = cur.fetchone()
                    last_ts = row["m"] if row and row["m"] else None
                    if last_ts:
                        last_event_at = str(last_ts)
                        last_event_ago = _format_ago(last_ts)
                        try:
                            ts = last_ts
                            if hasattr(ts, "tzinfo") and ts.tzinfo:
                                ts = ts.replace(tzinfo=None)
                            elif isinstance(ts, str):
                                ts = datetime.fromisoformat(ts.replace("Z", "+00:00")[:26])
                                if hasattr(ts, "tzinfo") and ts.tzinfo:
                                    ts = ts.replace(tzinfo=None)
                            delta = now - ts
                            if delta.total_seconds() < 900:
                                service_agent = "online"
                        except Exception:
                            pass
        except Exception as e:
            logger.warning("technical_status ivr_events failed: %s", e)
    else:
        import backend.db as db
        conn = db.get_conn()
        try:
            cur = conn.execute("SELECT MAX(created_at) FROM ivr_events WHERE client_id = ?", (tenant_id,))
            row = cur.fetchone()
            if row and row[0]:
                from datetime import datetime as dt
                last_ts = row[0]
                last_event_at = str(last_ts)
                last_event_ago = _format_ago(last_ts)
                try:
                    last_ts_parsed = dt.fromisoformat(str(last_ts).replace("Z", "")[:19])
                    if (now - last_ts_parsed).total_seconds() < 900:
                        service_agent = "online"
                except Exception:
                    pass
        except Exception as e:
            logger.warning("technical_status sqlite failed: %s", e)
        finally:
            conn.close()

    # KPI call_lock_timeout_rate (Phase 2.1) — si > 0.5% → Vapi doublons ou latence DB
    call_lock_timeout_rate = None
    if url_events:
        try:
            from datetime import timedelta
            start_7d = (now - timedelta(days=7)).strftime("%Y-%m-%d 00:00:00")
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(url_events, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT
                            COUNT(DISTINCT CASE WHEN call_id != '' THEN call_id END) as calls,
                            COUNT(*) FILTER (WHERE event = 'call_lock_timeout') as lock_timeouts
                        FROM ivr_events
                        WHERE client_id = %s AND created_at >= %s
                        """,
                        (tenant_id, start_7d),
                    )
                    row = cur.fetchone()
                    if row and row.get("calls", 0) > 0:
                        rate = (row.get("lock_timeouts") or 0) / row["calls"]
                        call_lock_timeout_rate = round(rate * 100, 2)
        except Exception as e:
            logger.debug("call_lock_timeout_rate failed: %s", e)

    return {
        "tenant_id": tenant_id,
        "did": did,
        "routing_status": routing_status,
        "calendar_provider": provider or "none",
        "calendar_id": cal_id or None,
        "calendar_status": calendar_status,
        "service_agent": service_agent,
        "last_event_at": last_event_at,
        "last_event_ago": last_event_ago,
        "call_lock_timeout_rate_pct": call_lock_timeout_rate,
        "call_lock_timeout_alert": call_lock_timeout_rate is not None and call_lock_timeout_rate > 0.5,
    }


def _get_kpis_daily(tenant_id: int, days: int = 7) -> dict:
    """
    KPIs par jour + trend vs semaine précédente.
    Returns: {days: [{date, calls, bookings, transfers}], current: {}, previous: {}, trend: {calls_pct, bookings_pct, transfers_pct}}
    """
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    end_curr = now.strftime("%Y-%m-%d %H:%M:%S")
    start_curr = (now - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")
    start_prev = (now - timedelta(days=days * 2)).strftime("%Y-%m-%d 00:00:00")

    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    days_data = []
    current = {"calls": 0, "bookings": 0, "transfers": 0}
    previous = {"calls": 0, "bookings": 0, "transfers": 0}

    if url:
        try:
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(url, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT DATE(created_at AT TIME ZONE 'UTC') as d,
                               COUNT(DISTINCT CASE WHEN call_id != '' THEN call_id END) as calls,
                               COUNT(*) FILTER (WHERE event = 'booking_confirmed') as bookings,
                               COUNT(*) FILTER (WHERE event IN ('transferred_human', 'transferred')) as transfers
                        FROM ivr_events
                        WHERE client_id = %s AND created_at >= %s AND created_at < %s
                        GROUP BY DATE(created_at AT TIME ZONE 'UTC')
                        ORDER BY d
                        """,
                        (tenant_id, start_prev, end_curr),
                    )
                    for r in cur.fetchall():
                        d = str(r["d"]) if r.get("d") else ""
                        c = int(r["calls"] or 0)
                        b = int(r["bookings"] or 0)
                        t = int(r["transfers"] or 0)
                        if d >= start_curr[:10]:
                            days_data.append({"date": d, "calls": c, "bookings": b, "transfers": t})
                            current["calls"] += c
                            current["bookings"] += b
                            current["transfers"] += t
                        else:
                            previous["calls"] += c
                            previous["bookings"] += b
                            previous["transfers"] += t
        except Exception as e:
            logger.warning("pg kpis_daily failed: %s", e)
    else:
        import backend.db as db
        conn = db.get_conn()
        try:
            db._ensure_ivr_tables(conn)
            rows = conn.execute(
                """
                SELECT date(created_at) as d,
                       (SELECT COUNT(DISTINCT call_id) FROM ivr_events e2
                        WHERE e2.client_id = ? AND date(e2.created_at) = date(ivr_events.created_at)
                        AND e2.call_id != '' AND e2.call_id IS NOT NULL) as calls,
                       SUM(CASE WHEN event = 'booking_confirmed' THEN 1 ELSE 0 END) as bookings,
                       SUM(CASE WHEN event IN ('transferred_human', 'transferred') THEN 1 ELSE 0 END) as transfers
                FROM ivr_events
                WHERE client_id = ? AND created_at >= ? AND created_at < ?
                GROUP BY date(created_at)
                ORDER BY d
                """,
                (tenant_id, tenant_id, start_prev, end_curr),
            ).fetchall()
            for r in rows:
                d = str(r[0]) if r[0] else ""
                c = int(r[1] or 0)
                b = int(r[2] or 0)
                t = int(r[3] or 0)
                if d >= start_curr[:10]:
                    days_data.append({"date": d, "calls": c, "bookings": b, "transfers": t})
                    current["calls"] += c
                    current["bookings"] += b
                    current["transfers"] += t
                else:
                    previous["calls"] += c
                    previous["bookings"] += b
                    previous["transfers"] += t
        except Exception as e:
            logger.warning("sqlite kpis_daily failed: %s", e)
        finally:
            conn.close()

    # Remplir les jours manquants avec 0
    for i in range(days):
        d = (now - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        if not any(x["date"] == d for x in days_data):
            days_data.append({"date": d, "calls": 0, "bookings": 0, "transfers": 0})
    days_data.sort(key=lambda x: x["date"])

    def _pct(curr, prev):
        if prev == 0:
            return curr and 100 or 0
        return round((curr - prev) / prev * 100)

    trend = {
        "calls_pct": _pct(current["calls"], previous["calls"]),
        "bookings_pct": _pct(current["bookings"], previous["bookings"]),
        "transfers_pct": _pct(current["transfers"], previous["transfers"]),
    }
    return {"days": days_data, "current": current, "previous": previous, "trend": trend}


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


def _extract_consent_version_short(context: str) -> str:
    """Extrait 'v1' depuis context JSON ou '2026-02-12_v1'."""
    if not context or not context.strip():
        return ""
    ctx = context.strip()
    if ctx.startswith("{"):
        try:
            data = json.loads(ctx)
            consent_ver = data.get("consent_version") or ""
            if "_" in consent_ver:
                return consent_ver.split("_", 1)[-1]  # v1
            return consent_ver or ""
        except Exception:
            pass
    if "_" in ctx:
        return ctx.split("_", 1)[-1]
    return ctx


def _get_rgpd_extended(tenant_id: int, start: str, end: str, last_n: int = 20) -> dict:
    """RGPD étendu : consent_rate 7j + derniers consent_obtained (call_id, date, version)."""
    base = _get_rgpd(tenant_id, start, end)
    last_consents: list[dict] = []
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    if url:
        try:
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(url, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT call_id, created_at, context
                        FROM ivr_events
                        WHERE client_id = %s AND event = 'consent_obtained'
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (tenant_id, last_n),
                    )
                    for r in cur.fetchall():
                        ctx = r.get("context") or ""
                        version_short = _extract_consent_version_short(ctx)
                        last_consents.append({
                            "call_id": r["call_id"] or "",
                            "at": str(r["created_at"]) if r.get("created_at") else "",
                            "version": version_short or ctx or "",
                        })
        except Exception as e:
            logger.warning("pg rgpd last_consents failed: %s", e)
    else:
        import backend.db as db
        conn = db.get_conn()
        try:
            rows = conn.execute(
                """
                SELECT call_id, created_at, context
                FROM ivr_events
                WHERE client_id = ? AND event = 'consent_obtained'
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (tenant_id, last_n),
            ).fetchall()
            for r in rows:
                ctx = r[2] or ""
                version_short = _extract_consent_version_short(ctx)
                last_consents.append({
                    "call_id": r[0] or "",
                    "at": str(r[1]) if r[1] else "",
                    "version": version_short or ctx or "",
                })
        finally:
            conn.close()
    base["last_consents"] = last_consents
    return base


# --- Helpers ---


def _link_demo_vocal_number(tenant_id: int) -> bool:
    """Admin only: enregistre la route numéro démo → tenant_id. Non utilisé par l'onboarding (numéro démo = TENANT_TEST fixe). Voir docs/ARCHITECTURE_VOCAL_TENANTS.md."""
    demo = getattr(config, "ONBOARDING_DEMO_VOCAL_NUMBER", None)
    if not demo:
        return False
    from backend.tenant_routing import normalize_did
    key = normalize_did(demo)
    if not key:
        return False
    try:
        if config.USE_PG_TENANTS:
            from backend.tenants_pg import pg_add_routing
            return bool(pg_add_routing("vocal", key, tenant_id))
        from backend.tenant_routing import add_route
        add_route("vocal", key, tenant_id)
        return True
    except Exception as e:
        logger.warning("link demo vocal number failed: %s", e)
        return False


# --- Routes ---


def _verify_admin_password(password: str) -> bool:
    """Vérifie le mot de passe : ADMIN_PASSWORD_HASH (bcrypt) prioritaire, sinon ADMIN_PASSWORD (déprécié)."""
    if not password:
        return False
    if ADMIN_PASSWORD_HASH:
        try:
            import bcrypt
            return bcrypt.checkpw(password.encode("utf-8"), ADMIN_PASSWORD_HASH.encode("utf-8"))
        except Exception as e:
            logger.warning("admin_password_hash_check failed: %s", e)
            return False
    if ADMIN_PASSWORD:
        if (os.environ.get("ENV") or os.environ.get("RAILWAY_ENVIRONMENT") or "").lower() in ("production", "prod"):
            logger.warning("ADMIN_PASSWORD in plain text is deprecated in production; use ADMIN_PASSWORD_HASH (bcrypt)")
        return password.strip() == ADMIN_PASSWORD
    return False


@router.post("/admin/auth/login")
def admin_auth_login(body: AdminLoginBody, request: Request):
    """Connexion admin par email + mot de passe. Pose un cookie HttpOnly (uwi_admin_session)."""
    if not ADMIN_EMAIL:
        raise HTTPException(503, "Admin login not configured (ADMIN_EMAIL)")
    if not ADMIN_PASSWORD_HASH and not ADMIN_PASSWORD:
        raise HTTPException(503, "Admin login not configured (ADMIN_PASSWORD_HASH or ADMIN_PASSWORD)")
    if not JWT_SECRET_ADMIN:
        raise HTTPException(503, "JWT_SECRET or ADMIN_SESSION_SECRET required for admin session")
    email = (body.email or "").strip().lower()
    if email != ADMIN_EMAIL or not _verify_admin_password((body.password or "").strip()):
        raise HTTPException(401, "Identifiants invalides")
    exp = datetime.utcnow() + timedelta(hours=ADMIN_SESSION_EXPIRES_HOURS)
    payload = {"sub": email, "email": email, "scope": "admin", "exp": exp, "iat": datetime.utcnow()}
    token = jwt.encode(payload, JWT_SECRET_ADMIN, algorithm="HS256")
    secure = (os.environ.get("ENV") or os.environ.get("RAILWAY_ENVIRONMENT") or "").lower() in ("production", "prod")
    samesite = ADMIN_COOKIE_SAMESITE if ADMIN_COOKIE_SAMESITE in ("none", "lax", "strict") else ("none" if secure else "lax")
    response = JSONResponse(content={"ok": True, "email": email})
    # Ne pas set domain= : avec API sur Railway (domaine différent de uwiapp.com), le cookie doit rester host-only sur *.railway.app.
    response.set_cookie(
        key=ADMIN_SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        path="/",
        max_age=ADMIN_SESSION_EXPIRES_HOURS * 3600,
    )
    logger.info("admin_login email=%s client=%s", email, request.client.host if request.client else None)
    return response


@router.get("/admin/auth/me")
def admin_auth_me(request: Request):
    """Retourne l'email de l'admin connecté (cookie). 401 si non connecté."""
    email = _get_admin_email_from_cookie(request)
    if not email:
        raise HTTPException(401, "Not authenticated")
    return {"email": email}


@router.post("/admin/auth/logout")
def admin_auth_logout():
    """Déconnexion : supprime le cookie admin (même samesite que login pour cross-domain)."""
    response = JSONResponse(content={"ok": True})
    secure = (os.environ.get("ENV") or os.environ.get("RAILWAY_ENVIRONMENT") or "").lower() in ("production", "prod")
    samesite = ADMIN_COOKIE_SAMESITE if ADMIN_COOKIE_SAMESITE in ("none", "lax", "strict") else ("none" if secure else "lax")
    response.delete_cookie(ADMIN_SESSION_COOKIE, path="/", samesite=samesite)
    return response


@router.post("/public/onboarding", response_model=OnboardingResponse)
def public_onboarding(body: OnboardingRequest):
    """Crée un tenant + config. Public (pas de auth). Aucun lien avec le numéro démo (voir docs/ARCHITECTURE_VOCAL_TENANTS.md)."""
    if config.USE_PG_TENANTS:
        tid = pg_create_tenant(
            name=body.company_name,
            contact_email=body.email,
            calendar_provider=body.calendar_provider,
            calendar_id=body.calendar_id,
            timezone="Europe/Paris",
        )
        if tid:
            pg_create_tenant_user(tid, body.email, role="owner")
            return OnboardingResponse(
                tenant_id=tid,
                message="Compte créé. Connectez-vous avec cet email pour accéder à votre dashboard. Pour tester l'IA en voix, appelez le numéro de démo 09 39 24 05 75 (démo partagée).",
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
            message="Compte créé. Connectez-vous avec cet email pour accéder à votre dashboard. Pour tester l'IA en voix, appelez le numéro de démo 09 39 24 05 75 (démo partagée).",
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


@router.post("/admin/tenants", response_model=TenantOut, status_code=201)
def admin_create_tenant(
    body: TenantCreateIn,
    _: None = Depends(_verify_admin),
):
    """
    Crée un tenant (client) par l'admin.
    409 si contact_email déjà associé à un autre tenant (v1 : 1 email = 1 tenant).
    """
    contact_email = (body.contact_email or "").strip().lower()
    if not contact_email:
        raise HTTPException(400, "contact_email required")

    if config.USE_PG_TENANTS:
        existing = pg_get_tenant_user_by_email(contact_email)
        if existing:
            return JSONResponse(
                status_code=409,
                content={
                    "detail": "Cet email est déjà rattaché à un autre client.",
                    "error_code": "EMAIL_ALREADY_ASSIGNED",
                },
            )
    else:
        import backend.db as db
        db.ensure_tenant_config()
        conn_sqlite = db.get_conn()
        try:
            rows = conn_sqlite.execute("SELECT tenant_id, params_json FROM tenant_config").fetchall()
            for r in rows:
                params = json.loads(r[1]) if r[1] else {}
                existing_email = (params.get("contact_email") or "").strip().lower()
                if existing_email == contact_email:
                    return JSONResponse(
                        status_code=409,
                        content={
                            "detail": "Cet email est déjà rattaché à un autre client.",
                            "error_code": "EMAIL_ALREADY_ASSIGNED",
                        },
                    )
        finally:
            conn_sqlite.close()

    tid = None
    if config.USE_PG_TENANTS:
        tid = pg_create_tenant(
            name=body.name.strip(),
            contact_email=contact_email,
            calendar_provider="none",
            calendar_id="",
            timezone=body.timezone or "Europe/Paris",
            business_type=(body.business_type or "").strip() or None,
            notes=(body.notes or "").strip() or None,
        )
    if not tid and not config.USE_PG_TENANTS:
        import backend.db as db
        db.ensure_tenant_config()
        conn = db.get_conn()
        try:
            conn.execute(
                "INSERT INTO tenants (name, timezone, status) VALUES (?, ?, 'active')",
                (body.name.strip() or "Nouveau", body.timezone or "Europe/Paris"),
            )
            row = conn.execute("SELECT last_insert_rowid()").fetchone()
            tid = row[0] if row else None
            if tid:
                params = json.dumps({
                    "contact_email": contact_email,
                    "business_type": (body.business_type or "").strip() or "",
                    "notes": (body.notes or "").strip() or "",
                })
                conn.execute(
                    "INSERT INTO tenant_config (tenant_id, flags_json, params_json) VALUES (?, '{}', ?)",
                    (tid, params),
                )
                conn.commit()
        except Exception as e:
            conn.rollback()
            logger.exception("admin_create_tenant sqlite failed")
            raise HTTPException(500, str(e))
        finally:
            conn.close()

    if not tid:
        raise HTTPException(500, "Failed to create tenant")

    created_at = datetime.utcnow().isoformat() + "Z"
    return TenantOut(
        tenant_id=int(tid),
        name=body.name.strip(),
        contact_email=contact_email,
        timezone=body.timezone or "Europe/Paris",
        business_type=(body.business_type or "").strip() or None,
        created_at=created_at,
    )


@router.get("/admin/tenants/{tenant_id}")
def admin_get_tenant(
    tenant_id: int = Depends(validate_tenant_id),
    _: None = Depends(_verify_admin),
):
    """Détail tenant (config + routing)."""
    d = _get_tenant_detail(tenant_id)
    if not d:
        raise HTTPException(404, "Tenant not found")
    return d


@router.delete("/admin/tenants/{tenant_id}")
def admin_delete_tenant(
    tenant_id: int = Depends(validate_tenant_id),
    _: None = Depends(_verify_admin),
):
    """Soft delete : passe le tenant en inactive (PG uniquement)."""
    if not config.USE_PG_TENANTS:
        raise HTTPException(501, "Delete tenant requires USE_PG_TENANTS (Postgres)")
    if not pg_deactivate_tenant(tenant_id):
        raise HTTPException(404, "Tenant not found or already inactive")
    return {"ok": True, "tenant_id": tenant_id}


@router.get("/admin/tenants/{tenant_id}/dashboard")
def admin_get_dashboard(
    tenant_id: int = Depends(validate_tenant_id),
    _: None = Depends(_verify_admin),
):
    """Snapshot dashboard: service_status, last_call, last_booking, counters_7d."""
    d = _get_tenant_detail(tenant_id)
    if not d:
        raise HTTPException(404, "Tenant not found")
    return _get_dashboard_snapshot(tenant_id, d.get("name", "N/A"))


@router.get("/admin/tenants/{tenant_id}/activity")
def admin_tenant_activity(
    tenant_id: int = Depends(validate_tenant_id),
    limit: int = Query(50, ge=1, le=200),
    _: None = Depends(_verify_admin),
):
    """Timeline des derniers events ivr_events (date, call_id, event, meta)."""
    return _get_tenant_activity(tenant_id, limit)


def _call_result_from_event(event: Optional[str]) -> str:
    """Priorité: rdv > transfer > abandoned > other."""
    if not event:
        return "other"
    if event == "booking_confirmed":
        return "rdv"
    if event in ("transferred_human", "transferred", "transfer_human", "transfer"):
        return "transfer"
    if event in ("user_abandon", "abandon", "hangup", "user_hangup"):
        return "abandoned"
    return "other"


def _get_calls_list(
    tenant_id: Optional[int],
    days: int,
    limit: int,
    cursor: Optional[str] = None,
    result_filter: Optional[str] = None,
) -> dict:
    """Liste appels depuis ivr_events (+ call_sessions pour duration). PG prioritaire."""
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    start = (now - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")
    end = now.strftime("%Y-%m-%d %H:%M:%S")
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    items: List[dict] = []
    next_cursor: Optional[str] = None

    if url:
        try:
            import psycopg
            from psycopg.rows import dict_row
            # Cursor : base64url(json {t, c}) pour éviter +/= en querystring ; fallback legacy "ts|call_id"
            cursor_ts: Optional[str] = None
            cursor_id: Optional[str] = None
            if cursor:
                try:
                    padded = cursor + ("=" * (4 - len(cursor) % 4)) if len(cursor) % 4 else cursor
                    raw = base64.urlsafe_b64decode(padded.encode()).decode()
                    obj = json.loads(raw)
                    cursor_ts = obj.get("t")
                    cursor_id = obj.get("c")
                except Exception:
                    parts = cursor.split("|", 1)
                    if len(parts) == 2:
                        cursor_ts, cursor_id = parts[0], parts[1]

            with psycopg.connect(url, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    params: List[Any] = [start, end]
                    tenant_filter = ""
                    if tenant_id is not None:
                        tenant_filter = " AND client_id = %s"
                        params.append(_ivr_client_id(tenant_id))

                    cursor_filter = ""
                    if cursor_ts and cursor_id:
                        cursor_filter = " AND (a.last_event_at < %s OR (a.last_event_at = %s AND a.call_id < %s))"
                        params.extend([cursor_ts, cursor_ts, cursor_id])

                    # Filtre sur dernier event (pas "call a eu au moins un event error" ; pour ça voir has_error plus tard)
                    result_filter_sql = ""
                    if result_filter == "rdv":
                        result_filter_sql = " AND a.last_event = 'booking_confirmed'"
                    elif result_filter == "transfer":
                        result_filter_sql = " AND a.last_event IN ('transferred_human', 'transferred', 'transfer_human', 'transfer')"
                    elif result_filter == "abandoned":
                        result_filter_sql = " AND a.last_event IN ('user_abandon', 'abandon', 'hangup', 'user_hangup')"
                    elif result_filter == "error":
                        result_filter_sql = " AND a.last_event = 'anti_loop_trigger'"

                    params.append(limit + 1)

                    cur.execute(
                        """
                        WITH agg AS (
                            SELECT client_id, call_id,
                                   MIN(created_at) AS started_at,
                                   MAX(created_at) AS last_event_at,
                                   (array_agg(event ORDER BY created_at DESC))[1] AS last_event
                            FROM ivr_events
                            WHERE created_at >= %s AND created_at <= %s
                              AND call_id IS NOT NULL AND TRIM(call_id) != ''
                              """ + tenant_filter + """
                            GROUP BY client_id, call_id
                        )
                        SELECT a.client_id, a.call_id, a.started_at, a.last_event_at, a.last_event,
                               cs.started_at AS cs_started, cs.updated_at AS cs_updated
                        FROM agg a
                        LEFT JOIN call_sessions cs ON cs.tenant_id = a.client_id AND cs.call_id = a.call_id
                        WHERE 1=1 """ + cursor_filter + result_filter_sql + """
                        ORDER BY a.last_event_at DESC, a.call_id DESC
                        LIMIT %s
                        """,
                        tuple(params),
                    )
                    rows = cur.fetchall()
                    if not rows:
                        return {"items": [], "next_cursor": None, "days": days}

                    for r in rows[:limit]:
                        started_at = r.get("started_at")
                        last_event_at = r.get("last_event_at")
                        last_event = r.get("last_event")
                        cs_started = r.get("cs_started")
                        cs_updated = r.get("cs_updated")
                        duration_min: Optional[int] = None
                        if cs_started and cs_updated:
                            delta_mins = (cs_updated - cs_started).total_seconds() / 60.0
                            delta_mins = max(0, min(MAX_SESSION_MINUTES, delta_mins))
                            duration_min = int(round(delta_mins, 0))
                        elif started_at and last_event_at:
                            delta_mins = (last_event_at - started_at).total_seconds() / 60.0
                            delta_mins = max(0, min(MAX_SESSION_MINUTES, delta_mins))
                            duration_min = int(round(delta_mins, 0))

                        items.append({
                            "call_id": r.get("call_id") or "",
                            "tenant_id": r.get("client_id"),
                            "started_at": started_at.isoformat() + "Z" if hasattr(started_at, "isoformat") else str(started_at),
                            "last_event_at": last_event_at.isoformat() + "Z" if hasattr(last_event_at, "isoformat") else str(last_event_at),
                            "last_event": last_event or "",
                            "result": _call_result_from_event(last_event),
                            "duration_min": duration_min,
                        })

                    if len(rows) > limit:
                        last_row = rows[limit - 1]
                        t_iso = last_row["last_event_at"].isoformat() if hasattr(last_row["last_event_at"], "isoformat") else str(last_row["last_event_at"])
                        c_id = last_row.get("call_id") or ""
                        next_cursor = base64.urlsafe_b64encode(json.dumps({"t": t_iso, "c": c_id}).encode()).decode().rstrip("=")

        except Exception as e:
            logger.warning("admin calls list pg failed: %s", e)
    # Pas de fallback SQLite pour la liste appels (PG uniquement en prod).

    return {"items": items, "next_cursor": next_cursor, "days": days}


@router.get("/admin/calls")
def admin_calls_list(
    tenant_id: Optional[int] = Query(None, description="Filtrer par tenant"),
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(50, ge=1, le=200),
    cursor: Optional[str] = Query(None),
    result: Optional[str] = Query(None, description="rdv | transfer | abandoned | error"),
    _: None = Depends(_verify_admin),
):
    """Liste appels. Filtre optionnel result=rdv|transfer|abandoned|error. Cursor base64(json {t,c})."""
    if tenant_id is not None:
        _get_tenant_detail(tenant_id)  # 404 if missing
    return _get_calls_list(tenant_id, days, limit, cursor, result)


def _iso_utc(dt: Any) -> str:
    """Format datetime en ISO UTC (suffixe Z) pour éviter confusion timezone dans le front."""
    if dt is None:
        return ""
    from datetime import timezone
    if hasattr(dt, "astimezone"):
        utc = dt.astimezone(timezone.utc) if getattr(dt, "tzinfo", None) else dt
        return utc.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    return str(dt)


def _get_call_detail(tenant_id: int, call_id: str) -> dict:
    """Détail d'un call : metadata + events[] depuis ivr_events (call_id unique par tenant). Timestamps en UTC (Z)."""
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    cid = _ivr_client_id(tenant_id)
    call_id_clean = (call_id or "").strip()
    if not call_id_clean:
        raise HTTPException(400, "call_id required")
    out: Dict[str, Any] = {
        "call_id": call_id_clean,
        "tenant_id": tenant_id,
        "started_at": None,
        "last_event_at": None,
        "duration_min": None,
        "result": "other",
        "events": [],
    }
    if not url:
        return out
    try:
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT created_at, event, context, reason
                    FROM ivr_events
                    WHERE client_id = %s AND call_id = %s
                    ORDER BY created_at ASC
                    """,
                    (cid, call_id_clean),
                )
                rows = cur.fetchall()
                if not rows:
                    raise HTTPException(404, "Call not found")
                events = []
                for r in rows:
                    meta = {}
                    if r.get("context"):
                        meta["context"] = r["context"]
                    if r.get("reason"):
                        meta["reason"] = r["reason"]
                    events.append({
                        "created_at": _iso_utc(r.get("created_at")),
                        "event": r.get("event") or "",
                        "meta": meta if meta else None,
                    })
                out["events"] = events
                out["started_at"] = events[0]["created_at"] if events else None
                out["last_event_at"] = events[-1]["created_at"] if events else None
                last_event = rows[-1].get("event") if rows else None
                out["result"] = _call_result_from_event(last_event)
                if len(rows) >= 2:
                    from datetime import datetime
                    try:
                        first_ts = rows[0]["created_at"]
                        last_ts = rows[-1]["created_at"]
                        if hasattr(first_ts, "timestamp") and hasattr(last_ts, "timestamp"):
                            delta_mins = (last_ts - first_ts).total_seconds() / 60.0
                        else:
                            delta_mins = 0
                        delta_mins = max(0, min(MAX_SESSION_MINUTES, delta_mins))
                        out["duration_min"] = int(round(delta_mins, 0))
                    except Exception:
                        pass
                cur.execute(
                    """
                    SELECT started_at, updated_at FROM call_sessions
                    WHERE tenant_id = %s AND call_id = %s
                    """,
                    (tenant_id, call_id_clean),
                )
                cs = cur.fetchone()
                if cs and cs.get("started_at") and cs.get("updated_at"):
                    delta_mins = (cs["updated_at"] - cs["started_at"]).total_seconds() / 60.0
                    delta_mins = max(0, min(MAX_SESSION_MINUTES, delta_mins))
                    out["duration_min"] = int(round(delta_mins, 0))
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("call detail pg failed: %s", e)
    return out


@router.get("/admin/tenants/{tenant_id}/calls/{call_id}")
def admin_call_detail(
    tenant_id: int = Depends(validate_tenant_id),
    call_id: str = ...,
    _: None = Depends(_verify_admin),
):
    """Détail d'un call : metadata + timeline events. call_id unique par tenant."""
    if _get_tenant_detail(tenant_id) is None:
        raise HTTPException(404, "Tenant not found")
    return _get_call_detail(tenant_id, call_id)


def _get_transfer_reasons(tenant_id: int, days: int = 7) -> dict:
    """
    Top 5 raisons de transfert (transferred_human) + transfer_prevented pour comparaison.
    Returns: {top_transferred: [{reason, count}], top_prevented: [{reason, count}]}
    """
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    start = (now - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")
    end = now.strftime("%Y-%m-%d %H:%M:%S")

    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    top_transferred = []
    top_prevented = []

    if url:
        try:
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(url, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT COALESCE(reason, 'unknown') as reason, COUNT(*) as cnt
                        FROM ivr_events
                        WHERE client_id = %s AND created_at >= %s AND created_at <= %s
                        AND event IN ('transferred_human', 'transferred')
                        GROUP BY COALESCE(reason, 'unknown')
                        ORDER BY cnt DESC
                        LIMIT 5
                        """,
                        (tenant_id, start, end),
                    )
                    top_transferred = [{"reason": r["reason"], "count": int(r["cnt"])} for r in cur.fetchall()]
                    cur.execute(
                        """
                        SELECT COALESCE(reason, 'unknown') as reason, COUNT(*) as cnt
                        FROM ivr_events
                        WHERE client_id = %s AND created_at >= %s AND created_at <= %s
                        AND event = 'transfer_prevented'
                        GROUP BY COALESCE(reason, 'unknown')
                        ORDER BY cnt DESC
                        LIMIT 5
                        """,
                        (tenant_id, start, end),
                    )
                    top_prevented = [{"reason": r["reason"], "count": int(r["cnt"])} for r in cur.fetchall()]
        except Exception as e:
            logger.warning("transfer_reasons failed: %s", e)
    else:
        import backend.db as db
        conn = db.get_conn()
        try:
            db._ensure_ivr_tables(conn)
            rows = conn.execute(
                """
                SELECT COALESCE(reason, 'unknown') as reason, COUNT(*) as cnt
                FROM ivr_events
                WHERE client_id = ? AND created_at >= ? AND created_at <= ?
                AND event IN ('transferred_human', 'transferred')
                GROUP BY COALESCE(reason, 'unknown')
                ORDER BY cnt DESC
                LIMIT 5
                """,
                (tenant_id, start, end),
            ).fetchall()
            top_transferred = [{"reason": r[0], "count": int(r[1])} for r in rows]
            rows = conn.execute(
                """
                SELECT COALESCE(reason, 'unknown') as reason, COUNT(*) as cnt
                FROM ivr_events
                WHERE client_id = ? AND created_at >= ? AND created_at <= ?
                AND event = 'transfer_prevented'
                GROUP BY COALESCE(reason, 'unknown')
                ORDER BY cnt DESC
                LIMIT 5
                """,
                (tenant_id, start, end),
            ).fetchall()
            top_prevented = [{"reason": r[0], "count": int(r[1])} for r in rows]
        except Exception as e:
            logger.warning("transfer_reasons sqlite failed: %s", e)
        finally:
            conn.close()

    return {
        "top_transferred": top_transferred,
        "top_prevented": top_prevented,
        "days": days,
    }


@router.get("/admin/tenants/{tenant_id}/transfer-reasons")
def admin_get_transfer_reasons(
    tenant_id: int = Depends(validate_tenant_id),
    days: int = Query(7, ge=1, le=90),
    _: None = Depends(_verify_admin),
):
    """Top 5 raisons de transfert (7j) — pour prioriser les corrections."""
    d = _get_tenant_detail(tenant_id)
    if not d:
        raise HTTPException(404, "Tenant not found")
    return _get_transfer_reasons(tenant_id, days)


@router.get("/admin/tenants/{tenant_id}/technical-status")
def admin_get_technical_status(
    tenant_id: int = Depends(validate_tenant_id),
    _: None = Depends(_verify_admin),
):
    """Statut technique: DID, routing, calendrier, agent."""
    s = _get_technical_status(tenant_id)
    if not s:
        raise HTTPException(404, "Tenant not found")
    return s


@router.get("/admin/tenants/{tenant_id}/billing")
def admin_get_tenant_billing(
    tenant_id: int = Depends(validate_tenant_id),
    _: None = Depends(_verify_admin),
):
    """Billing Stripe (customer, subscription, status) + suspension. Agnostique prix."""
    if not _get_tenant_detail(tenant_id):
        raise HTTPException(404, "Tenant not found")
    billing = get_tenant_billing(tenant_id)
    out = billing if billing is not None else {}
    for k in ("is_suspended", "suspension_reason", "suspended_at", "force_active_override", "force_active_until", "suspension_mode"):
        out.setdefault(k, None)
    return out


class ForceActiveBody(BaseModel):
    days: int = Field(7, ge=1, le=90, description="Nombre de jours pendant lesquels forcer actif")


class SuspendBody(BaseModel):
    mode: str = Field("hard", description="hard = phrase courte zero LLM; soft = message poli sans RDV (manual only)")


@router.post("/admin/tenants/{tenant_id}/suspend")
def admin_tenant_suspend(
    tenant_id: int = Depends(validate_tenant_id),
    body: SuspendBody = Body(SuspendBody()),
    _: None = Depends(_verify_admin),
):
    """Suspend le tenant manuellement. mode=soft uniquement pour manual (message poli, pas de RDV)."""
    if not _get_tenant_detail(tenant_id):
        raise HTTPException(404, "Tenant not found")
    mode = (body.mode or "hard").strip().lower()
    if mode not in ("hard", "soft"):
        mode = "hard"
    if not set_tenant_suspended(tenant_id, reason="manual", mode=mode):
        raise HTTPException(500, "Failed to suspend")
    return {"ok": True, "tenant_id": tenant_id, "is_suspended": True, "suspension_mode": mode}


@router.post("/admin/tenants/{tenant_id}/unsuspend")
def admin_tenant_unsuspend(
    tenant_id: int = Depends(validate_tenant_id),
    _: None = Depends(_verify_admin),
):
    """Lève la suspension (admin)."""
    if not _get_tenant_detail(tenant_id):
        raise HTTPException(404, "Tenant not found")
    if not set_tenant_unsuspended(tenant_id):
        raise HTTPException(500, "Failed to unsuspend")
    return {"ok": True, "tenant_id": tenant_id, "is_suspended": False}


@router.post("/admin/tenants/{tenant_id}/force-active")
def admin_tenant_force_active(
    tenant_id: int = Depends(validate_tenant_id),
    body: ForceActiveBody = Body(ForceActiveBody()),
    _: None = Depends(_verify_admin),
):
    """Force le tenant actif pendant X jours (pas de suspension même si past_due)."""
    if not _get_tenant_detail(tenant_id):
        raise HTTPException(404, "Tenant not found")
    if not set_force_active(tenant_id, body.days):
        raise HTTPException(500, "Failed to set force-active")
    return {"ok": True, "tenant_id": tenant_id, "force_active_days": body.days}


@router.post("/admin/tenants/{tenant_id}/stripe-customer")
def admin_create_stripe_customer(
    tenant_id: int = Depends(validate_tenant_id),
    _: None = Depends(_verify_admin),
):
    """Crée un Stripe Customer pour le tenant et enregistre stripe_customer_id."""
    d = _get_tenant_detail(tenant_id)
    if not d:
        raise HTTPException(404, "Tenant not found")
    stripe_key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if not stripe_key:
        raise HTTPException(503, "Stripe not configured (STRIPE_SECRET_KEY)")
    try:
        import stripe
        stripe.api_key = stripe_key
        name = (d.get("name") or f"Tenant #{tenant_id}")[:500]
        customer = stripe.Customer.create(
            name=name,
            metadata={"tenant_id": str(tenant_id)},
        )
        cid = (customer.id or "").strip()
        if not cid:
            raise HTTPException(500, "Stripe customer id empty")
        if not set_stripe_customer_id(tenant_id, cid):
            raise HTTPException(500, "Failed to save stripe_customer_id")
        logger.info("STRIPE_CUSTOMER_CREATED tenant_id=%s stripe_customer_id=%s", tenant_id, cid)
        return {"stripe_customer_id": cid, "tenant_id": tenant_id}
    except stripe.StripeError as e:
        logger.warning("stripe customer create failed: %s", e)
        raise HTTPException(502, str(e) or "Stripe error")


@router.get("/admin/tenants/{tenant_id}/usage")
def admin_get_tenant_usage(
    tenant_id: int = Depends(validate_tenant_id),
    month: str = Query(..., description="YYYY-MM"),
    _: None = Depends(_verify_admin),
):
    """Usage Vapi du mois (vapi_call_usage) : minutes_total, cost_usd, calls_count. Convention : mois calendaire en UTC (ended_at >= 1er 00:00:00 UTC, < 1er mois suivant)."""
    if not _get_tenant_detail(tenant_id):
        raise HTTPException(404, "Tenant not found")
    if len(month) != 7 or month[4] != "-":
        raise HTTPException(400, "month must be YYYY-MM")
    start = f"{month}-01 00:00:00"
    try:
        from datetime import datetime
        y, m = int(month[:4]), int(month[5:7])
        if m == 12:
            end = f"{y + 1}-01-01 00:00:00"
        else:
            end = f"{y}-{m + 1:02d}-01 00:00:00"
    except ValueError:
        raise HTTPException(400, "month must be YYYY-MM")
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    out = {"tenant_id": tenant_id, "month": month, "minutes_total": 0, "cost_usd": 0, "calls_count": 0}
    if url:
        try:
            import psycopg
            with psycopg.connect(url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT COALESCE(SUM(duration_sec), 0) / 60.0 AS mins,
                               COALESCE(SUM(cost_usd), 0) AS cost,
                               COUNT(*) AS cnt
                        FROM vapi_call_usage
                        WHERE tenant_id = %s AND ended_at IS NOT NULL AND ended_at >= %s AND ended_at < %s
                        """,
                        (tenant_id, start, end),
                    )
                    row = cur.fetchone()
                    if row:
                        out["minutes_total"] = round(float(row[0] or 0), 2)
                        out["cost_usd"] = round(float(row[1] or 0), 4)
                        out["calls_count"] = int(row[2] or 0)
        except Exception as e:
            if "does not exist" not in str(e).lower():
                logger.warning("tenant usage query failed: %s", e)
    return out


@router.post("/admin/tenants/{tenant_id}/users")
def admin_add_tenant_user(
    tenant_id: int = Depends(validate_tenant_id),
    body: AdminTenantUserCreate = ...,
    _: None = Depends(_verify_admin),
):
    """
    Ajoute un tenant_user (owner ou member).
    Idempotent si même tenant. 409 si email déjà sur un autre tenant.
    """
    d = _get_tenant_detail(tenant_id)
    if not d:
        raise HTTPException(404, "Tenant not found")
    email = (body.email or "").strip().lower()
    if not email:
        raise HTTPException(400, "Email required")
    role = (body.role or "owner").lower()
    if role not in ("owner", "member"):
        role = "owner"
    try:
        result = pg_add_tenant_user(tenant_id, email, role)
        return result
    except ValueError as e:
        msg = str(e).lower()
        if "autre tenant" in msg or "déjà associé" in msg:
            raise HTTPException(409, str(e))
        raise HTTPException(400, str(e))


@router.patch("/admin/tenants/{tenant_id}/flags")
def admin_patch_flags(
    tenant_id: int = Depends(validate_tenant_id),
    body: FlagsUpdate = ...,
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
    tenant_id: int = Depends(validate_tenant_id),
    body: ParamsUpdate = ...,
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
    """Ajoute une route DID → tenant. Rejette la réassignation du numéro démo vers un autre tenant (409)."""
    try:
        if config.USE_PG_TENANTS:
            ok = pg_add_routing(body.channel, body.key, body.tenant_id)
            if ok:
                return {"ok": True}
        from backend.tenant_routing import add_route
        add_route(body.channel, body.key, body.tenant_id)
        return {"ok": True}
    except ValueError as e:
        if "TEST_TENANT_ID" in str(e) or "Forbidden" in str(e) or "démo vocal" in str(e):
            return JSONResponse(
                status_code=409,
                content={"detail": str(e), "error_code": "TEST_NUMBER_IMMUTABLE"},
            )
        raise


def _get_global_stats(window_days: int) -> dict:
    """KPIs globaux sur la fenêtre. Prod = Postgres (Railway) ; fallback SQLite en dev local."""
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    start = (now - timedelta(days=window_days)).strftime("%Y-%m-%d 00:00:00")
    end = now.strftime("%Y-%m-%d %H:%M:%S")
    tenants_list = _get_tenant_list(include_inactive=True)
    tenants_total = len(tenants_list)
    tenants_active = sum(1 for t in tenants_list if (t.get("status") or "active") == "active")
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    calls_total = 0
    calls_abandoned = 0
    appointments_total = 0
    transfers_total = 0
    errors_total = 0
    last_activity_at: Optional[str] = None
    minutes_total = 0.0
    cost_usd_total: Optional[float] = None

    if url:
        try:
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(url, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT COUNT(DISTINCT call_id) AS c
                        FROM ivr_events
                        WHERE call_id IS NOT NULL AND TRIM(call_id) != '' AND created_at >= %s AND created_at <= %s
                        """,
                        (start, end),
                    )
                    row = cur.fetchone()
                    calls_total = row["c"] or 0
                    cur.execute(
                        """
                        SELECT event, COUNT(*) AS cnt FROM ivr_events
                        WHERE created_at >= %s AND created_at <= %s
                        GROUP BY event
                        """,
                        (start, end),
                    )
                    by_event = {r["event"]: r["cnt"] for r in cur.fetchall()}
                    calls_abandoned = sum(by_event.get(e, 0) for e in ("user_abandon", "abandon", "hangup", "user_hangup"))
                    transfers_total = sum(by_event.get(e, 0) for e in ("transferred_human", "transferred", "transfer_human", "transfer"))
                    appointments_total = by_event.get("booking_confirmed", 0)
                    errors_total = by_event.get("anti_loop_trigger", 0)
                    cur.execute(
                        "SELECT MAX(created_at) AS m FROM ivr_events WHERE created_at >= %s AND created_at <= %s",
                        (start, end),
                    )
                    r = cur.fetchone()
                    if r and r["m"]:
                        last_activity_at = r["m"].isoformat() + "Z" if hasattr(r["m"], "isoformat") else str(r["m"])
                    cur.execute(
                        """
                        SELECT SUM(LEAST(GREATEST(EXTRACT(EPOCH FROM (updated_at - started_at)) / 60.0, 0), %s)) AS mins
                        FROM call_sessions
                        WHERE started_at >= %s AND updated_at <= %s
                        """,
                        (MAX_SESSION_MINUTES, start, end),
                    )
                    row = cur.fetchone()
                    if row and row["mins"] is not None:
                        minutes_total = round(float(row["mins"]), 1)
                    # Vapi = source de vérité conso : priorité vapi_call_usage si dispo
                    vapi_mins, vapi_cost = _get_vapi_usage_for_window(url, start, end, tenant_id=None)
                    if vapi_mins is not None and vapi_mins > 0:
                        minutes_total = round(vapi_mins, 1)
                    if vapi_cost is not None and vapi_cost >= 0:
                        cost_usd_total = round(vapi_cost, 4)
        except Exception as e:
            logger.warning("stats global pg failed: %s", e)
    else:
        import backend.db as db
        conn = db.get_conn()
        try:
            db._ensure_ivr_tables(conn)
            cur = conn.execute(
                """SELECT COUNT(DISTINCT call_id) FROM ivr_events
                   WHERE call_id IS NOT NULL AND TRIM(call_id) != '' AND created_at >= ? AND created_at <= ?""",
                (start, end),
            )
            calls_total = cur.fetchone()[0] or 0
            cur = conn.execute(
                """SELECT event, COUNT(*) FROM ivr_events WHERE created_at >= ? AND created_at <= ? GROUP BY event""",
                (start, end),
            )
            by_event = dict(cur.fetchall())
            calls_abandoned = sum(by_event.get(e, 0) for e in ("user_abandon", "abandon", "hangup", "user_hangup"))
            transfers_total = sum(by_event.get(e, 0) for e in ("transferred_human", "transferred", "transfer_human", "transfer"))
            appointments_total = by_event.get("booking_confirmed", 0)
            errors_total = by_event.get("anti_loop_trigger", 0)
            cur = conn.execute(
                "SELECT MAX(created_at) FROM ivr_events WHERE created_at >= ? AND created_at <= ?",
                (start, end),
            )
            r = cur.fetchone()
            if r and r[0]:
                last_activity_at = r[0]
        finally:
            conn.close()

    if config.USE_PG_SLOTS:
        url_slots = os.environ.get("DATABASE_URL") or os.environ.get("PG_SLOTS_URL")
        if url_slots:
            try:
                import psycopg
                with psycopg.connect(url_slots) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT COUNT(*) FROM appointments WHERE created_at >= %s AND created_at <= %s",
                            (start, end),
                        )
                        row = cur.fetchone()
                        if row:
                            appointments_total = row[0] or appointments_total
            except Exception as e:
                logger.debug("stats global appointments pg: %s", e)

    out = {
        "window_days": window_days,
        "tenants_total": tenants_total,
        "tenants_active": tenants_active,
        "calls_total": calls_total,
        "calls_answered": max(0, calls_total - calls_abandoned),
        "calls_abandoned": calls_abandoned,
        "minutes_total": int(minutes_total),
        "appointments_total": appointments_total,
        "transfers_total": transfers_total,
        "errors_total": errors_total,
        "last_activity_at": last_activity_at,
    }
    if cost_usd_total is not None:
        out["cost_usd_total"] = cost_usd_total
    return out


def _get_stats_timeseries(metric: str, days: int) -> dict:
    """Série temporelle par jour. Sources = Postgres (Railway) en prod."""
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    points: List[dict] = []
    for i in range(days - 1, -1, -1):
        d = (now - timedelta(days=i)).date()
        date_str = d.strftime("%Y-%m-%d")
        start = date_str + " 00:00:00"
        end = date_str + " 23:59:59"
        value = 0
        if url:
            try:
                import psycopg
                with psycopg.connect(url) as conn:
                    with conn.cursor() as cur:
                        if metric == "calls":
                            cur.execute(
                                """SELECT COUNT(DISTINCT call_id) FROM ivr_events
                                   WHERE call_id IS NOT NULL AND TRIM(call_id) != '' AND created_at >= %s AND created_at <= %s""",
                                (start, end),
                            )
                            value = cur.fetchone()[0] or 0
                        elif metric == "appointments":
                            cur.execute(
                                """SELECT COUNT(*) FROM ivr_events WHERE event = 'booking_confirmed' AND created_at >= %s AND created_at <= %s""",
                                (start, end),
                            )
                            value = cur.fetchone()[0] or 0
                        elif metric == "minutes":
                            try:
                                cur.execute(
                                    """SELECT COALESCE(SUM(duration_sec), 0) / 60.0 FROM vapi_call_usage
                                       WHERE ended_at IS NOT NULL AND ended_at >= %s AND ended_at <= %s""",
                                    (start, end),
                                )
                                vapi_val = cur.fetchone()[0]
                                if vapi_val is not None and float(vapi_val) > 0:
                                    value = int(round(float(vapi_val), 0))
                            except Exception:
                                pass
                            if value == 0:
                                cur.execute(
                                    """SELECT COALESCE(SUM(LEAST(GREATEST(EXTRACT(EPOCH FROM (updated_at - started_at)) / 60.0, 0), %s)), 0) FROM call_sessions
                                       WHERE started_at >= %s AND updated_at <= %s""",
                                    (MAX_SESSION_MINUTES, start, end),
                                )
                                value = int(cur.fetchone()[0] or 0)
                        elif metric == "cost_usd":
                            try:
                                cur.execute(
                                    """SELECT COALESCE(SUM(cost_usd), 0) FROM vapi_call_usage
                                       WHERE ended_at IS NOT NULL AND ended_at >= %s AND ended_at <= %s""",
                                    (start, end),
                                )
                                vapi_val = cur.fetchone()[0]
                                if vapi_val is not None:
                                    value = round(float(vapi_val), 4)
                            except Exception:
                                pass
            except Exception:
                pass
        else:
            import backend.db as db
            conn = db.get_conn()
            try:
                db._ensure_ivr_tables(conn)
                if metric == "calls":
                    cur = conn.execute(
                        """SELECT COUNT(DISTINCT call_id) FROM ivr_events
                           WHERE call_id IS NOT NULL AND TRIM(call_id) != '' AND created_at >= ? AND created_at <= ?""",
                        (start, end),
                    )
                    value = cur.fetchone()[0] or 0
                elif metric == "appointments":
                    cur = conn.execute(
                        """SELECT COUNT(*) FROM ivr_events WHERE event = 'booking_confirmed' AND created_at >= ? AND created_at <= ?""",
                        (start, end),
                    )
                    value = cur.fetchone()[0] or 0
                # metric == "minutes" : pas de call_sessions en SQLite, value reste 0
            finally:
                conn.close()
        points.append({"date": date_str, "value": value})
    return {"metric": metric, "days": days, "points": points}


def _get_stats_top_tenants(metric: str, window_days: int, limit: int) -> dict:
    """Top tenants par métrique. Sources = Postgres (Railway) en prod."""
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    start = (now - timedelta(days=window_days)).strftime("%Y-%m-%d 00:00:00")
    end = now.strftime("%Y-%m-%d %H:%M:%S")
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    items: List[dict] = []
    if url:
        try:
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(url, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    if metric == "calls":
                        cur.execute(
                            """
                            SELECT client_id AS tenant_id, COUNT(DISTINCT call_id) AS value
                            FROM ivr_events
                            WHERE call_id IS NOT NULL AND TRIM(call_id) != '' AND created_at >= %s AND created_at <= %s
                            GROUP BY client_id ORDER BY value DESC LIMIT %s
                            """,
                            (start, end, limit),
                        )
                    elif metric == "appointments":
                        cur.execute(
                            """
                            SELECT client_id AS tenant_id, COUNT(*) AS value
                            FROM ivr_events
                            WHERE event = 'booking_confirmed' AND created_at >= %s AND created_at <= %s
                            GROUP BY client_id ORDER BY value DESC LIMIT %s
                            """,
                            (start, end, limit),
                        )
                    elif metric == "minutes":
                        try:
                            cur.execute(
                                """
                                SELECT tenant_id, (COALESCE(SUM(duration_sec), 0) / 60.0)::INT AS value
                                FROM vapi_call_usage
                                WHERE ended_at IS NOT NULL AND ended_at >= %s AND ended_at <= %s
                                GROUP BY tenant_id ORDER BY value DESC LIMIT %s
                                """,
                                (start, end, limit),
                            )
                            rows = cur.fetchall()
                            if not rows:
                                raise ValueError("no vapi rows")
                        except Exception:
                            cur.execute(
                                """
                                SELECT tenant_id, COALESCE(SUM(LEAST(GREATEST(EXTRACT(EPOCH FROM (updated_at - started_at)) / 60.0, 0), %s)), 0)::INT AS value
                                FROM call_sessions
                                WHERE started_at >= %s AND updated_at <= %s
                                GROUP BY tenant_id ORDER BY value DESC LIMIT %s
                                """,
                                (MAX_SESSION_MINUTES, start, end, limit),
                            )
                            rows = cur.fetchall()
                        for r in rows:
                            tid = r.get("tenant_id") if isinstance(r, dict) else r[0]
                            val = r.get("value") if isinstance(r, dict) else r[1]
                            d = _get_tenant_detail(tid) if tid else {}
                            items.append({
                                "tenant_id": tid,
                                "name": d.get("name") or f"Tenant #{tid}",
                                "value": val or 0,
                                "last_activity_at": None,
                            })
                    elif metric == "cost_usd":
                        try:
                            cur.execute(
                                """
                                SELECT tenant_id, COALESCE(SUM(cost_usd), 0) AS value
                                FROM vapi_call_usage
                                WHERE ended_at IS NOT NULL AND ended_at >= %s AND ended_at <= %s
                                GROUP BY tenant_id ORDER BY value DESC LIMIT %s
                                """,
                                (start, end, limit),
                            )
                            rows = cur.fetchall()
                            for r in rows:
                                tid = r.get("tenant_id") if isinstance(r, dict) else r[0]
                                val = r.get("value") if isinstance(r, dict) else r[1]
                                d = _get_tenant_detail(tid) if tid else {}
                                items.append({
                                    "tenant_id": tid,
                                    "name": d.get("name") or f"Tenant #{tid}",
                                    "value": round(float(val or 0), 4),
                                    "last_activity_at": None,
                                })
                        except Exception as e:
                            logger.warning("stats top_tenants cost_usd pg: %s", e)
                    else:
                        cur.execute(
                            """
                            SELECT client_id AS tenant_id, COUNT(DISTINCT call_id) AS value
                            FROM ivr_events
                            WHERE call_id IS NOT NULL AND TRIM(call_id) != '' AND created_at >= %s AND created_at <= %s
                            GROUP BY client_id ORDER BY value DESC LIMIT %s
                            """,
                            (start, end, limit),
                        )
                    if metric != "minutes":
                        rows = cur.fetchall()
                        for r in rows:
                            tid = r.get("tenant_id")
                            d = _get_tenant_detail(tid) if tid else {}
                            items.append({
                                "tenant_id": tid,
                                "name": d.get("name") or f"Tenant #{tid}",
                                "value": r.get("value") or 0,
                                "last_activity_at": None,
                            })
        except Exception as e:
            logger.warning("stats top_tenants pg failed: %s", e)
    else:
        import backend.db as db
        conn = db.get_conn()
        try:
            db._ensure_ivr_tables(conn)
            if metric == "calls":
                cur = conn.execute(
                    """SELECT client_id, COUNT(DISTINCT call_id) AS value FROM ivr_events
                       WHERE call_id != '' AND created_at >= ? AND created_at <= ?
                       GROUP BY client_id ORDER BY value DESC LIMIT ?""",
                    (start, end, limit),
                )
            elif metric == "appointments":
                cur = conn.execute(
                    """SELECT client_id, COUNT(*) AS value FROM ivr_events
                       WHERE event = 'booking_confirmed' AND created_at >= ? AND created_at <= ?
                       GROUP BY client_id ORDER BY value DESC LIMIT ?""",
                    (start, end, limit),
                )
            else:
                cur = conn.execute(
                    """SELECT client_id, COUNT(DISTINCT call_id) AS value FROM ivr_events
                       WHERE call_id != '' AND created_at >= ? AND created_at <= ?
                       GROUP BY client_id ORDER BY value DESC LIMIT ?""",
                    (start, end, limit),
                )
            for row in cur.fetchall():
                tid = row[0]
                d = _get_tenant_detail(tid) if tid else {}
                items.append({
                    "tenant_id": tid,
                    "name": d.get("name") or f"Tenant #{tid}",
                    "value": row[1] or 0,
                    "last_activity_at": None,
                })
        finally:
            conn.close()
    return {"metric": metric, "window_days": window_days, "items": items}


def _get_tenant_stats(tenant_id: int, window_days: int) -> dict:
    """KPIs pour un tenant sur la fenêtre. Prod = Postgres (Railway). calls_answered = calls_total - calls_abandoned."""
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    start = (now - timedelta(days=window_days)).strftime("%Y-%m-%d 00:00:00")
    end = now.strftime("%Y-%m-%d %H:%M:%S")
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    out = {
        "tenant_id": tenant_id,
        "window_days": window_days,
        "calls_total": 0,
        "calls_abandoned": 0,
        "calls_answered": 0,
        "minutes_total": 0,
        "appointments_total": 0,
        "transfers_total": 0,
        "errors_total": 0,
        "last_activity_at": None,
    }
    if url:
        try:
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(url, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cid = _ivr_client_id(tenant_id)
                    cur.execute(
                        """
                        SELECT COUNT(DISTINCT call_id) AS c
                        FROM ivr_events
                        WHERE client_id = %s AND call_id IS NOT NULL AND TRIM(call_id) != ''
                          AND created_at >= %s AND created_at <= %s
                        """,
                        (cid, start, end),
                    )
                    out["calls_total"] = cur.fetchone()["c"] or 0
                    cur.execute(
                        """
                        SELECT COUNT(DISTINCT call_id) AS c
                        FROM ivr_events
                        WHERE client_id = %s AND created_at >= %s AND created_at <= %s
                          AND event IN ('user_abandon', 'abandon', 'hangup', 'user_hangup')
                        """,
                        (cid, start, end),
                    )
                    out["calls_abandoned"] = cur.fetchone()["c"] or 0
                    out["calls_answered"] = max(0, out["calls_total"] - out["calls_abandoned"])
                    cur.execute(
                        """
                        SELECT COUNT(*) AS c FROM ivr_events
                        WHERE client_id = %s AND created_at >= %s AND created_at <= %s
                          AND event IN ('booking_confirmed')
                        """,
                        (cid, start, end),
                    )
                    out["appointments_total"] = cur.fetchone()["c"] or 0
                    cur.execute(
                        """
                        SELECT COUNT(*) AS c FROM ivr_events
                        WHERE client_id = %s AND created_at >= %s AND created_at <= %s
                          AND event IN ('transferred_human', 'transferred', 'transfer_human', 'transfer')
                        """,
                        (cid, start, end),
                    )
                    out["transfers_total"] = cur.fetchone()["c"] or 0
                    cur.execute(
                        """
                        SELECT COUNT(*) AS c FROM ivr_events
                        WHERE client_id = %s AND created_at >= %s AND created_at <= %s
                          AND event = 'anti_loop_trigger'
                        """,
                        (cid, start, end),
                    )
                    out["errors_total"] = cur.fetchone()["c"] or 0
                    cur.execute(
                        "SELECT MAX(created_at) AS m FROM ivr_events WHERE client_id = %s AND created_at >= %s AND created_at <= %s",
                        (cid, start, end),
                    )
                    r = cur.fetchone()
                    if r and r["m"]:
                        out["last_activity_at"] = r["m"].isoformat() + "Z" if hasattr(r["m"], "isoformat") else str(r["m"])
                    cur.execute(
                        """
                        SELECT COALESCE(SUM(LEAST(GREATEST(EXTRACT(EPOCH FROM (updated_at - started_at)) / 60.0, 0), %s)), 0) AS mins
                        FROM call_sessions
                        WHERE tenant_id = %s AND started_at >= %s AND updated_at <= %s
                        """,
                        (MAX_SESSION_MINUTES, tenant_id, start, end),
                    )
                    row = cur.fetchone()
                    if row and row["mins"] is not None:
                        out["minutes_total"] = int(round(float(row["mins"]), 0))
                    vapi_mins, vapi_cost = _get_vapi_usage_for_window(url, start, end, tenant_id=tenant_id)
                    if vapi_mins is not None and vapi_mins > 0:
                        out["minutes_total"] = int(round(vapi_mins, 0))
                    if vapi_cost is not None and vapi_cost >= 0:
                        out["cost_usd"] = round(vapi_cost, 4)
        except Exception as e:
            logger.warning("tenant stats pg failed: %s", e)
    else:
        import backend.db as db
        cid = _ivr_client_id(tenant_id)
        conn = db.get_conn()
        try:
            db._ensure_ivr_tables(conn)
            cur = conn.execute(
                """SELECT COUNT(DISTINCT call_id) FROM ivr_events
                   WHERE client_id = ? AND call_id IS NOT NULL AND TRIM(call_id) != '' AND created_at >= ? AND created_at <= ?""",
                (cid, start, end),
            )
            out["calls_total"] = cur.fetchone()[0] or 0
            cur = conn.execute(
                """SELECT COUNT(DISTINCT call_id) FROM ivr_events
                   WHERE client_id = ? AND created_at >= ? AND created_at <= ?
                     AND event IN ('user_abandon', 'abandon', 'hangup', 'user_hangup')""",
                (cid, start, end),
            )
            out["calls_abandoned"] = cur.fetchone()[0] or 0
            out["calls_answered"] = max(0, out["calls_total"] - out["calls_abandoned"])
            cur = conn.execute(
                """SELECT COUNT(*) FROM ivr_events WHERE client_id = ? AND created_at >= ? AND created_at <= ? AND event = 'booking_confirmed'""",
                (cid, start, end),
            )
            out["appointments_total"] = cur.fetchone()[0] or 0
            cur = conn.execute(
                """SELECT COUNT(*) FROM ivr_events WHERE client_id = ? AND created_at >= ? AND created_at <= ?
                   AND event IN ('transferred_human', 'transferred', 'transfer_human', 'transfer')""",
                (cid, start, end),
            )
            out["transfers_total"] = cur.fetchone()[0] or 0
            cur = conn.execute(
                """SELECT COUNT(*) FROM ivr_events WHERE client_id = ? AND created_at >= ? AND created_at <= ? AND event = 'anti_loop_trigger'""",
                (cid, start, end),
            )
            out["errors_total"] = cur.fetchone()[0] or 0
            cur = conn.execute(
                "SELECT MAX(created_at) FROM ivr_events WHERE client_id = ? AND created_at >= ? AND created_at <= ?",
                (cid, start, end),
            )
            r = cur.fetchone()
            if r and r[0]:
                out["last_activity_at"] = r[0].isoformat() + "Z" if hasattr(r[0], "isoformat") else str(r[0])
        finally:
            conn.close()
    return out


def _get_tenant_timeseries(tenant_id: int, metric: str, days: int) -> dict:
    """Série temporelle par jour pour un tenant. Sources = Postgres (Railway) en prod."""
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    points: List[dict] = []
    for i in range(days - 1, -1, -1):
        d = (now - timedelta(days=i)).date()
        date_str = d.strftime("%Y-%m-%d")
        start = date_str + " 00:00:00"
        end = date_str + " 23:59:59"
        value = 0
        if url:
            try:
                import psycopg
                with psycopg.connect(url) as conn:
                    with conn.cursor() as cur:
                        cid = _ivr_client_id(tenant_id)
                        if metric == "calls":
                            cur.execute(
                                """SELECT COUNT(DISTINCT call_id) FROM ivr_events
                                   WHERE client_id = %s AND call_id IS NOT NULL AND TRIM(call_id) != ''
                                     AND created_at >= %s AND created_at <= %s""",
                                (cid, start, end),
                            )
                            value = cur.fetchone()[0] or 0
                        elif metric == "appointments":
                            cur.execute(
                                """SELECT COUNT(*) FROM ivr_events
                                   WHERE client_id = %s AND event = 'booking_confirmed' AND created_at >= %s AND created_at <= %s""",
                                (cid, start, end),
                            )
                            value = cur.fetchone()[0] or 0
                        elif metric == "minutes":
                            try:
                                cur.execute(
                                    """SELECT COALESCE(SUM(duration_sec), 0) / 60.0 FROM vapi_call_usage
                                       WHERE tenant_id = %s AND ended_at IS NOT NULL AND ended_at >= %s AND ended_at <= %s""",
                                    (tenant_id, start, end),
                                )
                                vapi_val = cur.fetchone()[0]
                                if vapi_val is not None and float(vapi_val) > 0:
                                    value = int(round(float(vapi_val), 0))
                            except Exception:
                                pass
                            if value == 0:
                                cur.execute(
                                    """SELECT COALESCE(SUM(LEAST(GREATEST(EXTRACT(EPOCH FROM (updated_at - started_at)) / 60.0, 0), %s)), 0) FROM call_sessions
                                       WHERE tenant_id = %s AND started_at >= %s AND updated_at <= %s""",
                                    (MAX_SESSION_MINUTES, tenant_id, start, end),
                                )
                                value = int(cur.fetchone()[0] or 0)
            except Exception:
                pass
        else:
            import backend.db as db
            conn = db.get_conn()
            try:
                db._ensure_ivr_tables(conn)
                cid = _ivr_client_id(tenant_id)
                if metric == "calls":
                    cur = conn.execute(
                        """SELECT COUNT(DISTINCT call_id) FROM ivr_events
                           WHERE client_id = ? AND call_id IS NOT NULL AND TRIM(call_id) != '' AND created_at >= ? AND created_at <= ?""",
                        (cid, start, end),
                    )
                    value = cur.fetchone()[0] or 0
                elif metric == "appointments":
                    cur = conn.execute(
                        """SELECT COUNT(*) FROM ivr_events WHERE client_id = ? AND event = 'booking_confirmed' AND created_at >= ? AND created_at <= ?""",
                        (cid, start, end),
                    )
                    value = cur.fetchone()[0] or 0
            finally:
                conn.close()
        points.append({"date": date_str, "value": value})
    return {"metric": metric, "days": days, "points": points}


def _get_tenant_activity(tenant_id: int, limit: int) -> dict:
    """Timeline des derniers events ivr_events pour le tenant (preuve physique)."""
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    items: List[dict] = []
    if url:
        try:
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(url, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT created_at, call_id, event, context, reason
                        FROM ivr_events
                        WHERE client_id = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (_ivr_client_id(tenant_id), limit),
                    )
                    for r in cur.fetchall():
                        meta = {}
                        if r.get("context"):
                            meta["context"] = r["context"]
                        if r.get("reason"):
                            meta["reason"] = r["reason"]
                        items.append({
                            "date": r["created_at"].isoformat() + "Z" if hasattr(r["created_at"], "isoformat") else str(r["created_at"]),
                            "call_id": r.get("call_id") or "",
                            "event": r.get("event") or "",
                            "meta": meta if meta else None,
                        })
        except Exception as e:
            logger.warning("tenant activity pg failed: %s", e)
    else:
        import backend.db as db
        conn = db.get_conn()
        try:
            db._ensure_ivr_tables(conn)
            cur = conn.execute(
                """SELECT created_at, call_id, event, context, reason FROM ivr_events
                   WHERE client_id = ? ORDER BY created_at DESC LIMIT ?""",
                (_ivr_client_id(tenant_id), limit),
            )
            for row in cur.fetchall():
                meta = {}
                if row[3]:
                    meta["context"] = row[3]
                if row[4]:
                    meta["reason"] = row[4]
                items.append({
                    "date": row[0].isoformat() + "Z" if hasattr(row[0], "isoformat") else str(row[0]),
                    "call_id": row[1] or "",
                    "event": row[2] or "",
                    "meta": meta if meta else None,
                })
        finally:
            conn.close()
    return {"tenant_id": tenant_id, "event_count": len(items), "items": items}


def _get_billing_snapshot() -> dict:
    """Coût Vapi ce mois (UTC), top tenants par coût ce mois, tenants past_due. Ne dépend d'aucun prix Stripe."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    start_str = start.strftime("%Y-%m-%d %H:%M:%S")
    end_str = end.strftime("%Y-%m-%d %H:%M:%S")
    url_events = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    url_billing = os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL")
    out = {
        "cost_usd_this_month": 0.0,
        "top_tenants_by_cost_this_month": [],
        "tenants_past_due_count": 0,
        "tenant_ids_past_due": [],
        "tenants_past_due": [],
    }
    if url_events:
        try:
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(url_events, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT COALESCE(SUM(cost_usd), 0) AS total
                        FROM vapi_call_usage
                        WHERE ended_at IS NOT NULL AND ended_at >= %s AND ended_at < %s
                        """,
                        (start_str, end_str),
                    )
                    row = cur.fetchone()
                    if row:
                        out["cost_usd_this_month"] = round(float(row["total"] or 0), 4)
                    cur.execute(
                        """
                        SELECT tenant_id, COALESCE(SUM(cost_usd), 0) AS value
                        FROM vapi_call_usage
                        WHERE ended_at IS NOT NULL AND ended_at >= %s AND ended_at < %s
                        GROUP BY tenant_id ORDER BY value DESC LIMIT 10
                        """,
                        (start_str, end_str),
                    )
                    for r in cur.fetchall():
                        tid = r.get("tenant_id")
                        d = _get_tenant_detail(tid) if tid else {}
                        out["top_tenants_by_cost_this_month"].append({
                            "tenant_id": tid,
                            "name": d.get("name") or f"Tenant #{tid}",
                            "value": round(float(r.get("value") or 0), 4),
                        })
        except Exception as e:
            if "does not exist" not in str(e).lower():
                logger.warning("billing_snapshot vapi: %s", e)
    if url_billing:
        try:
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(url_billing, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT tb.tenant_id, tb.billing_status, tb.current_period_end, t.name
                        FROM tenant_billing tb
                        JOIN tenants t ON t.tenant_id = tb.tenant_id
                        WHERE tb.billing_status IN ('past_due', 'unpaid')
                        """,
                    )
                    rows = cur.fetchall()
                    out["tenant_ids_past_due"] = [int(r["tenant_id"]) for r in rows if r and r.get("tenant_id")]
                    out["tenants_past_due_count"] = len(out["tenant_ids_past_due"])
                    for r in rows:
                        tid = r.get("tenant_id")
                        if tid is None:
                            continue
                        period_end = r.get("current_period_end")
                        if period_end and hasattr(period_end, "isoformat"):
                            period_end = period_end.isoformat()
                        out["tenants_past_due"].append({
                            "tenant_id": int(tid),
                            "name": (r.get("name") or "").strip() or f"Tenant #{tid}",
                            "billing_status": r.get("billing_status") or "past_due",
                            "current_period_end": period_end,
                        })
        except Exception as e:
            if "does not exist" not in str(e).lower():
                logger.warning("billing_snapshot past_due: %s", e)
    return out


@router.get("/admin/stats/global")
def admin_stats_global(
    window_days: int = Query(7, ge=1, le=90, description="7 ou 30"),
    _: None = Depends(_verify_admin),
):
    """KPIs globaux : tenants, appels, RDV, transferts, erreurs, dernière activité."""
    return _get_global_stats(window_days)


def _get_operations_snapshot(window_days: int = 7) -> dict:
    """
    Snapshot unique pour /admin/operations : billing, suspensions, cost today/7d, errors.
    Tout en 1 appel. Today = UTC.
    Errors = event anti_loop_trigger (liste stricte).
    """
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    generated_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Billing : réutilise _get_billing_snapshot + month_utc
    billing = _get_billing_snapshot()
    billing["month_utc"] = now.strftime("%Y-%m")
    # Enrichir top_tenants_by_cost_this_month avec last_activity_at (1 seule requête groupée, pas de N+1)
    url_events = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    if url_events and billing.get("top_tenants_by_cost_this_month"):
        try:
            import psycopg
            from psycopg.rows import dict_row
            tids = [t["tenant_id"] for t in billing["top_tenants_by_cost_this_month"] if t.get("tenant_id") is not None]
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
            if tids:
                with psycopg.connect(url_events, row_factory=dict_row) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT client_id AS tenant_id, MAX(created_at) AS last_activity_at
                            FROM ivr_events
                            WHERE client_id = ANY(%s) AND created_at >= %s
                            GROUP BY client_id
                            """,
                            (tids, month_start),
                        )
                        last_by_tenant = {r["tenant_id"]: r["last_activity_at"] for r in cur.fetchall() if r.get("tenant_id")}
                for t in billing["top_tenants_by_cost_this_month"]:
                    la = last_by_tenant.get(t["tenant_id"])
                    t["last_activity_at"] = la.isoformat() + "Z" if la and hasattr(la, "isoformat") else (str(la) if la else None)
        except Exception as e:
            if "does not exist" not in str(e).lower():
                logger.warning("operations_snapshot last_activity: %s", e)

    # Suspensions : tenant_billing JOIN tenants
    url_billing = os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL")
    suspensions = {"suspended_total": 0, "items": []}
    if url_billing:
        try:
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(url_billing, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    try:
                        cur.execute(
                            """
                            SELECT tb.tenant_id, t.name, tb.suspension_reason AS reason, tb.suspension_mode AS mode,
                                   tb.suspended_at, tb.force_active_until
                            FROM tenant_billing tb
                            JOIN tenants t ON t.tenant_id = tb.tenant_id
                            WHERE tb.is_suspended = TRUE
                            ORDER BY tb.suspended_at DESC NULLS LAST
                            """,
                        )
                    except Exception:
                        cur.execute(
                            """
                            SELECT tb.tenant_id, t.name, tb.suspension_reason AS reason,
                                   tb.suspended_at, tb.force_active_until
                            FROM tenant_billing tb
                            JOIN tenants t ON t.tenant_id = tb.tenant_id
                            WHERE tb.is_suspended = TRUE
                            ORDER BY tb.suspended_at DESC NULLS LAST
                            """,
                        )
                    rows = cur.fetchall()
                    for r in rows:
                        mode = r.get("mode") if r.get("mode") else "hard"
                        suspended_at = r.get("suspended_at")
                        force_active_until = r.get("force_active_until")
                        if suspended_at and hasattr(suspended_at, "isoformat"):
                            suspended_at = suspended_at.isoformat() + "Z"
                        if force_active_until and hasattr(force_active_until, "isoformat"):
                            force_active_until = force_active_until.isoformat() + "Z"
                        suspensions["items"].append({
                            "tenant_id": int(r["tenant_id"]),
                            "name": (r.get("name") or "").strip() or f"Tenant #{r['tenant_id']}",
                            "reason": r.get("reason") or "manual",
                            "mode": mode,
                            "suspended_at": suspended_at,
                            "force_active_until": force_active_until,
                        })
                    suspensions["suspended_total"] = len(suspensions["items"])
        except Exception as e:
            if "does not exist" not in str(e).lower() and "tenant_billing" not in str(e).lower():
                logger.warning("operations_snapshot suspensions: %s", e)

    # Cost today UTC + last 7d (vapi_call_usage)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_str = today_start.strftime("%Y-%m-%d %H:%M:%S")
    end_str = now.strftime("%Y-%m-%d %H:%M:%S")
    seven_d_start = (today_start - timedelta(days=window_days))
    seven_d_str = seven_d_start.strftime("%Y-%m-%d %H:%M:%S")

    cost = {
        "today_utc": {"date_utc": today_start.strftime("%Y-%m-%d"), "total_usd": 0.0, "top": []},
        "last_7d": {"window_days": window_days, "total_usd": 0.0, "top": []},
    }
    if url_events:
        try:
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(url_events, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    for label, start_s, end_s in [("today_utc", today_str, end_str), ("last_7d", seven_d_str, end_str)]:
                        cur.execute(
                            """
                            SELECT COALESCE(SUM(cost_usd), 0) AS total
                            FROM vapi_call_usage
                            WHERE ended_at IS NOT NULL AND ended_at >= %s AND ended_at <= %s
                            """,
                            (start_s, end_s),
                        )
                        row = cur.fetchone()
                        cost[label]["total_usd"] = round(float(row["total"] or 0), 2)
                        cur.execute(
                            """
                            SELECT tenant_id, COALESCE(SUM(cost_usd), 0) AS value
                            FROM vapi_call_usage
                            WHERE ended_at IS NOT NULL AND ended_at >= %s AND ended_at <= %s
                            GROUP BY tenant_id ORDER BY value DESC LIMIT 5
                            """,
                            (start_s, end_s),
                        )
                        for r in cur.fetchall():
                            tid = r.get("tenant_id")
                            d = _get_tenant_detail(tid) if tid else {}
                            cost[label]["top"].append({
                                "tenant_id": tid,
                                "name": d.get("name") or f"Tenant #{tid}",
                                "value": round(float(r.get("value") or 0), 2),
                            })
        except Exception as e:
            if "does not exist" not in str(e).lower():
                logger.warning("operations_snapshot cost: %s", e)

    # Errors : top tenants par anti_loop_trigger (7j) + total
    errors = {"window_days": window_days, "top_tenants": [], "errors_total": 0}
    if url_events:
        try:
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(url_events, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT client_id AS tenant_id, COUNT(*) AS errors_total, MAX(created_at) AS last_error_at
                        FROM ivr_events
                        WHERE event = 'anti_loop_trigger' AND created_at >= %s AND created_at <= %s
                        GROUP BY client_id ORDER BY errors_total DESC LIMIT 10
                        """,
                        (seven_d_str, end_str),
                    )
                    for r in cur.fetchall():
                        tid = r.get("tenant_id")
                        d = _get_tenant_detail(tid) if tid else {}
                        last_at = r.get("last_error_at")
                        if last_at and hasattr(last_at, "isoformat"):
                            last_at = last_at.isoformat() + "Z"
                        errors["top_tenants"].append({
                            "tenant_id": tid,
                            "name": d.get("name") or f"Tenant #{tid}",
                            "errors_total": int(r.get("errors_total") or 0),
                            "last_error_at": last_at,
                        })
                    cur.execute(
                        """
                        SELECT COUNT(*) AS c FROM ivr_events
                        WHERE event = 'anti_loop_trigger' AND created_at >= %s AND created_at <= %s
                        """,
                        (seven_d_str, end_str),
                    )
                    row = cur.fetchone()
                    errors["errors_total"] = int(row["c"] or 0)
        except Exception as e:
            if "does not exist" not in str(e).lower():
                logger.warning("operations_snapshot errors: %s", e)

    return {
        "generated_at": generated_at,
        "billing": billing,
        "suspensions": suspensions,
        "cost": cost,
        "errors": errors,
    }


def _get_quality_snapshot(window_days: int = 7) -> dict:
    """
    Snapshot Quality : KPIs + top tenants par anti_loop, abandons, transferts.
    Source ivr_events (PG prioritaire). UTC.
    """
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=window_days)).strftime("%Y-%m-%d 00:00:00")
    end = now.strftime("%Y-%m-%d %H:%M:%S")
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")

    kpis = {"calls_total": 0, "abandons": 0, "transfers": 0, "anti_loop": 0, "appointments": 0}
    top = {"anti_loop": [], "abandons": [], "transfers": []}

    if url:
        try:
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(url, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT COUNT(DISTINCT call_id) AS c FROM ivr_events
                        WHERE call_id IS NOT NULL AND TRIM(call_id) != '' AND created_at >= %s AND created_at <= %s
                        """,
                        (start, end),
                    )
                    kpis["calls_total"] = cur.fetchone()["c"] or 0
                    cur.execute(
                        """
                        SELECT event, COUNT(*) AS cnt FROM ivr_events
                        WHERE created_at >= %s AND created_at <= %s GROUP BY event
                        """,
                        (start, end),
                    )
                    by_event = {r["event"]: r["cnt"] for r in cur.fetchall()}
                    abandon_events = ("user_abandon", "abandon", "hangup", "user_hangup")
                    transfer_events = ("transferred_human", "transferred", "transfer_human", "transfer")
                    kpis["abandons"] = sum(by_event.get(e, 0) for e in abandon_events)
                    kpis["transfers"] = sum(by_event.get(e, 0) for e in transfer_events)
                    kpis["anti_loop"] = by_event.get("anti_loop_trigger", 0)
                    kpis["appointments"] = by_event.get("booking_confirmed", 0)

                    for metric, event_filter, event_list in [
                        ("anti_loop", "event = 'anti_loop_trigger'", ["anti_loop_trigger"]),
                        ("abandons", "event IN ('user_abandon', 'abandon', 'hangup', 'user_hangup')", list(abandon_events)),
                        ("transfers", "event IN ('transferred_human', 'transferred', 'transfer_human', 'transfer')", list(transfer_events)),
                    ]:
                        cur.execute(
                            f"""
                            SELECT client_id AS tenant_id, COUNT(*) AS count, MAX(created_at) AS last_at
                            FROM ivr_events
                            WHERE {event_filter} AND created_at >= %s AND created_at <= %s
                            GROUP BY client_id ORDER BY count DESC LIMIT 10
                            """,
                            (start, end),
                        )
                        for r in cur.fetchall():
                            tid = r.get("tenant_id")
                            d = _get_tenant_detail(tid) if tid else {}
                            last_at = r.get("last_at")
                            if last_at and hasattr(last_at, "isoformat"):
                                last_at = last_at.isoformat() + "Z"
                            top[metric].append({
                                "tenant_id": tid,
                                "name": d.get("name") or f"Tenant #{tid}",
                                "count": int(r.get("count") or 0),
                                "last_at": last_at,
                            })
        except Exception as e:
            if "does not exist" not in str(e).lower():
                logger.warning("quality_snapshot failed: %s", e)

    abandon_rate = (kpis["abandons"] / kpis["calls_total"] * 100) if kpis["calls_total"] else 0
    return {
        "window_days": window_days,
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kpis": {**kpis, "abandon_rate_pct": round(abandon_rate, 1)},
        "top": top,
    }


@router.get("/admin/stats/billing-snapshot")
def admin_stats_billing_snapshot(
    _: None = Depends(_verify_admin),
):
    """Coût Vapi ce mois (UTC), top tenants par coût ce mois, nombre de tenants past_due. Sans prix Stripe."""
    return _get_billing_snapshot()


@router.get("/admin/stats/operations-snapshot")
def admin_stats_operations_snapshot(
    window_days: int = Query(7, ge=1, le=30),
    _: None = Depends(_verify_admin),
):
    """Snapshot unique pour /admin/operations : billing, suspensions, cost today/7d, errors. 1 seul fetch côté front."""
    return _get_operations_snapshot(window_days)


@router.get("/admin/stats/quality-snapshot")
def admin_stats_quality_snapshot(
    window_days: int = Query(7, ge=1, le=90),
    _: None = Depends(_verify_admin),
):
    """Snapshot Quality : KPIs (appels, abandons, transferts, anti_loop, RDV, taux abandon) + top 10 par problème. Drill-down vers /admin/calls?result=."""
    return _get_quality_snapshot(window_days)


@router.get("/admin/stats/timeseries")
def admin_stats_timeseries(
    metric: str = Query("calls", description="calls | appointments | minutes | cost_usd"),
    days: int = Query(30, ge=7, le=90),
    _: None = Depends(_verify_admin),
):
    """Série temporelle par jour pour graph."""
    if metric not in ("calls", "appointments", "minutes", "cost_usd"):
        metric = "calls"
    return _get_stats_timeseries(metric, days)


@router.get("/admin/stats/top-tenants")
def admin_stats_top_tenants(
    metric: str = Query("minutes", description="minutes | calls | appointments | cost_usd"),
    window_days: int = Query(30, ge=1, le=90),
    limit: int = Query(10, ge=1, le=50),
    _: None = Depends(_verify_admin),
):
    """Top tenants par métrique."""
    if metric not in ("minutes", "calls", "appointments", "cost_usd"):
        metric = "calls"
    return _get_stats_top_tenants(metric, window_days, limit)


@router.get("/admin/stats/tenants/{tenant_id}")
def admin_stats_tenant(
    tenant_id: int = Depends(validate_tenant_id),
    window_days: int = Query(7, ge=1, le=90, description="7 ou 30"),
    _: None = Depends(_verify_admin),
):
    """KPIs pour un tenant (calls, abandons, RDV, transferts, minutes, dernière activité)."""
    return _get_tenant_stats(tenant_id, window_days)


@router.get("/admin/stats/tenants/{tenant_id}/timeseries")
def admin_stats_tenant_timeseries(
    tenant_id: int = Depends(validate_tenant_id),
    metric: str = Query("calls", description="calls | appointments | minutes"),
    days: int = Query(30, ge=7, le=90),
    _: None = Depends(_verify_admin),
):
    """Série temporelle par jour pour un tenant."""
    if metric not in ("calls", "appointments", "minutes"):
        metric = "calls"
    return _get_tenant_timeseries(tenant_id, metric, days)


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
