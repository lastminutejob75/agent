# backend/routes/admin.py
"""
API admin / onboarding pour uwi-landing (Vite SPA).
- POST /public/onboarding (public)
- POST /api/admin/auth/login, GET /api/admin/auth/me, POST /api/admin/auth/logout (cookie session)
- GET/PATCH /admin/* (cookie session uwi_admin_session OU Bearer JWT session = même secret que cookie)
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import jwt
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field

from backend import config
from backend.deps import validate_tenant_id
from backend.auth_pg import pg_add_tenant_user, pg_create_tenant_user, pg_get_tenant_user_by_email
from backend.billing_pg import (
    get_billing_plans,
    get_plan_included_minutes,
    get_tenant_billing,
    load_cockpit_plan_quota_inputs_batch,
    set_force_active,
    set_stripe_customer_id,
    set_tenant_suspended,
    set_tenant_unsuspended,
    tenant_id_by_stripe_customer_id,
    upsert_billing_from_subscription,
)
from backend.tenants_pg import (
    pg_add_routing,
    pg_create_tenant,
    pg_delete_tenant_param_keys,
    pg_delete_tenant,
    pg_deactivate_tenant,
    pg_fetch_tenants,
    pg_get_tenant_full,
    pg_get_tenant_flags,
    pg_get_tenant_params,
    pg_get_routing_for_tenant,
    pg_update_tenant_flags,
    pg_update_tenant_params,
)
from backend.tenant_config import (
    convert_opening_hours_to_booking_rules,
    derive_horaires_text,
    get_faq,
    normalize_faq_payload,
    reset_faq_params,
    set_params,
)
from backend.vapi_utils import update_vapi_assistant_faq
from backend.cabinet_profile_pg import (
    DAY_KEYS,
    get_assistant_settings as pg_get_assistant_settings,
    get_availability_settings as pg_get_availability_settings,
    get_booking_rules as pg_get_booking_rules,
    get_opening_hours as pg_get_opening_hours,
    get_profile as pg_get_profile,
    list_appointment_reasons as pg_list_appointment_reasons,
    sync_normalized_from_params,
    sync_opening_hours_from_booking_rules,
)
from backend.dashboard_cockpit import (
    dash_build_action_items,
    dash_build_summary,
    dash_leads_block,
    dash_watchlist_items,
    dash_window_days,
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
        from backend.pg_pool import pg_connection_for

        with pg_connection_for(url) as conn:
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
                if row and (row.get("mins") or row.get("cost")):
                    return (float(row.get("mins") or 0), float(row.get("cost") or 0))
                return (None, None)
    except Exception as e:
        if "does not exist" not in str(e).lower() and "vapi_call_usage" not in str(e).lower():
            logger.debug("vapi_usage agg: %s", e)
        return (None, None)


def _normalize_call_result(result: Optional[str]) -> str:
    value = (result or "").strip().lower()
    if value in {"rdv", "transfer", "abandoned", "error", "other"}:
        return value
    return "other"


def _snapshot_outcome_from_sources(last_event: Optional[str], status: Optional[str], ended_reason: Optional[str]) -> str:
    event = (last_event or "").strip()
    if event == "booking_confirmed":
        return "booking_confirmed"
    if event in ("transferred_human", "transferred", "transfer_human", "transfer"):
        return "transferred_human"
    if event in ("user_abandon", "abandon", "hangup", "user_hangup"):
        return "user_abandon"
    result_val = _normalize_call_result(_vapi_call_result_from_status(status, ended_reason))
    if result_val == "transfer":
        return "transferred_human"
    if result_val == "abandoned":
        return "user_abandon"
    return "unknown"


def _build_call_item_from_vapi_row(row: dict, tenant_name: str) -> dict:
    started_at = row.get("started_at")
    sort_ts = row.get("sort_ts") or row.get("ended_at") or row.get("updated_at") or started_at
    duration_sec: Optional[int] = None
    raw_duration = row.get("duration_sec")
    if raw_duration is not None:
        duration_sec = int(float(raw_duration))
    elif started_at and sort_ts:
        delta_secs = (sort_ts - started_at).total_seconds()
        delta_secs = max(0, min(MAX_SESSION_MINUTES * 60, delta_secs))
        if delta_secs >= 1:
            duration_sec = int(delta_secs)
    result_val = _normalize_call_result(
        _call_result_from_event(row.get("last_event"))
        if row.get("last_event")
        else _vapi_call_result_from_status(row.get("status"), row.get("ended_reason"))
    )
    return {
        "call_id": row.get("call_id") or "",
        "tenant_id": row.get("tenant_id"),
        "tenant_name": tenant_name,
        "customer_number": (row.get("customer_number") or "").strip(),
        "started_at": _iso_utc(started_at),
        "last_event_at": _iso_utc(sort_ts),
        "last_event": row.get("last_event") or row.get("ended_reason") or row.get("status") or "",
        "result": result_val,
        "duration_min": (duration_sec // 60) if duration_sec is not None else None,
        "duration_sec": duration_sec,
    }


def _fetch_vapi_call_items_pg(
    tenant_id: int,
    start: str,
    end: str,
    limit: int,
    tenant_name: str,
    cursor: Optional[str] = None,
    result_filter: Optional[str] = None,
) -> tuple[list[dict], Optional[str]]:
    from backend.pg_pool import pg_connection

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

    items: list[dict] = []
    next_cursor: Optional[str] = None
    with pg_connection() as conn:
        from backend.pg_tenant_context import set_tenant_id_on_connection

        set_tenant_id_on_connection(conn, tenant_id)
        with conn.cursor() as cur:
            params: list = [tenant_id, start, end]
            cursor_filter = ""
            if cursor_ts and cursor_id:
                cursor_filter = """
                    AND (
                        COALESCE(v.ended_at, v.updated_at, v.started_at, v.created_at) < %s::timestamptz
                        OR (
                            COALESCE(v.ended_at, v.updated_at, v.started_at, v.created_at) = %s::timestamptz
                            AND v.call_id < %s
                        )
                    )
                """
                params.extend([cursor_ts, cursor_ts, cursor_id])
            params.append(limit + 1)
            cur.execute(
                """
                SELECT
                    v.tenant_id,
                    v.call_id,
                    v.customer_number,
                    COALESCE(v.started_at, v.created_at) AS started_at,
                    v.ended_at,
                    v.updated_at,
                    COALESCE(v.ended_at, v.updated_at, v.started_at, v.created_at) AS sort_ts,
                    v.status,
                    v.ended_reason,
                    u.duration_sec,
                    ie.last_event
                FROM vapi_calls v
                LEFT JOIN vapi_call_usage u
                    ON u.tenant_id = v.tenant_id
                   AND u.vapi_call_id = v.call_id
                LEFT JOIN LATERAL (
                    SELECT event AS last_event
                    FROM ivr_events
                    WHERE client_id = v.tenant_id AND call_id = v.call_id
                    ORDER BY created_at DESC
                    LIMIT 1
                ) ie ON TRUE
                WHERE v.tenant_id = %s
                  AND COALESCE(v.ended_at, v.updated_at, v.started_at, v.created_at) >= %s
                  AND COALESCE(v.ended_at, v.updated_at, v.started_at, v.created_at) <= %s
                  """ + cursor_filter + """
                ORDER BY COALESCE(v.ended_at, v.updated_at, v.started_at, v.created_at) DESC, v.call_id DESC
                LIMIT %s
                """,
                tuple(params),
            )
            rows = [dict(r) for r in cur.fetchall()]

    for row in rows[: limit + 1]:
        item = _build_call_item_from_vapi_row(row, tenant_name)
        if result_filter and item["result"] != result_filter:
            continue
        items.append(item)

    items.sort(key=lambda x: ((x.get("last_event_at") or ""), (x.get("call_id") or "")), reverse=True)
    if len(items) > limit:
        last_item = items[limit - 1]
        t_iso = str(last_item.get("last_event_at") or "")
        c_id = last_item.get("call_id") or ""
        next_cursor = base64.urlsafe_b64encode(json.dumps({"t": t_iso, "c": c_id}).encode()).decode().rstrip("=")
        items = items[:limit]
    return items, next_cursor


router = APIRouter(prefix="/api", tags=["admin"])
_security = HTTPBearer(auto_error=False)

# Auth admin = email + mot de passe (bcrypt) → cookie HttpOnly `uwi_admin_session`.
# ADMIN_API_TOKEN supprimé en prod (secret machine partagé = compromission totale en cas de vol).
# Seul vestige : back-door pytest pour ne pas réécrire toute la suite tests.
def _pytest_admin_token() -> str:
    """Retourne le token admin de test si on tourne sous pytest, vide sinon."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return (os.environ.get("ADMIN_API_TOKEN") or "").strip()
    return ""
ADMIN_EMAIL = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()
ADMIN_PASSWORD = (os.environ.get("ADMIN_PASSWORD") or "").strip()  # Déprécié : préférer ADMIN_PASSWORD_HASH
ADMIN_PASSWORD_HASH = (os.environ.get("ADMIN_PASSWORD_HASH") or "").strip()  # bcrypt hash (recommandé en prod)
ADMIN_SESSION_COOKIE = "uwi_admin_session"
def _jwt_secret_admin() -> str:
    from backend.security import admin_session_secret

    return admin_session_secret()


JWT_SECRET_ADMIN = _jwt_secret_admin()
ADMIN_SESSION_EXPIRES_HOURS = int(os.environ.get("ADMIN_SESSION_EXPIRES_HOURS") or "8")
# Cross-domain (front uwiapp.com / API Railway) : SameSite=None; Secure. Même domaine (api.uwiapp.com) : Lax.
ADMIN_COOKIE_SAMESITE = (os.environ.get("ADMIN_COOKIE_SAMESITE") or "").strip().lower() or None


def _get_admin_email_from_cookie(request: Request) -> Optional[str]:
    """Lit et valide le JWT admin depuis le cookie. Retourne l'email si valide, sinon None."""
    return _decode_admin_session_jwt(request.cookies.get(ADMIN_SESSION_COOKIE))


def _decode_admin_session_jwt(raw: Optional[str]) -> Optional[str]:
    """JWT cockpit scope=admin (même valeur que cookie ou session_token renvoyé au login)."""
    if not raw or not str(raw).strip():
        return None
    if not JWT_SECRET_ADMIN or not ADMIN_EMAIL:
        return None
    try:
        payload = jwt.decode(str(raw).strip(), JWT_SECRET_ADMIN, algorithms=["HS256"])
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
    Accès admin : 1) cookie `uwi_admin_session` (préféré), 2) Bearer JWT session (même secret).
    - 503 : auth admin non configurée (ADMIN_EMAIL + ADMIN_PASSWORD_HASH manquants)
    - 401 : non authentifié
    """
    if not (ADMIN_EMAIL and (ADMIN_PASSWORD or ADMIN_PASSWORD_HASH)):
        raise HTTPException(503, "Admin API not configured (ADMIN_EMAIL + ADMIN_PASSWORD_HASH required)")

    if JWT_SECRET_ADMIN:
        cookie_email = _get_admin_email_from_cookie(request)
        if cookie_email:
            logger.info(
                "admin_access path=%s client=%s auth=cookie",
                request.url.path,
                request.client.host if request.client else None,
            )
            return

    bearer = (credentials.credentials or "").strip() if credentials else ""
    if not bearer:
        raise HTTPException(401, "Missing credentials (cookie or Bearer required)")

    if JWT_SECRET_ADMIN and _decode_admin_session_jwt(bearer):
        logger.info(
            "admin_access path=%s client=%s auth=bearer_session",
            request.url.path,
            request.client.host if request.client else None,
        )
        return

    # Back-door pytest uniquement (PYTEST_CURRENT_TEST automatique, jamais set en prod).
    pytest_tok = _pytest_admin_token()
    if pytest_tok and bearer == pytest_tok:
        return

    raise HTTPException(401, "Invalid or expired token")


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


class ProvisionAccessBody(BaseModel):
    """Crée ou met à jour le compte login client et envoie l'email de première connexion."""
    email: Optional[str] = Field(default=None, max_length=255)
    name: Optional[str] = Field(default=None, max_length=120)


class TenantCreateIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    contact_email: str = Field(..., max_length=255)
    timezone: str = Field(default="Europe/Paris", max_length=64)
    business_type: Optional[str] = Field(default=None, max_length=64)
    notes: Optional[str] = Field(default=None, max_length=2000)
    plan_key: Optional[str] = Field(default="", max_length=64)
    billing_email: Optional[str] = Field(default=None, max_length=255)
    initial_status: Optional[str] = Field(default="active", max_length=32)


class TenantOut(BaseModel):
    tenant_id: int
    name: str
    contact_email: str
    timezone: str
    business_type: Optional[str] = None
    created_at: str


class CreateTenantRequest(BaseModel):
    """Création tenant complète : DB + Vapi + Stripe + Twilio + email."""

    name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(..., min_length=5, max_length=32)
    sector: str = Field(
        ...,
        pattern="^(medecin_generaliste|specialiste|kine|dentiste|infirmier)$",
    )
    plan_key: str = Field(..., pattern="^(starter|growth|pro)$")
    assistant_id: str = Field(..., min_length=2, max_length=32)
    twilio_number: Optional[str] = Field(default=None, max_length=32)
    timezone: str = Field(default="Europe/Paris", max_length=64)
    send_welcome: bool = Field(default=True)
    booking_rules: Optional[Dict[str, Any]] = None
    lead_id: Optional[str] = Field(default=None, max_length=64)


class HorairesBody(BaseModel):
    booking_days: List[int]
    booking_start_hour: int
    booking_end_hour: int
    booking_duration_minutes: int
    booking_buffer_minutes: int


# --- Helpers ---


def _validate_horaires_payload(body: HorairesBody) -> Dict[str, Any]:
    booking_days = sorted({int(day) for day in (body.booking_days or []) if 0 <= int(day) <= 6})
    if not booking_days:
        raise HTTPException(status_code=400, detail="Au moins un jour doit être sélectionné.")
    if not 6 <= int(body.booking_start_hour) <= 22:
        raise HTTPException(status_code=400, detail="Heure de début invalide.")
    if not 6 <= int(body.booking_end_hour) <= 22:
        raise HTTPException(status_code=400, detail="Heure de fin invalide.")
    if int(body.booking_end_hour) <= int(body.booking_start_hour):
        raise HTTPException(status_code=400, detail="L'heure de fin doit être après l'heure de début.")
    if not 5 <= int(body.booking_duration_minutes) <= 120:
        raise HTTPException(status_code=400, detail="Durée de rendez-vous invalide.")
    if not 0 <= int(body.booking_buffer_minutes) <= 120:
        raise HTTPException(status_code=400, detail="Buffer invalide.")
    return {
        "booking_days": booking_days,
        "booking_start_hour": int(body.booking_start_hour),
        "booking_end_hour": int(body.booking_end_hour),
        "booking_duration_minutes": int(body.booking_duration_minutes),
        "booking_buffer_minutes": int(body.booking_buffer_minutes),
    }


def _norm_text(value: Any) -> str:
    return str(value or "").strip()


def _norm_bool(value: Any, fallback: bool = False) -> bool:
    if value is None:
        return fallback
    if isinstance(value, bool):
        return value
    txt = str(value).strip().lower()
    return txt in {"1", "true", "yes", "oui", "on"}


def _norm_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return fallback


def _norm_list_of_text(value: Any) -> list[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            value = []
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()]


def _build_expected_opening_hours_from_params(params: dict) -> list[dict]:
    booking_days = params.get("booking_days")
    if isinstance(booking_days, str):
        try:
            booking_days = json.loads(booking_days)
        except Exception:
            booking_days = []
    if not isinstance(booking_days, list):
        booking_days = []
    open_idx = {int(v) for v in booking_days if str(v).strip().isdigit()}
    start_hour = _norm_int(params.get("booking_start_hour"), 9)
    end_hour = _norm_int(params.get("booking_end_hour"), 18)
    rows = []
    for idx, day in enumerate(DAY_KEYS):
        is_open = idx in open_idx
        rows.append(
            {
                "day": day,
                "is_open": is_open,
                "morning_start": f"{start_hour:02d}:00" if is_open else "",
                "morning_end": "12:30" if is_open else "",
                "afternoon_start": "14:00" if is_open else "",
                "afternoon_end": f"{end_hour:02d}:00" if is_open else "",
            }
        )
    return rows


def _audit_mismatch_map(expected: dict, actual: Optional[dict], defaults: Optional[dict] = None) -> dict:
    defaults = defaults or {}
    actual = actual or {}
    mismatches: list[dict] = []
    for key, exp in expected.items():
        act = actual.get(key, defaults.get(key))
        if act != exp:
            mismatches.append({"field": key, "expected": exp, "actual": act})
    return {"total_fields": len(expected), "mismatch_count": len(mismatches), "mismatches": mismatches}


def _audit_opening_hours(expected_rows: list[dict], actual_rows: Optional[list[dict]]) -> dict:
    actual_rows = actual_rows or []
    by_day = {str(r.get("day")): r for r in actual_rows if isinstance(r, dict)}
    mismatches: list[dict] = []
    for row in expected_rows:
        day = row.get("day")
        actual = by_day.get(day) or {}
        for key in ("is_open", "morning_start", "morning_end", "afternoon_start", "afternoon_end"):
            exp = row.get(key)
            act = actual.get(key, "" if key != "is_open" else False)
            if act != exp:
                mismatches.append(
                    {
                        "day": day,
                        "field": key,
                        "expected": exp,
                        "actual": act,
                    }
                )
    return {"expected_days": len(expected_rows), "actual_days": len(actual_rows), "mismatch_count": len(mismatches), "mismatches": mismatches}


def _audit_appointment_reasons(expected_rows: list[dict], actual_rows: Optional[list[dict]]) -> dict:
    actual_rows = actual_rows or []
    expected_by_id = {str(r.get("id")): r for r in expected_rows if str(r.get("id", "")).strip()}
    actual_by_id = {str(r.get("id")): r for r in actual_rows if str(r.get("id", "")).strip()}
    mismatches: list[dict] = []
    missing_ids = sorted([rid for rid in expected_by_id if rid not in actual_by_id])
    extra_ids = sorted([rid for rid in actual_by_id if rid not in expected_by_id])
    for rid, exp in expected_by_id.items():
        act = actual_by_id.get(rid)
        if not act:
            continue
        for field in ("label", "duration_minutes", "description", "enabled", "allowed_for_new_patients"):
            if act.get(field) != exp.get(field):
                mismatches.append(
                    {
                        "id": rid,
                        "field": field,
                        "expected": exp.get(field),
                        "actual": act.get(field),
                    }
                )
    return {
        "expected_count": len(expected_rows),
        "actual_count": len(actual_rows),
        "missing_ids": missing_ids,
        "extra_ids": extra_ids,
        "mismatch_count": len(mismatches) + len(missing_ids) + len(extra_ids),
        "mismatches": mismatches,
    }


def _build_cabinet_profile_audit(tenant_id: int) -> dict:
    params_payload = pg_get_tenant_params(tenant_id)
    params = (params_payload or ({}, "none"))[0] or {}
    source = (params_payload or ({}, "none"))[1]

    profile_expected = {
        "practitioner_name": _norm_text(params.get("practitioner_name")),
        "cabinet_name": _norm_text(params.get("business_name")),
        "specialty": _norm_text(params.get("specialty_label")),
        "phone": _norm_text(params.get("phone_number")),
        "email": _norm_text(params.get("contact_email")),
        "address_line": _norm_text(params.get("address_line1")),
        "postal_code": _norm_text(params.get("postal_code")),
        "city": _norm_text(params.get("city")),
        "website_url": _norm_text(params.get("website_url")),
        "languages": _norm_list_of_text(params.get("languages")),
        "accepts_new_patients": _norm_bool(params.get("accepts_new_patients"), True),
        "practitioner_photo_url": _norm_text(params.get("practitioner_photo_url")),
        "public_slug": _norm_text(params.get("public_slug")),
    }
    profile_actual = pg_get_profile(tenant_id)

    availability_expected = {
        "temporary_closure_enabled": _norm_bool(params.get("temporary_closure_enabled"), False),
        "temporary_closure_start": _norm_text(params.get("temporary_closure_start")),
        "temporary_closure_end": _norm_text(params.get("temporary_closure_end")),
        "temporary_closure_message": _norm_text(params.get("temporary_closure_message")),
    }
    availability_actual = pg_get_availability_settings(tenant_id)

    booking_expected = {
        "default_appointment_duration_minutes": _norm_int(params.get("default_appointment_duration_minutes"), 30),
        "minimum_booking_notice_hours": _norm_int(params.get("minimum_booking_notice_hours"), 24),
        "accepts_new_patients": _norm_bool(params.get("accepts_new_patients"), True),
        "appointment_reschedule_allowed": _norm_bool(params.get("appointment_reschedule_allowed"), True),
        "appointment_reschedule_notice_hours": _norm_int(params.get("appointment_reschedule_notice_hours"), 24),
        "appointment_cancel_allowed": _norm_bool(params.get("appointment_cancel_allowed"), True),
        "appointment_cancel_notice_hours": _norm_int(params.get("appointment_cancel_notice_hours"), 24),
        "emergency_instruction": _norm_text(params.get("emergency_instruction")),
        "new_patient_instruction": _norm_text(params.get("new_patient_instruction")),
        "booking_notes": _norm_text(params.get("booking_notes")),
    }
    booking_actual = pg_get_booking_rules(tenant_id)

    assistant_expected = {
        "assistant_name": _norm_text(params.get("assistant_name")),
        "welcome_message": _norm_text(params.get("welcome_message")),
        "documents_to_bring": _norm_text(params.get("documents_to_bring")),
        "access_instructions": _norm_text(params.get("access_instructions")),
        "payment_methods": _norm_text(params.get("payment_methods")),
        "parking_info": _norm_text(params.get("parking_info")),
        "pmr_access": _norm_text(params.get("pmr_access")),
        "sensitive_medical_instruction": _norm_text(params.get("sensitive_medical_instruction")),
        "escalation_instruction": _norm_text(params.get("escalation_instruction")),
        "human_handoff_instruction": _norm_text(params.get("human_handoff_instruction")),
        "faq_items": params.get("faq_items_json") if isinstance(params.get("faq_items_json"), list) else [],
    }
    assistant_actual = pg_get_assistant_settings(tenant_id)

    expected_opening_hours = _build_expected_opening_hours_from_params(params)
    actual_opening_hours = pg_get_opening_hours(tenant_id)

    reasons_expected_raw = params.get("appointment_reasons_json")
    if isinstance(reasons_expected_raw, str):
        try:
            reasons_expected_raw = json.loads(reasons_expected_raw)
        except Exception:
            reasons_expected_raw = []
    if not isinstance(reasons_expected_raw, list):
        reasons_expected_raw = []
    reasons_expected = []
    for row in reasons_expected_raw:
        if not isinstance(row, dict):
            continue
        rid = _norm_text(row.get("id"))
        if not rid:
            continue
        reasons_expected.append(
            {
                "id": rid,
                "label": _norm_text(row.get("label")),
                "duration_minutes": _norm_int(row.get("duration_minutes"), 30),
                "description": _norm_text(row.get("description")),
                "enabled": _norm_bool(row.get("enabled"), True),
                "allowed_for_new_patients": _norm_bool(row.get("allowed_for_new_patients"), True),
            }
        )
    reasons_actual = pg_list_appointment_reasons(tenant_id)

    profile_audit = _audit_mismatch_map(profile_expected, profile_actual, defaults={"accepts_new_patients": True, "languages": []})
    availability_audit = _audit_mismatch_map(availability_expected, availability_actual, defaults={"temporary_closure_enabled": False})
    booking_audit = _audit_mismatch_map(
        booking_expected,
        booking_actual,
        defaults={
            "default_appointment_duration_minutes": 30,
            "minimum_booking_notice_hours": 24,
            "accepts_new_patients": True,
            "appointment_reschedule_allowed": True,
            "appointment_reschedule_notice_hours": 24,
            "appointment_cancel_allowed": True,
            "appointment_cancel_notice_hours": 24,
        },
    )
    assistant_audit = _audit_mismatch_map(assistant_expected, assistant_actual, defaults={"faq_items": []})
    opening_hours_audit = _audit_opening_hours(expected_opening_hours, actual_opening_hours)
    reasons_audit = _audit_appointment_reasons(reasons_expected, reasons_actual)

    total_mismatches = (
        profile_audit["mismatch_count"]
        + availability_audit["mismatch_count"]
        + booking_audit["mismatch_count"]
        + assistant_audit["mismatch_count"]
        + opening_hours_audit["mismatch_count"]
        + reasons_audit["mismatch_count"]
    )

    return {
        "tenant_id": tenant_id,
        "params_source": source,
        "params_present": bool(params),
        "summary": {
            "total_mismatch_count": total_mismatches,
            "is_fully_synced": total_mismatches == 0,
        },
        "sections": {
            "profile": profile_audit,
            "availability_settings": availability_audit,
            "booking_rules": booking_audit,
            "assistant_settings": assistant_audit,
            "opening_hours": opening_hours_audit,
            "appointment_reasons": reasons_audit,
        },
    }


def _get_tenant_list(include_inactive: bool = False) -> List[dict]:
    """Liste tenants (PG-first, fallback SQLite). Enrichit avec params tenant_config pour recherche admin."""
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
            rows = conn.execute(
                """
                SELECT t.tenant_id, t.name, t.status, tc.params_json
                FROM tenants t
                LEFT JOIN tenant_config tc ON tc.tenant_id = t.tenant_id
                ORDER BY t.tenant_id
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT t.tenant_id, t.name, t.status, tc.params_json
                FROM tenants t
                LEFT JOIN tenant_config tc ON tc.tenant_id = t.tenant_id
                WHERE COALESCE(t.status,'active')='active'
                ORDER BY t.tenant_id
                """
            ).fetchall()
        out: List[dict] = []
        for r in rows:
            params = {}
            if r[3]:
                try:
                    params = json.loads(r[3]) if isinstance(r[3], str) else (r[3] if isinstance(r[3], dict) else {})
                except Exception:
                    params = {}
            out.append({
                "tenant_id": r[0],
                "name": r[1],
                "status": r[2],
                "contact_email": (params.get("contact_email") or "").strip(),
                "profession": (params.get("profession") or "").strip(),
                "city": (params.get("city") or "").strip(),
                "primary_practitioner_name": (params.get("primary_practitioner_name") or "").strip(),
                "plan_key_params": (params.get("plan_key") or "").strip(),
            })
        return out
    finally:
        conn.close()


def _get_admin_tenants_summary(period_days: int) -> dict:
    """Agrégats pour la liste admin clients : effectifs, alertes synthétiques, minutes vocales parc."""
    period_days = int(max(1, min(int(period_days or 30), 366)))
    tenants = _get_tenant_list(include_inactive=True) or []

    active = 0
    onboarding = 0
    suspended = 0
    for t in tenants:
        st = str(t.get("status") or "active").strip().lower()
        if st == "active":
            active += 1
        elif st == "suspended":
            suspended += 1
        elif st in ("pending_payment", "inactive"):
            onboarding += 1

    alert_tids: set = set()
    try:
        for it in (_get_activation_queue(400).get("items") or []):
            tid = it.get("tenant_id")
            if tid is not None:
                alert_tids.add(int(tid))
    except Exception:
        pass
    try:
        bill = _get_billing_snapshot()
        for row in bill.get("tenants_past_due") or []:
            tid = row.get("tenant_id")
            if tid is not None:
                alert_tids.add(int(tid))
    except Exception:
        pass
    try:
        ops = _get_operations_snapshot(window_days=min(30, period_days))
        for row in (ops.get("quota") or {}).get("over_100") or []:
            tid = row.get("tenant_id")
            if tid is not None:
                alert_tids.add(int(tid))
        for row in (ops.get("errors") or {}).get("top_tenants") or []:
            if int(row.get("errors_total") or 0) >= 8:
                tid = row.get("tenant_id")
                if tid is not None:
                    alert_tids.add(int(tid))
    except Exception:
        pass

    now = datetime.now(timezone.utc)
    end = now.strftime("%Y-%m-%d %H:%M:%S")
    start = (now - timedelta(days=period_days)).strftime("%Y-%m-%d %H:%M:%S")
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    mins, _cost = _get_vapi_usage_for_window(url, start, end, None)
    total_mins = int(round(float(mins))) if mins is not None else 0

    return {
        "period_days": period_days,
        "active_tenants_count": active,
        "onboarding_tenants_count": onboarding,
        "suspended_tenants_count": suspended,
        "alerts_count": len(alert_tids),
        "alert_tenant_ids": sorted(alert_tids)[:500],
        "total_voice_minutes_current_period": total_mins,
    }


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


def _is_truthy_admin(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "on", "oui"}


def _count_active_faq_items_admin(faq: Any) -> int:
    if not isinstance(faq, list):
        return 0
    count = 0
    for category in faq:
        if not isinstance(category, dict):
            continue
        items = category.get("items") or []
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            question = str(item.get("question") or "").strip()
            answer = str(item.get("answer") or "").strip()
            active = item.get("active", True)
            if question and answer and active is not False:
                count += 1
    return count


def _booking_days_ready_admin(raw_days: Any) -> bool:
    if isinstance(raw_days, (list, tuple, set)):
        return len(raw_days) > 0
    if isinstance(raw_days, str):
        raw = raw_days.strip()
        if not raw:
            return False
        try:
            parsed = json.loads(raw)
            return isinstance(parsed, (list, tuple)) and len(parsed) > 0
        except Exception:
            return bool(raw)
    return bool(raw_days)


def _activation_summary_from_tenant_detail(detail: dict) -> dict:
    params = (detail or {}).get("params") or {}
    routing = (detail or {}).get("routing") or []
    voice_number = next(
        ((r.get("key") or "").strip() for r in routing if (r.get("channel") or "").strip() == "vocal" and (r.get("key") or "").strip()),
        None,
    )
    calendar_provider = (params.get("calendar_provider") or "none").strip().lower() or "none"
    calendar_id = (params.get("calendar_id") or "").strip()
    faq_ready = _count_active_faq_items_admin(get_faq(detail["tenant_id"])) > 0
    onboarding_done = _is_truthy_admin(params.get("client_onboarding_completed"))
    assistant_name = (params.get("assistant_name") or "").strip()
    vapi_assistant_id = (params.get("vapi_assistant_id") or "").strip()
    horaires_ready = _booking_days_ready_admin(params.get("booking_days"))
    technical_status = _get_technical_status(int(detail["tenant_id"])) or {}
    billing = get_tenant_billing(int(detail["tenant_id"])) or {}
    steps = {
        "account": bool((params.get("contact_email") or "").strip()),
        "assistant": bool(assistant_name and vapi_assistant_id),
        "phone": bool(voice_number),
        "calendar": (calendar_provider == "google" and bool(calendar_id)) or calendar_provider == "none",
        "horaires": horaires_ready,
        "faq": faq_ready,
        "first_visit_done": onboarding_done,
    }
    missing = [key for key, done in steps.items() if not done]
    primary_reason_map = {
        "account": "Email client manquant",
        "assistant": "Assistant Vapi non configuré",
        "phone": "Numéro vocal non raccordé",
        "calendar": "Agenda non connecté",
        "horaires": "Horaires non configurés",
        "faq": "FAQ vide",
        "first_visit_done": "Première visite non finalisée",
    }
    critical_missing = {"account", "assistant", "phone"}
    setup_missing = {"calendar", "horaires", "faq"}
    stripe_status = str(billing.get("billing_status") or "").strip().lower()
    has_billing_risk = stripe_status in {"past_due", "canceled", "unpaid"}
    service_agent = str(technical_status.get("service_agent") or "offline").strip().lower()
    has_technical_alert = bool(technical_status.get("call_lock_timeout_alert")) or (
        bool(vapi_assistant_id) and bool(voice_number) and service_agent == "offline"
    )
    if any(step in missing for step in critical_missing):
        priority_key = "blocking_before_launch"
        priority_label = "Bloquant avant mise en prod"
        priority_rank = 0
    elif any(step in missing for step in setup_missing):
        priority_key = "setup_pending"
        priority_label = "Configuration à finir"
        priority_rank = 1
    elif "first_visit_done" in missing:
        priority_key = "first_visit_pending"
        priority_label = "Première visite en attente"
        priority_rank = 2
    elif has_technical_alert:
        priority_key = "fragile_active"
        priority_label = "Actif mais fragile"
        priority_rank = 3
    elif has_billing_risk:
        priority_key = "billing_risk"
        priority_label = "Billing à risque"
        priority_rank = 4
    else:
        priority_key = "ready"
        priority_label = "Cabinet activé"
        priority_rank = 5

    if priority_key == "blocking_before_launch":
        primary_reason = primary_reason_map.get(next((step for step in missing if step in critical_missing), missing[0] if missing else None))
    elif priority_key == "setup_pending":
        primary_reason = primary_reason_map.get(next((step for step in missing if step in setup_missing), missing[0] if missing else None))
    elif priority_key == "first_visit_pending":
        primary_reason = primary_reason_map["first_visit_done"]
    elif priority_key == "fragile_active":
        primary_reason = "Activité présente mais fragile"
    elif priority_key == "billing_risk":
        primary_reason = "Facturation à sécuriser"
    else:
        primary_reason = "Cabinet activé"

    return {
        "tenant_id": detail.get("tenant_id"),
        "tenant_name": detail.get("name") or f"Tenant #{detail.get('tenant_id')}",
        "contact_email": (params.get("contact_email") or "").strip(),
        "voice_number": voice_number,
        "assistant_name": assistant_name,
        "vapi_assistant_id": vapi_assistant_id,
        "plan_key": params.get("plan_key") or "growth",
        "calendar_provider": calendar_provider,
        "calendar_id": calendar_id or None,
        "onboarding_completed": onboarding_done,
        "steps": steps,
        "missing_steps": missing,
        "missing_count": len(missing),
        "primary_reason": primary_reason,
        "priority_key": priority_key,
        "priority_label": priority_label,
        "priority_rank": priority_rank,
        "stripe_status": stripe_status or None,
        "service_agent": service_agent,
        "call_lock_timeout_alert": bool(technical_status.get("call_lock_timeout_alert")),
        "calendar_status": technical_status.get("calendar_status"),
        "created_at": detail.get("created_at"),
    }


def _get_activation_queue(limit: int = 8) -> dict:
    items: List[dict] = []
    summary = {
        "pending_total": 0,
        "without_vapi": 0,
        "without_phone": 0,
        "without_calendar": 0,
        "without_horaires": 0,
        "without_faq": 0,
        "first_visit_pending": 0,
        "blocking_before_launch": 0,
        "setup_pending": 0,
        "fragile_active": 0,
        "billing_risk": 0,
    }
    tenants = _get_tenant_list(include_inactive=False)
    detail_batch: Dict[int, dict] = {}
    if getattr(config, "USE_PG_TENANTS", False) and tenants:
        from backend.tenants_pg import pg_get_tenant_full_batch

        tids_pg = [int(t["tenant_id"]) for t in tenants if t.get("tenant_id") is not None]
        detail_batch = pg_get_tenant_full_batch(tids_pg)

    for tenant in tenants:
        tenant_id = tenant.get("tenant_id")
        if not tenant_id:
            continue
        tid_int = int(tenant_id)
        detail = detail_batch.get(tid_int)
        if detail is None:
            detail = _get_tenant_detail(tid_int)
        if not detail:
            continue
        activation = _activation_summary_from_tenant_detail(detail)
        missing = activation["missing_steps"]
        if "assistant" in missing:
            summary["without_vapi"] += 1
        if "phone" in missing:
            summary["without_phone"] += 1
        if "calendar" in missing:
            summary["without_calendar"] += 1
        if "horaires" in missing:
            summary["without_horaires"] += 1
        if "faq" in missing:
            summary["without_faq"] += 1
        if "first_visit_done" in missing:
            summary["first_visit_pending"] += 1
        if activation["priority_key"] in summary:
            summary[activation["priority_key"]] += 1
        if activation["priority_key"] != "ready":
            items.append(activation)
    items.sort(
        key=lambda item: (
            int(item.get("priority_rank") or 99),
            -int(item.get("missing_count") or 0),
            0 if "assistant" in (item.get("missing_steps") or []) else 1,
            0 if "phone" in (item.get("missing_steps") or []) else 1,
            str(item.get("created_at") or ""),
        ),
        reverse=False,
    )
    summary["pending_total"] = len(items)
    return {"items": items[:limit], "summary": summary}


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
            from backend.pg_pool import pg_connection
            from backend.pg_tenant_context import set_tenant_id_on_connection
            from backend.public_bookings_pg import count_public_bookings, latest_public_booking

            with pg_connection() as conn:
                set_tenant_id_on_connection(conn, tenant_id)
                with conn.cursor() as cur:
                    # Dernière activité: source canonique vapi_calls
                    cur.execute(
                        "SELECT MAX(COALESCE(ended_at, updated_at, started_at, created_at)) as m FROM vapi_calls WHERE tenant_id = %s",
                        (tenant_id,),
                    )
                    row = cur.fetchone()
                    last_ts = row["m"] if row and row.get("m") else None
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
                        """
                        SELECT COUNT(DISTINCT v.call_id) AS c
                        FROM vapi_calls v
                        WHERE v.tenant_id = %s
                          AND COALESCE(v.ended_at, v.updated_at, v.started_at, v.created_at) >= %s
                          AND COALESCE(v.ended_at, v.updated_at, v.started_at, v.created_at) <= %s
                        """,
                        (tenant_id, start_7d, end_7d),
                    )
                    r = cur.fetchone()
                    calls_total = int(r["c"]) if r and r.get("c") else 0
                    counters_7d = {
                        "calls_total": calls_total,
                        "bookings_confirmed": by_event.get("booking_confirmed", 0),
                        "transfers": by_event.get("transferred_human", 0) + by_event.get("transferred", 0),
                        "abandons": by_event.get("user_abandon", 0),
                    }
                    public_count = count_public_bookings(tenant_id, start_7d, end_7d)
                    counters_7d["bookings_confirmed"] += public_count

                    # last_call: source canonique vapi_calls, enrichissement last_event si disponible
                    cur.execute(
                        """
                        SELECT
                            v.call_id,
                            COALESCE(v.ended_at, v.updated_at, v.started_at, v.created_at) AS ts,
                            v.status,
                            v.ended_reason,
                            ie.last_event
                        FROM vapi_calls v
                        LEFT JOIN LATERAL (
                            SELECT event AS last_event
                            FROM ivr_events
                            WHERE client_id = v.tenant_id AND call_id = v.call_id
                            ORDER BY created_at DESC
                            LIMIT 1
                        ) ie ON TRUE
                        WHERE v.tenant_id = %s
                          AND COALESCE(v.ended_at, v.updated_at, v.started_at, v.created_at) >= %s
                          AND COALESCE(v.ended_at, v.updated_at, v.started_at, v.created_at) <= %s
                        ORDER BY COALESCE(v.ended_at, v.updated_at, v.started_at, v.created_at) DESC NULLS LAST
                        LIMIT 1
                        """,
                        (tenant_id, start_7d, end_7d),
                    )
                    vapi_row = cur.fetchone()
                    if vapi_row:
                        outcome = _snapshot_outcome_from_sources(
                            vapi_row.get("last_event"),
                            vapi_row.get("status"),
                            vapi_row.get("ended_reason"),
                        )
                        last_call = {
                            "call_id": vapi_row.get("call_id") or "",
                            "created_at": str(vapi_row.get("ts") or ""),
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
            from backend.pg_pool import pg_connection
            from backend.pg_tenant_context import set_tenant_id_on_connection

            with pg_connection() as conn:
                set_tenant_id_on_connection(conn, tenant_id)
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

    if not last_booking:
        try:
            from backend.public_bookings_pg import latest_public_booking

            pb = latest_public_booking(tenant_id)
            if pb:
                last_booking = {
                    "created_at": str(pb.get("created_at") or ""),
                    "name": pb.get("patient_name"),
                    "slot_label": pb.get("slot_label"),
                    "source": "public_bookings",
                }
        except Exception as exc:
            logger.debug("dashboard public_bookings last_booking skipped: %s", exc)

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
            from backend.pg_pool import pg_connection
            from backend.pg_tenant_context import set_tenant_id_on_connection
            from backend.public_bookings_pg import count_public_bookings

            with pg_connection() as conn:
                set_tenant_id_on_connection(conn, tenant_id)
                with conn.cursor() as cur:
                    # Calls: source canonique vapi_calls
                    calls_by_day: Dict[str, int] = {}
                    try:
                        cur.execute(
                            """
                            SELECT DATE(COALESCE(v.started_at, v.created_at) AT TIME ZONE 'UTC') as d,
                                   COUNT(DISTINCT v.call_id) as calls
                            FROM vapi_calls v
                            WHERE v.tenant_id = %s
                              AND COALESCE(v.ended_at, v.updated_at, v.started_at, v.created_at) >= %s
                              AND COALESCE(v.ended_at, v.updated_at, v.started_at, v.created_at) < %s
                            GROUP BY DATE(COALESCE(v.started_at, v.created_at) AT TIME ZONE 'UTC')
                            ORDER BY d
                            """,
                            (tenant_id, start_prev, end_curr),
                        )
                        for r in cur.fetchall():
                            d = str(r["d"]) if r.get("d") else ""
                            if d:
                                calls_by_day[d] = int(r["calls"] or 0)
                    except Exception as ve:
                        if "does not exist" not in str(ve).lower():
                            logger.debug("kpis_daily canonical vapi_calls failed: %s", ve)

                    metric_by_day: Dict[str, Dict[str, int]] = {}
                    cur.execute(
                        """
                        SELECT DATE(created_at AT TIME ZONE 'UTC') as d,
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
                        b = int(r["bookings"] or 0)
                        t = int(r["transfers"] or 0)
                        metric_by_day[d] = {"bookings": b, "transfers": t}

                    merged_days = sorted(set(calls_by_day.keys()) | set(metric_by_day.keys()))
                    for d in merged_days:
                        c = int(calls_by_day.get(d, 0))
                        b = int((metric_by_day.get(d) or {}).get("bookings", 0))
                        t = int((metric_by_day.get(d) or {}).get("transfers", 0))
                        if d >= start_curr[:10]:
                            days_data.append({"date": d, "calls": c, "bookings": b, "transfers": t})
                            current["calls"] += c
                            current["bookings"] += b
                            current["transfers"] += t
                        else:
                            previous["calls"] += c
                            previous["bookings"] += b
                            previous["transfers"] += t
                    public_bookings_curr = count_public_bookings(tenant_id, start_curr, end_curr)
                    public_bookings_prev = count_public_bookings(tenant_id, start_prev, start_curr)
                    current["bookings"] += public_bookings_curr
                    previous["bookings"] += public_bookings_prev
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
    pwd = password.strip() if password else ""
    if not pwd:
        return False
    if ADMIN_PASSWORD_HASH:
        try:
            import bcrypt
            raw_hash = ADMIN_PASSWORD_HASH.strip()
            if not raw_hash:
                return False
            return bcrypt.checkpw(pwd.encode("utf-8"), raw_hash.encode("utf-8"))
        except Exception as e:
            logger.warning("admin_password_hash_check failed: %s", e)
            return False
    if ADMIN_PASSWORD:
        from backend.security import is_production

        if is_production():
            logger.error("ADMIN_PASSWORD en clair refusé en production — définir ADMIN_PASSWORD_HASH")
            return False
        return pwd == ADMIN_PASSWORD
    return False


@router.get("/admin/auth/status")
def admin_auth_status(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
):
    """
    Diagnostic (sans auth) : indique si le login email/mot de passe est configuré.
    Ne divulgue pas la présence de secrets machine (ADMIN_API_TOKEN).
    """
    from backend.security import is_production

    login_configured = bool(ADMIN_EMAIL and (ADMIN_PASSWORD or ADMIN_PASSWORD_HASH) and JWT_SECRET_ADMIN)
    if is_production():
        login_configured = bool(ADMIN_EMAIL and ADMIN_PASSWORD_HASH and JWT_SECRET_ADMIN)

    # Sans auth admin valide: payload minimal uniquement (pas de leak config).
    is_admin = False
    if _get_admin_email_from_cookie(request):
        is_admin = True
    else:
        bearer = (credentials.credentials or "").strip() if credentials else ""
        if bearer and JWT_SECRET_ADMIN and _decode_admin_session_jwt(bearer):
            is_admin = True
        elif bearer:
            pytest_tok = _pytest_admin_token()
            if pytest_tok and bearer == pytest_tok:
                is_admin = True

    if not is_admin:
        return {"login_configured": login_configured}

    return {
        "login_configured": login_configured,
        "email_set": bool(ADMIN_EMAIL),
        "password_plain_set": bool(ADMIN_PASSWORD),
        "password_hash_set": bool(ADMIN_PASSWORD_HASH),
        "jwt_secret_set": bool(JWT_SECRET_ADMIN),
        "admin_token_set": bool(_pytest_admin_token() or os.environ.get("ADMIN_API_TOKEN")),
    }


@router.post("/admin/auth/login")
def admin_auth_login(body: AdminLoginBody, request: Request):
    """Connexion admin par email + mot de passe. Pose un cookie HttpOnly (uwi_admin_session)."""
    try:
        from backend.auth_rate_limit import check_admin_login

        check_admin_login(request)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))
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
    # Session = cookie HttpOnly (uwi_admin_session). Plus de JWT renvoyé en clair (anti-XSS).
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
def admin_auth_me(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
):
    """Email de l'admin connecté : cookie session (préféré), ou Bearer JWT session (même secret)."""
    email = _get_admin_email_from_cookie(request)
    if email:
        return {"email": email}
    bearer = (credentials.credentials or "").strip() if credentials else ""
    if bearer:
        email = _decode_admin_session_jwt(bearer)
        if email:
            return {"email": email}
    raise HTTPException(401, "Not authenticated")


@router.post("/admin/auth/logout")
def admin_auth_logout():
    """Déconnexion : supprime le cookie admin (même samesite que login pour cross-domain)."""
    response = JSONResponse(content={"ok": True})
    secure = (os.environ.get("ENV") or os.environ.get("RAILWAY_ENVIRONMENT") or "").lower() in ("production", "prod")
    samesite = ADMIN_COOKIE_SAMESITE if ADMIN_COOKIE_SAMESITE in ("none", "lax", "strict") else ("none" if secure else "lax")
    response.delete_cookie(ADMIN_SESSION_COOKIE, path="/", samesite=samesite)
    return response


@router.get("/admin/audit-log")
def admin_audit_log(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0, le=5000),
    actor_email: Optional[str] = Query(None),
    tenant_id: Optional[int] = Query(None),
    method: Optional[str] = Query(None),
    path_prefix: Optional[str] = Query(None),
    _: None = Depends(require_admin),
):
    from backend.audit_log import fetch_recent_audit_entries

    items = fetch_recent_audit_entries(
        limit=limit,
        offset=offset,
        actor_email=actor_email,
        tenant_id=tenant_id,
        method=method,
        path_prefix=path_prefix,
    )
    return {"ok": True, "items": items, "count": len(items)}


class AdminEmailTestBody(BaseModel):
    to: str = Field(..., description="Adresse email de destination pour le test")


@router.post("/admin/email/test")
def admin_email_test(
    body: AdminEmailTestBody = Body(...),
    _: None = Depends(_verify_admin),
):
    """
    Envoie un email de test "Test UWi" pour vérifier Postmark/SMTP sans passer par /login.
    Permet de valider que l'envoi d'email (Postmark/SMTP) est opérationnel.
    """
    from backend.services.email_service import send_test_email
    ok, err = send_test_email(body.to.strip())
    if not ok:
        raise HTTPException(502, err or "Envoi échoué")
    return {"ok": True, "message": "Email envoyé"}


# --- Leads pré-onboarding (wizard "Créer votre assistante") ---


@router.get("/admin/leads/count-new")
def admin_leads_count_new(_: None = Depends(_verify_admin)):
    """Nombre de leads status=new (badge sidebar)."""
    from backend.leads_pg import count_new_leads
    return {"count": count_new_leads()}


@router.get("/admin/leads")
def admin_leads_list(
    status: Optional[str] = Query(None, description="Filter by status: new, contacted, converted, lost"),
    enterprise: Optional[int] = Query(None, description="Filter grands comptes only: 1"),
    search: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    priority: Optional[str] = Query(None, description="high|medium|low"),
    segment: Optional[str] = Query(None),
    sort: str = Query("created_desc", description="created_desc|score_desc|calls_desc|next_action_asc|name_asc"),
    follow_up: Optional[str] = Query(None, description="today"),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=500),
    _: None = Depends(_verify_admin),
):
    """Liste des leads avec filtres commerciaux + pagination."""
    from backend.leads_pg import list_leads
    status_norm = (status or "").strip().lower() or None
    if status_norm == "to_contact":
        status_norm = "new"
    elif status_norm == "demo":
        status_norm = "demo_scheduled"
    elif status_norm == "trial":
        status_norm = "trial_started"
    payload = list_leads(
        status=status_norm,
        enterprise_only=(enterprise == 1),
        search=search,
        source=source,
        priority=priority,
        segment=segment,
        sort=sort,
        page=page,
        limit=limit,
        follow_up_today=(str(follow_up or "").strip().lower() == "today"),
    )
    items = payload.get("items") or []
    logger.info("admin_leads_list status=%s enterprise=%s count=%s page=%s limit=%s", status, enterprise, len(items), page, limit)
    return {
        "items": items,
        "leads": items,  # compat historique frontend
        "total": payload.get("total", len(items)),
        "page": payload.get("page", page),
        "limit": payload.get("limit", limit),
        "pipeline": payload.get("pipeline", {}),
    }


@router.post("/admin/leads")
def admin_leads_create(
    body: Dict[str, Any] = Body(...),
    _: None = Depends(_verify_admin),
):
    """Création manuelle d'un lead commercial depuis l'admin."""
    from backend.leads_pg import get_lead, update_lead, upsert_lead

    payload = LeadCreateBody.model_validate(body or {})
    email = (str(payload.email or "").strip().lower() or None)
    phone = str(payload.phone or "").strip()
    if not email and not phone:
        raise HTTPException(400, "email ou phone requis")

    profession = (payload.profession or payload.specialty or "").strip()
    specialty_slug = (profession.lower().replace(" ", "_").replace("-", "_") or "autre")[:64]
    calls = (payload.calls_per_day or "unknown").strip()
    if calls not in {"<10", "10-25", "25-50", "50-100", "100+", "unknown"}:
        calls = "unknown"
    assistant_name = (payload.assistant_name or "").strip()
    if payload.has_assistant is False and not assistant_name:
        assistant_name = "none"
    if not assistant_name:
        assistant_name = "Assistante"
    pain = (payload.pain_point or payload.message or "Lead manuel").strip()
    opening_hours_default = {
        "monday": {"start": "09:00", "end": "18:00", "closed": False},
        "tuesday": {"start": "09:00", "end": "18:00", "closed": False},
        "wednesday": {"start": "09:00", "end": "18:00", "closed": False},
        "thursday": {"start": "09:00", "end": "18:00", "closed": False},
        "friday": {"start": "09:00", "end": "18:00", "closed": False},
        "saturday": {"start": "09:00", "end": "12:00", "closed": True},
        "sunday": {"start": "09:00", "end": "12:00", "closed": True},
    }

    lead_id = upsert_lead(
        email=email,
        daily_call_volume=calls,
        medical_specialty=specialty_slug,
        medical_specialty_label=profession or None,
        specialty_other=(payload.specialty or "").strip() or None,
        primary_pain_point=pain[:400],
        assistant_name=assistant_name[:80],
        voice_gender="female",
        opening_hours=opening_hours_default,
        wants_callback=bool(phone),
        callback_phone=phone or None,
        source=(payload.source or "manual").strip() or "manual",
    )
    if not lead_id:
        raise HTTPException(500, "Erreur création lead")

    lead = get_lead(lead_id)
    log = []
    existing = lead.get("notes_log") if lead else None
    try:
        if isinstance(existing, str) and existing.strip():
            log = json.loads(existing)
        elif isinstance(existing, list):
            log = list(existing)
    except Exception:
        log = []
    log.append(
        {
            "text": f"Lead créé manuellement: {payload.cabinet_name or payload.contact_name or (email or phone)}",
            "action": "lead_created_manual",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "meta": {
                "cabinet_name": payload.cabinet_name,
                "contact_name": payload.contact_name,
                "contact_role": payload.contact_role,
                "city": payload.city,
                "tenant_type": payload.tenant_type,
                "source_detail": payload.source_detail,
                "priority": payload.priority,
                "score": payload.score,
                "segment": payload.segment,
                "offer_suggested": payload.offer_suggested,
                "objection": payload.objection,
                "next_action": payload.next_action,
            },
        }
    )
    normalized_status = "new" if payload.status == "to_contact" else payload.status
    update_lead(
        lead_id,
        status=normalized_status,
        notes=(payload.message or payload.pain_point or None),
        follow_up_at=(payload.next_action_at or ""),
        notes_log=json.dumps(log, ensure_ascii=False),
    )
    refreshed = get_lead(lead_id) or {"id": lead_id}
    return {"ok": True, "lead_id": lead_id, "lead": refreshed}


@router.get("/admin/leads/summary")
def admin_leads_summary(
    period: int = Query(30, ge=1, le=366),
    _: None = Depends(_verify_admin),
):
    from backend.leads_pg import leads_summary
    return leads_summary(period)


@router.get("/admin/leads/stats")
def admin_leads_stats(
    period: int = Query(30, ge=1, le=366),
    _: None = Depends(_verify_admin),
):
    from backend.leads_pg import leads_stats
    return leads_stats(period)


@router.get("/admin/leads/{lead_id}")
def admin_lead_detail(
    lead_id: str,
    _: None = Depends(_verify_admin),
):
    """Détail d'un lead."""
    from backend.leads_pg import get_lead
    lead = get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "Lead non trouvé")
    return lead


@router.delete("/admin/leads/{lead_id}")
def admin_lead_delete(
    lead_id: str,
    _: None = Depends(_verify_admin),
):
    """Suppression définitive (nettoyage base). Réservé admin."""
    from backend.leads_pg import delete_lead

    if delete_lead(lead_id):
        return {"ok": True}
    raise HTTPException(404, "Lead introuvable")


class LeadPatchBody(BaseModel):
    status: Optional[str] = Field(None, pattern="^(new|to_contact|contacted|interested|demo_scheduled|trial_offered|trial_started|converted|lost|later)$")
    notes: Optional[str] = None
    notes_log: Optional[str] = None
    follow_up_at: Optional[str] = None
    tenant_id: Optional[int] = None


class LeadCreateBody(BaseModel):
    cabinet_name: str = Field(default="", max_length=160)
    contact_name: str = Field(default="", max_length=120)
    contact_role: str = Field(default="", max_length=120)
    email: Optional[EmailStr] = None
    phone: str = Field(default="", max_length=32)
    profession: str = Field(default="", max_length=120)
    specialty: str = Field(default="", max_length=120)
    city: str = Field(default="", max_length=120)
    tenant_type: str = Field(default="", max_length=64)
    source: str = Field(default="manual", max_length=64)
    source_detail: str = Field(default="Saisie admin", max_length=120)
    status: str = Field(default="new", pattern="^(new|to_contact|contacted|interested|demo_scheduled|trial_offered|trial_started|converted|lost|later)$")
    priority: Optional[str] = Field(default=None, pattern="^(high|medium|low)$")
    score: Optional[int] = Field(default=None, ge=0, le=100)
    segment: str = Field(default="", max_length=64)
    calls_per_day: str = Field(default="unknown", max_length=32)
    has_assistant: Optional[bool] = None
    assistant_name: str = Field(default="", max_length=120)
    pain_point: str = Field(default="", max_length=800)
    objection: str = Field(default="", max_length=800)
    offer_suggested: str = Field(default="", max_length=64)
    next_action: str = Field(default="", max_length=400)
    next_action_at: Optional[str] = None
    message: str = Field(default="", max_length=1200)


class OnboardingLinkBody(BaseModel):
    email: EmailStr
    name: Optional[str] = Field(default="", max_length=120)


class LeadStatusBody(BaseModel):
    status: str = Field(..., pattern="^(new|to_contact|contacted|interested|demo_scheduled|trial_offered|trial_started|converted|lost|later)$")
    reason: Optional[str] = None
    next_action: Optional[str] = None
    next_action_at: Optional[str] = None


class LeadMarkLostBody(BaseModel):
    lost_reason: Optional[str] = None
    note: Optional[str] = None


class LeadFollowUpBody(BaseModel):
    next_action: Optional[str] = None
    next_action_at: str = Field(..., min_length=8)
    note: Optional[str] = None


class LeadConvertBody(BaseModel):
    tenant_id: Optional[int] = None
    note: Optional[str] = None


class AdminPatientRequestPatchBody(BaseModel):
    status: str = Field(..., pattern="^(processed|cancelled)$")
    notes: Optional[str] = Field(default=None, max_length=1000)


def _slugify_patient_name(value: str) -> str:
    raw = (value or "").strip().lower()
    if not raw:
        return "patient"
    letters = []
    for ch in raw:
        if ("a" <= ch <= "z") or ("0" <= ch <= "9"):
            letters.append(ch)
        elif ch in {" ", "-", "_", "."}:
            letters.append("-")
    slug = "".join(letters).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "patient"


def _to_ui_request_status(raw_status: str) -> str:
    status = (raw_status or "").strip().lower()
    if status in {"processed", "cancelled"}:
        return "Traitées"
    if status in {"live_attempted", "live_forwarding_confirmed", "live_connected", "live_failed", "live_unconfirmed_timeout", "callback_scheduled"}:
        return "En cours"
    return "À traiter"


def _to_ui_priority(raw_priority: str) -> str:
    value = (raw_priority or "").strip().lower()
    if value in {"urgent", "high", "haute", "urgence"}:
        return "Urgence"
    if value in {"low", "faible"}:
        return "Faible"
    return "Standard"


def _to_ui_type(reason: str, summary: str, status: str) -> tuple[str, str]:
    haystack = f"{reason or ''} {summary or ''}".lower()
    if "renew" in haystack or "renouvel" in haystack or "ordonnance" in haystack:
        return ("Renouvellement", "renewal")
    if "document" in haystack or "certificat" in haystack or "arret" in haystack:
        return ("Document", "document")
    if "question" in haystack:
        return ("Question", "question")
    if "callback" in (status or "").lower():
        return ("Rappel", "callback")
    return ("Transfert humain", "transfer")


def _parse_any_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _format_waiting_time(created_at: Optional[datetime]) -> str:
    if not created_at:
        return "—"
    now = datetime.utcnow().replace(tzinfo=created_at.tzinfo)
    delta = max(0, int((now - created_at).total_seconds()))
    minutes = delta // 60
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes // 60
    rem = minutes % 60
    if hours < 24:
        return f"{hours}h{rem:02d}"
    days = hours // 24
    rem_h = hours % 24
    return f"{days}j {rem_h}h"


def _format_created_label(created_at: Optional[datetime]) -> str:
    if not created_at:
        return "—"
    now = datetime.utcnow().replace(tzinfo=created_at.tzinfo)
    if created_at.date() == now.date():
        return f"Aujourd'hui {created_at.strftime('%H:%M')}"
    if (now.date() - created_at.date()).days == 1:
        return f"Hier {created_at.strftime('%H:%M')}"
    return created_at.strftime("%d/%m %H:%M")


def _admin_patient_requests_payload(tenant_id: int, status_q: Optional[str], limit: int) -> Dict[str, Any]:
    from backend.db import get_cabinet_clients_by_phones
    from backend.handoffs import list_handoffs

    status_filter = (status_q or "").strip()
    handoffs = list_handoffs(tenant_id, status=None, target=None, limit=limit)
    phones = [str(h.get("patient_phone") or "").strip() for h in handoffs if str(h.get("patient_phone") or "").strip()]
    patient_by_phone = get_cabinet_clients_by_phones(tenant_id, phones) if phones else {}
    items: List[Dict[str, Any]] = []

    for h in handoffs:
        hid = int(h.get("id") or 0)
        request_id = f"req-{hid:03d}"
        ui_status = _to_ui_request_status(str(h.get("status") or ""))
        if status_filter and ui_status != status_filter:
            continue

        raw_phone = str(h.get("patient_phone") or "").strip()
        profile = patient_by_phone.get(raw_phone) or {}
        patient_name = (
            str(profile.get("display_name") or "").strip()
            or str(h.get("display_name") or "").strip()
            or "Patient"
        )
        patient_slug = _slugify_patient_name(patient_name)
        patient_id = f"patient-{patient_slug}"
        created_at_dt = _parse_any_datetime(h.get("created_at"))
        request_type, request_type_key = _to_ui_type(
            str(h.get("reason") or ""),
            str(h.get("summary") or ""),
            str(h.get("status") or ""),
        )
        priority = _to_ui_priority(str(h.get("priority") or ""))
        initials = "".join([part[:1].upper() for part in patient_name.split()[:2]]) or "PT"

        items.append(
            {
                "id": request_id,
                "handoff_id": hid,
                "tenant_id": tenant_id,
                "patientId": patient_id,
                "patientName": patient_name,
                "initials": initials,
                "type": request_type,
                "typeKey": request_type_key,
                "priority": priority,
                "status": ui_status,
                "status_raw": str(h.get("status") or "").strip().lower(),
                "summary": str(h.get("summary") or "").strip() or "Demande transférée car elle nécessite une action humaine.",
                "phone": raw_phone or "—",
                "createdAtLabel": _format_created_label(created_at_dt),
                "source": "Via transfert",
                "waitingTime": _format_waiting_time(created_at_dt),
                "created_at": str(h.get("created_at") or ""),
            }
        )

    urgent_count = sum(1 for item in items if item.get("priority") == "Urgence")
    transfer_count = sum(1 for item in items if item.get("type") == "Transfert humain")
    to_process_count = sum(1 for item in items if item.get("status") == "À traiter")
    return {
        "items": items,
        "kpis": {
            "to_process": to_process_count,
            "urgent": urgent_count,
            "transfers": transfer_count,
            "delay_urgent": "48 min",
            "delay_standard": "3h12",
        },
    }


@router.get("/admin/patient-requests")
def admin_patient_requests(
    tenant_id: int = Query(1, ge=1),
    status: Optional[str] = Query(None, description="À traiter | En cours | Traitées"),
    limit: int = Query(200, ge=1, le=500),
    _: None = Depends(_verify_admin),
):
    return _admin_patient_requests_payload(tenant_id, status, limit)


@router.get("/admin/tenants/{tenant_id}/patient-requests")
def admin_tenant_patient_requests_list(
    tenant_id: int = Depends(validate_tenant_id),
    status: Optional[str] = Query(None, description="À traiter | En cours | Traitées"),
    limit: int = Query(200, ge=1, le=500),
    _: None = Depends(_verify_admin),
):
    """Même réponse que GET /admin/patient-requests avec tenant_id dans le chemin."""
    return _admin_patient_requests_payload(tenant_id, status, limit)


@router.get("/admin/patient-requests/{request_id}")
def admin_patient_request_detail(
    request_id: str,
    tenant_id: int = Query(1, ge=1),
    _: None = Depends(_verify_admin),
):
    from backend.db import get_cabinet_client_by_phone
    from backend.handoffs import get_handoff_by_id

    token = (request_id or "").strip().lower()
    if token.startswith("req-"):
        token = token[4:]
    try:
        handoff_id = int(token)
    except Exception:
        raise HTTPException(400, "request_id invalide")

    handoff = get_handoff_by_id(tenant_id, handoff_id)
    if not handoff:
        raise HTTPException(404, "Demande introuvable")

    phone = str(handoff.get("patient_phone") or "").strip()
    profile = get_cabinet_client_by_phone(tenant_id, phone) if phone else None
    patient_name = (
        str((profile or {}).get("display_name") or "").strip()
        or str(handoff.get("display_name") or "").strip()
        or "Patient"
    )
    patient_slug = _slugify_patient_name(patient_name)
    patient_id = f"patient-{patient_slug}"
    created_at_dt = _parse_any_datetime(handoff.get("created_at"))
    request_type, request_type_key = _to_ui_type(
        str(handoff.get("reason") or ""),
        str(handoff.get("summary") or ""),
        str(handoff.get("status") or ""),
    )
    priority = _to_ui_priority(str(handoff.get("priority") or ""))

    return {
        "id": f"req-{handoff_id:03d}",
        "handoff_id": handoff_id,
        "tenant_id": tenant_id,
        "patientId": patient_id,
        "patientName": patient_name,
        "phone": phone or "—",
        "email": str((profile or {}).get("email") or "").strip() or "—",
        "type": request_type,
        "typeKey": request_type_key,
        "priority": priority,
        "status": _to_ui_request_status(str(handoff.get("status") or "")),
        "status_raw": str(handoff.get("status") or "").strip().lower(),
        "summary": str(handoff.get("summary") or "").strip() or "Demande transférée car elle nécessite une action humaine.",
        "createdAtLabel": _format_created_label(created_at_dt),
        "source": "Via transfert",
        "waitingTime": _format_waiting_time(created_at_dt),
    }


@router.patch("/admin/patient-requests/{request_id}")
def admin_patient_request_patch(
    request_id: str,
    body: AdminPatientRequestPatchBody,
    tenant_id: int = Query(1, ge=1),
    _: None = Depends(_verify_admin),
):
    from backend.handoffs import update_handoff_status

    token = (request_id or "").strip().lower()
    if token.startswith("req-"):
        token = token[4:]
    try:
        handoff_id = int(token)
    except Exception:
        raise HTTPException(400, "request_id invalide")

    updated = update_handoff_status(
        tenant_id,
        handoff_id,
        status=body.status,
        notes=body.notes,
    )
    if not updated:
        raise HTTPException(404, "Demande introuvable")
    return {"ok": True, "id": f"req-{handoff_id:03d}", "status": _to_ui_request_status(str(updated.get("status") or ""))}


class DeleteTenantBody(BaseModel):
    tenant_name: str = Field(..., min_length=1, max_length=120)
    confirmation_phrase: str = Field(..., min_length=3, max_length=32)


def _build_onboarding_link(email: str) -> str:
    base = (
        os.getenv("PUBLIC_BASE_URL")
        or os.getenv("CLIENT_APP_ORIGIN")
        or os.getenv("FRONT_BASE_URL")
        or "https://www.uwiapp.com"
    ).strip().rstrip("/")
    return f"{base}/creer-assistante?ref={email}&email={email}&new=1"


def _send_onboarding_link(email: str, name: str = "") -> Dict[str, Any]:
    from backend.services.email_service import send_onboarding_link_email

    email_clean = (email or "").strip().lower()
    if not email_clean:
        raise HTTPException(400, "email required")
    onboarding_url = _build_onboarding_link(email_clean)
    ok, err = send_onboarding_link_email(email_clean, (name or "").strip(), onboarding_url)
    if not ok:
        raise HTTPException(502, err or "Envoi email échoué")
    return {"ok": True, "email": email_clean, "onboarding_url": onboarding_url, "email_sent": True}


@router.patch("/admin/leads/{lead_id}")
def admin_lead_patch(
    lead_id: str,
    body: LeadPatchBody,
    _: None = Depends(_verify_admin),
):
    """Met à jour statut, notes, notes_log et/ou follow_up_at d'un lead."""
    from backend.leads_pg import get_lead, update_lead
    if get_lead(lead_id) is None:
        raise HTTPException(404, "Lead non trouvé")
    ok = update_lead(
        lead_id,
        status=body.status,
        notes=body.notes,
        notes_log=body.notes_log,
        follow_up_at=body.follow_up_at,
        tenant_id=body.tenant_id,
    )
    if not ok:
        raise HTTPException(500, "Erreur mise à jour")
    return {"ok": True}


@router.patch("/admin/leads/{lead_id}/status")
def admin_lead_set_status(
    lead_id: str,
    body: LeadStatusBody,
    _: None = Depends(_verify_admin),
):
    from backend.leads_pg import get_lead, update_lead

    lead = get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "Lead non trouvé")
    log = []
    existing = lead.get("notes_log")
    try:
        if isinstance(existing, str) and existing.strip():
            log = json.loads(existing)
        elif isinstance(existing, list):
            log = list(existing)
    except Exception:
        log = []
    normalized_status = "new" if body.status == "to_contact" else body.status
    note_parts = [f"Statut changé: {body.status}"]
    if body.reason:
        note_parts.append(f"raison={body.reason}")
    if body.next_action:
        note_parts.append(f"next_action={body.next_action}")
    if body.next_action_at:
        note_parts.append(f"next_action_at={body.next_action_at}")
    log.append(
        {
            "text": " · ".join(note_parts),
            "action": "status_changed",
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
    )
    ok = update_lead(
        lead_id,
        status=normalized_status,
        follow_up_at=(body.next_action_at or ""),
        notes_log=json.dumps(log, ensure_ascii=False),
    )
    if not ok:
        raise HTTPException(500, "Erreur mise à jour statut")
    return {"ok": True}


@router.post("/admin/leads/{lead_id}/follow-up")
def admin_lead_follow_up(
    lead_id: str,
    body: LeadFollowUpBody,
    _: None = Depends(_verify_admin),
):
    from backend.leads_pg import get_lead, update_lead

    lead = get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "Lead non trouvé")
    log = []
    existing = lead.get("notes_log")
    try:
        if isinstance(existing, str) and existing.strip():
            log = json.loads(existing)
        elif isinstance(existing, list):
            log = list(existing)
    except Exception:
        log = []
    text = f"Relance planifiée: {body.next_action_at}"
    if body.next_action:
        text += f" · {body.next_action}"
    if body.note:
        text += f" · {body.note}"
    log.append({"text": text, "action": "follow_up", "created_at": datetime.utcnow().isoformat() + "Z"})
    ok = update_lead(
        lead_id,
        follow_up_at=body.next_action_at,
        notes_log=json.dumps(log, ensure_ascii=False),
    )
    if not ok:
        raise HTTPException(500, "Erreur planification relance")
    return {"ok": True}


@router.post("/admin/leads/{lead_id}/mark-lost")
def admin_lead_mark_lost(
    lead_id: str,
    body: LeadMarkLostBody,
    _: None = Depends(_verify_admin),
):
    from backend.leads_pg import get_lead, update_lead

    lead = get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "Lead non trouvé")
    log = []
    existing = lead.get("notes_log")
    try:
        if isinstance(existing, str) and existing.strip():
            log = json.loads(existing)
        elif isinstance(existing, list):
            log = list(existing)
    except Exception:
        log = []
    note = body.note or body.lost_reason or "Lead marqué perdu"
    log.append({"text": note, "action": "marked_lost", "created_at": datetime.utcnow().isoformat() + "Z"})
    ok = update_lead(lead_id, status="lost", notes_log=json.dumps(log, ensure_ascii=False))
    if not ok:
        raise HTTPException(500, "Erreur mise à jour lead perdu")
    return {"ok": True}


@router.post("/admin/leads/{lead_id}/convert")
def admin_lead_convert(
    lead_id: str,
    body: LeadConvertBody = Body(default=LeadConvertBody()),
    _: None = Depends(_verify_admin),
):
    from backend.leads_pg import get_lead, update_lead

    lead = get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "Lead non trouvé")
    log = []
    existing = lead.get("notes_log")
    try:
        if isinstance(existing, str) and existing.strip():
            log = json.loads(existing)
        elif isinstance(existing, list):
            log = list(existing)
    except Exception:
        log = []
    txt = f"Lead converti en cabinet client"
    if body.tenant_id:
        txt += f" (tenant_id={body.tenant_id})"
    if body.note:
        txt += f" · {body.note}"
    log.append({"text": txt, "action": "lead_converted_to_tenant", "created_at": datetime.utcnow().isoformat() + "Z"})
    ok = update_lead(
        lead_id,
        status="converted",
        tenant_id=body.tenant_id if body.tenant_id else None,
        notes_log=json.dumps(log, ensure_ascii=False),
    )
    if not ok:
        raise HTTPException(500, "Erreur conversion lead")
    return {"ok": True, "lead_id": lead_id, "tenant_id": body.tenant_id}


@router.post("/admin/leads/{lead_id}/send-onboarding-link")
def admin_send_lead_onboarding_link(
    lead_id: str,
    body: Optional[OnboardingLinkBody] = Body(default=None),
    _: None = Depends(_verify_admin),
):
    from backend.leads_pg import get_lead, update_lead

    lead = get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "Lead non trouvé")
    email = ((body.email if body else None) or lead.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(400, "Lead sans email")
    name = ((body.name if body else None) or lead.get("cabinet_name") or lead.get("assistant_name") or "").strip()
    result = _send_onboarding_link(email=email, name=name)
    try:
        existing_log = lead.get("notes_log")
        parsed = []
        if isinstance(existing_log, str) and existing_log.strip():
            parsed = json.loads(existing_log)
        elif isinstance(existing_log, list):
            parsed = list(existing_log)
        parsed.append({
            "text": f"Lien wizard envoyé à {email}",
            "action": "wizard_link",
            "created_at": datetime.utcnow().isoformat() + "Z",
        })
        update_lead(
            lead_id,
            status="contacted" if (lead.get("status") or "") == "new" else None,
            notes_log=json.dumps(parsed, ensure_ascii=False),
        )
    except Exception as e:
        logger.warning("admin_send_lead_onboarding_link patch failed lead_id=%s: %s", lead_id, e)
    return result


@router.post("/admin/send-onboarding-link")
def admin_send_onboarding_link(
    body: OnboardingLinkBody = Body(...),
    _: None = Depends(_verify_admin),
):
    return _send_onboarding_link(email=body.email, name=body.name or "")


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
    search: Optional[str] = Query(
        None,
        description="Filtre serveur optionnel sur id, nom, email (PG : nom + id uniquement)",
    ),
    status: Optional[str] = Query(None, description="Statut exact (insensible à la casse), ex. active"),
    status_in: Optional[str] = Query(None, description="Liste séparée par des virgules, ex. pending_payment,inactive"),
    page: Optional[int] = Query(None, ge=1),
    limit: Optional[int] = Query(None, ge=1, le=500),
    _: None = Depends(_verify_admin),
):
    """Liste tous les tenants. Pagination optionnelle via page + limit (sinon liste complète)."""
    items = list(_get_tenant_list(include_inactive=include_inactive) or [])
    q = (search or "").strip().lower()
    if q:
        enriched = []
        for t in items:
            tid = str(t.get("tenant_id") or t.get("id") or "")
            name = str(t.get("name") or "").lower()
            email = str(t.get("contact_email") or "").lower()
            st = str(t.get("status") or "").lower()
            profession = str(t.get("profession") or "").lower()
            city = str(t.get("city") or "").lower()
            pract = str(t.get("primary_practitioner_name") or "").lower()
            pk = str(t.get("plan_key_params") or "").lower()
            blob = f"{tid} {name} {email} {st} {profession} {city} {pract} {pk}"
            if q in blob:
                enriched.append(t)
        items = enriched

    status_one = (status or "").strip().lower() if status else None
    status_csv = (status_in or "").strip().lower() if status_in else None
    if status_one:
        items = [
            t for t in items if str(t.get("status") or "active").strip().lower() == status_one
        ]
    elif status_csv:
        allowed = {s.strip() for s in status_csv.split(",") if s.strip()}
        items = [
            t for t in items if str(t.get("status") or "active").strip().lower() in allowed
        ]

    total = len(items)
    meta: Dict[str, Any] = {}
    if page is not None and limit is not None:
        start = (int(page) - 1) * int(limit)
        items = items[start : start + int(limit)]
        meta = {"total": total, "page": int(page), "limit": int(limit)}
    return {"tenants": items, **meta}


# Statuts human_handoffs considérés comme « En cours » ou « Traitées » (aligné avec _to_ui_request_status).
_HANDOFF_NOT_PENDING_STATUSES = frozenset(
    {
        "processed",
        "cancelled",
        "live_attempted",
        "live_forwarding_confirmed",
        "live_connected",
        "live_failed",
        "live_unconfirmed_timeout",
        "callback_scheduled",
    }
)


def _tenant_list_activity_hints(status: Optional[str], params: Any) -> List[str]:
    """Indices légers depuis tenant_config (pas d’IO calendrier en direct)."""
    if not isinstance(params, dict):
        params = {}
    st = str(status or "active").strip().lower()
    hints: List[str] = []
    vapi_id = str(params.get("vapi_assistant_id") or "").strip()
    cal_provider = str(params.get("calendar_provider") or "none").strip().lower()
    cal_id = str(params.get("calendar_id") or "").strip()

    if st == "active" and not vapi_id:
        hints.append("Assistant incomplet")

    # Google OAuth sans agenda choisi ⇒ UX « agenda pas prêt » comme sur la fiche cabinet.
    if cal_provider == "google" and not cal_id:
        hints.append("Agenda incomplet")

    return hints


def _bulk_merge_tenant_list_activity_hints(by_id: Dict[str, Dict[str, Any]]) -> None:
    """Enrichit by_id avec des indices config (PostgreSQL puis SQLite fallback)."""
    from backend.db import ensure_tenant_config, get_conn

    def upsert_hints(tenant_id_ish: Any, hints: List[str]) -> None:
        try:
            tid = int(tenant_id_ish)
        except (TypeError, ValueError):
            return
        if tid < 1:
            return
        k = str(tid)
        if k not in by_id:
            by_id[k] = {
                "calls": 0,
                "appointments": 0,
                "web_handoffs": 0,
                "patient_requests_pending": 0,
                "hints": [],
            }
        seen = set(by_id[k].get("hints") or [])
        for h in hints:
            hh = str(h).strip()
            if hh and hh not in seen:
                seen.add(hh)
                (by_id[k].setdefault("hints", []).append(hh))

    try:
        if config.USE_PG_TENANTS:
            url = os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL")
            if url:
                import psycopg
                from psycopg.rows import dict_row

                with psycopg.connect(url, row_factory=dict_row) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT t.tenant_id AS tenant_id, t.status AS status, tc.params_json AS params_json
                            FROM tenants t
                            LEFT JOIN tenant_config tc ON tc.tenant_id = t.tenant_id
                            ORDER BY t.tenant_id
                            """
                        )
                        for row in cur.fetchall():
                            tid = row.get("tenant_id")
                            params_raw = row.get("params_json")
                            params_obj: Dict[str, Any] = {}
                            if isinstance(params_raw, dict):
                                params_obj = params_raw
                            elif isinstance(params_raw, str) and params_raw.strip():
                                try:
                                    pj = json.loads(params_raw)
                                    if isinstance(pj, dict):
                                        params_obj = pj
                                except Exception:
                                    params_obj = {}
                            for hh in _tenant_list_activity_hints(row.get("status"), params_obj):
                                upsert_hints(tid, [hh])
                return
    except Exception as e:
        logger.debug("activity_grid hints PG tenants: %s", e)

    try:
        ensure_tenant_config()
        conn = get_conn()
        try:
            rows = conn.execute(
                """
                SELECT t.tenant_id, t.status, tc.params_json
                FROM tenants t
                LEFT JOIN tenant_config tc ON tc.tenant_id = t.tenant_id
                ORDER BY t.tenant_id
                """
            ).fetchall()
            for r in rows:
                pj: Dict[str, Any] = {}
                if len(r) > 2 and r[2]:
                    try:
                        pj = json.loads(r[2]) if isinstance(r[2], str) else (r[2] if isinstance(r[2], dict) else {})
                    except Exception:
                        pj = {}
                for hh in _tenant_list_activity_hints(r[1] if len(r) > 1 else None, pj):
                    upsert_hints(r[0], [hh])
        finally:
            conn.close()
    except Exception as e:
        logger.debug("activity_grid hints sqlite: %s", e)


def _get_tenant_list_activity_grid(window_days: int) -> Dict[str, Any]:
    """Agrège appels, RDV confirmés, handoffs hors vocal sur la fenêtre, file patient en attente, et indices config."""
    now = datetime.utcnow()
    start = (now - timedelta(days=max(1, min(int(window_days), 90)))).strftime("%Y-%m-%d %H:%M:%S")
    end = now.strftime("%Y-%m-%d %H:%M:%S")
    wdays = max(1, min(int(window_days), 90))

    by_id: Dict[str, Dict[str, Any]] = {}

    def ensure_row(tenant_id_key: Any) -> Dict[str, Any]:
        try:
            tid = int(tenant_id_key)
        except (TypeError, ValueError):
            tid = -1
        k = str(tid)
        if k not in by_id:
            by_id[k] = {
                "calls": 0,
                "appointments": 0,
                "web_handoffs": 0,
                "patient_requests_pending": 0,
                "hints": [],
            }
        return by_id[k]

    # ── ivr_events (appels & RDV) ───────────────────────────────────────────
    url_events = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    if url_events:
        try:
            import psycopg
            from psycopg.rows import dict_row

            with psycopg.connect(url_events, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT client_id AS tenant_id, COUNT(DISTINCT call_id) AS value
                        FROM ivr_events
                        WHERE call_id IS NOT NULL AND TRIM(call_id) != ''
                          AND created_at >= %s AND created_at <= %s
                        GROUP BY client_id
                        """,
                        (start, end),
                    )
                    for r in cur.fetchall():
                        tid = r.get("tenant_id")
                        row = ensure_row(tid)
                        row["calls"] = int(r.get("value") or 0)

                    cur.execute(
                        """
                        SELECT client_id AS tenant_id, COUNT(*) AS value
                        FROM ivr_events
                        WHERE event = 'booking_confirmed' AND created_at >= %s AND created_at <= %s
                        GROUP BY client_id
                        """,
                        (start, end),
                    )
                    for r in cur.fetchall():
                        tid = r.get("tenant_id")
                        row = ensure_row(tid)
                        row["appointments"] = int(r.get("value") or 0)
        except Exception as e:
            logger.warning("activity_grid ivr PG: %s", e)
    else:
        import backend.db as db

        conn_sql = db.get_conn()
        try:
            db._ensure_ivr_tables(conn_sql)
            cur_c = conn_sql.execute(
                """
                SELECT client_id, COUNT(DISTINCT call_id) AS value FROM ivr_events
                WHERE call_id != '' AND created_at >= ? AND created_at <= ?
                GROUP BY client_id
                """,
                (start, end),
            )
            for row in cur_c.fetchall():
                rr = ensure_row(row[0])
                rr["calls"] = int(row[1] or 0)

            cur_ap = conn_sql.execute(
                """
                SELECT client_id, COUNT(*) AS value FROM ivr_events
                WHERE event = 'booking_confirmed' AND created_at >= ? AND created_at <= ?
                GROUP BY client_id
                """,
                (start, end),
            )
            for row in cur_ap.fetchall():
                rr = ensure_row(row[0])
                rr["appointments"] = int(row[1] or 0)
        except Exception as e:
            logger.warning("activity_grid ivr sqlite: %s", e)
        finally:
            conn_sql.close()

    # ── human_handoffs (web & demandes ouvertes) ────────────────────────────
    from backend.db import _ensure_human_handoffs_table_pg, _pg_events_url

    _pending_statuses_sorted = tuple(sorted(_HANDOFF_NOT_PENDING_STATUSES))
    _pending_in_pg = ",".join(["%s"] * len(_HANDOFF_NOT_PENDING_STATUSES))

    pg_handoff_url = _pg_events_url() or ""
    url_tenants_alt = os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL") or ""

    def _merge_web_sqlite(conn_hand) -> None:
        import backend.db as db

        db._ensure_human_handoffs_table(conn_hand)
        try:
            q_web = conn_hand.execute(
                """
                SELECT tenant_id, COUNT(*) AS cnt FROM human_handoffs
                WHERE datetime(created_at) >= datetime(?) AND datetime(created_at) <= datetime(?)
                  AND LOWER(TRIM(COALESCE(channel, ''))) NOT IN ('', 'vocal', 'voice', 'phone')
                GROUP BY tenant_id
                """,
                (start, end),
            ).fetchall()
            for tid, cnt in q_web:
                rr = ensure_row(tid)
                rr["web_handoffs"] = int(cnt or 0)

            qi = "?," * len(_HANDOFF_NOT_PENDING_STATUSES)
            qi = qi[:-1]
            pend_params = _pending_statuses_sorted
            q_pend = conn_hand.execute(
                f"""
                SELECT tenant_id, COUNT(*) AS cnt FROM human_handoffs
                WHERE LOWER(TRIM(COALESCE(status, ''))) NOT IN ({qi})
                GROUP BY tenant_id
                """,
                pend_params,
            ).fetchall()
            for tid, cnt in q_pend:
                rr = ensure_row(tid)
                rr["patient_requests_pending"] = int(cnt or 0)
        except Exception as e_sql:
            logger.debug("activity_grid handoffs sqlite: %s", e_sql)

    if pg_handoff_url:
        pg_ok = False
        try:
            import psycopg
            from psycopg.rows import dict_row

            with psycopg.connect(pg_handoff_url, row_factory=dict_row) as conn_h:
                _ensure_human_handoffs_table_pg(conn_h)
                conn_h.commit()
                with conn_h.cursor() as cur_h:
                    try:
                        cur_h.execute(
                            """
                            SELECT tenant_id, COUNT(*) AS value
                            FROM human_handoffs
                            WHERE created_at >= %s::timestamptz AND created_at <= %s::timestamptz
                              AND LOWER(TRIM(COALESCE(channel, ''))) NOT IN ('', 'vocal', 'voice', 'phone')
                            GROUP BY tenant_id
                            """,
                            (start, end),
                        )
                        for r in cur_h.fetchall():
                            tid = r.get("tenant_id")
                            rr = ensure_row(tid)
                            rr["web_handoffs"] = int(r.get("value") or 0)

                        cur_h.execute(
                            f"""
                            SELECT tenant_id, COUNT(*) AS value
                            FROM human_handoffs
                            WHERE LOWER(TRIM(COALESCE(status, ''))) NOT IN ({_pending_in_pg})
                            GROUP BY tenant_id
                            """,
                            _pending_statuses_sorted,
                        )
                        for r in cur_h.fetchall():
                            tid = r.get("tenant_id")
                            rr = ensure_row(tid)
                            rr["patient_requests_pending"] = int(r.get("value") or 0)
                        pg_ok = True
                    except Exception as e_inner:
                        if "human_handoffs" not in str(e_inner).lower() and "does not exist" not in str(e_inner).lower():
                            logger.warning("activity_grid human_handoffs pg (events DB): %s", e_inner)
        except Exception as e_outer:
            logger.debug("activity_grid PG handoffs conn: %s", e_outer)

        if (
            not pg_ok
            and url_tenants_alt
            and pg_handoff_url.strip() != url_tenants_alt.strip()
        ):
            try:
                import psycopg
                from psycopg.rows import dict_row

                with psycopg.connect(url_tenants_alt, row_factory=dict_row) as conn_t:
                    _ensure_human_handoffs_table_pg(conn_t)
                    conn_t.commit()
                    with conn_t.cursor() as cur_tt:
                        cur_tt.execute(
                            """
                            SELECT tenant_id, COUNT(*) AS value
                            FROM human_handoffs
                            WHERE created_at >= %s::timestamptz AND created_at <= %s::timestamptz
                              AND LOWER(TRIM(COALESCE(channel, ''))) NOT IN ('', 'vocal', 'voice', 'phone')
                            GROUP BY tenant_id
                            """,
                            (start, end),
                        )
                        for r in cur_tt.fetchall():
                            rr = ensure_row(r.get("tenant_id"))
                            rr["web_handoffs"] = max(rr["web_handoffs"], int(r.get("value") or 0))
                        cur_tt.execute(
                            f"""
                            SELECT tenant_id, COUNT(*) AS value
                            FROM human_handoffs
                            WHERE LOWER(TRIM(COALESCE(status, ''))) NOT IN ({_pending_in_pg})
                            GROUP BY tenant_id
                            """,
                            _pending_statuses_sorted,
                        )
                        for r in cur_tt.fetchall():
                            rr = ensure_row(r.get("tenant_id"))
                            rr["patient_requests_pending"] = max(
                                rr["patient_requests_pending"],
                                int(r.get("value") or 0),
                            )
                        pg_ok = True
            except Exception as e2:
                logger.debug("activity_grid human_handoffs pg (tenants DB fallback): %s", e2)

        if not pg_ok:
            import backend.db as db

            cx = db.get_conn()
            try:
                _merge_web_sqlite(cx)
            finally:
                cx.close()
    else:
        import backend.db as db

        cx = db.get_conn()
        try:
            _merge_web_sqlite(cx)
        finally:
            cx.close()

    for k in list(by_id.keys()):
        pr = int(by_id[k].get("patient_requests_pending") or 0)
        hint_list = list(by_id[k].get("hints") or [])
        if pr > 0:
            label = "1 demande patient" if pr == 1 else f"{pr} demandes patient"
            if label not in hint_list:
                hint_list.insert(0, label)
        by_id[k]["hints"] = hint_list[:4]

    _bulk_merge_tenant_list_activity_hints(by_id)

    for bad in ("-1", "0"):
        by_id.pop(bad, None)

    return {"window_days": wdays, "by_tenant_id": by_id}


@router.get("/admin/tenants/activity-grid")
def admin_tenants_activity_grid(
    window_days: int = Query(30, ge=1, le=90, description="Fenêtre glissante UTC pour appels/RDV/handoffs web"),
    _: None = Depends(_verify_admin),
):
    """Agrégats liste cabinets : volume ivr_events + human_handoffs + indices légers depuis tenant_config."""
    return _get_tenant_list_activity_grid(window_days)


@router.get("/admin/tenants/summary")
def admin_tenants_summary(
    period: int = Query(30, ge=1, le=366, description="Fenêtre glissante (jours UTC) pour total minutes vocales parc"),
    _: None = Depends(_verify_admin),
):
    """KPIs liste clients : effectifs, alertes agrégées, minutes Vapi."""
    return _get_admin_tenants_summary(period)


def _admin_create_tenant_impl(body: TenantCreateIn) -> TenantOut:
    """Logique commune pour POST /admin/tenants et POST /admin/tenants/."""
    contact_email = (body.contact_email or "").strip().lower()
    if not contact_email:
        raise HTTPException(400, "contact_email required")

    if config.USE_PG_TENANTS:
        existing = pg_get_tenant_user_by_email(contact_email)
        if existing:
            raise HTTPException(
                409,
                detail="Cet email est déjà rattaché à un autre client.",
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
                    raise HTTPException(
                        409,
                        detail="Cet email est déjà rattaché à un autre client.",
                    )
        finally:
            conn_sqlite.close()

    initial_status = (body.initial_status or "active").strip() or "active"
    plan_key = (body.plan_key or "").strip() or ""
    billing_email = (body.billing_email or "").strip() or None

    tid = None
    if config.USE_PG_TENANTS:
        try:
            tid = pg_create_tenant(
                name=body.name.strip(),
                contact_email=contact_email,
                calendar_provider="none",
                calendar_id="",
                timezone=body.timezone or "Europe/Paris",
                business_type=(body.business_type or "").strip() or None,
                notes=(body.notes or "").strip() or None,
                status=initial_status,
                plan_key=plan_key or None,
                billing_email=billing_email,
            )
        except Exception as e:
            logger.exception("admin_create_tenant pg_create_tenant failed")
            raise HTTPException(500, "Impossible de créer le client (base de données). Réessayez ou vérifiez la configuration.")
    if not tid and not config.USE_PG_TENANTS:
        import backend.db as db
        db.ensure_tenant_config()
        conn = db.get_conn()
        try:
            conn.execute(
                "INSERT INTO tenants (name, timezone, status) VALUES (?, ?, ?)",
                (body.name.strip() or "Nouveau", body.timezone or "Europe/Paris", initial_status),
            )
            row = conn.execute("SELECT last_insert_rowid()").fetchone()
            tid = row[0] if row else None
            if tid:
                params = json.dumps({
                    "contact_email": contact_email,
                    "business_type": (body.business_type or "").strip() or "",
                    "notes": (body.notes or "").strip() or "",
                    "plan_key": plan_key or "",
                    "billing_email": (billing_email or "").strip() or "",
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
        raise HTTPException(500, "Impossible de créer le client. Vérifiez la configuration (base de données).")

    created_at = datetime.utcnow().isoformat() + "Z"
    return TenantOut(
        tenant_id=int(tid),
        name=body.name.strip(),
        contact_email=contact_email,
        timezone=body.timezone or "Europe/Paris",
        business_type=(body.business_type or "").strip() or None,
        created_at=created_at,
    )


def _admin_create_tenant_handle(body: TenantCreateIn):
    """Appelle l'impl et renvoie la réponse 409 avec error_code si besoin."""
    try:
        return _admin_create_tenant_impl(body)
    except HTTPException as e:
        if e.status_code == 409:
            return JSONResponse(
                status_code=409,
                content={"detail": (e.detail or "Conflict"), "error_code": "EMAIL_ALREADY_ASSIGNED"},
            )
        raise


@router.post("/admin/tenants", response_model=TenantOut, status_code=201)
def admin_create_tenant(
    body: TenantCreateIn,
    _: None = Depends(_verify_admin),
):
    """Crée un tenant (client) par l'admin. 409 si contact_email déjà associé à un autre tenant."""
    return _admin_create_tenant_handle(body)


@router.post("/admin/tenants/", response_model=TenantOut, status_code=201)
def admin_create_tenant_trailing_slash(
    body: TenantCreateIn,
    _: None = Depends(_verify_admin),
):
    """Même création, pour les clients qui envoient POST avec slash final (évite 405)."""
    return _admin_create_tenant_handle(body)


@router.post("/admin/tenant/create", response_model=TenantOut, status_code=201)
def admin_create_tenant_alt(
    body: TenantCreateIn,
    _: None = Depends(_verify_admin),
):
    """Création client (path alternatif pour éviter 405 sur certains proxies/CDN)."""
    return _admin_create_tenant_handle(body)


@router.post("/admin/create-tenant", response_model=TenantOut, status_code=201)
def admin_create_tenant_main(
    body: TenantCreateIn,
    _: None = Depends(_verify_admin),
):
    """Création client (path dédié, sans 'tenants' dans l'URL pour éviter 405)."""
    return _admin_create_tenant_handle(body)


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


IMPERSONATE_TTL_MINUTES = 5


@router.post("/admin/tenants/{tenant_id}/impersonate")
def admin_impersonate(
    tenant_id: int = Depends(validate_tenant_id),
    request: Request = None,
    _: None = Depends(_verify_admin),
):
    """
    Génère un token d’impersonation court (5 min) pour voir le dashboard client comme ce tenant.
    Audit log: ADMIN_IMPERSONATION. Le token est un JWT tenant (scope=impersonate) accepté par /api/tenant/*.
    """
    JWT_SECRET = (os.environ.get("JWT_SECRET") or "").strip()
    if not JWT_SECRET:
        raise HTTPException(503, "JWT_SECRET not configured")
    d = _get_tenant_detail(tenant_id)
    if not d:
        raise HTTPException(404, "Tenant not found")
    admin_email = _get_admin_email_from_cookie(request) if request else None
    admin_id = (admin_email or "admin").strip() or "admin"
    now = datetime.utcnow()
    exp = now + timedelta(minutes=IMPERSONATE_TTL_MINUTES)
    import uuid

    payload = {
        "sub": admin_id,
        "tenant_id": tenant_id,
        "email": admin_id,
        "role": "owner",
        "scope": "impersonate",
        "impersonated_by": admin_id,
        "jti": str(uuid.uuid4()),
        "exp": exp,
        "iat": now,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    logger.info("ADMIN_IMPERSONATION tenant_id=%s admin=%s", tenant_id, admin_id)
    expires_at = exp.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"token": token, "expires_at": expires_at}


@router.delete("/admin/tenants/{tenant_id}")
def admin_delete_tenant(
    body: DeleteTenantBody = Body(...),
    tenant_id: int = Depends(validate_tenant_id),
    _: None = Depends(_verify_admin),
):
    """Soft delete : passe le tenant en inactive (PG uniquement)."""
    if not config.USE_PG_TENANTS:
        raise HTTPException(501, "Delete tenant requires USE_PG_TENANTS (Postgres)")
    detail = _get_tenant_detail(tenant_id)
    if not detail:
        raise HTTPException(404, "Tenant not found")
    protected_ids = {
        int(config.DEFAULT_TENANT_ID),
        int(getattr(config, "TEST_TENANT_ID", config.DEFAULT_TENANT_ID)),
    }
    tenant_name = str(detail.get("name") or "").strip()
    if tenant_id in protected_ids or tenant_name.upper() == "DEFAULT":
        raise HTTPException(403, "Suppression interdite pour ce compte système")
    if str(detail.get("status") or "").strip().lower() == "inactive":
        raise HTTPException(409, "Ce client est déjà désactivé")
    if body.tenant_name.strip().casefold() != tenant_name.casefold():
        raise HTTPException(400, "Le nom du client ne correspond pas")
    if body.confirmation_phrase.strip().upper() != "SUPPRIMER":
        raise HTTPException(400, 'Tapez "SUPPRIMER" pour confirmer cette action')
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


def _vapi_call_result_from_status(status: Optional[str], ended_reason: Optional[str]) -> str:
    """Mappe status/ended_reason vapi_calls vers result (rdv|transfer|abandoned|other)."""
    if not status and not ended_reason:
        return "other"
    reason = (ended_reason or "").lower()
    if "transfer" in reason or "forward" in reason:
        return "transfer"
    if "hangup" in reason or "abandon" in reason or "user" in reason:
        return "abandoned"
    return "other"


def _get_calls_list(
    tenant_id: Optional[int],
    days: int,
    limit: int,
    cursor: Optional[str] = None,
    result_filter: Optional[str] = None,
    tenant_detail: Optional[dict] = None,
) -> dict:
    """Liste appels canonique tenant: vapi_calls/vapi_call_usage en priorité, fallback ivr_events."""
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    start = (now - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")
    end = now.strftime("%Y-%m-%d %H:%M:%S")
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
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    items: List[dict] = []
    next_cursor: Optional[str] = None
    fixed_tenant_name: Optional[str] = None
    tenant_name_cache: Dict[int, str] = {}

    if tenant_id is not None:
        fixed_detail = tenant_detail or (_get_tenant_detail(tenant_id) or {})
        fixed_tenant_name = (fixed_detail.get("name") or "").strip() or f"Client #{tenant_id}"

    if url:
        try:
            if tenant_id is not None:
                canonical_items, next_cursor = _fetch_vapi_call_items_pg(
                    tenant_id=tenant_id,
                    start=start,
                    end=end,
                    limit=limit,
                    tenant_name=fixed_tenant_name or f"Client #{tenant_id}",
                    cursor=cursor,
                    result_filter=result_filter,
                )
                if canonical_items:
                    items.extend(canonical_items)

            import psycopg
            from psycopg.rows import dict_row

            with psycopg.connect(url, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    # 1) Source canonique vapi_calls (fallback local ici pour conserver
                    # la fusion vapi+ivr même si le helper poolé échoue).
                    if tenant_id is not None:
                        vapi_params: List[Any] = [tenant_id, start, end, limit + 1]
                        vapi_cursor_filter = ""
                        if cursor_ts and cursor_id:
                            vapi_cursor_filter = (
                                " AND (COALESCE(v.ended_at, v.updated_at, v.started_at, v.created_at) < %s "
                                "OR (COALESCE(v.ended_at, v.updated_at, v.started_at, v.created_at) = %s AND v.call_id < %s))"
                            )
                            vapi_params = [tenant_id, start, end, cursor_ts, cursor_ts, cursor_id, limit + 1]
                        cur.execute(
                            """
                            SELECT
                                v.tenant_id,
                                v.call_id,
                                v.started_at,
                                v.ended_at,
                                v.updated_at,
                                v.status,
                                v.ended_reason,
                                ie.last_event
                            FROM vapi_calls v
                            LEFT JOIN LATERAL (
                                SELECT event AS last_event
                                FROM ivr_events
                                WHERE client_id = v.tenant_id AND call_id = v.call_id
                                ORDER BY created_at DESC
                                LIMIT 1
                            ) ie ON TRUE
                            WHERE v.tenant_id = %s
                              AND COALESCE(v.ended_at, v.updated_at, v.started_at, v.created_at) >= %s
                              AND COALESCE(v.ended_at, v.updated_at, v.started_at, v.created_at) <= %s
                            """
                            + vapi_cursor_filter
                            + """
                            ORDER BY COALESCE(v.ended_at, v.updated_at, v.started_at, v.created_at) DESC, v.call_id DESC
                            LIMIT %s
                            """,
                            tuple(vapi_params),
                        )
                        for vr in cur.fetchall()[:limit]:
                            ts = vr.get("ended_at") or vr.get("updated_at") or vr.get("started_at")
                            event = vr.get("last_event")
                            items.append(
                                {
                                    "call_id": vr.get("call_id") or "",
                                    "tenant_id": tenant_id,
                                    "tenant_name": fixed_tenant_name or f"Client #{tenant_id}",
                                    "customer_number": "",
                                    "started_at": _iso_utc(vr.get("started_at")),
                                    "last_event_at": _iso_utc(ts),
                                    "last_event": event or "",
                                    "result": _snapshot_outcome_from_sources(event, vr.get("status"), vr.get("ended_reason")),
                                    "duration_min": None,
                                    "duration_sec": None,
                                }
                            )

                    seen_call_ids: set[str] = {str(it.get("call_id") or "") for it in items if it.get("call_id")}

                    # 2) Fallback ivr_events (comportement historique)
                    params = [start, end]
                    tenant_filter = ""
                    if tenant_id is not None:
                        tenant_filter = " AND client_id = %s"
                        params.append(_ivr_client_id(tenant_id))

                    cursor_filter = ""
                    if cursor_ts and cursor_id:
                        cursor_filter = " AND (a.last_event_at < %s OR (a.last_event_at = %s AND a.call_id < %s))"
                        params.extend([cursor_ts, cursor_ts, cursor_id])

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
                        items.sort(key=lambda x: ((x.get("last_event_at") or ""), (x.get("call_id") or "")), reverse=True)
                        if len(items) > limit:
                            last_item = items[limit - 1]
                            t_iso = str(last_item.get("last_event_at") or "")
                            c_id = last_item.get("call_id") or ""
                            next_cursor = base64.urlsafe_b64encode(json.dumps({"t": t_iso, "c": c_id}).encode()).decode().rstrip("=")
                            items = items[:limit]
                        return {"items": items, "next_cursor": next_cursor, "days": days}

                    for r in rows[:limit]:
                        if (r.get("call_id") or "") in seen_call_ids:
                            continue
                        started_at = r.get("started_at")
                        last_event_at = r.get("last_event_at")
                        last_event = r.get("last_event")
                        cs_started = r.get("cs_started")
                        cs_updated = r.get("cs_updated")
                        duration_min: Optional[int] = None
                        duration_sec: Optional[int] = None
                        if cs_started and cs_updated:
                            delta_secs = (cs_updated - cs_started).total_seconds()
                            delta_secs = max(0, min(MAX_SESSION_MINUTES * 60, delta_secs))
                            duration_sec = int(delta_secs)
                            duration_min = duration_sec // 60
                        elif started_at and last_event_at:
                            delta_secs = (last_event_at - started_at).total_seconds()
                            delta_secs = max(0, min(MAX_SESSION_MINUTES * 60, delta_secs))
                            duration_sec = int(delta_secs)
                            duration_min = duration_sec // 60

                        tid = r.get("client_id")
                        if tid and tenant_id is None:
                            if tid not in tenant_name_cache:
                                d = _get_tenant_detail(tid) or {}
                                tenant_name_cache[tid] = (d.get("name") or "").strip() or f"Client #{tid}"
                            tenant_name = tenant_name_cache[tid]
                        else:
                            tenant_name = fixed_tenant_name or (f"Client #{tid}" if tid else "—")
                        items.append({
                            "call_id": r.get("call_id") or "",
                            "tenant_id": tid,
                            "tenant_name": tenant_name,
                            "customer_number": "",
                            "started_at": _iso_utc(started_at),
                            "last_event_at": _iso_utc(last_event_at),
                            "last_event": last_event or "",
                            "result": _call_result_from_event(last_event),
                            "duration_min": duration_min,
                            "duration_sec": duration_sec,
                        })
                    items.sort(key=lambda x: ((x.get("last_event_at") or ""), (x.get("call_id") or "")), reverse=True)
                    if len(items) > limit:
                        last_item = items[limit - 1]
                        t_iso = str(last_item.get("last_event_at") or "")
                        c_id = last_item.get("call_id") or ""
                        next_cursor = base64.urlsafe_b64encode(json.dumps({"t": t_iso, "c": c_id}).encode()).decode().rstrip("=")
                        items = items[:limit]

        except Exception as e:
            logger.warning("admin calls list pg failed: %s", e)

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
        "customer_number": None,
        "started_at": None,
        "last_event_at": None,
        "duration_min": None,
        "duration_sec": None,
        "result": "other",
        "events": [],
    }
    if not url:
        return out
    try:
        from backend.pg_pool import pg_connection
        with pg_connection() as conn:
            with conn.cursor() as cur:
                vapi_row = None
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
                events = []
                for r in rows:
                    meta = {}
                    raw_context = r.get("context")
                    if raw_context:
                        meta["context"] = raw_context
                        try:
                            parsed_context = json.loads(raw_context)
                            if isinstance(parsed_context, dict):
                                for key, value in parsed_context.items():
                                    if value is not None and key not in meta:
                                        meta[key] = value
                        except Exception:
                            pass
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
                out["result"] = _call_result_from_event(last_event) if last_event else "other"
                if len(rows) >= 2:
                    from datetime import datetime
                    try:
                        first_ts = rows[0]["created_at"]
                        last_ts = rows[-1]["created_at"]
                        if hasattr(first_ts, "timestamp") and hasattr(last_ts, "timestamp"):
                            delta_secs = (last_ts - first_ts).total_seconds()
                        else:
                            delta_secs = 0
                        delta_secs = max(0, min(MAX_SESSION_MINUTES * 60, delta_secs))
                        out["duration_sec"] = int(delta_secs)
                        out["duration_min"] = out["duration_sec"] // 60
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
                    delta_secs = (cs["updated_at"] - cs["started_at"]).total_seconds()
                    delta_secs = max(0, min(MAX_SESSION_MINUTES * 60, delta_secs))
                    out["duration_sec"] = int(delta_secs)
                    out["duration_min"] = out["duration_sec"] // 60
                try:
                    cur.execute(
                        """
                        SELECT customer_number, started_at, ended_at, updated_at, status, ended_reason
                        FROM vapi_calls
                        WHERE tenant_id = %s AND call_id = %s
                        LIMIT 1
                        """,
                        (tenant_id, call_id_clean),
                    )
                    vc = cur.fetchone()
                    if vc and vc.get("customer_number"):
                        out["customer_number"] = str(vc.get("customer_number")).strip()
                    vapi_row = vc
                except Exception:
                    pass
                if vapi_row:
                    v_started = vapi_row.get("started_at")
                    v_ended = vapi_row.get("ended_at")
                    v_updated = vapi_row.get("updated_at")
                    if not out.get("started_at"):
                        out["started_at"] = _iso_utc(v_started) if v_started else None
                    if not out.get("last_event_at"):
                        fallback_last = v_ended or v_updated or v_started
                        out["last_event_at"] = _iso_utc(fallback_last) if fallback_last else None
                    if out.get("result") == "other":
                        out["result"] = _vapi_call_result_from_status(vapi_row.get("status"), vapi_row.get("ended_reason"))
                    if out.get("duration_sec") is None and v_started and v_updated:
                        delta_secs = (v_updated - v_started).total_seconds()
                        delta_secs = max(0, min(MAX_SESSION_MINUTES * 60, delta_secs))
                        if delta_secs >= 1:
                            out["duration_sec"] = int(delta_secs)
                            out["duration_min"] = out["duration_sec"] // 60
                try:
                    cur.execute(
                        "SELECT duration_sec FROM vapi_call_usage WHERE tenant_id = %s AND vapi_call_id = %s",
                        (tenant_id, call_id_clean),
                    )
                    usage_row = cur.fetchone()
                    if usage_row and usage_row.get("duration_sec") is not None:
                        out["duration_sec"] = int(float(usage_row["duration_sec"]))
                        out["duration_min"] = out["duration_sec"] // 60
                except Exception:
                    pass
                # Transcription depuis call_transcripts (déchiffrement transparent au repos)
                try:
                    from backend.crypto_at_rest import decrypt_str

                    cur.execute(
                        """
                        SELECT role, transcript, created_at
                        FROM call_transcripts
                        WHERE tenant_id = %s AND call_id = %s AND is_final = TRUE
                        ORDER BY created_at ASC
                        """,
                        (tenant_id, call_id_clean),
                    )
                    rows_t = cur.fetchall()
                    if rows_t:
                        parts = []
                        for r in rows_t:
                            role = (r.get("role") or "user").lower()
                            txt = (decrypt_str(r.get("transcript")) or "").strip()
                            if txt:
                                prefix = "Patient:" if role == "user" else "Assistant:"
                                parts.append(f"{prefix} {txt}")
                        out["transcript"] = "\n\n".join(parts) if parts else None
                except Exception:
                    pass
                if not rows and not vapi_row:
                    raise HTTPException(404, "Call not found")
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


class SetMeteredItemBody(BaseModel):
    stripe_metered_item_id: str = Field(..., min_length=3, description="ID si_... du subscription item metered (Stripe Dashboard)")


@router.post("/admin/tenants/{tenant_id}/billing/set-metered-item")
def admin_set_metered_item(
    tenant_id: int = Depends(validate_tenant_id),
    body: SetMeteredItemBody = Body(...),
    _: None = Depends(_verify_admin),
):
    """Force stripe_metered_item_id manuellement (si_... copié depuis Stripe Dashboard → Subscription items)."""
    if not _get_tenant_detail(tenant_id):
        raise HTTPException(404, "Tenant not found")
    si_id = (body.stripe_metered_item_id or "").strip()
    if not si_id.startswith("si_"):
        raise HTTPException(400, "stripe_metered_item_id doit commencer par si_")
    from backend.billing_pg import set_stripe_metered_item_id
    if not set_stripe_metered_item_id(tenant_id, si_id):
        raise HTTPException(500, "Failed to update stripe_metered_item_id")
    return {"ok": True, "tenant_id": tenant_id, "stripe_metered_item_id": si_id}


@router.post("/admin/tenants/{tenant_id}/billing/resync-metered-item")
def admin_resync_metered_item(
    tenant_id: int = Depends(validate_tenant_id),
    _: None = Depends(_verify_admin),
):
    """Re-fetch subscription Stripe (expand items.data.price) et met à jour stripe_metered_item_id. Backfill si webhook n'a pas persisté."""
    if not _get_tenant_detail(tenant_id):
        raise HTTPException(404, "Tenant not found")
    from backend.routes.stripe_webhook import resync_metered_item_for_tenant
    result = resync_metered_item_for_tenant(tenant_id)
    # Toujours retourner 200 avec le résultat complet (ok, error, items_debug, expected_metered_price_ids)
    return {
        "ok": result["ok"],
        "tenant_id": tenant_id,
        "stripe_metered_item_id": result.get("stripe_metered_item_id"),
        "error": result.get("error"),
        "items_debug": result.get("items_debug"),
        "expected_metered_price_ids": result.get("expected_metered_price_ids"),
    }


class ChangePlanBody(BaseModel):
    plan_key: str = Field(..., description="starter | growth | pro")


@router.post("/admin/tenants/{tenant_id}/billing/change-plan")
def admin_billing_change_plan(
    tenant_id: int = Depends(validate_tenant_id),
    body: ChangePlanBody = Body(...),
    _: None = Depends(_verify_admin),
):
    """Change le plan Stripe du tenant (starter/growth/pro). Met à jour base + metered prices."""
    if not _get_tenant_detail(tenant_id):
        raise HTTPException(404, "Tenant not found")
    plan_key = (body.plan_key or "").strip().lower()
    if plan_key not in STRIPE_CHECKOUT_PLAN_KEYS:
        raise HTTPException(400, "plan_key must be one of: starter, growth, pro")
    billing = get_tenant_billing(tenant_id)
    sub_id = (billing or {}).get("stripe_subscription_id") or ""
    if not sub_id.strip():
        raise HTTPException(400, "No Stripe subscription for this tenant")
    stripe_key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if not stripe_key:
        raise HTTPException(503, "Stripe not configured (STRIPE_SECRET_KEY)")
    base_price_id, metered_price_id = _get_stripe_price_ids_for_plan(plan_key)
    if not base_price_id or not metered_price_id:
        raise HTTPException(400, "Stripe prices not configured for this plan")
    try:
        import stripe
        stripe.api_key = stripe_key
        sub = stripe.Subscription.retrieve(sub_id, expand=["items.data.price"])
        items = sub.get("items", {}).get("data", []) or []
        base_item_id = None
        metered_item_id = (billing or {}).get("stripe_metered_item_id") or ""
        for it in items:
            pid = (it.get("price") or {}).get("id") or ""
            if it.get("recurring", {}).get("usage_type") == "metered":
                metered_item_id = (it.get("id") or "").strip() or metered_item_id
            else:
                base_item_id = (it.get("id") or "").strip()
        if not base_item_id or not metered_item_id:
            raise HTTPException(400, "Could not resolve subscription items (base + metered)")
        stripe.Subscription.modify(
            sub_id,
            items=[
                {"id": base_item_id, "price": base_price_id},
                {"id": metered_item_id, "price": metered_price_id},
            ],
            metadata={"tenant_id": str(tenant_id), "plan_key": plan_key},
        )
        from backend.billing_pg import upsert_billing_from_subscription
        upsert_billing_from_subscription(
            tenant_id,
            stripe_subscription_id=sub_id,
            billing_status="active",
            plan_key=plan_key,
            stripe_customer_id=(billing or {}).get("stripe_customer_id"),
        )
        logger.info("BILLING_CHANGE_PLAN tenant_id=%s plan_key=%s", tenant_id, plan_key)
        return {"ok": True, "tenant_id": tenant_id, "plan_key": plan_key}
    except stripe.StripeError as e:
        logger.warning("stripe change-plan failed: %s", e)
        raise HTTPException(502, str(e) or "Stripe error")


@router.post("/admin/tenants/{tenant_id}/billing/cancel")
def admin_billing_cancel(
    tenant_id: int = Depends(validate_tenant_id),
    _: None = Depends(_verify_admin),
):
    """Annule l'abonnement Stripe à la fin de la période (cancel_at_period_end)."""
    if not _get_tenant_detail(tenant_id):
        raise HTTPException(404, "Tenant not found")
    billing = get_tenant_billing(tenant_id)
    sub_id = (billing or {}).get("stripe_subscription_id") or ""
    if not sub_id.strip():
        raise HTTPException(400, "No Stripe subscription for this tenant")
    stripe_key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if not stripe_key:
        raise HTTPException(503, "Stripe not configured (STRIPE_SECRET_KEY)")
    try:
        import stripe
        stripe.api_key = stripe_key
        stripe.Subscription.modify(sub_id, cancel_at_period_end=True)
        logger.info("BILLING_CANCEL_AT_PERIOD_END tenant_id=%s sub=%s", tenant_id, sub_id[:20])
        return {"ok": True, "tenant_id": tenant_id, "cancel_at_period_end": True}
    except stripe.StripeError as e:
        logger.warning("stripe cancel failed: %s", e)
        raise HTTPException(502, str(e) or "Stripe error")


@router.post("/admin/tenants/{tenant_id}/billing/resume")
def admin_billing_resume(
    tenant_id: int = Depends(validate_tenant_id),
    _: None = Depends(_verify_admin),
):
    """Réactive un abonnement annulé (cancel_at_period_end=False)."""
    if not _get_tenant_detail(tenant_id):
        raise HTTPException(404, "Tenant not found")
    billing = get_tenant_billing(tenant_id)
    sub_id = (billing or {}).get("stripe_subscription_id") or ""
    if not sub_id.strip():
        raise HTTPException(400, "No Stripe subscription for this tenant")
    stripe_key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if not stripe_key:
        raise HTTPException(503, "Stripe not configured (STRIPE_SECRET_KEY)")
    try:
        import stripe
        stripe.api_key = stripe_key
        stripe.Subscription.modify(sub_id, cancel_at_period_end=False)
        logger.info("BILLING_RESUME tenant_id=%s sub=%s", tenant_id, sub_id[:20])
        return {"ok": True, "tenant_id": tenant_id, "cancel_at_period_end": False}
    except stripe.StripeError as e:
        logger.warning("stripe resume failed: %s", e)
        raise HTTPException(502, str(e) or "Stripe error")


@router.post("/admin/tenants/{tenant_id}/billing/portal-link")
def admin_billing_portal_link(
    tenant_id: int = Depends(validate_tenant_id),
    _: None = Depends(_verify_admin),
):
    """Génère un lien vers le portail client Stripe (gestion factures, moyen de paiement)."""
    if not _get_tenant_detail(tenant_id):
        raise HTTPException(404, "Tenant not found")
    billing = get_tenant_billing(tenant_id)
    customer_id = (billing or {}).get("stripe_customer_id") or ""
    if not customer_id.strip():
        raise HTTPException(400, "No Stripe customer for this tenant")
    stripe_key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if not stripe_key:
        raise HTTPException(503, "Stripe not configured (STRIPE_SECRET_KEY)")
    return_url = (
        os.environ.get("STRIPE_PORTAL_RETURN_URL")
        or os.environ.get("STRIPE_CHECKOUT_SUCCESS_URL")
        or os.environ.get("FRONTEND_URL")
        or "https://www.uwiapp.com"
    ).strip().rstrip("/")
    try:
        import stripe
        stripe.api_key = stripe_key
        session = stripe.billing_portal.Session.create(
            customer=customer_id.strip(),
            return_url=return_url,
        )
        url = (session.get("url") or "").strip()
        if not url:
            raise HTTPException(500, "Stripe portal did not return URL")
        return {"url": url}
    except stripe.StripeError as e:
        logger.warning("stripe portal session failed: %s", e)
        raise HTTPException(502, str(e) or "Stripe error")


@router.get("/admin/tenants/{tenant_id}/billing/invoices")
def admin_billing_invoices(
    tenant_id: int = Depends(validate_tenant_id),
    limit: int = Query(10, ge=1, le=50),
    _: None = Depends(_verify_admin),
):
    """Liste les factures Stripe du tenant (dernières N)."""
    if not _get_tenant_detail(tenant_id):
        raise HTTPException(404, "Tenant not found")
    billing = get_tenant_billing(tenant_id)
    customer_id = (billing or {}).get("stripe_customer_id") or ""
    if not customer_id.strip():
        return {"items": []}
    stripe_key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if not stripe_key:
        return {"items": []}
    try:
        import stripe
        stripe.api_key = stripe_key
        invoices = stripe.Invoice.list(customer=customer_id.strip(), limit=limit)
        items = []
        for inv in (invoices.get("data") or []):
            items.append({
                "id": inv.get("id"),
                "number": inv.get("number"),
                "status": inv.get("status"),
                "amount_due": (inv.get("amount_due") or 0) / 100,
                "currency": inv.get("currency", "eur").upper(),
                "created": inv.get("created"),
                "invoice_pdf": (inv.get("invoice_pdf") or "").strip() or None,
            })
        return {"items": items}
    except stripe.StripeError as e:
        logger.warning("stripe invoice list failed: %s", e)
        return {"items": []}


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


# Plans Stripe : starter, growth, pro (3 base + 3 metered prices).
STRIPE_CHECKOUT_PLAN_KEYS = ("starter", "growth", "pro")


def _get_stripe_price_ids_for_plan(plan_key: str) -> tuple[str | None, str | None]:
    """
    Mapping unique plan_key → (base_price_id, metered_price_id) depuis les env.
    Env: STRIPE_PRICE_BASE_STARTER/GROWTH/PRO, STRIPE_PRICE_METERED_STARTER/GROWTH/PRO
    (fallback: STRIPE_PRICE_METERED_MINUTES / STRIPE_METERED_PRICE_ID si un seul metered).
    """
    pk = (plan_key or "").strip().lower()
    base = (os.environ.get(f"STRIPE_PRICE_BASE_{pk.upper()}") or "").strip() or None
    metered = (
        (os.environ.get(f"STRIPE_PRICE_METERED_{pk.upper()}") or "").strip()
        or (os.environ.get("STRIPE_PRICE_METERED_MINUTES") or os.environ.get("STRIPE_METERED_PRICE_ID") or "").strip()
        or None
    )
    return (base, metered)


def _get_payment_collection_urls() -> tuple[str, str]:
    base = (
        os.environ.get("CLIENT_APP_ORIGIN")
        or os.environ.get("ADMIN_BASE_URL")
        or os.environ.get("FRONT_BASE_URL")
        or os.environ.get("APP_BASE_URL")
        or ""
    ).strip().rstrip("/")
    if base:
        return (f"{base}/app?payment=success", f"{base}/app?payment=cancelled")

    success_url = (os.environ.get("STRIPE_CHECKOUT_SUCCESS_URL") or "").strip()
    cancel_url = (os.environ.get("STRIPE_CHECKOUT_CANCEL_URL") or "").strip()
    if success_url and cancel_url:
        return (success_url, cancel_url)
    raise HTTPException(503, "CLIENT_APP_ORIGIN or STRIPE_CHECKOUT_SUCCESS_URL/STRIPE_CHECKOUT_CANCEL_URL required")


def _extract_trial_end_date_display(trial_ends_at: Any) -> str | None:
    if not trial_ends_at:
        return None
    try:
        if isinstance(trial_ends_at, datetime):
            dt = trial_ends_at
        else:
            raw = str(trial_ends_at).replace("Z", "+00:00")
            dt = datetime.fromisoformat(raw)
        months = [
            "janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre",
        ]
        return f"{dt.day} {months[dt.month - 1]} {dt.year}"
    except Exception:
        return str(trial_ends_at)[:10] or None


class StripeCheckoutBody(BaseModel):
    plan_key: str = Field(..., description="starter | growth | pro")
    trial_days: Optional[int] = Field(None, ge=1, le=365, description="Jours d'essai avant première facture")


@router.post("/admin/tenants/{tenant_id}/stripe-checkout")
def admin_create_stripe_checkout(
    tenant_id: int = Depends(validate_tenant_id),
    body: StripeCheckoutBody = Body(...),
    _: None = Depends(_verify_admin),
):
    """
    Crée une session Stripe Checkout (subscription) pour le tenant.
    Ensure customer existe (création si absent), map plan_key → (base_price, metered_price),
    2 line items : base (qty 1) + metered minutes (qty 1). Metadata tenant_id + plan_key.
    Retourne checkout_url pour redirection. Webhooks sync subscription + stripe_metered_item_id.
    """
    d = _get_tenant_detail(tenant_id)
    if not d:
        raise HTTPException(404, "Tenant not found")
    billing = get_tenant_billing(tenant_id)
    status = (billing or {}).get("billing_status") or ""
    if status in ("active", "trialing"):
        raise HTTPException(400, "Abonnement déjà actif")
    stripe_key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if not stripe_key:
        raise HTTPException(503, "Stripe not configured (STRIPE_SECRET_KEY)")
    success_url = (os.environ.get("STRIPE_CHECKOUT_SUCCESS_URL") or "").strip()
    cancel_url = (os.environ.get("STRIPE_CHECKOUT_CANCEL_URL") or "").strip()
    if not success_url or not cancel_url:
        raise HTTPException(503, "STRIPE_CHECKOUT_SUCCESS_URL and STRIPE_CHECKOUT_CANCEL_URL required")
    plan_key = (body.plan_key or "").strip().lower()
    if plan_key not in STRIPE_CHECKOUT_PLAN_KEYS:
        raise HTTPException(400, "plan_key must be one of: starter, growth, pro")
    base_price_id, metered_price_id = _get_stripe_price_ids_for_plan(plan_key)
    # En prod : privilégier les 6 vars (STRIPE_PRICE_METERED_STARTER/GROWTH/PRO) ; legacy peut masquer une mauvaise config.
    if metered_price_id and not (os.environ.get(f"STRIPE_PRICE_METERED_{plan_key.upper()}") or "").strip():
        logger.warning(
            "STRIPE_CHECKOUT_LEGACY_METERED plan_key=%s tenant_id=%s (définir STRIPE_PRICE_METERED_* pour des prices par plan)",
            plan_key, tenant_id,
        )
    if not base_price_id:
        raise HTTPException(400, "PRICE_NOT_CONFIGURED")
    if not metered_price_id:
        raise HTTPException(503, "STRIPE_PRICE_METERED_* or STRIPE_PRICE_METERED_MINUTES required")
    customer_id = (billing or {}).get("stripe_customer_id") or ""
    customer_id = (customer_id or "").strip()
    if not customer_id:
        try:
            import stripe
            stripe.api_key = stripe_key
            name = (d.get("name") or f"Tenant #{tenant_id}")[:500]
            customer = stripe.Customer.create(
                name=name,
                metadata={"tenant_id": str(tenant_id)},
            )
            customer_id = (customer.id or "").strip()
            if not customer_id:
                raise HTTPException(500, "Stripe customer id empty")
            if not set_stripe_customer_id(tenant_id, customer_id):
                raise HTTPException(500, "Failed to save stripe_customer_id")
            logger.info("STRIPE_CUSTOMER_CREATED tenant_id=%s stripe_customer_id=%s (checkout)", tenant_id, customer_id)
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            logger.warning("stripe customer create (checkout) failed: %s", e)
            raise HTTPException(502, str(e) or "Stripe error")
    try:
        import stripe
        stripe.api_key = stripe_key
        # Metered price : ne pas envoyer quantity (Stripe le rejette pour usage_type=metered)
        line_items = [
            {"price": base_price_id, "quantity": 1},
            {"price": metered_price_id},
        ]
        subscription_data = {"metadata": {"tenant_id": str(tenant_id), "plan_key": plan_key}}
        if body.trial_days is not None and body.trial_days >= 1:
            subscription_data["trial_period_days"] = body.trial_days
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=line_items,
            success_url=success_url,
            cancel_url=cancel_url,
            locale="fr",
            metadata={"tenant_id": str(tenant_id), "plan_key": plan_key},
            subscription_data=subscription_data,
        )
        url = (getattr(session, "url", None) or "").strip()
        if not url:
            raise HTTPException(500, "Stripe did not return checkout URL")
        return {"checkout_url": url}
    except stripe.StripeError as e:
        logger.warning("stripe checkout session create failed: %s", e)
        raise HTTPException(502, str(e) or "Stripe error")


@router.post("/admin/tenants/{tenant_id}/send-payment-link")
def admin_send_payment_link(
    tenant_id: int = Depends(validate_tenant_id),
    _: None = Depends(_verify_admin),
):
    """
    Génère un lien Stripe pour ajouter un moyen de paiement.
    - Si une subscription existe déjà : Checkout mode=setup pour sauver la carte.
    - Sinon : Checkout mode=subscription pour démarrer l'abonnement (trial 30j).
    """
    d = _get_tenant_detail(tenant_id)
    if not d:
        raise HTTPException(404, "Tenant not found")
    billing = get_tenant_billing(tenant_id) or {}
    params = d.get("params") or {}
    contact_email = (
        (d.get("contact_email") or "").strip()
        or (params.get("contact_email") or "").strip()
        or (params.get("billing_email") or "").strip()
    )
    if not contact_email:
        raise HTTPException(400, "contact_email required")

    stripe_key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if not stripe_key:
        raise HTTPException(503, "Stripe not configured (STRIPE_SECRET_KEY)")
    success_url, cancel_url = _get_payment_collection_urls()

    customer_id = (billing.get("stripe_customer_id") or "").strip()
    try:
        import stripe

        stripe.api_key = stripe_key
        if not customer_id:
            customer = stripe.Customer.create(
                email=contact_email,
                name=(d.get("name") or f"Tenant #{tenant_id}")[:500],
                phone=(params.get("phone_number") or "").strip() or None,
                metadata={"tenant_id": str(tenant_id), "plan": (billing.get("plan_key") or params.get("plan_key") or "")},
            )
            customer_id = (customer.id or "").strip()
            if not customer_id:
                raise HTTPException(500, "Stripe customer id empty")
            if not set_stripe_customer_id(tenant_id, customer_id):
                raise HTTPException(500, "Failed to save stripe_customer_id")

        subscription_id = (billing.get("stripe_subscription_id") or "").strip()
        plan_key = ((billing.get("plan_key") or params.get("plan_key") or "starter") or "").strip().lower()
        metadata = {"tenant_id": str(tenant_id), "plan_key": plan_key}
        if subscription_id:
            session = stripe.checkout.Session.create(
                customer=customer_id,
                mode="setup",
                payment_method_types=["card"],
                success_url=success_url,
                cancel_url=cancel_url,
                locale="fr",
                metadata=metadata,
                setup_intent_data={"metadata": metadata},
            )
        else:
            base_price_id, metered_price_id = _get_stripe_price_ids_for_plan(plan_key)
            if plan_key not in STRIPE_CHECKOUT_PLAN_KEYS:
                raise HTTPException(400, "plan_key must be one of: starter, growth, pro")
            if not base_price_id:
                raise HTTPException(400, "PRICE_NOT_CONFIGURED")
            if not metered_price_id:
                raise HTTPException(503, "STRIPE_PRICE_METERED_* or STRIPE_PRICE_METERED_MINUTES required")
            session = stripe.checkout.Session.create(
                mode="subscription",
                customer=customer_id,
                line_items=[
                    {"price": base_price_id, "quantity": 1},
                    {"price": metered_price_id},
                ],
                success_url=success_url,
                cancel_url=cancel_url,
                locale="fr",
                metadata=metadata,
                subscription_data={
                    "trial_period_days": 30,
                    "metadata": metadata,
                },
            )

        checkout_url = (getattr(session, "url", None) or "").strip()
        if not checkout_url:
            raise HTTPException(500, "Stripe did not return checkout URL")

        from backend.services.email_service import send_payment_link_email

        trial_end_date = _extract_trial_end_date_display(billing.get("trial_ends_at"))
        ok, err = send_payment_link_email(
            to=contact_email,
            tenant_name=(d.get("name") or f"Tenant #{tenant_id}"),
            checkout_url=checkout_url,
            trial_end_date=trial_end_date,
        )
        if not ok:
            logger.warning("payment_link_email_failed tenant_id=%s: %s", tenant_id, err or "unknown")

        return {
            "ok": True,
            "checkout_url": checkout_url,
            "email": contact_email,
            "email_sent": bool(ok),
            "trial_end_date": trial_end_date,
        }
    except stripe.StripeError as e:
        logger.warning("send payment link stripe failed tenant_id=%s: %s", tenant_id, e)
        raise HTTPException(502, str(e) or "Stripe error")


@router.post("/admin/tenants/{tenant_id}/send-onboarding-link")
def admin_send_tenant_onboarding_link(
    tenant_id: int = Depends(validate_tenant_id),
    body: Optional[OnboardingLinkBody] = Body(default=None),
    _: None = Depends(_verify_admin),
):
    d = _get_tenant_detail(tenant_id)
    if not d:
        raise HTTPException(404, "Tenant not found")
    params = d.get("params") or {}
    email = (
        (body.email if body else None)
        or (d.get("contact_email") or "")
        or (params.get("contact_email") or "")
        or (params.get("billing_email") or "")
    )
    email = (email or "").strip().lower()
    if not email:
        raise HTTPException(400, "contact_email required")
    name = ((body.name if body else None) or d.get("name") or params.get("manager_name") or "").strip()
    return _send_onboarding_link(email=email, name=name)


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


def _get_quota_used_minutes(tenant_id: int, start: str, end: str) -> float:
    """Somme duration_sec/60 pour le tenant sur [start, end[ (mois UTC). Utilisé par quota + tests."""
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    if not url:
        return 0.0
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(duration_sec), 0) / 60.0
                    FROM vapi_call_usage
                    WHERE tenant_id = %s AND ended_at IS NOT NULL AND ended_at >= %s AND ended_at < %s
                    """,
                    (tenant_id, start, end),
                )
                row = cur.fetchone()
                return round(float(row[0] or 0), 2) if row else 0.0
    except Exception as e:
        if "does not exist" not in str(e).lower():
            logger.warning("tenant quota usage query failed: %s", e)
    return 0.0


# MRR € par plan (aligné billing_upgrade.PLAN_BASE_EUR)
PLAN_MRR_EUR = {"starter": 99, "growth": 149, "pro": 199, "free": 0, "business": 0, "custom": 0}


def _get_billing_overview(month: str) -> dict:
    """
    Overview billing agrégé (DB only, pas d'appel Stripe).
    1 query tenants+tenant_billing, 1 query usage vapi_call_usage.
    """
    if len(month) != 7 or month[4] != "-":
        return {"month": month, "summary": {"mrr_eur_total": 0, "tenants_past_due_count": 0, "cost_usd_month_total": 0}, "tenants": []}
    try:
        y, m = int(month[:4]), int(month[5:7])
        end = f"{y}-{m + 1:02d}-01 00:00:00" if m < 12 else f"{y + 1}-01-01 00:00:00"
    except ValueError:
        return {"month": month, "summary": {"mrr_eur_total": 0, "tenants_past_due_count": 0, "cost_usd_month_total": 0}, "tenants": []}
    start = f"{month}-01 00:00:00"

    url_billing = os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL")
    url_events = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")

    tenants_data: List[dict] = []
    past_due_count = 0
    mrr_total = 0
    cost_total = 0.0

    if not url_billing:
        return {"month": month, "summary": {"mrr_eur_total": 0, "tenants_past_due_count": 0, "cost_usd_month_total": 0}, "tenants": []}

    try:
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(url_billing, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT t.tenant_id, t.name, t.status,
                           tb.stripe_customer_id, tb.stripe_subscription_id, tb.billing_status,
                           tb.plan_key, tb.current_period_start, tb.current_period_end
                    FROM tenants t
                    LEFT JOIN tenant_billing tb ON tb.tenant_id = t.tenant_id
                    WHERE COALESCE(t.status, 'active') = 'active' AND COALESCE(t.status, '') != 'deleted'
                    ORDER BY t.name
                    """,
                )
                rows = cur.fetchall()
    except Exception as e:
        if "does not exist" not in str(e).lower() and "tenant" not in str(e).lower():
            logger.warning("billing overview tenants query: %s", e)
        return {"month": month, "summary": {"mrr_eur_total": 0, "tenants_past_due_count": 0, "cost_usd_month_total": 0}, "tenants": []}

    usage_by_tenant: dict = {}
    if url_events:
        try:
            import psycopg
            with psycopg.connect(url_events) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT tenant_id,
                               COALESCE(SUM(duration_sec), 0) / 60.0 AS minutes,
                               COALESCE(SUM(cost_usd), 0) AS cost_usd
                        FROM vapi_call_usage
                        WHERE ended_at IS NOT NULL AND ended_at >= %s AND ended_at < %s
                        GROUP BY tenant_id
                        """,
                        (start, end),
                    )
                    for r in cur.fetchall() or []:
                        tid = r[0]
                        usage_by_tenant[tid] = {"minutes": round(float(r[1] or 0), 2), "cost_usd": round(float(r[2] or 0), 4)}
        except Exception as e:
            if "does not exist" not in str(e).lower() and "vapi_call_usage" not in str(e).lower():
                logger.warning("billing overview usage query: %s", e)

    for r in rows or []:
        tid = r.get("tenant_id")
        if tid is None:
            continue
        name = (r.get("name") or f"Tenant #{tid}")[:200]
        plan_key = (r.get("plan_key") or "").strip().lower() or "free"
        billing_status = (r.get("billing_status") or "").strip() or None
        if billing_status in ("past_due", "unpaid"):
            past_due_count += 1

        mrr_eur = PLAN_MRR_EUR.get(plan_key, 0)
        if billing_status in ("active", "trialing"):
            mrr_total += mrr_eur

        usage = usage_by_tenant.get(tid) or {"minutes": 0, "cost_usd": 0}
        cost_total += float(usage.get("cost_usd") or 0)

        included = get_plan_included_minutes(plan_key)
        used = round(float(usage.get("minutes") or 0), 2)

        period_end = r.get("current_period_end")
        if period_end and hasattr(period_end, "timestamp"):
            period_end_ts = int(period_end.timestamp())
        elif period_end and hasattr(period_end, "isoformat"):
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(period_end.replace("Z", "+00:00"))
                period_end_ts = int(dt.timestamp())
            except Exception:
                period_end_ts = None
        else:
            period_end_ts = None

        tenants_data.append({
            "tenant_id": tid,
            "name": name,
            "plan_key": plan_key,
            "stripe_status": billing_status,
            "stripe_customer_id": (r.get("stripe_customer_id") or "").strip() or None,
            "stripe_subscription_id": (r.get("stripe_subscription_id") or "").strip() or None,
            "current_period_end": period_end_ts,
            "mrr_eur": mrr_eur if billing_status in ("active", "trialing") else 0,
            "usage": {"minutes": used, "cost_usd": round(float(usage.get("cost_usd") or 0), 4)},
            "quota": {"included": included, "used": int(used)},
        })

    return {
        "month": month,
        "summary": {
            "mrr_eur_total": mrr_total,
            "tenants_past_due_count": past_due_count,
            "cost_usd_month_total": round(cost_total, 2),
        },
        "tenants": tenants_data,
    }


@router.get("/admin/billing/overview")
def admin_get_billing_overview(
    month: str = Query(..., description="YYYY-MM"),
    _: None = Depends(_verify_admin),
):
    """Overview billing agrégé : tenants + billing + usage + quota en 1 round-trip (DB only)."""
    if len(month) != 7 or month[4] != "-":
        raise HTTPException(400, "month must be YYYY-MM")
    return _get_billing_overview(month)


@router.get("/admin/billing/plans")
def admin_get_billing_plans(_: None = Depends(_verify_admin)):
    """Liste des plans (plan_key, name, mrr_eur, quota_min)."""
    items = get_billing_plans()
    out = []
    for it in items or []:
        pk = (it.get("plan_key") or "").strip().lower()
        quota = int(it.get("included_minutes_month") or 0)
        out.append({
            "id": pk,
            "plan_key": pk,
            "name": pk.capitalize() if pk else "",
            "included_minutes_month": quota,
            "quota_min": quota,
            "mrr_eur": PLAN_MRR_EUR.get(pk, 0),
        })
    return {"items": out}


_PLAN_INCLUDED_MIN = {"starter": 400, "growth": 800, "pro": 1200, "trial": 200, "free": 0}
_PLAN_OVERAGE_EUR = {"starter": 0.19, "growth": 0.17, "pro": 0.15, "trial": 0.0, "free": 0.0}


def _period_to_month(period: str) -> str:
    token = (period or "").strip().lower()
    now = datetime.utcnow()
    if token in {"", "month", "current", "current_month"}:
        return now.strftime("%Y-%m")
    if token in {"prev_month", "previous_month", "last_month"}:
        y = now.year
        m = now.month - 1
        if m == 0:
            y -= 1
            m = 12
        return f"{y}-{m:02d}"
    if len(token) == 7 and token[4] == "-" and token[:4].isdigit() and token[5:7].isdigit():
        return token
    return now.strftime("%Y-%m")


def _enrich_billing_tenant(item: Dict[str, Any]) -> Dict[str, Any]:
    plan_key = str(item.get("plan_key") or "free").strip().lower()
    included = int(item.get("quota", {}).get("included") or _PLAN_INCLUDED_MIN.get(plan_key, 0))
    used = float(item.get("usage", {}).get("minutes") or item.get("quota", {}).get("used") or 0)
    overage_price = float(_PLAN_OVERAGE_EUR.get(plan_key, 0.0))
    over_minutes = max(0, int(round(used - included)))
    over_amount = round(over_minutes * overage_price, 2)
    mrr = float(item.get("mrr_eur") or PLAN_MRR_EUR.get(plan_key, 0))
    vapi_cost = float(item.get("usage", {}).get("cost_usd") or 0)
    expected_revenue = round(mrr + over_amount, 2)
    margin = round(expected_revenue - vapi_cost, 2)
    margin_rate = round((margin / expected_revenue), 4) if expected_revenue > 0 else 0.0
    usage_pct = int(round((used / included) * 100)) if included > 0 else 0
    alerts: List[str] = []
    stripe_customer_id = item.get("stripe_customer_id")
    stripe_subscription_id = item.get("stripe_subscription_id")
    stripe_status = str(item.get("stripe_status") or "").strip().lower()
    if not stripe_customer_id:
        alerts.append("stripe_customer_missing")
    if not stripe_subscription_id:
        alerts.append("subscription_missing")
    if stripe_status in {"past_due", "unpaid"}:
        alerts.append("payment_failed")
    if stripe_status in {"incomplete", "incomplete_expired"}:
        alerts.append("stripe_incomplete")
    if usage_pct >= 85:
        alerts.append("quota_high")
    if over_minutes > 0:
        alerts.append("overage")
    if margin < 0:
        alerts.append("margin_negative")
    if stripe_status == "trialing":
        alerts.append("trial_expiring")

    return {
        **item,
        "included_minutes": included,
        "voice_minutes_used": round(used, 2),
        "overage_price_per_minute": overage_price,
        "overage_minutes": over_minutes,
        "overage_amount_estimate": over_amount,
        "vapi_cost_estimate": round(vapi_cost, 4),
        "vapi_cost_is_estimate": True,
        "estimated_revenue": expected_revenue,
        "estimated_margin": margin,
        "estimated_margin_rate": margin_rate,
        "usage_percent": usage_pct,
        "alerts": alerts,
        "alerts_count": len(alerts),
    }


@router.get("/admin/billing/summary")
def admin_billing_summary(
    period: str = Query("month"),
    _: None = Depends(_verify_admin),
):
    """Résumé agrégé billing pour cockpit admin."""
    month = _period_to_month(period)
    payload = _get_billing_overview(month)
    tenants = [_enrich_billing_tenant(item) for item in (payload.get("tenants") or [])]
    mrr = round(sum(float(t.get("mrr_eur") or 0) for t in tenants), 2)
    estimated_revenue = round(sum(float(t.get("estimated_revenue") or 0) for t in tenants), 2)
    vapi_cost = round(sum(float(t.get("vapi_cost_estimate") or 0) for t in tenants), 2)
    margin = round(estimated_revenue - vapi_cost, 2)
    margin_rate = round((margin / estimated_revenue), 4) if estimated_revenue > 0 else 0.0
    minutes = round(sum(float(t.get("voice_minutes_used") or 0) for t in tenants), 2)
    overage = round(sum(float(t.get("overage_amount_estimate") or 0) for t in tenants), 2)
    alerts_count = int(sum(int(t.get("alerts_count") or 0) for t in tenants))
    return {
        "period": month,
        "mrr": mrr,
        "estimated_revenue": estimated_revenue,
        "vapi_cost_estimate": vapi_cost,
        "vapi_cost_currency": "EUR",
        "vapi_cost_is_estimate": True,
        "estimated_margin": margin,
        "estimated_margin_rate": margin_rate,
        "voice_minutes_used": minutes,
        "estimated_overage_amount": overage,
        "billing_alerts_count": alerts_count,
    }


@router.get("/admin/billing/action-items")
def admin_billing_action_items(
    period: str = Query("month"),
    _: None = Depends(_verify_admin),
):
    """Actions billing prioritaires (paiement, quota, marge)."""
    month = _period_to_month(period)
    payload = _get_billing_overview(month)
    tenants = [_enrich_billing_tenant(item) for item in (payload.get("tenants") or [])]
    items: List[Dict[str, Any]] = []
    for tenant in tenants:
        tid = int(tenant.get("tenant_id") or 0)
        tname = str(tenant.get("name") or f"Tenant #{tid}")
        if "stripe_customer_missing" in tenant.get("alerts", []):
            items.append(
                {
                    "id": f"{tid}:stripe_missing",
                    "severity": "critical",
                    "tenant_id": tid,
                    "tenant_name": tname,
                    "type": "stripe_missing",
                    "title": "Stripe customer manquant",
                    "description": "Créer checkout + synchroniser la fiche Stripe.",
                    "primary_action_label": "Créer checkout",
                    "primary_action_url": f"/admin/billing/{tid}?tab=actions",
                    "secondary_action_label": "Voir fiche",
                    "secondary_action_url": f"/admin/tenants/{tid}",
                    "created_at": datetime.utcnow().isoformat() + "Z",
                }
            )
        if "margin_negative" in tenant.get("alerts", []):
            items.append(
                {
                    "id": f"{tid}:margin_negative",
                    "severity": "critical",
                    "tenant_id": tid,
                    "tenant_name": tname,
                    "type": "margin_negative",
                    "title": "Marge négative estimée",
                    "description": "Le coût Vapi dépasse le revenu estimé sur la période.",
                    "primary_action_label": "Voir usage",
                    "primary_action_url": f"/admin/billing/{tid}?tab=usage",
                    "secondary_action_label": "Changer plan",
                    "secondary_action_url": f"/admin/billing/{tid}?tab=actions",
                    "created_at": datetime.utcnow().isoformat() + "Z",
                }
            )
        if "quota_high" in tenant.get("alerts", []):
            items.append(
                {
                    "id": f"{tid}:quota_high",
                    "severity": "warning",
                    "tenant_id": tid,
                    "tenant_name": tname,
                    "type": "quota_high",
                    "title": f"Quota à {tenant.get('usage_percent', 0)}%",
                    "description": "Dépassement probable avant fin de mois.",
                    "primary_action_label": "Proposer Growth",
                    "primary_action_url": f"/admin/billing/{tid}?tab=actions",
                    "secondary_action_label": "Voir billing",
                    "secondary_action_url": f"/admin/billing/{tid}",
                    "created_at": datetime.utcnow().isoformat() + "Z",
                }
            )
        if "trial_expiring" in tenant.get("alerts", []):
            items.append(
                {
                    "id": f"{tid}:trial_expiring",
                    "severity": "warning",
                    "tenant_id": tid,
                    "tenant_name": tname,
                    "type": "trial_expiring",
                    "title": "Essai gratuit actif",
                    "description": "Prévoir la conversion vers un plan Starter/Growth.",
                    "primary_action_label": "Relancer",
                    "primary_action_url": f"/admin/billing/{tid}?tab=actions",
                    "secondary_action_label": "Créer checkout",
                    "secondary_action_url": f"/admin/billing/{tid}?tab=actions",
                    "created_at": datetime.utcnow().isoformat() + "Z",
                }
            )
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    items.sort(key=lambda it: (severity_order.get(str(it.get("severity")), 9), str(it.get("tenant_name") or "")))
    return {"items": items}


@router.get("/admin/billing/tenants")
def admin_billing_tenants(
    period: str = Query("month"),
    filter: str = Query("all"),
    sort: str = Query("margin_low"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200),
    _: None = Depends(_verify_admin),
):
    """Liste des tenants enrichie pour cockpit billing (filtres/tri/pagination)."""
    month = _period_to_month(period)
    payload = _get_billing_overview(month)
    rows = [_enrich_billing_tenant(item) for item in (payload.get("tenants") or [])]
    q = (search or "").strip().lower()
    if q:
        rows = [r for r in rows if q in f"{r.get('name','')} {r.get('plan_key','')} {r.get('stripe_status','')} {r.get('tenant_id','')}".lower()]
    f = (filter or "all").strip().lower()
    if f in {"active", "actifs"}:
        rows = [r for r in rows if str(r.get("stripe_status") or "").lower() == "active"]
    elif f in {"trial", "essais", "trialing"}:
        rows = [r for r in rows if str(r.get("stripe_status") or "").lower() == "trialing"]
    elif f in {"quota_high", "quota élevé", "quota_eleve"}:
        rows = [r for r in rows if int(r.get("usage_percent") or 0) >= 85]
    elif f in {"overage", "depassement", "dépassement"}:
        rows = [r for r in rows if int(r.get("overage_minutes") or 0) > 0]
    elif f in {"margin_low", "marge_faible", "marge faible"}:
        rows = [r for r in rows if float(r.get("estimated_margin") or 0) < 30]
    elif f in {"stripe_incomplete", "stripe incomplet"}:
        rows = [r for r in rows if (not r.get("stripe_customer_id")) or (not r.get("stripe_subscription_id")) or str(r.get("stripe_status") or "").lower() == "incomplete"]
    elif f in {"alerts", "alertes"}:
        rows = [r for r in rows if int(r.get("alerts_count") or 0) > 0]

    s = (sort or "margin_low").strip().lower()
    if s in {"mrr_desc", "mrr"}:
        rows.sort(key=lambda r: float(r.get("mrr_eur") or 0), reverse=True)
    elif s in {"vapi_cost_desc", "vapi"}:
        rows.sort(key=lambda r: float(r.get("vapi_cost_estimate") or 0), reverse=True)
    elif s in {"usage_desc", "usage"}:
        rows.sort(key=lambda r: float(r.get("usage_percent") or 0), reverse=True)
    elif s in {"name_asc", "name"}:
        rows.sort(key=lambda r: str(r.get("name") or "").lower())
    elif s in {"next_invoice_asc", "invoice"}:
        rows.sort(key=lambda r: int(r.get("current_period_end") or 0))
    elif s in {"last_stripe_sync_desc"}:
        rows.sort(key=lambda r: str(r.get("updated_at") or ""), reverse=True)
    else:
        rows.sort(key=lambda r: float(r.get("estimated_margin") or 0))

    total = len(rows)
    start = (page - 1) * limit
    items = rows[start : start + limit]
    return {"period": month, "items": items, "total": total, "page": page, "limit": limit}


@router.get("/admin/billing/tenants/{tenant_id}/overview")
def admin_billing_tenant_overview(
    tenant_id: int = Depends(validate_tenant_id),
    period: str = Query("month"),
    _: None = Depends(_verify_admin),
):
    month = _period_to_month(period)
    payload = _get_billing_overview(month)
    for item in payload.get("tenants") or []:
        if int(item.get("tenant_id") or 0) == tenant_id:
            enriched = _enrich_billing_tenant(item)
            return {"period": month, "tenant": enriched}
    raise HTTPException(404, "Tenant billing overview not found")


@router.get("/admin/billing/tenants/{tenant_id}/usage")
def admin_billing_tenant_usage(
    tenant_id: int = Depends(validate_tenant_id),
    period: str = Query("month"),
    _: None = Depends(_verify_admin),
):
    month = _period_to_month(period)
    usage = _get_tenant_usage(tenant_id, month)
    quota = admin_get_tenant_quota(tenant_id=tenant_id, month=month, _=None)  # type: ignore[arg-type]
    used = float(usage.get("minutes_total") or 0)
    included = int(quota.get("included_minutes_month") or 0)
    over = max(0, round(used - included, 2))
    plan_key = str(quota.get("plan_key") or "free").lower()
    overage_amount = round(over * float(_PLAN_OVERAGE_EUR.get(plan_key, 0.0)), 2)
    return {
        "tenant_id": tenant_id,
        "period": month,
        "voice_minutes_used": used,
        "included_minutes": included,
        "overage_minutes": over,
        "overage_amount": overage_amount,
        "vapi_cost_estimate": float(usage.get("cost_usd") or 0),
        "vapi_cost_is_estimate": True,
        "projected_minutes_end_period": round(used * 1.18, 2),
        "projected_overage_amount": round(max(0, (used * 1.18) - included) * float(_PLAN_OVERAGE_EUR.get(plan_key, 0.0)), 2),
    }


@router.get("/admin/billing/tenants/{tenant_id}/stripe")
def admin_billing_tenant_stripe(
    tenant_id: int = Depends(validate_tenant_id),
    _: None = Depends(_verify_admin),
):
    billing = get_tenant_billing(tenant_id)
    if billing is None:
        raise HTTPException(404, "Tenant billing not found")
    return {
        "tenant_id": tenant_id,
        "stripe_customer_id": billing.get("stripe_customer_id"),
        "stripe_subscription_id": billing.get("stripe_subscription_id"),
        "stripe_metered_item_id": billing.get("stripe_metered_item_id"),
        "billing_status": billing.get("billing_status"),
        "plan_key": billing.get("plan_key"),
        "current_period_start": billing.get("current_period_start"),
        "current_period_end": billing.get("current_period_end"),
        "trial_ends_at": billing.get("trial_ends_at"),
        "updated_at": billing.get("updated_at"),
    }


@router.get("/admin/billing/tenants/{tenant_id}/invoices")
def admin_billing_tenant_invoices(
    tenant_id: int = Depends(validate_tenant_id),
    limit: int = Query(10, ge=1, le=50),
    _: None = Depends(_verify_admin),
):
    return admin_billing_invoices(tenant_id=tenant_id, limit=limit, _=None)  # type: ignore[arg-type]


def _admin_actor_label(request: Optional[Request]) -> str:
    if not request:
        return "admin"
    return _get_admin_email_from_cookie(request) or "admin_token"


@router.post("/admin/billing/sync-stripe")
def admin_billing_sync_stripe(
    period: str = Query("month"),
    request: Request = None,
    _: None = Depends(_verify_admin),
):
    """Resync metered item pour tous les tenants présents dans la vue billing."""
    from backend.routes.stripe_webhook import resync_metered_item_for_tenant

    actor = _admin_actor_label(request)
    month = _period_to_month(period)
    payload = _get_billing_overview(month)
    results = []
    for item in payload.get("tenants") or []:
        tid = int(item.get("tenant_id") or 0)
        if tid < 1:
            continue
        result = resync_metered_item_for_tenant(tid)
        results.append({"tenant_id": tid, **result})
    logger.info("BILLING_SYNC_STRIPE actor=%s period=%s tenants=%s", actor, month, len(results))
    return {"period": month, "items": results}


@router.post("/admin/billing/tenants/{tenant_id}/sync-stripe")
def admin_billing_sync_stripe_tenant(
    tenant_id: int = Depends(validate_tenant_id),
    request: Request = None,
    _: None = Depends(_verify_admin),
):
    from backend.routes.stripe_webhook import resync_metered_item_for_tenant

    actor = _admin_actor_label(request)
    result = resync_metered_item_for_tenant(tenant_id)
    logger.info("BILLING_SYNC_STRIPE_TENANT actor=%s tenant_id=%s ok=%s", actor, tenant_id, bool(result.get("ok")))
    return {"tenant_id": tenant_id, **result}


def _push_usage_for_single_tenant(tenant_id: int, date_utc: date) -> Dict[str, Any]:
    """Push usage journalier pour un tenant (idempotent via stripe_usage_push_log)."""
    from backend.billing_pg import get_tenant_billing as _get_tb
    from backend.stripe_usage import (
        _aggregate_usage_by_tenant_for_day,  # pylint: disable=protected-access
        try_acquire_usage_push,
        mark_usage_push_failed,
        mark_usage_push_sent,
    )

    rows = {int(tid): int(minutes) for tid, minutes in (_aggregate_usage_by_tenant_for_day(date_utc) or [])}
    minutes = int(rows.get(int(tenant_id), 0))
    if minutes <= 0:
        return {"ok": True, "tenant_id": tenant_id, "date_utc": date_utc.isoformat(), "status": "skipped", "reason": "no_usage"}

    billing = _get_tb(tenant_id) or {}
    metered_item_id = str(billing.get("stripe_metered_item_id") or "").strip()
    if not metered_item_id:
        return {"ok": False, "tenant_id": tenant_id, "date_utc": date_utc.isoformat(), "status": "failed", "reason": "no_metered_item"}

    acquired = try_acquire_usage_push(tenant_id, date_utc, minutes)
    if not acquired:
        return {"ok": True, "tenant_id": tenant_id, "date_utc": date_utc.isoformat(), "status": "skipped", "reason": "already_sent_or_pending"}

    stripe_key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if not stripe_key:
        mark_usage_push_failed(tenant_id, date_utc, "STRIPE_SECRET_KEY not set")
        return {"ok": False, "tenant_id": tenant_id, "date_utc": date_utc.isoformat(), "status": "failed", "reason": "stripe_key_missing"}
    try:
        import stripe

        stripe.api_key = stripe_key
        end_of_day_ts = int(datetime(date_utc.year, date_utc.month, date_utc.day, 23, 59, 59, tzinfo=timezone.utc).timestamp())
        record = stripe.UsageRecord.create(
            subscription_item=metered_item_id,
            quantity=minutes,
            timestamp=end_of_day_ts,
            action="set",
        )
        usage_record_id = getattr(record, "id", None) if record else None
        mark_usage_push_sent(tenant_id, date_utc, stripe_usage_record_id=usage_record_id)
        return {
            "ok": True,
            "tenant_id": tenant_id,
            "date_utc": date_utc.isoformat(),
            "status": "sent",
            "minutes_pushed": minutes,
            "stripe_usage_record_id": usage_record_id,
        }
    except Exception as e:
        mark_usage_push_failed(tenant_id, date_utc, str(e)[:255])
        return {"ok": False, "tenant_id": tenant_id, "date_utc": date_utc.isoformat(), "status": "failed", "reason": str(e)[:200]}


@router.post("/admin/billing/tenants/{tenant_id}/push-usage")
def admin_billing_push_usage_tenant(
    tenant_id: int = Depends(validate_tenant_id),
    target_date: Optional[str] = Query(None, description="YYYY-MM-DD (UTC), default yesterday"),
    request: Request = None,
    _: None = Depends(_verify_admin),
):
    try:
        if target_date:
            d = datetime.fromisoformat(target_date).date()
        else:
            d = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    except Exception:
        raise HTTPException(400, "target_date must be YYYY-MM-DD")
    result = _push_usage_for_single_tenant(tenant_id, d)
    actor = _admin_actor_label(request)
    logger.info(
        "BILLING_PUSH_USAGE_TENANT actor=%s tenant_id=%s date_utc=%s status=%s",
        actor,
        tenant_id,
        d.isoformat(),
        result.get("status"),
    )
    return result


@router.post("/admin/billing/push-usage")
def admin_billing_push_usage_global(
    target_date: Optional[str] = Query(None, description="YYYY-MM-DD (UTC), default yesterday"),
    request: Request = None,
    _: None = Depends(_verify_admin),
):
    from backend.stripe_usage import push_daily_usage_to_stripe

    try:
        if target_date:
            d = datetime.fromisoformat(target_date).date()
        else:
            d = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    except Exception:
        raise HTTPException(400, "target_date must be YYYY-MM-DD")
    result = push_daily_usage_to_stripe(d)
    actor = _admin_actor_label(request)
    logger.info("BILLING_PUSH_USAGE_GLOBAL actor=%s date_utc=%s ok=%s", actor, d.isoformat(), bool(result.get("ok")))
    return {"date_utc": d.isoformat(), **result}


@router.patch("/admin/billing/tenants/{tenant_id}/plan")
def admin_billing_patch_plan(
    body: ChangePlanBody,
    tenant_id: int = Depends(validate_tenant_id),
    _: None = Depends(_verify_admin),
):
    return admin_billing_change_plan(tenant_id=tenant_id, body=body, _=None)  # type: ignore[arg-type]


class BillingSuspendBody(BaseModel):
    mode: str = Field(default="hard", pattern="^(hard|soft)$")


@router.post("/admin/billing/tenants/{tenant_id}/suspend")
def admin_billing_suspend_tenant(
    body: BillingSuspendBody,
    tenant_id: int = Depends(validate_tenant_id),
    request: Request = None,
    _: None = Depends(_verify_admin),
):
    ok = set_tenant_suspended(tenant_id, reason="manual", mode=body.mode)
    if not ok:
        raise HTTPException(500, "Failed to suspend tenant")
    actor = _admin_actor_label(request)
    logger.info("BILLING_SUSPEND_TENANT actor=%s tenant_id=%s mode=%s", actor, tenant_id, body.mode)
    return {"ok": True, "tenant_id": tenant_id, "mode": body.mode}


@router.get("/admin/tenants/{tenant_id}/quota")
def admin_get_tenant_quota(
    tenant_id: int = Depends(validate_tenant_id),
    month: str = Query(..., description="YYYY-MM (mois UTC)"),
    _: None = Depends(_verify_admin),
):
    """Snapshot quota mois UTC : used_minutes / included_minutes, usage_pct, remaining."""
    d = _get_tenant_detail(tenant_id)
    if not d:
        raise HTTPException(404, "Tenant not found")
    if len(month) != 7 or month[4] != "-":
        raise HTTPException(400, "month must be YYYY-MM")
    start = f"{month}-01 00:00:00"
    try:
        y, m = int(month[:4]), int(month[5:7])
        end = f"{y}-{m + 1:02d}-01 00:00:00" if m < 12 else f"{y + 1}-01-01 00:00:00"
    except ValueError:
        raise HTTPException(400, "month must be YYYY-MM")

    params = d.get("params") or {}
    plan_key = params.get("plan_key") or ""
    if not plan_key and get_tenant_billing(tenant_id):
        plan_key = (get_tenant_billing(tenant_id) or {}).get("plan_key") or ""
    plan_key = (plan_key or "").strip() or "free"

    if plan_key == "custom":
        try:
            custom_val = int(params.get("custom_included_minutes_month") or 0)
            included = custom_val if custom_val > 0 else get_plan_included_minutes("custom")
            quota_source = "custom" if custom_val > 0 else "plan"
        except (TypeError, ValueError):
            included = get_plan_included_minutes("custom")
            quota_source = "plan"
    else:
        included = get_plan_included_minutes(plan_key)
        quota_source = "plan"

    used_minutes_month = _get_quota_used_minutes(tenant_id, start, end)

    usage_pct = (used_minutes_month / included * 100) if included else (100.0 if used_minutes_month else 0.0)
    remaining = max(0, included - used_minutes_month) if included else 0

    return {
        "tenant_id": tenant_id,
        "month_utc": month,
        "plan_key": plan_key,
        "included_minutes_month": included,
        "used_minutes_month": used_minutes_month,
        "usage_pct": round(usage_pct, 1),
        "remaining_minutes_month": int(remaining),
        "quota_source": quota_source,
    }


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


@router.post("/admin/tenants/{tenant_id}/provision-access")
def admin_provision_tenant_access(
    tenant_id: int = Depends(validate_tenant_id),
    body: Optional[ProvisionAccessBody] = Body(default=None),
    _: None = Depends(_verify_admin),
):
    """
    Crée un tenant_user (mot de passe temporaire) et envoie l'email de première connexion (/login).
    Distinct du lien wizard public (/creer-assistante) envoyé via send-onboarding-link.
    """
    import secrets

    from backend.services.email_service import send_welcome_email

    d = _get_tenant_detail(tenant_id)
    if not d:
        raise HTTPException(404, "Tenant not found")
    params = d.get("params") or {}
    contact_email = (
        (body.email if body else None)
        or (params.get("owner_login_email") or "")
        or (d.get("contact_email") or "")
        or (params.get("contact_email") or "")
    ).strip().lower()
    if not contact_email:
        raise HTTPException(400, "email required")

    existing = pg_get_tenant_user_by_email(contact_email)
    if existing:
        existing_tid, _, _ = existing
        if int(existing_tid) != int(tenant_id):
            raise HTTPException(409, "Cet email est déjà rattaché à un autre client.")

    temp_password = secrets.token_urlsafe(10)
    if not pg_create_tenant_user(
        tenant_id,
        contact_email,
        role="owner",
        password=temp_password,
        must_change_password=True,
    ):
        raise HTTPException(500, "Impossible de créer ou mettre à jour l'utilisateur")

    client_name = (
        (body.name if body else None)
        or d.get("name")
        or params.get("business_name")
        or "Votre cabinet"
    ).strip()
    assistant_id = (params.get("assistant_name") or "sophie").strip()
    plan_key = (params.get("plan_key") or d.get("plan_key") or "starter").strip() or "starter"
    phone = (params.get("phone_number") or "").strip()

    ok, err = send_welcome_email(
        email=contact_email,
        client_name=client_name,
        assistant_id=assistant_id,
        plan_key=plan_key,
        phone_number=phone,
        temp_password=temp_password,
    )
    if not ok:
        raise HTTPException(502, err or "Envoi email échoué")
    return {"ok": True, "email": contact_email, "email_sent": True}


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
    from backend.cabinet_profile_pg import canonicalize_cabinet_params

    params = canonicalize_cabinet_params(body.params or {})
    if config.USE_PG_TENANTS:
        ok = pg_update_tenant_params(tenant_id, params)
        if ok:
            sync_normalized_from_params(tenant_id, params)
            return {"ok": True}
    from backend.tenant_config import set_params
    set_params(tenant_id, body.params)
    return {"ok": True}


@router.patch("/admin/tenants/{tenant_id}/horaires")
def admin_patch_horaires(
    tenant_id: int = Depends(validate_tenant_id),
    body: HorairesBody = ...,
    _: None = Depends(_verify_admin),
):
    """Met à jour les horaires structurés d'un tenant et dérive le texte d'affichage."""
    rules = _validate_horaires_payload(body)
    horaires = derive_horaires_text(rules)
    payload = {**rules, "horaires": horaires}
    if config.USE_PG_TENANTS:
        ok = pg_update_tenant_params(tenant_id, payload)
        if ok:
            sync_opening_hours_from_booking_rules(tenant_id, payload)
            return {"ok": True, "horaires": horaires, **rules}
    from backend.tenant_config import set_params
    set_params(tenant_id, payload)
    return {"ok": True, "horaires": horaires, **rules}


@router.get("/admin/tenants/{tenant_id}/cabinet-profile-audit")
def admin_get_cabinet_profile_audit(
    tenant_id: int = Depends(validate_tenant_id),
    _: None = Depends(_verify_admin),
):
    """
    Audit post-backfill: compare tenant_config.params_json vs tables normalisées
    utilisées par la page "Mon cabinet".
    """
    return _build_cabinet_profile_audit(tenant_id)


@router.get("/admin/cabinet-profile-audit")
def admin_get_cabinet_profile_audit_all(
    include_inactive: bool = Query(False, description="Inclure les tenants inactifs"),
    only_mismatch: bool = Query(False, description="Ne retourner que les tenants avec mismatch"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: None = Depends(_verify_admin),
):
    """
    Audit global post-backfill sur plusieurs tenants.
    """
    tenants = _get_tenant_list(include_inactive=include_inactive)
    rows: list[dict] = []
    for tenant in tenants:
        tid = int(tenant.get("tenant_id") or 0)
        if tid < 1:
            continue
        try:
            audit = _build_cabinet_profile_audit(tid)
            mismatch_count = int(audit.get("summary", {}).get("total_mismatch_count") or 0)
            if only_mismatch and mismatch_count == 0:
                continue
            rows.append(
                {
                    "tenant_id": tid,
                    "tenant_name": tenant.get("name") or "",
                    "tenant_status": tenant.get("status") or "active",
                    "is_fully_synced": bool(audit.get("summary", {}).get("is_fully_synced")),
                    "total_mismatch_count": mismatch_count,
                    "sections": {
                        "profile": int(audit["sections"]["profile"]["mismatch_count"]),
                        "availability_settings": int(audit["sections"]["availability_settings"]["mismatch_count"]),
                        "booking_rules": int(audit["sections"]["booking_rules"]["mismatch_count"]),
                        "assistant_settings": int(audit["sections"]["assistant_settings"]["mismatch_count"]),
                        "opening_hours": int(audit["sections"]["opening_hours"]["mismatch_count"]),
                        "appointment_reasons": int(audit["sections"]["appointment_reasons"]["mismatch_count"]),
                    },
                }
            )
        except Exception as e:
            rows.append(
                {
                    "tenant_id": tid,
                    "tenant_name": tenant.get("name") or "",
                    "tenant_status": tenant.get("status") or "active",
                    "error": str(e)[:300],
                }
            )

    rows.sort(key=lambda item: int(item.get("total_mismatch_count") or -1), reverse=True)
    total = len(rows)
    paged = rows[offset: offset + limit]
    synced = sum(1 for item in rows if item.get("is_fully_synced") is True)
    mismatch = sum(1 for item in rows if int(item.get("total_mismatch_count") or 0) > 0)
    errored = sum(1 for item in rows if "error" in item)

    return {
        "summary": {
            "total_tenants": total,
            "fully_synced_tenants": synced,
            "tenants_with_mismatch": mismatch,
            "tenants_with_error": errored,
        },
        "pagination": {
            "limit": limit,
            "offset": offset,
            "returned": len(paged),
            "has_more": (offset + limit) < total,
        },
        "rows": paged,
    }


async def _sync_admin_faq_to_vapi(tenant_id: int) -> None:
    try:
        await update_vapi_assistant_faq(tenant_id)
    except Exception as e:
        logger.error("admin_faq_vapi_sync_failed tenant_id=%s error=%s", tenant_id, e)


@router.get("/admin/tenants/{tenant_id}/faq")
def admin_get_tenant_faq(
    tenant_id: int = Depends(validate_tenant_id),
    _: None = Depends(_verify_admin),
):
    return get_faq(tenant_id)


@router.put("/admin/tenants/{tenant_id}/faq")
async def admin_put_tenant_faq(
    tenant_id: int = Depends(validate_tenant_id),
    body: List[Dict[str, Any]] = Body(...),
    _: None = Depends(_verify_admin),
):
    faq_payload = normalize_faq_payload(body)
    if not faq_payload:
        raise HTTPException(status_code=400, detail="FAQ invalide.")
    if config.USE_PG_TENANTS:
        ok = pg_update_tenant_params(tenant_id, {"faq_json": faq_payload})
        if not ok:
            raise HTTPException(status_code=500, detail="Impossible d'enregistrer la FAQ.")
    else:
        set_params(tenant_id, {"faq_json": faq_payload})
    await _sync_admin_faq_to_vapi(tenant_id)
    return {"ok": True, "faq": faq_payload}


@router.post("/admin/tenants/{tenant_id}/faq/reset")
async def admin_reset_tenant_faq(
    tenant_id: int = Depends(validate_tenant_id),
    _: None = Depends(_verify_admin),
):
    if config.USE_PG_TENANTS:
        ok = pg_delete_tenant_param_keys(tenant_id, ["faq_json"])
        if not ok:
            raise HTTPException(status_code=500, detail="Impossible de réinitialiser la FAQ.")
    else:
        reset_faq_params(tenant_id)
    await _sync_admin_faq_to_vapi(tenant_id)
    return {"ok": True, "faq": get_faq(tenant_id)}


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


@router.post("/admin/tenants/create")
async def admin_create_tenant_full(
    body: CreateTenantRequest,
    _: None = Depends(_verify_admin),
):
    """
    Crée un tenant complet : DB + Vapi + Stripe + Twilio + email.
    Retourne tenant_id et les IDs externes (vapi, stripe, twilio).
    """
    from datetime import datetime

    import stripe

    from backend.services.email_service import send_welcome_email
    from backend.vapi_utils import assign_twilio_to_vapi, create_vapi_assistant, delete_vapi_assistant

    results: Dict[str, Any] = {
        "tenant_id": None,
        "vapi_assistant_id": None,
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
        "twilio_number": body.twilio_number,
        "errors": [],
        "warnings": [],
    }
    created: Dict[str, Any] = {}
    current_step = 0

    if not config.USE_PG_TENANTS:
        raise HTTPException(503, "Création tenant complète requiert Postgres (USE_PG_TENANTS)")

    contact_email = (body.email or "").strip().lower()
    if not contact_email:
        raise HTTPException(400, "email requis")

    existing = pg_get_tenant_user_by_email(contact_email)
    if existing:
        raise HTTPException(409, "Cet email est déjà rattaché à un autre client.")

    lead = None
    if body.lead_id:
        try:
            from backend.leads_pg import get_lead

            lead = get_lead(body.lead_id)
        except Exception as e:
            logger.warning("createTenantFull lead load failed lead_id=%s: %s", body.lead_id, e)

    temp_password = secrets.token_urlsafe(10)
    stripe_key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if not stripe_key:
        raise HTTPException(503, "STRIPE_SECRET_KEY non configuré")
    stripe.api_key = stripe_key

    base_price_id, metered_price_id = _get_stripe_price_ids_for_plan(body.plan_key)
    if not base_price_id:
        raise HTTPException(503, "STRIPE_PRICE_BASE_* non configuré pour ce plan")

    async def _rollback_provisioning() -> None:
        if created.get("stripe_subscription_id"):
            try:
                stripe.Subscription.cancel(created["stripe_subscription_id"])
            except Exception as rollback_exc:
                logger.warning("createTenantFull rollback stripe subscription failed: %s", rollback_exc)
        if created.get("stripe_customer_id"):
            try:
                stripe.Customer.delete(created["stripe_customer_id"])
            except Exception as rollback_exc:
                logger.warning("createTenantFull rollback stripe customer failed: %s", rollback_exc)
        if created.get("vapi_assistant_id"):
            ok = await delete_vapi_assistant(created["vapi_assistant_id"])
            if not ok:
                logger.warning("createTenantFull rollback vapi assistant failed: %s", created["vapi_assistant_id"])
        if created.get("tenant_id"):
            ok = pg_delete_tenant(created["tenant_id"])
            if not ok:
                logger.warning("createTenantFull rollback tenant failed tenant_id=%s", created["tenant_id"])

    try:
        current_step = 1
        logger.info("createTenantFull step=1 started tenant_id=pending")
        tid = pg_create_tenant(
            name=body.name.strip(),
            contact_email=contact_email,
            calendar_provider="none",
            calendar_id="",
            timezone=body.timezone,
            status="active",
            plan_key=body.plan_key,
        )
        if not tid:
            raise RuntimeError("Impossible de créer le tenant en base")
        created["tenant_id"] = tid
        results["tenant_id"] = tid

        if not pg_create_tenant_user(
            tid,
            contact_email,
            role="owner",
            password=temp_password,
            must_change_password=True,
        ):
            raise RuntimeError("Impossible de créer le tenant_user")
        if not pg_update_tenant_flags(
            tid,
            {
                "ENABLE_BOOKING": True,
                "ENABLE_TRANSFER": True,
                "ENABLE_FAQ": True,
                "ENABLE_ANTI_LOOP": True,
            },
        ):
            raise RuntimeError("Impossible d'enregistrer les flags du tenant")
        tenant_params_payload: Dict[str, Any] = {
            "assistant_name": body.assistant_id,
            "business_name": body.name.strip(),
            "phone_number": body.phone,
            "sector": body.sector,
            "plan_key": body.plan_key,
            "contact_email": contact_email,
            "client_onboarding_completed": False,
        }
        if lead:
            tenant_params_payload.update(
                {
                    "specialty_label": (lead.get("medical_specialty_label") or "").strip(),
                    "city": (lead.get("city") or "").strip(),
                    "lead_id": lead.get("id"),
                    "lead_source": lead.get("source") or "landing_cta",
                    "lead_daily_call_volume": lead.get("daily_call_volume") or "",
                    "lead_primary_pain_point": lead.get("primary_pain_point") or "",
                    "lead_opening_hours": lead.get("opening_hours") or {},
                }
            )
        if not pg_update_tenant_params(
            tid,
            tenant_params_payload,
        ):
            raise RuntimeError("Impossible d'enregistrer les paramètres du tenant")
        booking_rules_payload = body.booking_rules
        if not booking_rules_payload and lead and isinstance(lead.get("opening_hours"), dict):
            booking_rules_payload = convert_opening_hours_to_booking_rules(lead.get("opening_hours") or {})
        booking_rules_final: Dict[str, Any] = {}
        if booking_rules_payload:
            booking_rules_final = _validate_horaires_payload(HorairesBody(**booking_rules_payload))
            booking_rules_final["horaires"] = derive_horaires_text(booking_rules_final)
            if not pg_update_tenant_params(tid, booking_rules_final):
                raise RuntimeError("Impossible d'enregistrer les horaires du tenant")

        # Init des tables normalisées "Mon cabinet" à partir de params_json + booking_rules
        try:
            sync_normalized_from_params(tid, tenant_params_payload)
        except Exception as sync_exc:
            logger.warning("createTenantFull sync_normalized_from_params non bloquant tenant_id=%s: %s", tid, sync_exc)
            results["warnings"].append("cabinet_profile_sync_failed")
        if booking_rules_final:
            try:
                sync_opening_hours_from_booking_rules(tid, booking_rules_final)
            except Exception as sync_exc:
                logger.warning("createTenantFull sync_opening_hours non bloquant tenant_id=%s: %s", tid, sync_exc)
                results["warnings"].append("opening_hours_sync_failed")
        logger.info("createTenantFull step=1 ok tenant_id=%s", tid)

        current_step = 2
        logger.info("createTenantFull step=2 started tenant_id=%s", tid)
        vapi_assistant = await create_vapi_assistant(
            tenant_id=tid,
            tenant_name=body.name.strip(),
            assistant_id=body.assistant_id,
            sector=body.sector,
            phone=body.phone,
        )
        vapi_id = (vapi_assistant or {}).get("id") or ""
        if not vapi_id:
            raise RuntimeError("Assistant Vapi créé sans identifiant")
        created["vapi_assistant_id"] = vapi_id
        results["vapi_assistant_id"] = vapi_id
        if not pg_update_tenant_params(tid, {"vapi_assistant_id": vapi_id}):
            raise RuntimeError("Impossible d'enregistrer l'assistant Vapi sur le tenant")
        logger.info("createTenantFull step=2 ok tenant_id=%s", tid)

        current_step = 3
        logger.info("createTenantFull step=3 started tenant_id=%s", tid)
        if body.twilio_number:
            await assign_twilio_to_vapi(vapi_id, body.twilio_number)
            if not pg_add_routing("vocal", body.twilio_number.strip().replace(" ", ""), tid):
                raise RuntimeError("Impossible d'enregistrer le routing Twilio")
            created["twilio_assigned"] = True
        logger.info("createTenantFull step=3 ok tenant_id=%s", tid)

        current_step = 4
        logger.info("createTenantFull step=4 started tenant_id=%s", tid)
        customer = stripe.Customer.create(
            email=contact_email,
            name=body.name.strip(),
            phone=body.phone,
            metadata={"tenant_id": str(tid), "plan": body.plan_key},
        )
        created["stripe_customer_id"] = customer.id
        results["stripe_customer_id"] = customer.id

        line_items = [{"price": base_price_id, "quantity": 1}]
        if metered_price_id:
            line_items.append({"price": metered_price_id})
        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=line_items,
            trial_period_days=30,
            payment_behavior="default_incomplete",
            payment_settings={"save_default_payment_method": "on_subscription"},
            expand=["latest_invoice.payment_intent"],
            metadata={"tenant_id": str(tid), "plan_key": body.plan_key},
        )
        created["stripe_subscription_id"] = subscription.id
        results["stripe_subscription_id"] = subscription.id

        cps = None
        cpe = None
        if getattr(subscription, "current_period_start", None):
            cps = datetime.utcfromtimestamp(subscription.current_period_start)
        if getattr(subscription, "current_period_end", None):
            cpe = datetime.utcfromtimestamp(subscription.current_period_end)
        trial_ends_at = None
        if getattr(subscription, "trial_end", None):
            trial_ends_at = datetime.utcfromtimestamp(subscription.trial_end)
        if not upsert_billing_from_subscription(
            tid,
            stripe_subscription_id=subscription.id,
            billing_status=subscription.status or "active",
            plan_key=body.plan_key,
            current_period_start=cps,
            current_period_end=cpe,
            trial_ends_at=trial_ends_at,
            stripe_customer_id=customer.id,
        ):
            raise RuntimeError("Impossible d'enregistrer la souscription Stripe en base")
        logger.info("createTenantFull step=4 ok tenant_id=%s", tid)

        current_step = 5
        logger.info("createTenantFull step=5 started tenant_id=%s", tid)
        if body.send_welcome:
            try:
                ok, err = send_welcome_email(
                    email=contact_email,
                    client_name=body.name.strip(),
                    assistant_id=body.assistant_id,
                    plan_key=body.plan_key,
                    phone_number=body.twilio_number or body.phone,
                    temp_password=temp_password,
                )
                if not ok:
                    logger.warning("Email bienvenue échoué (non bloquant) tenant_id=%s: %s", tid, err or "unknown")
                    results["warnings"].append("email_failed")
            except Exception as e:
                logger.warning("Email bienvenue échoué (non bloquant) tenant_id=%s: %s", tid, e)
                results["warnings"].append("email_failed")
        logger.info("createTenantFull step=5 ok tenant_id=%s", tid)

        if body.lead_id:
            try:
                from backend.leads_pg import get_lead, update_lead

                lead_for_sync = lead or get_lead(body.lead_id)
                if lead_for_sync:
                    existing_log = lead_for_sync.get("notes_log")
                    parsed = []
                    if isinstance(existing_log, str) and existing_log.strip():
                        parsed = json.loads(existing_log)
                    elif isinstance(existing_log, list):
                        parsed = list(existing_log)
                    parsed.append({
                        "text": f"Tenant créé : {body.name.strip()} (id: {tid})",
                        "action": "conversion",
                        "created_at": datetime.utcnow().isoformat() + "Z",
                    })
                    if not update_lead(
                        body.lead_id,
                        status="converted",
                        tenant_id=tid,
                        notes_log=json.dumps(parsed, ensure_ascii=False),
                    ):
                        results["warnings"].append("lead_link_failed")
                else:
                    results["warnings"].append("lead_not_found")
            except Exception as e:
                logger.warning("createTenantFull lead sync failed lead_id=%s tenant_id=%s: %s", body.lead_id, tid, e)
                results["warnings"].append("lead_link_failed")

        return {
            "success": True,
            "tenant_id": tid,
            "results": results,
        }
    except stripe.StripeError as e:
        logger.error(
            "createTenantFull step=4 FAILED, rollback triggered tenant_id=%s: %s",
            created.get("tenant_id"),
            e,
        )
        await _rollback_provisioning()
        raise HTTPException(502, detail=f"Stripe error: {str(e)}")
    except Exception as e:
        logger.error(
            "createTenantFull step=%s FAILED, rollback triggered tenant_id=%s: %s",
            current_step or "unknown",
            created.get("tenant_id"),
            e,
            exc_info=True,
        )
        await _rollback_provisioning()
        raise HTTPException(500, detail=f"Provisioning failed: {str(e)}")


def _get_assigned_voice_numbers() -> set:
    """Numéros déjà assignés dans tenant_routing (channel vocal)."""
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL")
    if not url:
        return set()
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT key FROM tenant_routing WHERE channel IN ('voice', 'vocal') AND is_active = TRUE"
                )
                return {r[0] for r in cur.fetchall() if r and r[0]}
    except Exception as e:
        logger.warning("_get_assigned_voice_numbers failed: %s", e)
        return set()


@router.get("/admin/twilio/numbers")
def admin_list_twilio_numbers(_: None = Depends(_verify_admin)):
    """Retourne les numéros Twilio (disponibles = non assignés)."""
    try:
        from twilio.rest import Client

        sid = (os.environ.get("TWILIO_ACCOUNT_SID") or "").strip()
        token = (os.environ.get("TWILIO_AUTH_TOKEN") or "").strip()
        if not sid or not token:
            return []
        client = Client(sid, token)
        numbers = client.incoming_phone_numbers.list()
        assigned = _get_assigned_voice_numbers()
        out = []
        for n in numbers:
            num = (n.phone_number or "").strip()
            friendly = (n.friendly_name or num or "—")[:80]
            out.append({
                "number": num,
                "friendly": friendly,
                "available": num not in assigned if num else False,
            })
        return out
    except Exception as e:
        logger.warning("admin_list_twilio_numbers failed: %s", e)
        return []


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
                    # Fallback vapi_calls si ivr_events vide (USE_PG_EVENTS=false ou appels sans interaction)
                    if calls_total == 0:
                        try:
                            cur.execute(
                                """
                                SELECT COUNT(*) AS c FROM vapi_calls
                                WHERE (started_at >= %s AND started_at <= %s)
                                   OR (updated_at >= %s AND updated_at <= %s)
                                """,
                                (start, end, start, end),
                            )
                            r = cur.fetchone()
                            if r and r.get("c"):
                                calls_total = int(r["c"])
                        except Exception:
                            pass
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
                    if not last_activity_at and calls_total > 0:
                        try:
                            cur.execute(
                                "SELECT MAX(COALESCE(ended_at, updated_at, started_at)) AS m FROM vapi_calls WHERE updated_at >= %s AND updated_at <= %s",
                                (start, end),
                            )
                            r = cur.fetchone()
                            if r and r.get("m"):
                                last_activity_at = r["m"].isoformat() + "Z" if hasattr(r["m"], "isoformat") else str(r["m"])
                        except Exception:
                            pass
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
    """Série temporelle par jour. Une connexion + une requête agrégée par jour (évite N connexions)."""
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    start = (now - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")
    end = now.strftime("%Y-%m-%d %H:%M:%S")
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    by_date: Dict[str, float] = {}
    for i in range(days):
        d = (now - timedelta(days=days - 1 - i)).date()
        by_date[d.strftime("%Y-%m-%d")] = 0

    if url:
        try:
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(url, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    if metric == "calls":
                        cur.execute(
                            """
                            SELECT DATE(created_at AT TIME ZONE 'UTC') AS d,
                                   COUNT(DISTINCT call_id) AS value
                            FROM ivr_events
                            WHERE call_id IS NOT NULL AND TRIM(call_id) != '' AND created_at >= %s AND created_at <= %s
                            GROUP BY DATE(created_at AT TIME ZONE 'UTC')
                            """,
                            (start, end),
                        )
                        for r in cur.fetchall():
                            if r.get("d"):
                                by_date[str(r["d"])] = int(r["value"] or 0)
                    elif metric == "appointments":
                        cur.execute(
                            """
                            SELECT DATE(created_at AT TIME ZONE 'UTC') AS d, COUNT(*) AS value
                            FROM ivr_events
                            WHERE event = 'booking_confirmed' AND created_at >= %s AND created_at <= %s
                            GROUP BY DATE(created_at AT TIME ZONE 'UTC')
                            """,
                            (start, end),
                        )
                        for r in cur.fetchall():
                            if r.get("d"):
                                by_date[str(r["d"])] = int(r["value"] or 0)
                    elif metric == "minutes":
                        try:
                            cur.execute(
                                """
                                SELECT DATE(ended_at AT TIME ZONE 'UTC') AS d,
                                       COALESCE(SUM(duration_sec), 0) / 60.0 AS value
                                FROM vapi_call_usage
                                WHERE ended_at IS NOT NULL AND ended_at >= %s AND ended_at <= %s
                                GROUP BY DATE(ended_at AT TIME ZONE 'UTC')
                                """,
                                (start, end),
                            )
                            for r in cur.fetchall():
                                if r.get("d"):
                                    by_date[str(r["d"])] = int(round(float(r["value"] or 0), 0))
                        except Exception:
                            pass
                    elif metric == "cost_usd":
                        try:
                            cur.execute(
                                """
                                SELECT DATE(ended_at AT TIME ZONE 'UTC') AS d, COALESCE(SUM(cost_usd), 0) AS value
                                FROM vapi_call_usage
                                WHERE ended_at IS NOT NULL AND ended_at >= %s AND ended_at <= %s
                                GROUP BY DATE(ended_at AT TIME ZONE 'UTC')
                                """,
                                (start, end),
                            )
                            for r in cur.fetchall():
                                if r.get("d"):
                                    by_date[str(r["d"])] = round(float(r["value"] or 0), 4)
                        except Exception:
                            pass
        except Exception as e:
            logger.warning("stats_timeseries pg: %s", e)
    else:
        import backend.db as db
        conn = db.get_conn()
        try:
            db._ensure_ivr_tables(conn)
            if metric == "calls":
                rows = conn.execute(
                    """SELECT date(created_at) AS d, COUNT(DISTINCT call_id) AS value
                       FROM ivr_events
                       WHERE created_at >= ? AND created_at <= ? AND call_id IS NOT NULL AND TRIM(call_id) != ''
                       GROUP BY date(created_at)""",
                    (start, end),
                ).fetchall()
                for r in rows:
                    if r[0]:
                        by_date[str(r[0])] = int(r[1] or 0)
            elif metric == "appointments":
                rows = conn.execute(
                    """SELECT date(created_at) AS d, COUNT(*) AS value FROM ivr_events
                       WHERE event = 'booking_confirmed' AND created_at >= ? AND created_at <= ?
                       GROUP BY date(created_at)""",
                    (start, end),
                ).fetchall()
                for r in rows:
                    if r[0]:
                        by_date[str(r[0])] = int(r[1] or 0)
        finally:
            conn.close()

    points = [{"date": d, "value": by_date[d]} for d in sorted(by_date.keys())]
    return {"metric": metric, "days": days, "points": points}


def _get_stats_top_tenants(metric: str, window_days: int, limit: int) -> dict:
    """Top tenants par métrique. Sources = Postgres (Railway) en prod."""
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    start = (now - timedelta(days=window_days)).strftime("%Y-%m-%d %H:%M:%S")
    end = now.strftime("%Y-%m-%d %H:%M:%S")
    if metric == "web_handoffs":
        items_wb: List[dict] = []
        url_tenants = os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL")
        if url_tenants:
            try:
                import psycopg
                from psycopg.rows import dict_row
                with psycopg.connect(url_tenants, row_factory=dict_row) as conn_h:
                    with conn_h.cursor() as cur_h:
                        cur_h.execute(
                            """
                            SELECT tenant_id, COUNT(*) AS value
                            FROM human_handoffs
                            WHERE created_at >= %s::timestamptz AND created_at <= %s::timestamptz
                              AND LOWER(TRIM(COALESCE(channel, ''))) NOT IN ('', 'vocal', 'voice', 'phone')
                            GROUP BY tenant_id ORDER BY value DESC LIMIT %s
                            """,
                            (start, end, limit),
                        )
                        for r in cur_h.fetchall():
                            tid = r.get("tenant_id")
                            if tid is None:
                                continue
                            items_wb.append({
                                "tenant_id": tid,
                                "name": "",
                                "value": int(r.get("value") or 0),
                                "last_activity_at": None,
                            })
                        if items_wb:
                            tids_wb = [int(x["tenant_id"]) for x in items_wb if x.get("tenant_id") is not None]
                            names_wb = _batch_tenant_names_from_pg(tids_wb)
                            for item in items_wb:
                                tid_int = int(item["tenant_id"])
                                item["name"] = names_wb.get(tid_int, f"Tenant #{tid_int}")
            except Exception as e:
                if "human_handoffs" not in str(e).lower() and "does not exist" not in str(e).lower():
                    logger.warning("stats top_tenants web_handoffs pg: %s", e)
        else:
            import backend.db as db
            conn = db.get_conn()
            try:
                db._ensure_human_handoffs_table(conn)
                cur_sql = conn.execute(
                    """SELECT tenant_id, COUNT(*) AS cnt FROM human_handoffs
                       WHERE datetime(created_at) >= datetime(?) AND datetime(created_at) <= datetime(?)
                       GROUP BY tenant_id ORDER BY cnt DESC LIMIT ?""",
                    (start, end, limit),
                )
                for row in cur_sql.fetchall() or []:
                    tid = row[0]
                    d = _get_tenant_detail(tid) if tid else {}
                    items_wb.append({"tenant_id": tid, "name": d.get("name") or f"Tenant #{tid}", "value": row[1] or 0, "last_activity_at": None})
            except Exception:
                pass
            finally:
                conn.close()
        return {"metric": metric, "window_days": window_days, "items": items_wb}
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


def _batch_tenant_names_from_pg(tenant_ids: List[int]) -> Dict[int, str]:
    """
    Résout tenant_id -> nom en une requête PG.
    Évite jusqu'à 10 appels pg_get_tenant_full dans _get_billing_snapshot (top coût Vapi).
    """
    out: Dict[int, str] = {}
    ids = sorted({int(t) for t in tenant_ids if t is not None})
    if not ids:
        return out
    if not getattr(config, "USE_PG_TENANTS", False):
        return out
    url_billing = os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL")
    if not url_billing:
        return out
    try:
        from backend.pg_pool import pg_connection_for

        with pg_connection_for(url_billing) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT tenant_id, name FROM tenants WHERE tenant_id = ANY(%s)",
                    (ids,),
                )
                for r in cur.fetchall():
                    tid = r.get("tenant_id")
                    if tid is None:
                        continue
                    tid_int = int(tid)
                    nm = (r.get("name") or "").strip()
                    out[tid_int] = nm if nm else f"Tenant #{tid_int}"
    except Exception as e:
        if "does not exist" not in str(e).lower():
            logger.warning("batch_tenant_names_from_pg: %s", e)
    return out


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
            from backend.pg_pool import pg_connection_for

            with pg_connection_for(url_events) as conn:
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
                        out["cost_usd_this_month"] = round(float(row.get("total") or 0), 4)
                    cur.execute(
                        """
                        SELECT tenant_id, COALESCE(SUM(cost_usd), 0) AS value
                        FROM vapi_call_usage
                        WHERE ended_at IS NOT NULL AND ended_at >= %s AND ended_at < %s
                        GROUP BY tenant_id ORDER BY value DESC LIMIT 10
                        """,
                        (start_str, end_str),
                    )
                    cost_rows = cur.fetchall()
                    tids_for_names = [int(r["tenant_id"]) for r in cost_rows if r.get("tenant_id") is not None]
                    names_map = _batch_tenant_names_from_pg(tids_for_names)
                    for r in cost_rows:
                        tid = r.get("tenant_id")
                        if tid is None:
                            continue
                        tid_int = int(tid)
                        name = names_map.get(tid_int)
                        if name is None and not getattr(config, "USE_PG_TENANTS", False):
                            d = _get_tenant_detail(tid_int) or {}
                            name = d.get("name") or f"Tenant #{tid_int}"
                        elif name is None:
                            name = f"Tenant #{tid_int}"
                        out["top_tenants_by_cost_this_month"].append({
                            "tenant_id": tid_int,
                            "name": name,
                            "value": round(float(r.get("value") or 0), 4),
                        })
        except Exception as e:
            if "does not exist" not in str(e).lower():
                logger.warning("billing_snapshot vapi: %s", e)
    if url_billing:
        try:
            from backend.pg_pool import pg_connection_for

            with pg_connection_for(url_billing) as conn:
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


@router.get("/admin/stats/dashboard-payload")
def admin_stats_dashboard_payload(
    window_days: int = Query(30, ge=7, le=90),
    _: None = Depends(_verify_admin),
):
    """Payload unique pour la page Dashboard admin : global + timeseries + topTenants (calls + cost) + billing. 1 seul round-trip."""
    return {
        "global": _get_global_stats(window_days),
        "timeseries": _get_stats_timeseries("calls", window_days),
        "topTenantsCalls": _get_stats_top_tenants("calls", window_days, 10),
        "topTenantsCost": _get_stats_top_tenants("cost_usd", window_days, 10),
        "billing": _get_billing_snapshot(),
        "activationQueue": _get_activation_queue(8),
    }


def _get_operations_snapshot(window_days: int = 7, billing_snapshot: Optional[dict] = None) -> dict:
    """
    Snapshot unique pour /admin/operations : billing, suspensions, cost today/7d, errors.
    Tout en 1 appel. Today = UTC.
    Errors = event anti_loop_trigger (liste stricte).

    Args:
        billing_snapshot: si fourni (ex. bundle cockpit), évite un second _get_billing_snapshot().
    """
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    generated_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Billing : réutilise _get_billing_snapshot + month_utc (ou snapshot déjà calculé pour /dashboard/bundle)
    if billing_snapshot is not None:
        billing = {**billing_snapshot}
    else:
        billing = _get_billing_snapshot()
    billing["month_utc"] = now.strftime("%Y-%m")
    url_events = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    url_billing = os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL")

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_str = today_start.strftime("%Y-%m-%d %H:%M:%S")
    end_str = now.strftime("%Y-%m-%d %H:%M:%S")
    seven_d_start = today_start - timedelta(days=window_days)
    seven_d_str = seven_d_start.strftime("%Y-%m-%d %H:%M:%S")

    cost = {
        "today_utc": {"date_utc": today_start.strftime("%Y-%m-%d"), "total_usd": 0.0, "top": []},
        "last_7d": {"window_days": window_days, "total_usd": 0.0, "top": []},
    }
    errors = {"window_days": window_days, "top_tenants": [], "errors_total": 0}

    month_utc = now.strftime("%Y-%m")
    start_quota = f"{month_utc}-01 00:00:00"
    try:
        y, m = int(month_utc[:4]), int(month_utc[5:7])
        end_quota = f"{y}-{m + 1:02d}-01 00:00:00" if m < 12 else f"{y + 1}-01-01 00:00:00"
    except ValueError:
        end_quota = start_quota
    quota_risk = {"month_utc": month_utc, "over_80": [], "over_100": []}

    # Suspensions : tenant_billing JOIN tenants
    suspensions = {"suspended_total": 0, "items": []}
    if url_billing:
        try:
            from backend.pg_pool import pg_connection_for

            with pg_connection_for(url_billing) as conn:
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

    # Une session PG événements : last_activity billing + coûts + erreurs + quota (~3 handshakes économisés)
    month_start_la = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")

    rows_quota: List[Any] = []
    if url_events:
        try:
            from backend.pg_pool import pg_connection_for

            with pg_connection_for(url_events) as conn:
                with conn.cursor() as cur:
                    if billing.get("top_tenants_by_cost_this_month"):
                        try:
                            tids_la = [
                                t["tenant_id"]
                                for t in billing["top_tenants_by_cost_this_month"]
                                if t.get("tenant_id") is not None
                            ]
                            if tids_la:
                                cur.execute(
                                    """
                                    SELECT client_id AS tenant_id, MAX(created_at) AS last_activity_at
                                    FROM ivr_events
                                    WHERE client_id = ANY(%s) AND created_at >= %s
                                    GROUP BY client_id
                                    """,
                                    (tids_la, month_start_la),
                                )
                                last_by_tenant = {
                                    r["tenant_id"]: r["last_activity_at"]
                                    for r in cur.fetchall()
                                    if r.get("tenant_id")
                                }
                                for t in billing["top_tenants_by_cost_this_month"]:
                                    la = last_by_tenant.get(t["tenant_id"])
                                    t["last_activity_at"] = (
                                        la.isoformat() + "Z"
                                        if la and hasattr(la, "isoformat")
                                        else (str(la) if la else None)
                                    )
                        except Exception as e:
                            if "does not exist" not in str(e).lower():
                                logger.warning("operations_snapshot last_activity: %s", e)

                    try:
                        for label, start_s, end_s in [
                            ("today_utc", today_str, end_str),
                            ("last_7d", seven_d_str, end_str),
                        ]:
                            cur.execute(
                                """
                                SELECT COALESCE(SUM(cost_usd), 0) AS total
                                FROM vapi_call_usage
                                WHERE ended_at IS NOT NULL AND ended_at >= %s AND ended_at <= %s
                                """,
                                (start_s, end_s),
                            )
                            row = cur.fetchone()
                            cost[label]["total_usd"] = round(float((row or {}).get("total") or 0), 2)
                            cur.execute(
                                """
                                SELECT tenant_id, COALESCE(SUM(cost_usd), 0) AS value
                                FROM vapi_call_usage
                                WHERE ended_at IS NOT NULL AND ended_at >= %s AND ended_at <= %s
                                GROUP BY tenant_id ORDER BY value DESC LIMIT 5
                                """,
                                (start_s, end_s),
                            )
                            top_rows = cur.fetchall()
                            tnames_cost = _batch_tenant_names_from_pg(
                                [int(r["tenant_id"]) for r in top_rows if r.get("tenant_id") is not None]
                            )
                            for r in top_rows:
                                tid = r.get("tenant_id")
                                if tid is None:
                                    continue
                                tid_int = int(tid)
                                cost[label]["top"].append({
                                    "tenant_id": tid_int,
                                    "name": tnames_cost.get(tid_int, f"Tenant #{tid_int}"),
                                    "value": round(float(r.get("value") or 0), 2),
                                })
                    except Exception as e:
                        if "does not exist" not in str(e).lower():
                            logger.warning("operations_snapshot cost: %s", e)

                    try:
                        cur.execute(
                            """
                            SELECT client_id AS tenant_id, COUNT(*) AS errors_total, MAX(created_at) AS last_error_at
                            FROM ivr_events
                            WHERE event = 'anti_loop_trigger' AND created_at >= %s AND created_at <= %s
                            GROUP BY client_id ORDER BY errors_total DESC LIMIT 10
                            """,
                            (seven_d_str, end_str),
                        )
                        err_rows = cur.fetchall()
                        tnames_err = _batch_tenant_names_from_pg(
                            [int(r["tenant_id"]) for r in err_rows if r.get("tenant_id") is not None]
                        )
                        for r in err_rows:
                            tid = r.get("tenant_id")
                            if tid is None:
                                continue
                            tid_int = int(tid)
                            last_at = r.get("last_error_at")
                            if last_at and hasattr(last_at, "isoformat"):
                                last_at = last_at.isoformat() + "Z"
                            errors["top_tenants"].append({
                                "tenant_id": tid_int,
                                "name": tnames_err.get(tid_int, f"Tenant #{tid_int}"),
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
                        erow = cur.fetchone()
                        errors["errors_total"] = int(((erow or {}).get("c")) or 0)
                    except Exception as e:
                        if "does not exist" not in str(e).lower():
                            logger.warning("operations_snapshot errors: %s", e)

                    try:
                        cur.execute(
                            """
                            SELECT tenant_id, COALESCE(SUM(duration_sec), 0) / 60.0 AS used_minutes
                            FROM vapi_call_usage
                            WHERE ended_at IS NOT NULL AND ended_at >= %s AND ended_at < %s
                            GROUP BY tenant_id
                            """,
                            (start_quota, end_quota),
                        )
                        rows_quota = cur.fetchall() or []
                    except Exception as e:
                        if "does not exist" not in str(e).lower():
                            logger.warning("operations_snapshot quota: %s", e)

            try:
                tids_quota = [int(r["tenant_id"]) for r in rows_quota if r.get("tenant_id") is not None]
                names_quota = _batch_tenant_names_from_pg(tids_quota)
                plan_quota = load_cockpit_plan_quota_inputs_batch(tids_quota)
                for r in rows_quota:
                    tid = r.get("tenant_id")
                    if tid is None:
                        continue
                    tid_int = int(tid)
                    used_minutes = round(float(r.get("used_minutes") or 0), 2)
                    row_plan = plan_quota.get(tid_int) or {}
                    params = row_plan.get("params") or {}
                    tb_plan = (row_plan.get("billing_plan_key") or "").strip()
                    plan_key = (params.get("plan_key") or "").strip()
                    if not plan_key and tb_plan:
                        plan_key = tb_plan
                    plan_key = (plan_key or "").strip() or "free"
                    if plan_key == "custom":
                        try:
                            custom_val = int(params.get("custom_included_minutes_month") or 0)
                            included = custom_val if custom_val > 0 else get_plan_included_minutes("custom")
                        except (TypeError, ValueError):
                            included = get_plan_included_minutes("custom")
                    else:
                        included = get_plan_included_minutes(plan_key)
                    if included <= 0:
                        continue
                    usage_pct = round((used_minutes / included) * 100, 1)
                    name = names_quota.get(tid_int) or f"Tenant #{tid_int}"
                    item = {
                        "tenant_id": tid_int,
                        "name": name,
                        "used_minutes": used_minutes,
                        "included_minutes": included,
                        "usage_pct": usage_pct,
                    }
                    if usage_pct > 100:
                        quota_risk["over_100"].append(item)
                    if usage_pct >= 80:
                        quota_risk["over_80"].append(item)
                quota_risk["over_80"].sort(key=lambda x: -x["usage_pct"])
                quota_risk["over_100"].sort(key=lambda x: -x["usage_pct"])
            except Exception as e:
                if "does not exist" not in str(e).lower():
                    logger.warning("operations_snapshot quota post: %s", e)

        except Exception as e:
            if "does not exist" not in str(e).lower():
                logger.warning("operations_snapshot events session: %s", e)

    return {
        "generated_at": generated_at,
        "billing": billing,
        "suspensions": suspensions,
        "cost": cost,
        "errors": errors,
        "quota": quota_risk,
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
                        q_rows = cur.fetchall()
                        tnames_q = _batch_tenant_names_from_pg(
                            [int(r["tenant_id"]) for r in q_rows if r.get("tenant_id") is not None]
                        )
                        for r in q_rows:
                            tid = r.get("tenant_id")
                            if tid is None:
                                continue
                            tid_int = int(tid)
                            last_at = r.get("last_at")
                            if last_at and hasattr(last_at, "isoformat"):
                                last_at = last_at.isoformat() + "Z"
                            top[metric].append({
                                "tenant_id": tid_int,
                                "name": tnames_q.get(tid_int, f"Tenant #{tid_int}"),
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


_ALLOWED_DASHBOARD_PERIODS = frozenset({"24h", "7d", "30d", "month"})

_cockpit_bundle_cache_lock = threading.Lock()
_cockpit_bundle_cache: Dict[tuple, tuple] = {}


def _cockpit_bundle_cache_ttl_sec() -> float:
    try:
        return float(os.environ.get("COCKPIT_BUNDLE_CACHE_SEC", "45") or "45")
    except ValueError:
        return 45.0


def _cockpit_bundle_cache_get(period: str, severity_key: str) -> Optional[dict]:
    ttl = _cockpit_bundle_cache_ttl_sec()
    if ttl <= 0:
        return None
    key = (period, severity_key)
    now = time.monotonic()
    with _cockpit_bundle_cache_lock:
        entry = _cockpit_bundle_cache.get(key)
        if entry and entry[0] > now:
            return entry[1]
    return None


def _cockpit_bundle_cache_set(period: str, severity_key: str, payload: dict) -> None:
    ttl = _cockpit_bundle_cache_ttl_sec()
    if ttl <= 0:
        return
    key = (period, severity_key)
    with _cockpit_bundle_cache_lock:
        _cockpit_bundle_cache[key] = (time.monotonic() + ttl, payload)
        if len(_cockpit_bundle_cache) > 16:
            now = time.monotonic()
            for stale in [k for k, (exp, _) in _cockpit_bundle_cache.items() if exp <= now]:
                _cockpit_bundle_cache.pop(stale, None)


def _normalize_dashboard_period(period: Optional[str]) -> str:
    p = (period or "30d").strip()
    return p if p in _ALLOWED_DASHBOARD_PERIODS else "30d"


def _admin_cockpit_ctx() -> Dict[str, Any]:
    """Context injecté dans dashboard_cockpit (helpers définis ci-dessus)."""
    return {
        "_get_tenant_list": _get_tenant_list,
        "_get_tenant_detail": _get_tenant_detail,
        "_get_vapi_usage_for_window": _get_vapi_usage_for_window,
        "_get_operations_snapshot": _get_operations_snapshot,
        "_get_quality_snapshot": _get_quality_snapshot,
        "_get_stats_top_tenants": _get_stats_top_tenants,
        "_get_billing_snapshot": _get_billing_snapshot,
        "_get_activation_queue": _get_activation_queue,
    }


@router.get("/admin/dashboard/bundle")
def admin_dashboard_bundle(
    period: str = Query("30d", description="24h, 7d, 30d, month"),
    severity: Optional[str] = Query(None, description="critical, warning ou omis (= tout)"),
    _: None = Depends(_verify_admin),
):
    """
    Cockpit en une requête : KPI + leads + actions + watchlist.
    Réutilise billing / operations snapshots entre agrégats (évite 3× la même charge PG).
    """
    ctx = _admin_cockpit_ctx()
    p = _normalize_dashboard_period(period)
    sf = (severity or "").strip().lower()
    filt = sf if sf in ("critical", "warning") else None
    severity_key = filt or ""

    cached = _cockpit_bundle_cache_get(p, severity_key)
    if cached is not None:
        return cached

    wd_ops = max(7, min(90, dash_window_days(p)))
    ops_window = min(wd_ops, 30)
    from concurrent.futures import ThreadPoolExecutor
    from concurrent.futures import TimeoutError as FuturesTimeout

    tout = float(os.environ.get("COCKPIT_BUNDLE_PHASE_TIMEOUT_SEC", "120") or "120")
    act_limit = max(8, min(int(os.environ.get("COCKPIT_ACTIVATION_LIMIT", "12") or "12"), 42))
    try:
        with ThreadPoolExecutor(max_workers=2) as ex:
            f_b = ex.submit(ctx["_get_billing_snapshot"])
            f_a = ex.submit(ctx["_get_activation_queue"], act_limit)
            billing_snap = f_b.result(timeout=tout)
            activation_slice = f_a.result(timeout=tout).get("items") or []
    except (FuturesTimeout, Exception):
        billing_snap = ctx["_get_billing_snapshot"]()
        activation_slice = ctx["_get_activation_queue"](act_limit).get("items") or []
    # Réutilise le même billing_snap : sinon _get_operations_snapshot refait tout le snapshot (+ N+1 historique).
    ops_snap = ctx["_get_operations_snapshot"](window_days=ops_window, billing_snapshot=billing_snap)

    tout_body = float(os.environ.get("COCKPIT_BUNDLE_BODY_TIMEOUT_SEC", "120") or "120")
    try:
        with ThreadPoolExecutor(max_workers=3) as ex:
            f_sum = ex.submit(
                dash_build_summary,
                ctx,
                p,
                billing_snap=billing_snap,
                ops_snap=ops_snap,
                activation_slice=activation_slice,
            )
            f_act = ex.submit(
                dash_build_action_items,
                ctx,
                p,
                filt,
                billing_snap=billing_snap,
                ops_snap=ops_snap,
                activation_slice=activation_slice,
            )
            f_wat = ex.submit(dash_watchlist_items, ctx, p, ops_snap=ops_snap)
            summary = f_sum.result(timeout=tout_body)
            actions = f_act.result(timeout=tout_body)
            watch = f_wat.result(timeout=tout_body)
    except (FuturesTimeout, Exception):
        summary = dash_build_summary(
            ctx,
            p,
            billing_snap=billing_snap,
            ops_snap=ops_snap,
            activation_slice=activation_slice,
        )
        actions = dash_build_action_items(
            ctx,
            p,
            filt,
            billing_snap=billing_snap,
            ops_snap=ops_snap,
            activation_slice=activation_slice,
        )
        watch = dash_watchlist_items(ctx, p, ops_snap=ops_snap)

    result = {
        **summary,
        "actions": {"items": actions},
        "watchlist": {"items": watch},
    }
    _cockpit_bundle_cache_set(p, severity_key, result)
    return result


@router.get("/admin/dashboard/summary")
def admin_dashboard_summary(
    period: str = Query("30d", description="24h, 7d, 30d, month"),
    _: None = Depends(_verify_admin),
):
    """Cockpit : KPI fenêtrés, leads bloc, hints (sans dépendances circulaires)."""
    p = _normalize_dashboard_period(period)
    return dash_build_summary(_admin_cockpit_ctx(), p)


@router.get("/admin/dashboard/new-leads")
def admin_dashboard_new_leads(
    period: str = Query("7d", description="24h, 7d, 30d, month — fenêtre glissante (sauf month = depuis le 1er du mois UTC)"),
    _: None = Depends(_verify_admin),
):
    """Bloc leads cockpit (nouveaux, à qualifier, derniers entrées). Fenêtre pilotée par `period`."""
    p = _normalize_dashboard_period(period)
    return dash_leads_block(_admin_cockpit_ctx(), p)


@router.get("/admin/dashboard/action-items")
def admin_dashboard_action_items(
    period: str = Query("30d", description="Fenêtre relative pour quotas / erreurs agrégées"),
    severity: Optional[str] = Query(None, description="critical, warning ou omis (= tout)"),
    _: None = Depends(_verify_admin),
):
    """File d’actions prioritaires cockpit (Stripe, onboarding, quotas, anomalies)."""
    p = _normalize_dashboard_period(period)
    sf = (severity or "").strip().lower()
    filt = sf if sf in ("critical", "warning") else None
    items = dash_build_action_items(_admin_cockpit_ctx(), p, filt)
    return {"items": items}


@router.get("/admin/dashboard/tenant-watchlist")
def admin_dashboard_tenant_watchlist(
    period: str = Query("30d", description="24h, 7d, 30d, month"),
    _: None = Depends(_verify_admin),
):
    """Signaux métiers condensés (demandes web fortes, dépassement quota, friction quality)."""
    p = _normalize_dashboard_period(period)
    items = dash_watchlist_items(_admin_cockpit_ctx(), p)
    return {"items": items}


@router.get("/admin/stats/billing-snapshot")
def admin_stats_billing_snapshot(
    _: None = Depends(_verify_admin),
):
    """Coût Vapi ce mois (UTC), top tenants par coût ce mois, nombre de tenants past_due. Sans prix Stripe."""
    return _get_billing_snapshot()


@router.post("/admin/jobs/quota-alerts-80")
def admin_job_quota_alerts_80(
    month: Optional[str] = Query(None, description="YYYY-MM (défaut: mois courant UTC)"),
    _: None = Depends(_verify_admin),
):
    """Lance le job d’alertes quota 80 % (email + log). Anti-spam : 1 email/tenant/mois. À appeler en cron daily."""
    from backend.quota_alerts import run_quota_alerts_80
    return run_quota_alerts_80(month_utc=month)


@router.post("/admin/jobs/insert-test-usage")
def admin_job_insert_test_usage(
    tenant_id: int = Query(1, description="Tenant pour usage test"),
    _: None = Depends(_verify_admin),
):
    """Insère 55 min de test dans vapi_call_usage pour hier UTC (E2E Stripe)."""
    import uuid
    from datetime import datetime, timedelta, timezone

    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    if not url:
        raise HTTPException(503, "DATABASE_URL not configured")
    now = datetime.now(timezone.utc)
    yesterday = (now.date() - timedelta(days=1))
    start = datetime(yesterday.year, yesterday.month, yesterday.day, 10, 0, 0, tzinfo=timezone.utc)
    rows = [
        (tenant_id, f"test-usage-{uuid.uuid4()}", start, start + timedelta(minutes=15), 900, 0.05),
        (tenant_id, f"test-usage-{uuid.uuid4()}", start + timedelta(hours=4), start + timedelta(hours=4, minutes=20), 1200, 0.07),
        (tenant_id, f"test-usage-{uuid.uuid4()}", start + timedelta(hours=6), start + timedelta(hours=6, minutes=20), 1200, 0.07),
    ]
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                for tid, vid, s, e, dur, cost in rows:
                    cur.execute(
                        """
                        INSERT INTO vapi_call_usage (tenant_id, vapi_call_id, started_at, ended_at, duration_sec, cost_usd, cost_currency)
                        VALUES (%s, %s, %s, %s, %s, %s, 'USD')
                        ON CONFLICT (tenant_id, vapi_call_id) DO NOTHING
                        """,
                        (tid, vid, s, e, dur, cost),
                    )
                conn.commit()
        return {"ok": True, "tenant_id": tenant_id, "minutes": 55, "date_utc": yesterday.isoformat()}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/admin/tenants/{tenant_id}/stripe-usage-push-log")
def admin_get_stripe_usage_push_log(
    tenant_id: int = Depends(validate_tenant_id),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD (optionnel)"),
    limit: int = Query(10, ge=1, le=50),
    _: None = Depends(_verify_admin),
):
    """Diagnostic : stripe_usage_push_log pour le tenant (status, error_short)."""
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL")
    if not url:
        raise HTTPException(503, "DATABASE_URL not configured")
    try:
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                if date_from:
                    cur.execute(
                        """
                        SELECT tenant_id, date_utc, status, quantity_minutes, error_short, stripe_usage_record_id, pushed_at
                        FROM stripe_usage_push_log
                        WHERE tenant_id = %s AND date_utc >= %s::date
                        ORDER BY date_utc DESC
                        LIMIT %s
                        """,
                        (tenant_id, date_from, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT tenant_id, date_utc, status, quantity_minutes, error_short, stripe_usage_record_id, pushed_at
                        FROM stripe_usage_push_log
                        WHERE tenant_id = %s
                        ORDER BY date_utc DESC
                        LIMIT %s
                        """,
                        (tenant_id, limit),
                    )
                rows = cur.fetchall()
        return {"tenant_id": tenant_id, "rows": [dict(r) for r in rows]}
    except Exception as e:
        if "does not exist" in str(e).lower():
            return {"tenant_id": tenant_id, "rows": []}
        raise HTTPException(500, str(e))


@router.post("/admin/jobs/push-daily-usage")
def admin_job_push_daily_usage(
    _: None = Depends(_verify_admin),
):
    """Pousse l'usage Vapi → Stripe (yesterday + day_before si pas sent). Retry 48h. Cron 01:00 UTC recommandé."""
    from backend.stripe_usage import push_daily_usage_with_retry_48h
    return push_daily_usage_with_retry_48h()


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
    metric: str = Query("minutes", description="minutes | calls | appointments | cost_usd | web_handoffs"),
    window_days: int = Query(30, ge=1, le=90),
    limit: int = Query(10, ge=1, le=50),
    _: None = Depends(_verify_admin),
):
    """Top tenants par métrique."""
    if metric not in ("minutes", "calls", "appointments", "cost_usd", "web_handoffs"):
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


@router.post("/admin/calendar/reconcile")
def admin_calendar_reconcile(
    tenant_id: Optional[int] = Query(None, description="tenant_id (optionnel : si absent, tous les tenants Google)"),
    window_days: int = Query(30, ge=1, le=90),
    dry_run: bool = Query(False, description="True = simule sans modifier le miroir"),
    _: None = Depends(require_admin),
):
    """
    Lance une réconciliation Google Calendar ↔ miroir UWI à la demande.

    - Détecte les miroirs UWI orphelins (event Google supprimé) et les nettoie.
    - Logue les events Google UWI orphelins (sans miroir).
    - Conservatif : ne touche jamais à Google.
    """
    from backend.reconcile_calendar import reconcile_tenant, reconcile_all_tenants
    if tenant_id is not None:
        report = reconcile_tenant(int(tenant_id), window_days=window_days, dry_run=dry_run)
        return {"ok": True, "reports": [report]}
    reports = reconcile_all_tenants(window_days=window_days, dry_run=dry_run)
    return {"ok": True, "reports": reports}
