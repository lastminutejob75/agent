# backend/routes/tenant.py
"""
API tenant (client): dashboard, technical-status, me, params, agenda.
Protégé par cookie uwi_session uniquement (require_tenant_auth).
"""
from __future__ import annotations

import copy
import json
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

import bcrypt
import jwt
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, validator

from backend.auth_pg import pg_get_tenant_user_by_id, pg_update_password
from backend.calendar_adapter import _GoogleCalendarAdapter
from backend import config
from backend.config import get_service_account_email
from backend.db import (
    cancel_booking_sqlite,
    book_slot_atomic,
    delete_patient_note,
    delete_patient_document,
    ensure_slot_id_by_datetime,
    ensure_tenant_config,
    get_cabinet_clients_by_phones,
    find_slot_id_by_datetime,
    get_cabinet_client_by_phone,
    get_call_followup,
    get_conn,
    insert_patient_note,
    insert_patient_document,
    list_cabinet_clients,
    search_cabinet_clients,
    search_cabinet_clients_with_fallback,
    list_free_slots,
    list_call_followups,
    list_patient_notes,
    list_patient_documents,
    normalize_phone_number,
    reschedule_booking_atomic,
    _migrate_sqlite_add_booking_origin,
    update_patient_fields,
    upsert_cabinet_client,
    upsert_call_followup,
)
from backend.google_calendar import GoogleCalendarNotFoundError, GoogleCalendarPermissionError, GoogleCalendarService
from backend.handoffs import get_handoff_by_id, list_handoffs, update_handoff_status
from backend.routes.admin import (
    _get_call_detail,
    _get_calls_list,
    _get_dashboard_snapshot,
    _get_kpis_daily,
    _get_stripe_price_ids_for_plan,
    _get_quota_used_minutes,
    _get_rgpd_extended,
    _get_technical_status,
    _get_tenant_detail,
)
from backend.billing_pg import (
    get_billing_plans,
    get_plan_included_minutes,
    get_plan_overage_rate,
    get_tenant_billing,
    upsert_billing_from_subscription,
)
from backend.cabinet_profile_pg import (
    create_appointment_reason as pg_create_appointment_reason,
    disable_appointment_reason as pg_disable_appointment_reason,
    get_assistant_settings as pg_get_assistant_settings,
    get_availability_settings as pg_get_availability_settings,
    get_booking_rules as pg_get_booking_rules,
    get_opening_hours as pg_get_opening_hours,
    get_profile as pg_get_profile,
    list_appointment_reasons as pg_list_appointment_reasons,
    replace_opening_hours as pg_replace_opening_hours,
    update_appointment_reason as pg_update_appointment_reason,
    upsert_assistant_settings as pg_upsert_assistant_settings,
    upsert_availability_settings as pg_upsert_availability_settings,
    upsert_booking_rules as pg_upsert_booking_rules,
    upsert_profile as pg_upsert_profile,
    sync_normalized_from_params as pg_sync_normalized_from_params,
    sync_opening_hours_from_booking_rules as pg_sync_opening_hours_from_booking_rules,
)
from backend.services.email_service import send_agenda_contact_request_email, send_patient_document_email
from backend.tenant_config import (
    DEFAULT_FAQ,
    derive_horaires_text,
    get_booking_rules,
    get_tenant_display_config,
    get_faq,
    normalize_faq_payload,
    reset_faq_params,
    set_params,
)
from backend.tenants_pg import pg_delete_tenant_param_keys, pg_update_tenant_name, pg_update_tenant_params
from backend.vapi_utils import update_vapi_assistant_faq

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore

logger = logging.getLogger(__name__)

# Réponses Google Calendar `events.list` pour l'agenda : cache court (souvent >200 ms / requête hors cache).
_AGENDA_GCAL_EVENTS_LOCK = threading.Lock()
_AGENDA_GCAL_EVENTS_CACHE: Dict[tuple, tuple[float, dict]] = {}


def _tenant_google_calendar_list_events_cached(
    calendar_svc: GoogleCalendarService,
    *,
    calendar_id: str,
    time_min_iso: str,
    time_max_iso: str,
) -> dict:
    """Même fenêtre temporelle dans les ~AGENDA_GOOGLE_CACHE_SECONDS s = pas d'appel Google répété."""
    cid = (calendar_id or "").strip()
    try:
        ttl = float((os.environ.get("AGENDA_GOOGLE_CACHE_SECONDS") or "30").strip() or "30")
    except ValueError:
        ttl = 30.0
    # Pytest définit cette variable pendant l'exécution d'un test : ne pas mutualiser les réponses google entre tests.
    if os.environ.get("PYTEST_CURRENT_TEST"):
        ttl = -1.0
    if ttl <= 0:
        return (
            calendar_svc.service.events()
            .list(
                calendarId=cid,
                timeMin=time_min_iso,
                timeMax=time_max_iso,
                singleEvents=True,
                orderBy="startTime",
                fields="items(id,summary,description,start,end)",
            )
            .execute()
        )

    key = (cid, time_min_iso, time_max_iso)
    now_mono = time.monotonic()
    with _AGENDA_GCAL_EVENTS_LOCK:
        hit = _AGENDA_GCAL_EVENTS_CACHE.get(key)
        if hit and hit[0] > now_mono:
            return copy.deepcopy(hit[1])

    executed = (
        calendar_svc.service.events()
        .list(
            calendarId=cid,
            timeMin=time_min_iso,
            timeMax=time_max_iso,
            singleEvents=True,
            orderBy="startTime",
            fields="items(id,summary,description,start,end)",
        )
        .execute()
    )

    with _AGENDA_GCAL_EVENTS_LOCK:
        _AGENDA_GCAL_EVENTS_CACHE[key] = (now_mono + ttl, copy.deepcopy(executed))
        if len(_AGENDA_GCAL_EVENTS_CACHE) > 200:
            stale_keys = [k for k, (exp, _) in _AGENDA_GCAL_EVENTS_CACHE.items() if exp <= now_mono]
            for stale_k in stale_keys[:120]:
                _AGENDA_GCAL_EVENTS_CACHE.pop(stale_k, None)

    return executed


_TENANT_AGENDA_DETAIL_LOCK = threading.Lock()
_TENANT_AGENDA_DETAIL_CACHE: Dict[int, tuple[float, dict]] = {}


def _get_tenant_detail_for_agenda_cached(tenant_id: int) -> Optional[dict]:
    """Réduit les appels PG `pg_get_tenant_full` lors des lectures agenda (liste souvent rejouée)."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return _get_tenant_detail(tenant_id)
    raw_ttl = (os.environ.get("AGENDA_TENANT_DETAIL_CACHE_SECONDS") or "45").strip()
    try:
        ttl = float(raw_ttl or "45")
    except ValueError:
        ttl = 45.0
    if ttl <= 0:
        return _get_tenant_detail(tenant_id)

    now = time.monotonic()
    with _TENANT_AGENDA_DETAIL_LOCK:
        hit = _TENANT_AGENDA_DETAIL_CACHE.get(int(tenant_id))
        if hit and hit[0] > now:
            return copy.deepcopy(hit[1])

    detail = _get_tenant_detail(tenant_id)
    if detail is None:
        return None

    with _TENANT_AGENDA_DETAIL_LOCK:
        _TENANT_AGENDA_DETAIL_CACHE[int(tenant_id)] = (now + ttl, copy.deepcopy(detail))
        if len(_TENANT_AGENDA_DETAIL_CACHE) > 300:
            stale_keys = [
                tid for tid, (exp, _) in _TENANT_AGENDA_DETAIL_CACHE.items() if exp <= now
            ]
            for tid in stale_keys[:120]:
                _TENANT_AGENDA_DETAIL_CACHE.pop(tid, None)

    return copy.deepcopy(detail)


def _invalidate_tenant_agenda_detail_cache(tenant_id: int) -> None:
    with _TENANT_AGENDA_DETAIL_LOCK:
        _TENANT_AGENDA_DETAIL_CACHE.pop(int(tenant_id), None)


router = APIRouter(prefix="/api/tenant", tags=["tenant"])

JWT_SECRET = os.environ.get("JWT_SECRET", "")
SESSION_COOKIE_NAME = os.environ.get("SESSION_COOKIE_NAME", "uwi_session")

STATUS_MAP = {
    "rdv": "CONFIRMED",
    "transfer": "TRANSFERRED",
    "abandoned": "ABANDONED",
    "cancelled": "CANCELLED",
    "rescheduled": "RESCHEDULED",
    "other": "FAQ",
}


def _tenant_display_name(detail: Optional[dict], tenant_id: Optional[int] = None) -> str:
    params = (detail or {}).get("params") or {}
    for key in ("business_name", "tenant_name", "company_name", "cabinet_name"):
        preferred = str(params.get(key) or "").strip()
        if preferred:
            return preferred
    fallback = str((detail or {}).get("name") or "").strip()
    if fallback.lower() in {"uwi", "cabinet uwi"} and tenant_id is not None:
        configured = str((get_tenant_display_config(tenant_id) or {}).get("business_name") or "").strip()
        if configured:
            return configured
    if fallback:
        return fallback
    if tenant_id is not None:
        return f"Client #{tenant_id}"
    return "N/A"


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
    Le payload est aussi posé dans `request.state.auth` pour le middleware d'audit patient (pt 8).
    """
    if not JWT_SECRET:
        raise HTTPException(503, "JWT_SECRET not configured")
    auth = _auth_from_cookie(request) or _auth_from_bearer(request)
    if auth:
        try:
            request.state.auth = auth
        except Exception:
            pass
        return auth
    raise HTTPException(401, "Missing or invalid token")


def require_tenant_owner(auth: Dict[str, Any] = Depends(require_tenant_auth)) -> Dict[str, Any]:
    """Actions sensibles (facturation, paramètres système, intégrations) : titulaire uniquement."""
    role = (auth.get("role") or "owner").strip().lower()
    if role != "owner":
        raise HTTPException(
            403,
            "Cette action est réservée au titulaire du cabinet. Contactez l'administrateur de votre compte.",
        )
    return auth


def _tenant_timezone(detail: Optional[dict]) -> str:
    params = (detail or {}).get("params") or {}
    return (params.get("timezone") or (detail or {}).get("timezone") or "Europe/Paris").strip() or "Europe/Paris"


def _is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on", "oui"}


def _looks_like_service_account_email(value: Optional[str]) -> bool:
    raw = str(value or "").strip().lower()
    return raw.endswith(".iam.gserviceaccount.com")


def _parse_string_list(value: Any) -> List[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(x) for x in value if str(x).strip()]
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, (list, tuple, set)):
                return [str(x) for x in parsed if str(x).strip()]
        except Exception:
            pass
        return [x.strip() for x in raw.split(",") if x.strip()]
    return []


def _parse_dict_value(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


DAY_ORDER = [
    ("monday", "Lundi"),
    ("tuesday", "Mardi"),
    ("wednesday", "Mercredi"),
    ("thursday", "Jeudi"),
    ("friday", "Vendredi"),
    ("saturday", "Samedi"),
    ("sunday", "Dimanche"),
]


def _slugify(value: str) -> str:
    raw = (value or "").strip().lower()
    if not raw:
        return ""
    raw = re.sub(r"[^\w\s-]", "", raw, flags=re.UNICODE)
    return re.sub(r"[-\s]+", "-", raw).strip("-")


def _build_default_opening_hours(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    booking_days = params.get("booking_days") or [0, 1, 2, 3, 4]
    if isinstance(booking_days, str):
        try:
            booking_days = json.loads(booking_days)
        except Exception:
            booking_days = [0, 1, 2, 3, 4]
    day_set = {int(d) for d in booking_days if str(d).strip().isdigit()}
    start_hour = int(params.get("booking_start_hour") or 9)
    end_hour = int(params.get("booking_end_hour") or 18)
    start = f"{start_hour:02d}:00"
    end = f"{end_hour:02d}:00"
    rows: List[Dict[str, Any]] = []
    for idx, (day_key, _label) in enumerate(DAY_ORDER):
        is_open = idx in day_set
        rows.append(
            {
                "day": day_key,
                "is_open": is_open,
                "morning_start": start if is_open else "",
                "morning_end": "12:30" if is_open else "",
                "afternoon_start": "14:00" if is_open else "",
                "afternoon_end": end if is_open else "",
            }
        )
    return rows


def _normalize_opening_hours_payload(payload: Any) -> List[Dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    by_key: Dict[str, Dict[str, Any]] = {}
    for row in payload:
        if not isinstance(row, dict):
            continue
        day = str(row.get("day") or "").strip().lower()
        if day not in {d for d, _ in DAY_ORDER}:
            continue
        by_key[day] = {
            "day": day,
            "is_open": _is_truthy(row.get("is_open")),
            "morning_start": str(row.get("morning_start") or "").strip(),
            "morning_end": str(row.get("morning_end") or "").strip(),
            "afternoon_start": str(row.get("afternoon_start") or "").strip(),
            "afternoon_end": str(row.get("afternoon_end") or "").strip(),
        }
    return [by_key.get(day, {"day": day, "is_open": False, "morning_start": "", "morning_end": "", "afternoon_start": "", "afternoon_end": ""}) for day, _ in DAY_ORDER]


def _normalize_faq_items(value: Any) -> List[Dict[str, Any]]:
    items = value if isinstance(value, list) else []
    out: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        q = str(item.get("question") or "").strip()
        a = str(item.get("answer") or "").strip()
        if not q and not a:
            continue
        out.append(
            {
                "id": str(item.get("id") or uuid4().hex),
                "question": q,
                "answer": a,
                "enabled": _is_truthy(item.get("enabled", True)),
            }
        )
    return out


def _get_zoneinfo(tz_name: str):
    if ZoneInfo:
        try:
            return ZoneInfo(tz_name or "Europe/Paris")
        except Exception:
            return ZoneInfo("Europe/Paris")
    return timezone(timedelta(hours=1))


def _parse_dt(value: Any, tz_name: str = "Europe/Paris") -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value).strip()
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            try:
                dt = datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S")
            except Exception:
                return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=_get_zoneinfo(tz_name))
    return dt


def _format_hhmm(value: Any, tz_name: str) -> str:
    dt = _parse_dt(value, tz_name)
    if not dt:
        return "—"
    tz = _get_zoneinfo(tz_name)
    local = dt.astimezone(tz)
    now = datetime.now(tz)
    if local.date() == now.date():
        return local.strftime("%H:%M")
    return local.strftime("%d/%m %H:%M")


def _format_hour_slot(value: Any, tz_name: str) -> str:
    dt = _parse_dt(value, tz_name)
    if not dt:
        return "—"
    return dt.astimezone(_get_zoneinfo(tz_name)).strftime("%Hh")


def _format_duration_short(duration_sec: Optional[int]) -> str:
    if duration_sec is None:
        return "—"
    total_seconds = max(0, int(duration_sec))
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}'{seconds:02d}"


def _humanize_reason(reason: Optional[str]) -> Optional[str]:
    if not reason:
        return None
    text = str(reason).strip().replace("_", " ")
    if not text:
        return None
    return text[:1].upper() + text[1:]


def _count_active_faq_items(faq: Any) -> int:
    total = 0
    for category in normalize_faq_payload(faq if isinstance(faq, list) else []):
        for item in category.get("items") or []:
            if item.get("active", True) and (item.get("question") or item.get("answer")):
                total += 1
    return total


def _faq_from_tenant_params(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    faq = params.get("faq_json")
    if faq:
        if isinstance(faq, str):
            try:
                parsed = json.loads(faq)
                normalized = normalize_faq_payload(parsed)
                if normalized:
                    return normalized
            except Exception:
                pass
        elif isinstance(faq, list):
            normalized = normalize_faq_payload(faq)
            if normalized:
                return normalized
    specialty = str(params.get("sector") or "default").strip() or "default"
    return DEFAULT_FAQ.get(specialty, DEFAULT_FAQ["default"])


def _get_tenant_me_detail(tenant_id: int) -> Optional[dict]:
    """Charge seulement les données nécessaires à /api/tenant/me."""
    if config.USE_PG_TENANTS:
        try:
            from backend.tenants_pg import _pg_url, pg_tenants_connection, set_tenant_id_on_connection

            url = _pg_url()
            if url:
                with pg_tenants_connection() as conn:
                    set_tenant_id_on_connection(conn, tenant_id)
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT
                                t.tenant_id,
                                t.name,
                                t.timezone,
                                t.status,
                                t.created_at,
                                tc.params_json,
                                (
                                    SELECT tr.key
                                    FROM tenant_routing tr
                                    WHERE tr.tenant_id = t.tenant_id
                                      AND tr.channel IN ('vocal', 'voice')
                                      AND COALESCE(tr.is_active, TRUE) = TRUE
                                    ORDER BY tr.key
                                    LIMIT 1
                                ) AS voice_number
                            FROM tenants t
                            LEFT JOIN tenant_config tc ON tc.tenant_id = t.tenant_id
                            WHERE t.tenant_id = %s
                            LIMIT 1
                            """,
                            (tenant_id,),
                        )
                        row = cur.fetchone()
                        if row:
                            params = row.get("params_json") or {}
                            if isinstance(params, str):
                                try:
                                    params = json.loads(params)
                                except Exception:
                                    params = {}
                            elif not isinstance(params, dict):
                                params = {}
                            return {
                                "tenant_id": row.get("tenant_id"),
                                "name": row.get("name"),
                                "timezone": row.get("timezone"),
                                "status": row.get("status"),
                                "created_at": str(row.get("created_at")) if row.get("created_at") else None,
                                "params": params,
                                "voice_number": row.get("voice_number") or None,
                            }
        except Exception as e:
            logger.debug("tenant me detail pg failed tenant_id=%s err=%s", tenant_id, e)

    ensure_tenant_config()
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT
                t.tenant_id,
                t.name,
                t.timezone,
                t.status,
                t.created_at,
                tc.params_json,
                (
                    SELECT tr.did_key
                    FROM tenant_routing tr
                    WHERE tr.tenant_id = t.tenant_id
                      AND tr.channel IN ('vocal', 'voice')
                    ORDER BY tr.did_key
                    LIMIT 1
                ) AS voice_number
            FROM tenants t
            LEFT JOIN tenant_config tc ON tc.tenant_id = t.tenant_id
            WHERE t.tenant_id = ?
            LIMIT 1
            """,
            (tenant_id,),
        ).fetchone()
        if not row:
            return None
        params = {}
        raw_params = row["params_json"]
        if raw_params:
            try:
                parsed = json.loads(raw_params)
                if isinstance(parsed, dict):
                    params = parsed
            except Exception:
                params = {}
        return {
            "tenant_id": row["tenant_id"],
            "name": row["name"],
            "timezone": row["timezone"],
            "status": row["status"],
            "created_at": row["created_at"],
            "params": params,
            "voice_number": row["voice_number"] or None,
        }
    finally:
        conn.close()


def _last_call_signal(detail: dict) -> Dict[str, Optional[str]]:
    for event in reversed(detail.get("events") or []):
        meta = event.get("meta") or {}
        reason = _humanize_reason(meta.get("reason"))
        context = (meta.get("context") or "").strip() or None
        if reason or context:
            return {"reason": reason, "context": context}
    return {"reason": None, "context": None}


def _classify_call_context(status: str, detail: dict) -> Dict[str, Any]:
    signal = _last_call_signal(detail)
    reason = signal.get("reason")
    context = signal.get("context")
    transcript = (detail.get("transcript") or "").strip()
    summary = _call_summary_from_detail(status, detail)
    haystack = " ".join(part for part in [reason, context, summary, transcript] if part).lower()

    if status in {"CONFIRMED", "CANCELLED", "RESCHEDULED"} or any(token in haystack for token in ("rdv", "rendez-vous", "agenda", "créneau", "creneau", "booking", "annuler", "déplacer", "deplacer")):
        return {
            "reason_label": reason or "Demande de rendez-vous",
            "reason_context": context,
            "reason_category": "agenda",
            "contextual_action": {"kind": "open_agenda", "label": "Ouvrir l'agenda"},
        }

    emergency_number_mentioned = bool(
        re.search(r"\b(?:appelez?|contactez?|joindre|composez?)\s+(?:le\s+)?(?:15|112)\b", haystack)
        or re.search(r"\b(?:samu|urgence vitale|urgences?)\b", haystack)
    )
    if emergency_number_mentioned or any(token in haystack for token in ("urgence", "urgent", "douleur thorac", "saign", "respir")):
        return {
            "reason_label": reason or "Urgence médicale signalée",
            "reason_context": context,
            "reason_category": "urgency",
            "contextual_action": {"kind": "followup_callback", "label": "Rappeler maintenant"},
        }
    if any(token in haystack for token in ("ordonnance", "renouvel", "prescription", "traitement", "médicament", "medicament")):
        return {
            "reason_label": reason or "Demande d'ordonnance à traiter",
            "reason_context": context,
            "reason_category": "prescription",
            "contextual_action": {"kind": "mark_processed", "label": "Marquer traité"},
        }
    if any(token in haystack for token in ("rappel", "rappele", "rappelez", "rappeler", "callback", "recontact")):
        return {
            "reason_label": reason or "Patient à rappeler",
            "reason_context": context,
            "reason_category": "callback",
            "contextual_action": {"kind": "followup_callback", "label": "Mettre en rappel"},
        }
    return {
        "reason_label": reason or ("Information transmise au cabinet" if status == "TRANSFERRED" else "Demande d'information"),
        "reason_context": context,
        "reason_category": "general",
        "contextual_action": {"kind": "open_detail", "label": "Voir le détail"},
    }


def _call_summary_from_detail(status: str, detail: dict) -> str:
    transcript = (detail.get("transcript") or "").strip()
    user_lines = []
    if transcript:
        for line in transcript.splitlines():
            clean = line.strip()
            if clean.startswith("Patient:"):
                user_lines.append(clean.replace("Patient:", "", 1).strip())
    latest_reason = _last_call_signal(detail).get("reason")
    if status == "TRANSFERRED":
        return f"{latest_reason} — transfert humain" if latest_reason else "Transféré à un humain"
    if status == "CANCELLED":
        return "Rendez-vous annulé" if not user_lines else f"RDV annulé — {user_lines[0][:72]}"
    if status == "RESCHEDULED":
        return "Rendez-vous déplacé" if not user_lines else f"RDV déplacé — {user_lines[0][:72]}"
    if status == "CONFIRMED":
        return "Rendez-vous confirmé" if not user_lines else f"RDV confirmé — {user_lines[0][:72]}"
    if status == "ABANDONED":
        return "Appel interrompu par le patient"
    if user_lines:
        return user_lines[0][:96]
    return "Demande d'information traitée par l'assistant"


def _resolve_call_status(item: Optional[dict], detail: Optional[dict]) -> str:
    event_names = [str((event or {}).get("event") or "").strip().lower() for event in (detail or {}).get("events") or []]
    if "modify_done" in event_names:
        return "RESCHEDULED"
    if "cancel_done" in event_names:
        return "CANCELLED"
    if "booking_confirmed" in event_names:
        return "CONFIRMED"
    if any(name in {"transferred_human", "transferred", "transfer_human", "transfer"} for name in event_names):
        return "TRANSFERRED"
    if any(name in {"user_abandon", "abandon", "hangup", "user_hangup"} for name in event_names):
        return "ABANDONED"

    detail_result = str((detail or {}).get("result") or "").strip().lower()
    if detail_result in STATUS_MAP:
        return STATUS_MAP.get(detail_result, "FAQ")

    item_result = str((item or {}).get("result") or "").strip().lower()
    return STATUS_MAP.get(item_result, "FAQ")


def _call_display_phone(item: Optional[dict], detail: Optional[dict]) -> str:
    for candidate in (
        (detail or {}).get("customer_number"),
        (item or {}).get("customer_number"),
    ):
        value = str(candidate or "").strip()
        if value:
            return value
    booking = _latest_booking_meta(detail)
    for candidate in (
        booking.get("patient_contact"),
        booking.get("contact"),
    ):
        value = str(candidate or "").strip()
        if value:
            return value
    for event in reversed((detail or {}).get("events") or []):
        meta = (event or {}).get("meta") or {}
        if not isinstance(meta, dict):
            continue
        for candidate in (
            meta.get("patient_contact"),
            meta.get("customer_number"),
            meta.get("customer_phone"),
            meta.get("phone"),
            meta.get("contact"),
        ):
            value = str(candidate or "").strip()
            if value:
                return value
    return ""


def _latest_booking_meta(detail: Optional[dict]) -> Dict[str, Any]:
    for event in reversed((detail or {}).get("events") or []):
        if str((event or {}).get("event") or "").strip().lower() != "booking_confirmed":
            continue
        meta = (event or {}).get("meta") or {}
        if isinstance(meta, dict):
            return meta
    return {}


def _derive_raw_patient_name(detail: Optional[dict]) -> str:
    booking = _latest_booking_meta(detail)
    for candidate in (
        booking.get("patient_name"),
        booking.get("raw_name"),
        (detail or {}).get("patient_name"),
    ):
        value = str(candidate or "").strip()
        if value and value.lower() != "patient":
            return value
    return ""


def _build_patient_payload(
    tenant_id: int,
    item: Optional[dict],
    detail: Optional[dict],
    profile_cache: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Bloc `patient` des réponses appels : dossier pour le téléphone dans la base fiches patient (`cabinet_clients`).
    `is_validated` reflète une identité enregistrée par le praticien sur le dashboard client (validated_name ≥ 2 car.).
    """
    phone = normalize_phone_number(_call_display_phone(item, detail))
    profile = None
    if phone:
        if profile_cache is not None:
            profile = profile_cache.get(phone)
        else:
            profile = get_cabinet_client_by_phone(tenant_id, phone)
    raw_name = _derive_raw_patient_name(detail) or (profile or {}).get("raw_name") or ""
    validated_name = str((profile or {}).get("validated_name") or "").strip()
    display_name = validated_name or raw_name or "Patient"
    return {
        "phone": phone or "",
        "raw_name": raw_name,
        "validated_name": validated_name,
        "display_name": display_name,
        "validation_status": (profile or {}).get("validation_status")
        or ("validated" if len(validated_name) >= 2 else "pending"),
        "profile_exists": bool(profile),
        "is_validated": len(validated_name) >= 2,
        "source_call_id": (profile or {}).get("source_call_id") or "",
        "updated_at": (profile or {}).get("updated_at") or "",
    }


def _build_booking_payload(detail: Optional[dict]) -> Optional[Dict[str, Any]]:
    booking = _latest_booking_meta(detail)
    if not booking:
        return None
    start_iso = str(booking.get("start_iso") or "").strip()
    end_iso = str(booking.get("end_iso") or "").strip()
    slot_label = str(booking.get("slot_label") or "").strip()
    motif = str(booking.get("motif") or "").strip()
    event_id = str(booking.get("event_id") or "").strip()
    if not any([start_iso, end_iso, slot_label, motif, event_id]):
        return None
    return {
        "start_iso": start_iso,
        "end_iso": end_iso,
        "slot_label": slot_label,
        "motif": motif,
        "event_id": event_id,
        "source": str(booking.get("booking_source") or ("google" if event_id else "local")).strip() or "local",
    }


def _resolve_agenda_patient_name(tenant_id: int, phone: Optional[str], fallback_name: Optional[str]) -> str:
    phone_norm = normalize_phone_number(phone)
    if phone_norm:
        profile = get_cabinet_client_by_phone(tenant_id, phone_norm) or {}
        display_name = str(profile.get("display_name") or "").strip()
        if display_name:
            return display_name
    fallback = str(fallback_name or "").strip()
    return fallback or "Patient"


def _resolve_agenda_patient_name_cached(
    tenant_id: int,
    phone: Optional[str],
    fallback_name: Optional[str],
    profile_cache: Optional[Dict[str, Optional[Dict[str, Any]]]] = None,
) -> str:
    phone_norm = normalize_phone_number(phone)
    if phone_norm:
        profile: Optional[Dict[str, Any]]
        if profile_cache is not None and phone_norm in profile_cache:
            profile = profile_cache.get(phone_norm)
        else:
            profile = get_cabinet_client_by_phone(tenant_id, phone_norm) or None
            if profile_cache is not None:
                profile_cache[phone_norm] = profile
        display_name = str((profile or {}).get("display_name") or "").strip()
        if display_name:
            return display_name
    fallback = str(fallback_name or "").strip()
    return fallback or "Patient"


def _dashboard_patient_file_has_validated_identity(profile: Optional[Dict[str, Any]]) -> bool:
    """Une fiche patient « complète » sur le dashboard client : identité validée par le praticien (≥ 2 car.).

    Technique : ligne patient en base (`cabinet_clients`) avec champ `validated_name` renseigné.
    Ce n’est pas le nom du cabinet médical."""
    if not profile:
        return False
    vn = str(profile.get("validated_name") or "").strip()
    return len(vn) >= 2


def _agenda_lookup_dashboard_patient_profile(
    tenant_id: int,
    phone_norm: str,
    profile_cache: Dict[str, Optional[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    """Fiche patient (dashboard) pour ce numéro, avec cache mutualisé sur la journée agenda."""
    if not phone_norm:
        return None
    if phone_norm in profile_cache:
        return profile_cache.get(phone_norm)
    profile = get_cabinet_client_by_phone(tenant_id, phone_norm) or None
    profile_cache[phone_norm] = profile
    return profile


def _decorate_agenda_slots_patient_has_file(
    tenant_id: int,
    slots: List[Dict[str, Any]],
    profile_cache: Dict[str, Optional[Dict[str, Any]]],
) -> None:
    """Ajoute ``patient_has_file`` : True si une fiche patient existe avec identité validée sur le dashboard client."""
    for item in slots:
        phone_norm = normalize_phone_number(item.get("patient_phone") or "")
        if not phone_norm:
            item["patient_has_file"] = False
            continue
        profile = _agenda_lookup_dashboard_patient_profile(tenant_id, phone_norm, profile_cache)
        item["patient_has_file"] = _dashboard_patient_file_has_validated_identity(profile)


def _warm_agenda_profiles_from_contact_strings(
    tenant_id: int,
    contact_values: Iterable[Optional[str]],
    profile_cache: Dict[str, Optional[Dict[str, Any]]],
) -> None:
    """Remplit ``profile_cache`` par lots pour éviter N connexions / N requêtes sur l'agenda."""
    pending: List[str] = []
    seen = set()
    for raw in contact_values:
        pn = normalize_phone_number(raw or "")
        if not pn or pn in profile_cache or pn in seen:
            continue
        seen.add(pn)
        pending.append(pn)
    if not pending:
        return
    loaded = get_cabinet_clients_by_phones(tenant_id, pending)
    for pn, profile in loaded.items():
        profile_cache[pn] = profile


def _warm_profile_cache_google_event_descriptions(
    tenant_id: int,
    google_items: List[Dict[str, Any]],
    profile_cache: Dict[str, Optional[Dict[str, Any]]],
) -> None:
    contacts: List[str] = []
    for event in google_items or []:
        description = str((event.get("description") or "")).strip()
        contacts.append(_extract_calendar_event_patient_contact(description) or "")
    _warm_agenda_profiles_from_contact_strings(tenant_id, contacts, profile_cache)


def _warm_agenda_profiles_from_slots_patient_phone(
    tenant_id: int,
    slots: List[Dict[str, Any]],
    profile_cache: Dict[str, Optional[Dict[str, Any]]],
) -> None:
    vals = [(item.get("patient_phone") or "") for item in (slots or [])]
    _warm_agenda_profiles_from_contact_strings(tenant_id, vals, profile_cache)


def _extract_google_description_line(description: str, prefix: str) -> Optional[str]:
    for line in (description or "").splitlines():
        if line.lower().startswith(prefix.lower()):
            return line.split(":", 1)[1].strip() if ":" in line else line.strip()
    return None


def _extract_calendar_event_patient_contact(description: str) -> str:
    """Ligne téléphone patient dans la description agenda (libellés usuels FR)."""
    for key in ("Contact", "Téléphone", "Telephone", "Tel", "Portable", "Mobile"):
        v = _extract_google_description_line(description, key)
        if v:
            return v
    return ""

def _get_local_appointment_by_id(tenant_id: int, appointment_id: int) -> Optional[Dict[str, Any]]:
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_SLOTS_URL")
    if url:
        try:
            import psycopg
            from psycopg.rows import dict_row

            with psycopg.connect(url, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT a.id, a.slot_id, a.name, a.contact, a.contact_type, a.motif, s.start_ts
                        FROM appointments a
                        JOIN slots s ON s.id = a.slot_id
                        WHERE a.tenant_id = %s AND a.id = %s
                        LIMIT 1
                        """,
                        (tenant_id, appointment_id),
                    )
                    row = cur.fetchone()
                    if not row:
                        return None
                    start_dt = row.get("start_ts")
                    date_str = ""
                    time_str = ""
                    if start_dt:
                        parsed = _parse_dt(start_dt)
                        if parsed:
                            date_str = parsed.strftime("%Y-%m-%d")
                            time_str = parsed.strftime("%H:%M")
                    return {
                        "id": int(row.get("id") or 0),
                        "slot_id": int(row.get("slot_id") or 0),
                        "name": row.get("name") or "",
                        "contact": row.get("contact") or "",
                        "contact_type": row.get("contact_type") or "",
                        "motif": row.get("motif") or "",
                        "date": date_str,
                        "time": time_str,
                    }
        except Exception as e:
            logger.debug("local appointment lookup pg failed tenant_id=%s appointment_id=%s err=%s", tenant_id, appointment_id, e)

    ensure_tenant_config()
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT a.id, a.slot_id, a.name, a.contact, a.contact_type, a.motif, s.date, s.time
            FROM appointments a
            JOIN slots s ON s.id = a.slot_id AND s.tenant_id = a.tenant_id
            WHERE a.tenant_id = ? AND a.id = ?
            LIMIT 1
            """,
            (tenant_id, appointment_id),
        ).fetchone()
        if not row:
            return None
        return {
            "id": int(row["id"] or 0),
            "slot_id": int(row["slot_id"] or 0),
            "name": row["name"] or "",
            "contact": row["contact"] or "",
            "contact_type": row["contact_type"] or "",
            "motif": row["motif"] or "",
            "date": row["date"] or "",
            "time": row["time"] or "",
        }
    finally:
        conn.close()


def _google_mirror_enabled(detail: Optional[dict]) -> bool:
    params = (detail or {}).get("params") or {}
    provider = (params.get("calendar_provider") or "").strip() == "google"
    raw = params.get("mirror_google_bookings_to_internal")
    if provider and raw is None:
        return True
    return provider and _is_truthy(raw)


def _appointment_lookup_key(start_local: Optional[datetime]) -> str:
    if not start_local:
        return ""
    return start_local.strftime("%Y-%m-%dT%H:%M")


def _normalize_lookup_text(value: Optional[str]) -> str:
    return str(value or "").strip().lower()


def _appointment_matches_lookup(appointment: Dict[str, Any], patient_contact: Optional[str], fallback_name: Optional[str]) -> bool:
    contact = str(patient_contact or "").strip()
    name = str(fallback_name or "").strip()

    if contact:
        contact_norm = normalize_phone_number(contact)
        appt_contact = str(appointment.get("contact") or "").strip()
        appt_contact_norm = normalize_phone_number(appt_contact)
        if contact_norm and appt_contact_norm:
            return contact_norm == appt_contact_norm
        return _normalize_lookup_text(appt_contact) == _normalize_lookup_text(contact)

    if name:
        return _normalize_lookup_text(appointment.get("name")) == _normalize_lookup_text(name)

    return False


def _load_local_appointments_for_window(
    tenant_id: int,
    day_start: datetime,
    day_end: datetime,
    tz_name: str,
) -> Dict[str, List[Dict[str, Any]]]:
    index: Dict[str, List[Dict[str, Any]]] = {}
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_SLOTS_URL")
    if url:
        try:
            from backend.pg_pool import pg_connection_for

            with pg_connection_for(url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT a.id, a.slot_id, a.name, a.contact, a.contact_type, a.motif, s.start_ts,
                               a.booking_origin
                        FROM appointments a
                        JOIN slots s ON s.id = a.slot_id
                        WHERE a.tenant_id = %s
                          AND s.start_ts >= %s
                          AND s.start_ts < %s
                        ORDER BY a.created_at DESC
                        """,
                        (tenant_id, day_start.astimezone(timezone.utc), day_end.astimezone(timezone.utc)),
                    )
                    for row in cur.fetchall():
                        start_local = _parse_dt(row.get("start_ts"), tz_name)
                        key = _appointment_lookup_key(start_local.astimezone(_get_zoneinfo(tz_name)) if start_local else None)
                        if not key:
                            continue
                        index.setdefault(key, []).append(
                            {
                                "id": int(row.get("id") or 0),
                                "slot_id": int(row.get("slot_id") or 0),
                                "name": row.get("name") or "",
                                "contact": row.get("contact") or "",
                                "contact_type": row.get("contact_type") or "",
                                "motif": row.get("motif") or "",
                                "booking_origin": row.get("booking_origin") or "",
                            }
                        )
                    return index
        except Exception as e:
            logger.debug("local appointments window lookup pg failed tenant_id=%s err=%s", tenant_id, e)

    ensure_tenant_config()
    conn = get_conn()
    try:
        _migrate_sqlite_add_booking_origin(conn)
        rows = conn.execute(
            """
            SELECT a.id, a.slot_id, a.name, a.contact, a.contact_type, a.motif,
                   a.booking_origin, s.date, s.time
            FROM appointments a
            JOIN slots s ON s.id = a.slot_id AND s.tenant_id = a.tenant_id
            WHERE a.tenant_id = ?
              AND s.date >= ?
              AND s.date <= ?
            ORDER BY a.created_at DESC
            """,
            (tenant_id, day_start.strftime("%Y-%m-%d"), (day_end - timedelta(days=1)).strftime("%Y-%m-%d")),
        ).fetchall()
        for row in rows:
            start_local = _parse_dt(f"{row['date']}T{row['time']}:00", tz_name)
            key = _appointment_lookup_key(start_local)
            if not key:
                continue
            index.setdefault(key, []).append(
                {
                    "id": int(row["id"] or 0),
                    "slot_id": int(row["slot_id"] or 0),
                    "name": row["name"] or "",
                    "contact": row["contact"] or "",
                    "contact_type": row["contact_type"] or "",
                    "motif": row["motif"] or "",
                    "booking_origin": row["booking_origin"] or "",
                }
            )
        return index
    finally:
        conn.close()


def _agenda_resolve_booking_origin_google(
    description: str,
    mirror_booking: Optional[Dict[str, Any]],
) -> str:
    from backend.booking_origin import UNKNOWN, canonical, parse_google_description

    parsed = parse_google_description(description)
    if parsed:
        return canonical(parsed)
    if mirror_booking and str(mirror_booking.get("booking_origin") or "").strip():
        return canonical(mirror_booking.get("booking_origin"))
    return UNKNOWN


def _agenda_booking_origin_from_local_row(row: Any) -> str:
    from backend.booking_origin import UNKNOWN, canonical

    if row is None:
        return UNKNOWN
    try:
        raw = row.get("booking_origin") if hasattr(row, "get") else row["booking_origin"]
    except (KeyError, TypeError, AttributeError):
        raw = None
    if not raw:
        return UNKNOWN
    return canonical(str(raw))


def _find_local_appointment_for_google_event(
    tenant_id: int,
    start_local: datetime,
    patient_contact: Optional[str],
    fallback_name: Optional[str],
    appointments_index: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> Optional[Dict[str, Any]]:
    if appointments_index is not None:
        for appointment in appointments_index.get(_appointment_lookup_key(start_local), []):
            if _appointment_matches_lookup(appointment, patient_contact, fallback_name):
                return appointment

    contact = str(patient_contact or "").strip()
    name = str(fallback_name or "").strip()
    if not start_local or (not contact and not name):
        return None

    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_SLOTS_URL")
    if url:
        try:
            import psycopg
            from psycopg.rows import dict_row

            start_utc = start_local.astimezone(timezone.utc)
            window_start = start_utc - timedelta(minutes=1)
            window_end = start_utc + timedelta(minutes=1)
            with psycopg.connect(url, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT a.id, a.slot_id, a.name, a.contact, a.contact_type, a.motif, s.start_ts
                        FROM appointments a
                        JOIN slots s ON s.id = a.slot_id
                        WHERE a.tenant_id = %s
                          AND s.start_ts >= %s
                          AND s.start_ts < %s
                          AND (
                                (%s <> '' AND LOWER(TRIM(COALESCE(a.contact, ''))) = LOWER(TRIM(%s)))
                             OR (%s = '' AND %s <> '' AND LOWER(TRIM(COALESCE(a.name, ''))) = LOWER(TRIM(%s)))
                          )
                        ORDER BY a.created_at DESC
                        LIMIT 1
                        """,
                        (tenant_id, window_start, window_end, contact, contact, contact, name, name),
                    )
                    row = cur.fetchone()
                    if row:
                        return {
                            "id": int(row.get("id") or 0),
                            "slot_id": int(row.get("slot_id") or 0),
                            "name": row.get("name") or "",
                            "contact": row.get("contact") or "",
                            "contact_type": row.get("contact_type") or "",
                            "motif": row.get("motif") or "",
                        }
        except Exception as e:
            logger.debug("local appointment mirror lookup pg failed tenant_id=%s err=%s", tenant_id, e)

    ensure_tenant_config()
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT a.id, a.slot_id, a.name, a.contact, a.contact_type, a.motif
            FROM appointments a
            JOIN slots s ON s.id = a.slot_id AND s.tenant_id = a.tenant_id
            WHERE a.tenant_id = ?
              AND s.date = ?
              AND s.time = ?
              AND (
                    (? <> '' AND LOWER(TRIM(COALESCE(a.contact, ''))) = LOWER(TRIM(?)))
                 OR (? = '' AND ? <> '' AND LOWER(TRIM(COALESCE(a.name, ''))) = LOWER(TRIM(?)))
              )
            ORDER BY a.created_at DESC
            LIMIT 1
            """,
            (
                tenant_id,
                start_local.strftime("%Y-%m-%d"),
                start_local.strftime("%H:%M"),
                contact,
                contact,
                contact,
                name,
                name,
            ),
        ).fetchone()
        if not row:
            return None
        return {
            "id": int(row["id"] or 0),
            "slot_id": int(row["slot_id"] or 0),
            "name": row["name"] or "",
            "contact": row["contact"] or "",
            "contact_type": row["contact_type"] or "",
            "motif": row["motif"] or "",
        }
    finally:
        conn.close()


def _get_slot_window(
    tenant_id: int,
    slot_id: int,
    tz_name: str,
    duration_minutes: int,
) -> Optional[tuple[datetime, datetime]]:
    if not slot_id:
        return None
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_SLOTS_URL")
    if url:
        try:
            import psycopg

            with psycopg.connect(url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT start_ts
                        FROM slots
                        WHERE tenant_id = %s AND id = %s
                        LIMIT 1
                        """,
                        (tenant_id, slot_id),
                    )
                    row = cur.fetchone()
                    if row and row[0]:
                        start_local = _parse_dt(row[0], tz_name)
                        if start_local:
                            return start_local, start_local + timedelta(minutes=duration_minutes)
        except Exception as e:
            logger.debug("slot window pg lookup failed tenant_id=%s slot_id=%s err=%s", tenant_id, slot_id, e)

    ensure_tenant_config()
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT date, time
            FROM slots
            WHERE tenant_id = ? AND id = ?
            LIMIT 1
            """,
            (tenant_id, slot_id),
        ).fetchone()
        if not row:
            return None
        start_local = _parse_dt(f"{row['date']}T{row['time']}:00", tz_name)
        if not start_local:
            return None
        return start_local, start_local + timedelta(minutes=duration_minutes)
    finally:
        conn.close()


class TenantAgendaCancelBody(BaseModel):
    source: str = "UWI"
    external_event_id: str = ""


class TenantAgendaRescheduleBody(BaseModel):
    new_slot_id: int
    external_event_id: str = ""


class TenantAgendaCreateBookingBody(BaseModel):
    """Création d'un RDV par le praticien depuis l'espace client."""

    patient_name: str = Field(..., min_length=1, max_length=200)
    patient_phone: str = Field("", max_length=40)
    patient_email: str = Field("", max_length=200)
    motif: str = Field("Consultation", max_length=500)
    start_iso: str = Field(..., min_length=10, description="ISO 8601 début")
    end_iso: str = Field("", max_length=64, description="Fin ISO (optionnel)")


class TenantCallFollowupBody(BaseModel):
    followup_state: str
    notes: str = ""


class TenantCallPatientBody(BaseModel):
    validated_name: str
    raw_name: str = ""
    patient_phone: str = ""


class TenantHandoffUpdateBody(BaseModel):
    status: Optional[str] = Field(default=None, max_length=32)
    notes: Optional[str] = Field(default=None, max_length=1000)


class TenantProfileBody(BaseModel):
    practitioner_name: Optional[str] = None
    cabinet_name: Optional[str] = None
    specialty: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address_line: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    website_url: Optional[str] = None
    languages: Optional[List[str]] = None
    accepts_new_patients: Optional[bool] = None
    practitioner_photo_url: Optional[str] = None
    public_slug: Optional[str] = None


class OpeningHoursBody(BaseModel):
    opening_hours: List[Dict[str, Any]]


class AvailabilitySettingsBody(BaseModel):
    temporary_closure_enabled: Optional[bool] = None
    temporary_closure_start: Optional[str] = None
    temporary_closure_end: Optional[str] = None
    temporary_closure_message: Optional[str] = None


class BookingRulesBody(BaseModel):
    default_appointment_duration_minutes: Optional[int] = None
    minimum_booking_notice_hours: Optional[int] = None
    accepts_new_patients: Optional[bool] = None
    appointment_reschedule_allowed: Optional[bool] = None
    appointment_reschedule_notice_hours: Optional[int] = None
    appointment_cancel_allowed: Optional[bool] = None
    appointment_cancel_notice_hours: Optional[int] = None
    emergency_instruction: Optional[str] = None
    new_patient_instruction: Optional[str] = None
    booking_notes: Optional[str] = None


class AppointmentReasonBody(BaseModel):
    label: str
    duration_minutes: int = 30
    enabled: bool = True
    description: str = ""
    allowed_for_new_patients: Optional[bool] = None


class AssistantSettingsBody(BaseModel):
    assistant_name: Optional[str] = None
    welcome_message: Optional[str] = None
    documents_to_bring: Optional[str] = None
    access_instructions: Optional[str] = None
    payment_methods: Optional[str] = None
    parking_info: Optional[str] = None
    pmr_access: Optional[str] = None
    sensitive_medical_instruction: Optional[str] = None
    escalation_instruction: Optional[str] = None
    human_handoff_instruction: Optional[str] = None
    faq_items: Optional[List[Dict[str, Any]]] = None


class PreviewMessageBody(BaseModel):
    message: str = Field(default="", max_length=2000)


class BillingChangePlanBody(BaseModel):
    plan_key: str


@router.get("/me")
def tenant_me(auth: dict = Depends(require_tenant_auth)):
    """Profil du tenant connecté."""
    tenant_id = auth["tenant_id"]
    d = _get_tenant_me_detail(tenant_id)
    if not d:
        raise HTTPException(404, "Tenant not found")
    params = d.get("params") or {}
    voice_number = (d.get("voice_number") or "").strip() or None
    vapi_assistant_id = (params.get("vapi_assistant_id") or "").strip()
    calendar_provider = (params.get("calendar_provider") or "none").strip() or "none"
    calendar_id = (params.get("calendar_id") or "").strip()
    assistant_name = (params.get("assistant_name") or "").strip()
    faq = _faq_from_tenant_params(params)
    faq_ready = _count_active_faq_items(faq) > 0
    _explicit = _is_truthy(params.get("client_onboarding_completed"))
    _vapi_ready = bool(vapi_assistant_id)
    booking_days = params.get("booking_days")
    horaires_ready = False
    if isinstance(booking_days, (list, tuple, set)):
        horaires_ready = len(booking_days) > 0
    elif isinstance(booking_days, str):
        raw_days = booking_days.strip()
        if raw_days:
            try:
                parsed_days = json.loads(raw_days)
                horaires_ready = isinstance(parsed_days, (list, tuple)) and len(parsed_days) > 0
            except Exception:
                horaires_ready = bool(raw_days)
    elif booking_days is not None:
        horaires_ready = bool(booking_days)

    calendar_configured = bool(calendar_id) and not _looks_like_service_account_email(calendar_id)
    onboarding_steps = {
        "assistant_ready": bool(assistant_name and vapi_assistant_id),
        "phone_ready": bool(voice_number),
        "calendar_ready": (calendar_provider == "google" and calendar_configured) or calendar_provider == "none",
        "horaires_ready": horaires_ready,
        "faq_ready": faq_ready,
    }
    onboarding_completed = all(onboarding_steps.values())
    client_onboarding_completed = _explicit or onboarding_completed
    transfer_hours = _parse_dict_value(params.get("transfer_hours"))
    transfer_cases = _parse_string_list(params.get("transfer_cases"))
    tenant_display_name = _tenant_display_name(d, tenant_id)
    try:
        from backend.auth_pg import pg_get_must_change_password
        must_change_password = pg_get_must_change_password(int(auth["sub"]))
    except Exception:
        must_change_password = False

    return {
        "tenant_id": tenant_id,
        "tenant_name": tenant_display_name,
        "email": auth.get("email"),
        "role": auth.get("role", "owner"),
        "must_change_password": must_change_password,
        "contact_email": params.get("contact_email", ""),
        "phone_number": params.get("phone_number", ""),
        "timezone": params.get("timezone", "Europe/Paris"),
        "calendar_id": calendar_id,
        "calendar_provider": calendar_provider,
        "agenda_software": params.get("agenda_software", ""),
        "sector": params.get("sector", ""),
        "specialty_label": params.get("specialty_label", ""),
        "address_line1": params.get("address_line1", ""),
        "postal_code": params.get("postal_code", ""),
        "city": params.get("city", ""),
        "assistant_name": assistant_name or "sophie",
        "plan_key": params.get("plan_key", "growth"),
        "vapi_assistant_id": vapi_assistant_id,
        "assistant_live": _vapi_ready,
        "voice_number": voice_number,
        "client_onboarding_completed": client_onboarding_completed,
        "dashboard_tour_completed": _is_truthy(params.get("dashboard_tour_completed")),
        "transfer_number": params.get("transfer_number", ""),
        "transfer_practitioner_phone": params.get("transfer_practitioner_phone", ""),
        "transfer_live_enabled": _is_truthy(params.get("transfer_live_enabled")),
        "transfer_callback_enabled": params.get("transfer_callback_enabled") is None or _is_truthy(params.get("transfer_callback_enabled")),
        "transfer_cases": transfer_cases,
        "transfer_hours": transfer_hours,
        "transfer_always_urgent": _is_truthy(params.get("transfer_always_urgent")),
        "transfer_no_consultation": _is_truthy(params.get("transfer_no_consultation")),
        "transfer_config_confirmed_signature": params.get("transfer_config_confirmed_signature", ""),
        "transfer_config_confirmed_at": params.get("transfer_config_confirmed_at", ""),
        "onboarding_steps": onboarding_steps,
        "onboarding_completed": onboarding_completed,
        "faq_items_count": _count_active_faq_items(faq),
    }


@router.get("/profile-summary")
def tenant_profile_summary(auth: dict = Depends(require_tenant_auth)):
    tenant_id = auth["tenant_id"]
    detail = _get_tenant_me_detail(tenant_id)
    if not detail:
        raise HTTPException(404, "Tenant not found")
    params = detail.get("params") or {}
    pg_profile = pg_get_profile(tenant_id) or {}
    pg_opening = pg_get_opening_hours(tenant_id) or []
    pg_rules = pg_get_booking_rules(tenant_id) or {}
    pg_assistant = pg_get_assistant_settings(tenant_id) or {}
    tech = _get_technical_status(tenant_id) or {}
    calendar_connected = (tech.get("calendar_status") or "") == "connected"
    billing = get_tenant_billing(tenant_id) or {}

    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.month < 12:
        month_end = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        month_end = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    used_minutes = int(round(_get_quota_used_minutes(tenant_id, month_start.strftime("%Y-%m-%d %H:%M:%S"), month_end.strftime("%Y-%m-%d %H:%M:%S")), 0))

    checks = {
        "identity": bool((pg_profile.get("cabinet_name") or params.get("business_name") or params.get("practitioner_name") or detail.get("name")) and (pg_profile.get("email") or params.get("contact_email")) and (pg_profile.get("phone") or params.get("phone_number"))),
        "horaires": bool(pg_opening or params.get("opening_hours_json") or params.get("booking_days")),
        "agenda": calendar_connected,
        "rules": bool(pg_rules.get("default_appointment_duration_minutes") or params.get("default_appointment_duration_minutes") or params.get("booking_duration_minutes")),
        "clara": bool(pg_assistant.get("welcome_message") or pg_assistant.get("sensitive_medical_instruction") or params.get("welcome_message") or params.get("sensitive_medical_instruction")),
        "billing": bool(billing.get("plan_key") or params.get("plan_key")),
    }
    score = int(round((sum(1 for ok in checks.values() if ok) / len(checks)) * 100))

    missing_items: List[Dict[str, Any]] = []
    if not (pg_rules.get("new_patient_instruction") or params.get("new_patient_instruction")):
        missing_items.append({"key": "new_patient_instruction", "label": "Ajouter les consignes pour nouveaux patients", "severity": "warning"})
    if not pg_opening and not params.get("opening_hours_json") and not params.get("booking_days"):
        missing_items.append({"key": "opening_hours", "label": "Completer les horaires du cabinet", "severity": "warning"})
    if not calendar_connected:
        missing_items.append({"key": "calendar", "label": "Reconnecter l'agenda Google", "severity": "warning"})

    return {
        "profile_completion_percentage": score,
        "calendar_connected": calendar_connected,
        "billing_status": (billing.get("billing_status") or "unknown"),
        "current_plan": (billing.get("plan_key") or params.get("plan_key") or "growth"),
        "used_minutes_current_month": used_minutes,
        "missing_items": missing_items,
    }


@router.get("/profile")
def tenant_get_profile(auth: dict = Depends(require_tenant_auth)):
    tenant_id = auth["tenant_id"]
    detail = _get_tenant_me_detail(tenant_id)
    if not detail:
        raise HTTPException(404, "Tenant not found")
    params = detail.get("params") or {}
    pg_profile = pg_get_profile(tenant_id) or {}
    voice_number = (detail.get("voice_number") or "").strip()

    def _param_str(*keys: str) -> str:
        for key in keys:
            val = params.get(key)
            if val is not None and str(val).strip():
                return str(val).strip()
        return ""

    public_slug = (params.get("public_slug") or "").strip() or _slugify(str(params.get("business_name") or detail.get("name") or "cabinet"))
    languages = _parse_string_list(params.get("languages"))
    if pg_profile:
        public_slug = pg_profile.get("public_slug") or public_slug
        if pg_profile.get("languages"):
            languages = pg_profile.get("languages")
    return {
        "tenant_id": tenant_id,
        "practitioner_name": pg_profile.get("practitioner_name") or _param_str("practitioner_name", "primary_practitioner_name") or params.get("business_name") or detail.get("name") or "",
        "cabinet_name": pg_profile.get("cabinet_name") or params.get("business_name") or detail.get("name") or "",
        "specialty": pg_profile.get("specialty") or _param_str("specialty_label", "profession") or "",
        "phone": pg_profile.get("phone") or _param_str("phone_number", "current_phone_number") or voice_number or "",
        "email": pg_profile.get("email") or params.get("contact_email") or "",
        "address_line": pg_profile.get("address_line") or _param_str("address_line1", "address_line", "address") or "",
        "postal_code": pg_profile.get("postal_code") or params.get("postal_code") or "",
        "city": pg_profile.get("city") or params.get("city") or "",
        "website_url": pg_profile.get("website_url") or params.get("website_url") or "",
        "languages": languages,
        "accepts_new_patients": bool(pg_profile.get("accepts_new_patients")) if "accepts_new_patients" in pg_profile else _is_truthy(params.get("accepts_new_patients", True)),
        "public_page_url": f"/praticiens/{public_slug}" if public_slug else "",
        "practitioner_photo_url": pg_profile.get("practitioner_photo_url") or params.get("practitioner_photo_url") or "",
    }


@router.patch("/profile")
def tenant_patch_profile(body: TenantProfileBody, auth: dict = Depends(require_tenant_auth)):
    tenant_id = auth["tenant_id"]
    payload = body.model_dump(exclude_none=True)
    params: Dict[str, Any] = {}
    mapping = {
        "practitioner_name": "practitioner_name",
        "cabinet_name": "business_name",
        "specialty": "specialty_label",
        "phone": "phone_number",
        "email": "contact_email",
        "address_line": "address_line1",
        "postal_code": "postal_code",
        "city": "city",
        "website_url": "website_url",
        "accepts_new_patients": "accepts_new_patients",
        "practitioner_photo_url": "practitioner_photo_url",
        "public_slug": "public_slug",
    }
    for source_key, target_key in mapping.items():
        if source_key in payload:
            params[target_key] = payload[source_key]
    if "languages" in payload:
        params["languages"] = [str(item).strip() for item in (payload.get("languages") or []) if str(item).strip()]
    if payload.get("cabinet_name"):
        pg_update_tenant_name(tenant_id, str(payload.get("cabinet_name")).strip())
    pg_payload = {
        "practitioner_name": payload.get("practitioner_name"),
        "cabinet_name": payload.get("cabinet_name"),
        "specialty": payload.get("specialty"),
        "phone": payload.get("phone"),
        "email": payload.get("email"),
        "address_line": payload.get("address_line"),
        "postal_code": payload.get("postal_code"),
        "city": payload.get("city"),
        "website_url": payload.get("website_url"),
        "languages": payload.get("languages"),
        "accepts_new_patients": payload.get("accepts_new_patients"),
        "practitioner_photo_url": payload.get("practitioner_photo_url"),
        "public_slug": payload.get("public_slug"),
    }
    pg_upsert_profile(tenant_id, pg_payload)
    if params:
        ok = pg_update_tenant_params(tenant_id, params)
        if not ok:
            raise HTTPException(500, "Failed to update profile")
    return {"ok": True}


@router.get("/opening-hours")
def tenant_get_opening_hours(auth: dict = Depends(require_tenant_auth)):
    tenant_id = auth["tenant_id"]
    detail = _get_tenant_me_detail(tenant_id)
    if not detail:
        raise HTTPException(404, "Tenant not found")
    params = detail.get("params") or {}
    opening = pg_get_opening_hours(tenant_id) or _normalize_opening_hours_payload(_parse_dict_value(params.get("opening_hours_json")).get("opening_hours"))
    if not opening:
        opening = _build_default_opening_hours(params)
    return {"opening_hours": opening}


@router.patch("/opening-hours")
def tenant_patch_opening_hours(body: OpeningHoursBody, auth: dict = Depends(require_tenant_auth)):
    tenant_id = auth["tenant_id"]
    opening = _normalize_opening_hours_payload(body.opening_hours)
    if not opening:
        raise HTTPException(400, "opening_hours invalide")
    open_indexes = [idx for idx, row in enumerate(opening) if row.get("is_open")]
    start_hour = min([to_hour for to_hour in [int(str(row.get("morning_start") or "09:00").split(":")[0]) for row in opening if row.get("is_open")] or [9]])
    end_hour = max([to_hour for to_hour in [int(str(row.get("afternoon_end") or row.get("morning_end") or "18:00").split(":")[0]) for row in opening if row.get("is_open")] or [18]])
    payload = {
        "opening_hours_json": {"opening_hours": opening},
        "booking_days": open_indexes,
        "booking_start_hour": start_hour,
        "booking_end_hour": end_hour,
    }
    pg_replace_opening_hours(tenant_id, opening)
    if not pg_update_tenant_params(tenant_id, payload):
        raise HTTPException(500, "Failed to update opening hours")
    return {"ok": True, "opening_hours": opening}


@router.get("/availability-settings")
def tenant_get_availability_settings(auth: dict = Depends(require_tenant_auth)):
    tenant_id = auth["tenant_id"]
    detail = _get_tenant_me_detail(tenant_id)
    if not detail:
        raise HTTPException(404, "Tenant not found")
    params = detail.get("params") or {}
    pg_row = pg_get_availability_settings(tenant_id) or {}
    return {
        "temporary_closure_enabled": bool(pg_row.get("temporary_closure_enabled")) if "temporary_closure_enabled" in pg_row else _is_truthy(params.get("temporary_closure_enabled")),
        "temporary_closure_start": pg_row.get("temporary_closure_start") or params.get("temporary_closure_start") or "",
        "temporary_closure_end": pg_row.get("temporary_closure_end") or params.get("temporary_closure_end") or "",
        "temporary_closure_message": pg_row.get("temporary_closure_message") or params.get("temporary_closure_message") or "",
    }


@router.patch("/availability-settings")
def tenant_patch_availability_settings(body: AvailabilitySettingsBody, auth: dict = Depends(require_tenant_auth)):
    tenant_id = auth["tenant_id"]
    payload = body.model_dump(exclude_none=True)
    pg_upsert_availability_settings(tenant_id, payload)
    if payload and not pg_update_tenant_params(tenant_id, payload):
        raise HTTPException(500, "Failed to update availability settings")
    return {"ok": True}


@router.get("/booking-rules")
def tenant_get_booking_rules(auth: dict = Depends(require_tenant_auth)):
    tenant_id = auth["tenant_id"]
    detail = _get_tenant_me_detail(tenant_id)
    if not detail:
        raise HTTPException(404, "Tenant not found")
    params = detail.get("params") or {}
    pg_rules = pg_get_booking_rules(tenant_id) or {}
    return {
        "default_appointment_duration_minutes": int(pg_rules.get("default_appointment_duration_minutes") or params.get("default_appointment_duration_minutes") or params.get("booking_duration_minutes") or 30),
        "minimum_booking_notice_hours": int(pg_rules.get("minimum_booking_notice_hours") or params.get("minimum_booking_notice_hours") or 24),
        "accepts_new_patients": bool(pg_rules.get("accepts_new_patients")) if "accepts_new_patients" in pg_rules else _is_truthy(params.get("accepts_new_patients", True)),
        "appointment_reschedule_allowed": bool(pg_rules.get("appointment_reschedule_allowed")) if "appointment_reschedule_allowed" in pg_rules else _is_truthy(params.get("appointment_reschedule_allowed", True)),
        "appointment_reschedule_notice_hours": int(pg_rules.get("appointment_reschedule_notice_hours") or params.get("appointment_reschedule_notice_hours") or 24),
        "appointment_cancel_allowed": bool(pg_rules.get("appointment_cancel_allowed")) if "appointment_cancel_allowed" in pg_rules else _is_truthy(params.get("appointment_cancel_allowed", True)),
        "appointment_cancel_notice_hours": int(pg_rules.get("appointment_cancel_notice_hours") or params.get("appointment_cancel_notice_hours") or 24),
        "emergency_instruction": pg_rules.get("emergency_instruction") or params.get("emergency_instruction") or "",
        "new_patient_instruction": pg_rules.get("new_patient_instruction") or params.get("new_patient_instruction") or "",
        "booking_notes": pg_rules.get("booking_notes") or params.get("booking_notes") or "",
    }


@router.patch("/booking-rules")
def tenant_patch_booking_rules(body: BookingRulesBody, auth: dict = Depends(require_tenant_auth)):
    tenant_id = auth["tenant_id"]
    payload = body.model_dump(exclude_none=True)
    pg_upsert_booking_rules(tenant_id, payload)
    if payload and not pg_update_tenant_params(tenant_id, payload):
        raise HTTPException(500, "Failed to update booking rules")
    return {"ok": True}


def _get_appointment_reasons_from_params(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = params.get("appointment_reasons_json")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = []
    if not isinstance(raw, list):
        raw = []
    out: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "id": str(item.get("id") or uuid4().hex),
                "label": str(item.get("label") or "").strip(),
                "duration_minutes": int(item.get("duration_minutes") or 30),
                "description": str(item.get("description") or "").strip(),
                "enabled": _is_truthy(item.get("enabled", True)),
                "allowed_for_new_patients": _is_truthy(item.get("allowed_for_new_patients", True)),
            }
        )
    return [item for item in out if item["label"]]


@router.get("/appointment-reasons")
def tenant_get_appointment_reasons(auth: dict = Depends(require_tenant_auth)):
    tenant_id = auth["tenant_id"]
    detail = _get_tenant_me_detail(tenant_id)
    if not detail:
        raise HTTPException(404, "Tenant not found")
    items = pg_list_appointment_reasons(tenant_id) or _get_appointment_reasons_from_params(detail.get("params") or {})
    return {"items": items}


@router.post("/appointment-reasons")
def tenant_create_appointment_reason(body: AppointmentReasonBody, auth: dict = Depends(require_tenant_auth)):
    tenant_id = auth["tenant_id"]
    detail = _get_tenant_me_detail(tenant_id)
    if not detail:
        raise HTTPException(404, "Tenant not found")
    created = {
        "id": uuid4().hex,
        "label": body.label.strip(),
        "duration_minutes": int(body.duration_minutes or 30),
        "description": body.description.strip(),
        "enabled": bool(body.enabled),
        "allowed_for_new_patients": True if body.allowed_for_new_patients is None else bool(body.allowed_for_new_patients),
    }
    pg_created = pg_create_appointment_reason(tenant_id, created)
    if pg_created:
        created = pg_created
    items = _get_appointment_reasons_from_params(detail.get("params") or {})
    items.append(created)
    if not pg_update_tenant_params(tenant_id, {"appointment_reasons_json": items}):
        raise HTTPException(500, "Failed to update appointment reasons")
    return created


@router.patch("/appointment-reasons/{reason_id}")
def tenant_patch_appointment_reason(reason_id: str, body: Dict[str, Any], auth: dict = Depends(require_tenant_auth)):
    tenant_id = auth["tenant_id"]
    detail = _get_tenant_me_detail(tenant_id)
    if not detail:
        raise HTTPException(404, "Tenant not found")
    pg_updated = pg_update_appointment_reason(tenant_id, reason_id, body)
    items = _get_appointment_reasons_from_params(detail.get("params") or {})
    updated = None
    for item in items:
        if item["id"] != reason_id:
            continue
        for key in ("label", "description"):
            if key in body and body[key] is not None:
                item[key] = str(body[key]).strip()
        for key in ("enabled", "allowed_for_new_patients"):
            if key in body and body[key] is not None:
                item[key] = bool(body[key])
        if "duration_minutes" in body and body["duration_minutes"] is not None:
            item["duration_minutes"] = int(body["duration_minutes"])
        updated = item
        break
    if not updated and pg_updated:
        updated = pg_updated
    if not updated:
        raise HTTPException(404, "Reason not found")
    if not pg_update_tenant_params(tenant_id, {"appointment_reasons_json": items}):
        raise HTTPException(500, "Failed to update appointment reasons")
    return updated


@router.delete("/appointment-reasons/{reason_id}")
def tenant_delete_appointment_reason(reason_id: str, auth: dict = Depends(require_tenant_auth)):
    tenant_id = auth["tenant_id"]
    detail = _get_tenant_me_detail(tenant_id)
    if not detail:
        raise HTTPException(404, "Tenant not found")
    pg_disable_appointment_reason(tenant_id, reason_id)
    items = _get_appointment_reasons_from_params(detail.get("params") or {})
    found = False
    for item in items:
        if item["id"] == reason_id:
            item["enabled"] = False
            found = True
            break
    if not found:
        raise HTTPException(404, "Reason not found")
    if not pg_update_tenant_params(tenant_id, {"appointment_reasons_json": items}):
        raise HTTPException(500, "Failed to update appointment reasons")
    return {"ok": True}


@router.get("/assistant-settings")
def tenant_get_assistant_settings(auth: dict = Depends(require_tenant_auth)):
    tenant_id = auth["tenant_id"]
    detail = _get_tenant_me_detail(tenant_id)
    if not detail:
        raise HTTPException(404, "Tenant not found")
    params = detail.get("params") or {}
    pg_settings = pg_get_assistant_settings(tenant_id) or {}
    return {
        "assistant_name": pg_settings.get("assistant_name") or params.get("assistant_name") or "Clara",
        "welcome_message": pg_settings.get("welcome_message") or params.get("welcome_message") or "",
        "documents_to_bring": pg_settings.get("documents_to_bring") or params.get("documents_to_bring") or "",
        "access_instructions": pg_settings.get("access_instructions") or params.get("access_instructions") or "",
        "payment_methods": pg_settings.get("payment_methods") or params.get("payment_methods") or "",
        "parking_info": pg_settings.get("parking_info") or params.get("parking_info") or "",
        "pmr_access": pg_settings.get("pmr_access") or params.get("pmr_access") or "",
        "sensitive_medical_instruction": pg_settings.get("sensitive_medical_instruction") or params.get("sensitive_medical_instruction") or "Clara ne donne jamais d'avis médical.",
        "escalation_instruction": pg_settings.get("escalation_instruction") or params.get("escalation_instruction") or "",
        "human_handoff_instruction": pg_settings.get("human_handoff_instruction") or params.get("human_handoff_instruction") or "",
        "faq_items": _normalize_faq_items(pg_settings.get("faq_items") if pg_settings else params.get("faq_items_json")),
    }


@router.patch("/assistant-settings")
def tenant_patch_assistant_settings(body: AssistantSettingsBody, auth: dict = Depends(require_tenant_auth)):
    tenant_id = auth["tenant_id"]
    payload = body.model_dump(exclude_none=True)
    if "faq_items" in payload:
        faq_items = _normalize_faq_items(payload.get("faq_items"))
        payload["faq_items_json"] = faq_items
        payload.pop("faq_items", None)
    pg_payload = dict(payload)
    if "faq_items_json" in pg_payload:
        pg_payload["faq_items"] = pg_payload.pop("faq_items_json")
    pg_upsert_assistant_settings(tenant_id, pg_payload)
    if payload and not pg_update_tenant_params(tenant_id, payload):
        raise HTTPException(500, "Failed to update assistant settings")
    return {"ok": True}


@router.post("/assistant-preview")
def tenant_assistant_preview(body: PreviewMessageBody, auth: dict = Depends(require_tenant_auth)):
    tenant_id = auth["tenant_id"]
    detail = _get_tenant_me_detail(tenant_id)
    if not detail:
        raise HTTPException(404, "Tenant not found")
    params = detail.get("params") or {}
    text = (body.message or "").strip().lower()
    used_sources = ["assistant_settings"]
    if any(token in text for token in ["douleur", "thoracique", "urgence", "essoufflement", "malaise"]):
        answer = params.get("sensitive_medical_instruction") or "En cas de symptomes inquietants, veuillez appeler le 15 ou le 112 immediatement."
        used_sources.append("sensitive_medical_instruction")
    elif "samedi" in text:
        opening = _normalize_opening_hours_payload(_parse_dict_value(params.get("opening_hours_json")).get("opening_hours")) or _build_default_opening_hours(params)
        sat = next((row for row in opening if row.get("day") == "saturday"), {"is_open": False})
        answer = "Le cabinet est ouvert le samedi." if sat.get("is_open") else "Le cabinet est ferme le samedi."
        used_sources.append("opening_hours")
    elif "document" in text:
        answer = params.get("documents_to_bring") or "Pensez a apporter votre carte Vitale, ordonnance et vos derniers examens."
        used_sources.append("documents_to_bring")
    else:
        answer = params.get("welcome_message") or "Bonjour, vous etes bien au cabinet. Je suis Clara, comment puis-je vous aider ?"
    return {"answer": answer, "used_sources": used_sources}


@router.post("/test-booking-rule")
def tenant_test_booking_rule(body: PreviewMessageBody, auth: dict = Depends(require_tenant_auth)):
    tenant_id = auth["tenant_id"]
    detail = _get_tenant_me_detail(tenant_id)
    if not detail:
        raise HTTPException(404, "Tenant not found")
    params = detail.get("params") or {}
    reasons = _get_appointment_reasons_from_params(params)
    msg = (body.message or "").strip().lower()
    detected = next((reason for reason in reasons if reason.get("enabled") and reason.get("label", "").lower() in msg), None)
    duration = int((detected or {}).get("duration_minutes") or params.get("default_appointment_duration_minutes") or params.get("booking_duration_minutes") or 30)
    allowed = bool(detected) or bool(reasons) is False
    return {
        "allowed": allowed,
        "detected_reason": (detected or {}).get("label"),
        "duration_minutes": duration,
        "simulated_answer": "Bien sur, je peux vous proposer un rendez-vous selon les disponibilites du cabinet." if allowed else "Je ne peux pas confirmer ce type de demande avec les regles actuelles.",
    }


@router.get("/calendar/status")
def tenant_calendar_status(auth: dict = Depends(require_tenant_auth)):
    tenant_id = auth["tenant_id"]
    tech = _get_technical_status(tenant_id) or {}
    connected = (tech.get("calendar_status") or "") == "connected"
    return {
        "connected": connected,
        "email": tech.get("calendar_id"),
        "last_sync_at": tech.get("last_event_at"),
        "permission_status": "ok" if connected else "missing",
    }


@router.get("/billing/summary")
def tenant_billing_summary(auth: dict = Depends(require_tenant_owner)):
    tenant_id = auth["tenant_id"]
    billing = get_tenant_billing(tenant_id) or {}
    plan_key = (billing.get("plan_key") or "growth").strip().lower()
    included = int(get_plan_included_minutes(plan_key) or 0)
    overage_rate = float(get_plan_overage_rate(plan_key) or 0)
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.month < 12:
        month_end = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        month_end = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    used_minutes = int(round(_get_quota_used_minutes(tenant_id, month_start.strftime("%Y-%m-%d %H:%M:%S"), month_end.strftime("%Y-%m-%d %H:%M:%S")), 0))
    usage_pct = int(round((used_minutes / included) * 100)) if included > 0 else 0
    overage_minutes = max(0, used_minutes - included) if included > 0 else 0
    overage_cost = round(overage_minutes * overage_rate, 2)
    monthly_prices = {"starter": 99, "growth": 149, "pro": 199}
    plans = get_billing_plans()
    return {
        "current_plan": plan_key,
        "monthly_price": monthly_prices.get(plan_key, 0),
        "included_minutes": included,
        "used_minutes_current_month": used_minutes,
        "usage_percentage": usage_pct,
        "estimated_overage_minutes": overage_minutes,
        "estimated_overage_cost": overage_cost,
        "billing_status": billing.get("billing_status") or "unknown",
        "payment_method_brand": billing.get("payment_method_brand") or "",
        "payment_method_last4": billing.get("payment_method_last4") or "",
        "next_invoice_date": (billing.get("current_period_end") or "")[:10] if billing.get("current_period_end") else "",
        "plans": plans,
    }


@router.get("/billing/invoices")
def tenant_billing_invoices(
    auth: dict = Depends(require_tenant_owner),
    limit: int = Query(10, ge=1, le=50),
):
    tenant_id = auth["tenant_id"]
    billing = get_tenant_billing(tenant_id) or {}
    customer_id = (billing.get("stripe_customer_id") or "").strip()
    if not customer_id:
        return {"items": []}
    stripe_key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if not stripe_key:
        return {"items": []}
    try:
        import stripe

        stripe.api_key = stripe_key
        invoices = stripe.Invoice.list(customer=customer_id, limit=limit)
        items = []
        for inv in (invoices.get("data") or []):
            items.append(
                {
                    "id": inv.get("id"),
                    "number": inv.get("number"),
                    "status": inv.get("status"),
                    "amount_due": (inv.get("amount_due") or 0) / 100,
                    "currency": inv.get("currency", "eur").upper(),
                    "created": inv.get("created"),
                    "invoice_pdf": (inv.get("invoice_pdf") or "").strip() or None,
                }
            )
        return {"items": items}
    except Exception as e:
        logger.warning("tenant billing invoices failed tenant_id=%s error=%s", tenant_id, e)
        return {"items": []}


@router.post("/billing/portal-session")
def tenant_billing_portal_session(auth: dict = Depends(require_tenant_owner)):
    tenant_id = auth["tenant_id"]
    billing = get_tenant_billing(tenant_id) or {}
    customer_id = (billing.get("stripe_customer_id") or "").strip()
    if not customer_id:
        raise HTTPException(400, "No Stripe customer for this tenant")
    stripe_key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if not stripe_key:
        raise HTTPException(503, "Stripe not configured")
    return_url = (
        os.environ.get("STRIPE_PORTAL_RETURN_URL")
        or os.environ.get("STRIPE_CHECKOUT_SUCCESS_URL")
        or os.environ.get("FRONTEND_URL")
        or "https://www.uwiapp.com"
    ).strip().rstrip("/")
    try:
        import stripe

        stripe.api_key = stripe_key
        session = stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)
        url = (session.get("url") or "").strip()
        if not url:
            raise HTTPException(500, "Stripe portal did not return URL")
        return {"url": url}
    except Exception as e:
        logger.warning("tenant billing portal failed tenant_id=%s error=%s", tenant_id, e)
        raise HTTPException(502, "Stripe error")


@router.post("/billing/change-plan")
def tenant_billing_change_plan(body: BillingChangePlanBody, auth: dict = Depends(require_tenant_owner)):
    tenant_id = auth["tenant_id"]
    plan_key = (body.plan_key or "").strip().lower()
    if plan_key not in {"starter", "growth", "pro"}:
        raise HTTPException(400, "Invalid plan_key")
    billing = get_tenant_billing(tenant_id) or {}
    sub_id = (billing.get("stripe_subscription_id") or "").strip()
    if not sub_id:
        raise HTTPException(400, "No Stripe subscription for this tenant")
    stripe_key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if not stripe_key:
        raise HTTPException(503, "Stripe not configured")
    base_price_id, metered_price_id = _get_stripe_price_ids_for_plan(plan_key)
    if not base_price_id or not metered_price_id:
        raise HTTPException(400, "Stripe prices not configured for this plan")
    try:
        import stripe

        stripe.api_key = stripe_key
        sub = stripe.Subscription.retrieve(sub_id, expand=["items.data.price"])
        items = sub.get("items", {}).get("data", []) or []
        base_item_id = None
        metered_item_id = (billing.get("stripe_metered_item_id") or "").strip()
        for item in items:
            price = item.get("price") or {}
            recurring = price.get("recurring") or {}
            if recurring.get("usage_type") == "metered":
                metered_item_id = (item.get("id") or "").strip() or metered_item_id
            else:
                base_item_id = (item.get("id") or "").strip()
        if not base_item_id or not metered_item_id:
            raise HTTPException(400, "Could not resolve subscription items")
        stripe.Subscription.modify(
            sub_id,
            items=[
                {"id": base_item_id, "price": base_price_id},
                {"id": metered_item_id, "price": metered_price_id},
            ],
            metadata={"tenant_id": str(tenant_id), "plan_key": plan_key},
        )
        upsert_billing_from_subscription(
            tenant_id,
            stripe_subscription_id=sub_id,
            billing_status="active",
            plan_key=plan_key,
            stripe_customer_id=billing.get("stripe_customer_id"),
        )
        return {"ok": True, "plan_key": plan_key}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("tenant billing change-plan failed tenant_id=%s error=%s", tenant_id, e)
        raise HTTPException(502, "Stripe error")


@router.get("/vapi/status")
def tenant_vapi_status(auth: dict = Depends(require_tenant_auth)):
    """Retourne l'état de connexion de l'assistant VAPI pour le tenant."""
    tenant_id = auth["tenant_id"]
    detail = _get_tenant_me_detail(tenant_id)
    if not detail:
        raise HTTPException(404, "Tenant not found")
    params = detail.get("params") or {}
    vapi_assistant_id = (params.get("vapi_assistant_id") or "").strip()
    assistant_name = ((params.get("assistant_name") or "Sophie").strip() or "Sophie").title()
    voice_number = (detail.get("voice_number") or "").strip()
    return {
        "tenant_id": tenant_id,
        "connected": bool(vapi_assistant_id),
        "assistant_live": bool(vapi_assistant_id),
        "vapi_assistant_id": vapi_assistant_id,
        "assistant_name": assistant_name,
        "voice_number": voice_number,
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
    return _safe_dashboard_snapshot(tenant_id, _tenant_display_name(d, tenant_id))


@router.get("/kpis")
def tenant_kpis(auth: dict = Depends(require_tenant_auth), days: int = Query(7, ge=1, le=30)):
    """KPIs par jour + trend vs semaine précédente (graphique 7j)."""
    tenant_id = auth["tenant_id"]
    data = _get_kpis_daily(tenant_id, days=days)
    current = data.get("current") or {}
    calls = int(current.get("calls") or 0)
    transfers = int(current.get("transfers") or 0)
    answered = max(0, calls - transfers)
    data["pickup_rate"] = round((answered / calls) * 100) if calls else 100
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_end = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0) if now.month < 12 else now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    data["minutes_month"] = int(round(_get_quota_used_minutes(tenant_id, month_start.strftime("%Y-%m-%d %H:%M:%S"), month_end.strftime("%Y-%m-%d %H:%M:%S")), 0))
    return data


@router.get("/rgpd")
def tenant_rgpd(auth: dict = Depends(require_tenant_owner)):
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


@router.get("/calls")
def tenant_calls(
    auth: dict = Depends(require_tenant_auth),
    limit: int = Query(10, ge=1, le=50),
    days: int = Query(7, ge=1, le=30),
    compact: bool = Query(False),
):
    """Retourne les derniers appels formatés pour le dashboard client."""
    tenant_id = auth["tenant_id"]
    detail = _get_tenant_detail(tenant_id)
    if not detail:
        raise HTTPException(404, "Tenant not found")
    tz_name = _tenant_timezone(detail)
    assistant_name = (((detail.get("params") or {}).get("assistant_name")) or "Sophie").strip().title()
    raw = _get_calls_list(tenant_id=tenant_id, days=days, limit=limit, tenant_detail=detail)
    items = raw.get("items") or []
    logger.info("[tenant_calls] tenant_id=%s days=%s limit=%s compact=%s raw_items=%d", tenant_id, days, limit, compact, len(items))
    if not items and not (os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")):
        ensure_tenant_config()
        conn = get_conn()
        try:
            rows = conn.execute(
                """
                SELECT call_id, MIN(created_at) AS started_at, MAX(created_at) AS last_event_at
                FROM ivr_events
                WHERE client_id = ? AND call_id IS NOT NULL AND TRIM(call_id) != ''
                  AND created_at >= datetime('now', ?)
                GROUP BY call_id
                ORDER BY last_event_at DESC
                LIMIT ?
                """,
                (tenant_id, f"-{int(days)} day", limit),
            ).fetchall()
            items = [
                {
                    "call_id": row[0],
                    "started_at": row[1],
                    "last_event_at": row[2],
                    "result": "other",
                    "duration_min": None,
                }
                for row in rows
            ]
        finally:
            conn.close()
    items = items[:limit]
    compact_mode = bool(compact)
    if compact_mode:
        calls = []
        for item in items:
            call_id = (item.get("call_id") or "").strip()
            if not call_id:
                continue
            started_at = item.get("started_at") or item.get("last_event_at")
            detail_for_display = {
                "call_id": call_id,
                "tenant_id": tenant_id,
                "customer_number": item.get("customer_number"),
                "started_at": item.get("started_at"),
                "last_event_at": item.get("last_event_at"),
                "duration_sec": item.get("duration_sec"),
                "duration_min": item.get("duration_min"),
                "result": item.get("result") or "other",
                "events": [{"event": item.get("last_event"), "meta": {}}] if item.get("last_event") else [],
                "transcript": None,
            }
            status = _resolve_call_status(item, detail_for_display)
            booking = _build_booking_payload(detail_for_display)
            call_context = _classify_call_context(status, detail_for_display)
            resolved_duration_sec = detail_for_display.get("duration_sec")
            if resolved_duration_sec is None:
                raw_minutes = detail_for_display.get("duration_min")
                try:
                    if raw_minutes is not None:
                        resolved_duration_sec = int(raw_minutes) * 60
                except Exception:
                    resolved_duration_sec = None
            if resolved_duration_sec is None:
                try:
                    start_dt = _parse_dt(detail_for_display.get("started_at") or item.get("started_at"), tz_name)
                    end_dt = _parse_dt(detail_for_display.get("last_event_at") or item.get("last_event_at"), tz_name)
                    if start_dt and end_dt:
                        resolved_duration_sec = max(0, int((end_dt - start_dt).total_seconds()))
                except Exception:
                    resolved_duration_sec = None
            calls.append({
                "id": call_id,
                "started_at": detail_for_display.get("started_at") or item.get("started_at"),
                "last_event_at": detail_for_display.get("last_event_at") or item.get("last_event_at"),
                "time": _format_hhmm(started_at, tz_name),
                "duration": _format_duration_short(resolved_duration_sec),
                "duration_sec": resolved_duration_sec,
                "patient_name": "Patient",
                "customer_number": _call_display_phone(item, detail_for_display),
                "agent_name": assistant_name,
                "summary": _call_summary_from_detail(status, detail_for_display),
                "status": status,
                "call_id": call_id,
                "patient": {
                    "raw_name": "",
                    "validated_name": "",
                    "display_name": "Patient",
                    "validation_status": "pending",
                    "profile_exists": False,
                    "is_validated": False,
                    "phone": item.get("customer_number") or "",
                },
                "booking": booking,
                "followup_state": "new",
                "followup_notes": "",
                "reason_label": call_context.get("reason_label") or "",
                "reason_context": call_context.get("reason_context") or "",
                "reason_category": call_context.get("reason_category") or "general",
                "contextual_action": call_context.get("contextual_action") or {"kind": "open_detail", "label": "Voir le détail"},
            })
        return {
            "calls": calls,
            "total": len(calls),
            "date": datetime.now(_get_zoneinfo(tz_name)).strftime("%Y-%m-%d"),
            "_debug_tenant_id": tenant_id,
        }
    call_ids_for_followup = [(item.get("call_id") or "").strip() for item in items]
    phones_for_patients = [item.get("customer_number") or "" for item in items]
    followups_by_call: dict = {}
    patient_profiles_by_phone: dict = {}
    _pg_url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    if _pg_url:
        try:
            from backend.pg_pool import pg_connection
            _cids = list(dict.fromkeys(c for c in call_ids_for_followup if c))
            _phones = list(dict.fromkeys(normalize_phone_number(p) for p in phones_for_patients if p))
            _phones = [p for p in _phones if p]
            with pg_connection() as _conn:
                with _conn.cursor() as _cur:
                    if _cids:
                        try:
                            _cur.execute(
                                "SELECT call_id, followup_state, notes, updated_at FROM call_followups WHERE tenant_id = %s AND call_id = ANY(%s)",
                                (tenant_id, _cids),
                            )
                            for _r in _cur.fetchall():
                                _k = str(_r.get("call_id") or "").strip()
                                if _k:
                                    followups_by_call[_k] = {
                                        "followup_state": _r.get("followup_state") or "new",
                                        "notes": _r.get("notes") or "",
                                        "updated_at": str(_r.get("updated_at") or ""),
                                    }
                        except Exception:
                            pass
                    if _phones:
                        try:
                            _cur.execute(
                                """SELECT phone, raw_name, validated_name, display_name, validation_status,
                                          source_call_id, last_call_id, last_booking_start, last_booking_end,
                                          last_booking_motif, created_at, updated_at
                                   FROM cabinet_clients WHERE tenant_id = %s AND phone = ANY(%s)""",
                                (tenant_id, _phones),
                            )
                            for _r in _cur.fetchall():
                                _ph = str(_r.get("phone") or "").strip()
                                if _ph:
                                    patient_profiles_by_phone[_ph] = {
                                        "phone": _ph,
                                        "raw_name": _r.get("raw_name") or "",
                                        "validated_name": _r.get("validated_name") or "",
                                        "display_name": _r.get("display_name") or _r.get("validated_name") or _r.get("raw_name") or "",
                                        "validation_status": _r.get("validation_status") or "pending",
                                        "source_call_id": _r.get("source_call_id") or "",
                                        "last_call_id": _r.get("last_call_id") or "",
                                        "last_booking_start": str(_r.get("last_booking_start") or ""),
                                        "last_booking_end": str(_r.get("last_booking_end") or ""),
                                        "last_booking_motif": _r.get("last_booking_motif") or "",
                                        "created_at": str(_r.get("created_at") or ""),
                                        "updated_at": str(_r.get("updated_at") or ""),
                                    }
                        except Exception:
                            pass
        except Exception:
            followups_by_call = list_call_followups(tenant_id, call_ids_for_followup)
            patient_profiles_by_phone = get_cabinet_clients_by_phones(tenant_id, phones_for_patients)
    else:
        followups_by_call = list_call_followups(tenant_id, call_ids_for_followup)
        patient_profiles_by_phone = get_cabinet_clients_by_phones(tenant_id, phones_for_patients)
    calls = []
    for item in items:
        call_id = (item.get("call_id") or "").strip()
        if not call_id:
            continue
        started_at = item.get("started_at") or item.get("last_event_at")
        list_detail = {
            "call_id": call_id,
            "tenant_id": tenant_id,
            "customer_number": item.get("customer_number"),
            "started_at": item.get("started_at"),
            "last_event_at": item.get("last_event_at"),
            "duration_sec": item.get("duration_sec"),
            "duration_min": item.get("duration_min"),
            "result": item.get("result") or "other",
            "events": [{"event": item.get("last_event"), "meta": {}}] if item.get("last_event") else [],
            "transcript": None,
        }
        detail_for_display = list_detail
        followup = followups_by_call.get(call_id) or {}
        status = _resolve_call_status(item, detail_for_display)
        booking = _build_booking_payload(detail_for_display)
        # Fast path: use the list payload whenever it already carries enough signal.
        if (not compact_mode) and status == "FAQ" and booking is None and not (detail_for_display.get("transcript") or "").strip():
            try:
                raw_detail = _get_call_detail(tenant_id, call_id) or {}
            except Exception:
                raw_detail = {}
            if raw_detail:
                detail_for_display = {
                    **list_detail,
                    **raw_detail,
                    "customer_number": raw_detail.get("customer_number") or list_detail.get("customer_number"),
                    "started_at": raw_detail.get("started_at") or list_detail.get("started_at"),
                    "last_event_at": raw_detail.get("last_event_at") or list_detail.get("last_event_at"),
                    "duration_sec": raw_detail.get("duration_sec") if raw_detail.get("duration_sec") is not None else list_detail.get("duration_sec"),
                    "duration_min": raw_detail.get("duration_min") if raw_detail.get("duration_min") is not None else list_detail.get("duration_min"),
                    "result": raw_detail.get("result") or list_detail.get("result") or "other",
                    "events": raw_detail.get("events") or list_detail.get("events") or [],
                    "transcript": raw_detail.get("transcript") if raw_detail.get("transcript") is not None else list_detail.get("transcript"),
                }
                status = _resolve_call_status(item, detail_for_display)
                booking = _build_booking_payload(detail_for_display)
        call_context = _classify_call_context(status, detail_for_display)
        patient = _build_patient_payload(tenant_id, item, detail_for_display, patient_profiles_by_phone)
        resolved_duration_sec = detail_for_display.get("duration_sec")
        if resolved_duration_sec is None:
            resolved_duration_sec = item.get("duration_sec")
        if resolved_duration_sec is None:
            raw_minutes = detail_for_display.get("duration_min")
            if raw_minutes is None:
                raw_minutes = item.get("duration_min")
            try:
                if raw_minutes is not None:
                    resolved_duration_sec = int(raw_minutes) * 60
            except Exception:
                resolved_duration_sec = None
        if resolved_duration_sec is None:
            try:
                start_dt = _parse_dt(detail_for_display.get("started_at") or item.get("started_at"), tz_name)
                end_dt = _parse_dt(detail_for_display.get("last_event_at") or item.get("last_event_at"), tz_name)
                if start_dt and end_dt:
                    resolved_duration_sec = max(0, int((end_dt - start_dt).total_seconds()))
            except Exception:
                resolved_duration_sec = None
        calls.append({
            "id": call_id,
            "started_at": detail_for_display.get("started_at") or item.get("started_at"),
            "last_event_at": detail_for_display.get("last_event_at") or item.get("last_event_at"),
            "time": _format_hhmm(started_at, tz_name),
            "duration": _format_duration_short(resolved_duration_sec),
            "duration_sec": resolved_duration_sec,
            "patient_name": patient.get("display_name") or "Patient",
            "customer_number": _call_display_phone(item, detail_for_display),
            "agent_name": assistant_name,
            "summary": _call_summary_from_detail(status, detail_for_display),
            "status": status,
            "call_id": call_id,
            "patient": patient,
            "booking": booking,
            "followup_state": followup.get("followup_state") or "new",
            "followup_notes": followup.get("notes") or "",
            "reason_label": call_context.get("reason_label") or "",
            "reason_context": call_context.get("reason_context") or "",
            "reason_category": call_context.get("reason_category") or "general",
            "contextual_action": call_context.get("contextual_action") or {"kind": "open_detail", "label": "Voir le détail"},
        })
    return {
        "calls": calls,
        "total": len(calls),
        "date": datetime.now(_get_zoneinfo(tz_name)).strftime("%Y-%m-%d"),
        "_debug_tenant_id": tenant_id,
    }


@router.get("/calls/{call_id}")
def tenant_call_detail(
    call_id: str,
    auth: dict = Depends(require_tenant_auth),
):
    """Retourne le détail d'un appel pour le tenant connecté."""
    tenant_id = auth["tenant_id"]
    detail = _get_tenant_detail(tenant_id)
    if not detail:
        raise HTTPException(404, "Tenant not found")
    tz_name = _tenant_timezone(detail)
    assistant_name = (((detail.get("params") or {}).get("assistant_name")) or "Sophie").strip().title()
    raw = _get_call_detail(tenant_id, call_id)
    followup = get_call_followup(tenant_id, call_id) or {}
    status = _resolve_call_status(None, raw)
    call_context = _classify_call_context(status, raw)
    patient = _build_patient_payload(tenant_id, None, raw)
    booking = _build_booking_payload(raw)
    events = []
    for event in raw.get("events") or []:
        events.append(
            {
                "created_at": event.get("created_at"),
                "time": _format_hhmm(event.get("created_at"), tz_name),
                "event": event.get("event") or "",
                "reason": _humanize_reason(((event.get("meta") or {}).get("reason"))),
                "context": ((event.get("meta") or {}).get("context")),
            }
        )
    return {
        "call_id": raw.get("call_id") or call_id,
        "status": status,
        "assistant_name": assistant_name,
        "customer_number": _call_display_phone(None, raw),
        "patient_name": patient.get("display_name") or "Patient",
        "patient": patient,
        "booking": booking,
        "summary": _call_summary_from_detail(status, raw),
        "started_at": raw.get("started_at"),
        "started_time": _format_hhmm(raw.get("started_at"), tz_name),
        "last_event_at": raw.get("last_event_at"),
        "last_event_time": _format_hhmm(raw.get("last_event_at"), tz_name),
        "duration": _format_duration_short(raw.get("duration_sec")),
        "duration_sec": raw.get("duration_sec"),
        "duration_min": raw.get("duration_min"),
        "transcript": raw.get("transcript"),
        "events": events,
        "followup_state": followup.get("followup_state") or "new",
        "followup_notes": followup.get("notes") or "",
        "followup_updated_at": followup.get("updated_at") or "",
        "reason_label": call_context.get("reason_label") or "",
        "reason_context": call_context.get("reason_context") or "",
        "reason_category": call_context.get("reason_category") or "general",
        "contextual_action": call_context.get("contextual_action") or {"kind": "open_detail", "label": "Voir le détail"},
    }


@router.patch("/calls/{call_id}/followup")
def tenant_call_followup_update(
    call_id: str,
    body: TenantCallFollowupBody,
    auth: dict = Depends(require_tenant_auth),
):
    """Met à jour le suivi produit d'un appel côté tenant."""
    tenant_id = auth["tenant_id"]
    raw = _get_call_detail(tenant_id, call_id)
    if not raw:
        raise HTTPException(404, "Call not found")

    state = (body.followup_state or "").strip().lower()
    if state not in {"new", "callback", "processed"}:
        raise HTTPException(400, "Invalid followup_state")
    if not upsert_call_followup(tenant_id, call_id, state, body.notes or ""):
        raise HTTPException(500, "Unable to save followup")
    followup = get_call_followup(tenant_id, call_id) or {}
    return {
        "ok": True,
        "call_id": call_id,
        "followup_state": followup.get("followup_state") or "new",
        "followup_notes": followup.get("notes") or "",
        "followup_updated_at": followup.get("updated_at") or "",
    }


@router.patch("/calls/{call_id}/patient")
def tenant_call_patient_update(
    call_id: str,
    body: TenantCallPatientBody,
    auth: dict = Depends(require_tenant_auth),
):
    """Valide/corrige l'identité patient et l'enregistre sur sa fiche (dashboard client), liée au numéro de téléphone."""
    tenant_id = auth["tenant_id"]
    raw = _get_call_detail(tenant_id, call_id)
    if not raw:
        raise HTTPException(404, "Call not found")
    patient = _build_patient_payload(tenant_id, None, raw)
    phone_from_call = patient.get("phone") or ""
    phone_from_body = normalize_phone_number(body.patient_phone or "")
    phone = phone_from_call or phone_from_body
    if not phone:
        raise HTTPException(400, "Numéro du patient introuvable pour cet appel")

    validated_name = (body.validated_name or "").strip()
    if len(validated_name) < 2:
        raise HTTPException(400, "validated_name too short")

    booking = _build_booking_payload(raw) or {}
    profile = upsert_cabinet_client(
        tenant_id,
        phone,
        raw_name=(body.raw_name or patient.get("raw_name") or "").strip() or None,
        validated_name=validated_name,
        source_call_id=call_id,
        last_call_id=call_id,
        last_booking_start=booking.get("start_iso"),
        last_booking_end=booking.get("end_iso"),
        last_booking_motif=booking.get("motif"),
    )
    if not profile:
        raise HTTPException(500, "Impossible d'enregistrer la fiche client")

    profile_payload = _build_patient_payload(tenant_id, None, raw)
    if not profile_payload.get("phone"):
        vn_final = str(profile.get("validated_name") or validated_name or "").strip()
        profile_payload = {
            "phone": phone,
            "raw_name": profile.get("raw_name") or "",
            "validated_name": vn_final,
            "display_name": str(profile.get("display_name") or validated_name).strip(),
            "validation_status": profile.get("validation_status") or "validated",
            "profile_exists": True,
            "is_validated": len(vn_final) >= 2,
            "source_call_id": profile.get("source_call_id") or call_id,
            "updated_at": str(profile.get("updated_at") or ""),
        }

    logger.info("tenant patient validated tenant_id=%s call_id=%s phone=%s", tenant_id, call_id, phone)
    return {"ok": True, "call_id": call_id, "patient": profile_payload}


@router.get("/patients")
def tenant_list_patients(
    auth: dict = Depends(require_tenant_auth),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(None, max_length=160, description="Filtre recherche nom / téléphone / email"),
):
    """Liste les fiches patient du tenant (dashboard client)."""
    tenant_id = auth["tenant_id"]
    qs = (q or "").strip()
    if qs:
        cap = min(limit, 100)
        items = search_cabinet_clients_with_fallback(tenant_id, qs, limit=cap)
        return {"items": items, "total": len(items), "mode": "search"}
    items = list_cabinet_clients(tenant_id, limit=limit, offset=offset)
    return {"items": items, "total": len(items), "mode": "list"}


@router.get("/patients/{phone}")
def tenant_get_patient(
    phone: str,
    auth: dict = Depends(require_tenant_auth),
):
    """Fiche patient complète : profil, appels liés, handoffs liés."""
    tenant_id = auth["tenant_id"]
    profile = get_cabinet_client_by_phone(tenant_id, phone)
    if not profile:
        raise HTTPException(404, "Patient not found")

    phone_norm = normalize_phone_number(phone)

    related_calls = []
    detail = _get_tenant_detail(tenant_id)
    if detail:
        tz_name = _tenant_timezone(detail)
        assistant_name = (((detail.get("params") or {}).get("assistant_name")) or "Sophie").strip().title()
        raw = _get_calls_list(tenant_id=tenant_id, days=90, limit=50, tenant_detail=detail)
        items = raw.get("items") or []
        for item in items:
            item_phone = normalize_phone_number(item.get("customer_number") or "")
            if item_phone == phone_norm:
                call_id = (item.get("call_id") or "").strip()
                started_at = item.get("started_at") or item.get("last_event_at")
                status = _resolve_call_status(item.get("result"), item, None)
                duration_sec = item.get("duration_sec") or 0
                related_calls.append({
                    "call_id": call_id,
                    "status": status,
                    "time": _format_hhmm(started_at, tz_name) if started_at else "—",
                    "duration": _format_duration_short(duration_sec),
                    "summary": item.get("summary") or "",
                    "reason_category": item.get("reason_category") or "general",
                    "followup_state": item.get("followup_state") or "new",
                    "started_at": item.get("started_at") or "",
                })

    related_handoffs = []
    try:
        all_handoffs = list_handoffs(tenant_id, status=None, target=None, limit=50)
        for h in all_handoffs:
            h_phone = normalize_phone_number(h.get("patient_phone") or "")
            if h_phone == phone_norm:
                related_handoffs.append(h)
    except Exception:
        pass

    docs = list_patient_documents(tenant_id, phone)
    notes = list_patient_notes(tenant_id, phone, limit=200)
    return {
        "patient": profile,
        "calls": related_calls,
        "handoffs": related_handoffs,
        "notes": [
            {
                "id": n.get("id"),
                "text": n.get("note_text") or "",
                "author": n.get("author") or "Cabinet",
                "created_at": str(n.get("created_at", "")),
            }
            for n in notes
        ],
        "documents": [
            {"id": d.get("id"), "original_name": d.get("original_name"), "mime_type": d.get("mime_type"),
             "size_bytes": d.get("size_bytes"), "created_at": str(d.get("created_at", ""))}
            for d in docs
        ],
    }


class TenantPatientPracticeCreateBody(BaseModel):
    """Création ou complément d'une fiche patient sur le dashboard client (sans passer par un appel vocal)."""

    patient_phone: str = Field(..., max_length=40)
    validated_name: str = Field(..., min_length=2, max_length=160)
    raw_name: Optional[str] = Field(default=None, max_length=160)
    initial_note: Optional[str] = Field(default=None, max_length=4000)
    agenda_motif: Optional[str] = Field(default=None, max_length=240)


@router.post("/patients")
def tenant_register_patient_practice(
    body: TenantPatientPracticeCreateBody,
    auth: dict = Depends(require_tenant_auth),
):
    """Enregistre une fiche patient sur le dashboard client (nom validé), ex. depuis l'agenda."""
    tenant_id = auth["tenant_id"]
    phone = normalize_phone_number(body.patient_phone)
    if not phone:
        raise HTTPException(400, "Numéro de téléphone invalide")
    vn = body.validated_name.strip()
    if len(vn) < 2:
        raise HTTPException(400, "Nom valide trop court")
    motif = (body.agenda_motif or "").strip()[:240] or None
    rn = (body.raw_name or "").strip()[:160] or None

    prior = get_cabinet_client_by_phone(tenant_id, phone)
    had_row = prior is not None
    had_validated = had_row and bool(str(prior.get("validated_name") or "").strip())

    profile = upsert_cabinet_client(
        tenant_id,
        phone,
        raw_name=rn,
        validated_name=vn,
        last_booking_motif=motif,
    )
    if not profile:
        raise HTTPException(500, "Impossible d'enregistrer la fiche client")

    if had_validated:
        register_mode = "updated"
    elif had_row:
        register_mode = "completed"
    else:
        register_mode = "created"

    note = (body.initial_note or "").strip()
    if note:
        inserted = insert_patient_note(tenant_id, phone, note_text=note, author="Praticien")
        if not inserted:
            logger.warning(
                "tenant_register_patient note insert failed tenant_id=%s phone=%s",
                tenant_id,
                phone,
            )

    return {"ok": True, "patient": profile, "register_mode": register_mode}


class PatientUpdateBody(BaseModel):
    email: Optional[str] = Field(default=None, max_length=254)

    @validator("email")
    def _validate_email(cls, v):
        if v is None:
            return None
        v = v.strip()
        if v == "":
            return ""
        # Validation simple (rejet espaces et absence de @, sans dépendre de la couverture RFC complète).
        if " " in v or "@" not in v or "." not in v.split("@", 1)[1]:
            raise ValueError("Email invalide (format attendu: prenom@domaine.fr)")
        return v


class PatientNoteCreateBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    author: Optional[str] = Field(default="Praticien", max_length=120)


@router.patch("/patients/{phone}")
def tenant_update_patient(
    phone: str,
    body: PatientUpdateBody,
    auth: dict = Depends(require_tenant_auth),
):
    """Met à jour les champs modifiables d'un patient (email, etc.)."""
    tenant_id = auth["tenant_id"]
    phone_norm = normalize_phone_number(phone) or phone.strip()
    profile = get_cabinet_client_by_phone(tenant_id, phone)
    if not profile:
        logger.warning(
            "tenant_update_patient: fiche introuvable tenant=%s phone=%s",
            tenant_id,
            phone_norm,
        )
        raise HTTPException(404, "Fiche patient introuvable pour ce cabinet. Créez d'abord la fiche.")

    updated = update_patient_fields(tenant_id, phone, email=body.email)
    if not updated:
        logger.error(
            "tenant_update_patient: update_patient_fields a renvoyé None tenant=%s phone=%s email_len=%s",
            tenant_id,
            phone_norm,
            len(body.email or ""),
        )
        raise HTTPException(500, "Impossible de mettre à jour la fiche (erreur base de données).")
    logger.info(
        "tenant_update_patient ok tenant=%s phone=%s email_set=%s",
        tenant_id,
        phone_norm,
        bool((updated.get("email") or "").strip()),
    )
    return {"ok": True, "patient": updated}


@router.get("/patients/{phone}/notes")
def tenant_list_patient_notes(
    phone: str,
    auth: dict = Depends(require_tenant_auth),
    limit: int = Query(100, ge=1, le=300),
):
    tenant_id = auth["tenant_id"]
    profile = get_cabinet_client_by_phone(tenant_id, phone)
    if not profile:
        raise HTTPException(404, "Patient not found")
    notes = list_patient_notes(tenant_id, phone, limit=limit)
    return {
        "items": [
            {
                "id": n.get("id"),
                "text": n.get("note_text") or "",
                "author": n.get("author") or "Cabinet",
                "created_at": str(n.get("created_at", "")),
            }
            for n in notes
        ]
    }


@router.post("/patients/{phone}/notes")
def tenant_create_patient_note(
    phone: str,
    body: PatientNoteCreateBody,
    auth: dict = Depends(require_tenant_auth),
):
    tenant_id = auth["tenant_id"]
    profile = get_cabinet_client_by_phone(tenant_id, phone)
    if not profile:
        raise HTTPException(404, "Patient not found")
    created = insert_patient_note(
        tenant_id,
        phone,
        note_text=body.text,
        author=(body.author or "Praticien"),
    )
    if not created:
        raise HTTPException(500, "Impossible d'enregistrer la note")
    return {
        "ok": True,
        "item": {
            "id": created.get("id"),
            "text": created.get("note_text") or "",
            "author": created.get("author") or "Cabinet",
            "created_at": str(created.get("created_at", "")),
        },
    }


@router.delete("/patients/{phone}/notes/{note_id}")
def tenant_delete_patient_note(
    phone: str,
    note_id: int,
    auth: dict = Depends(require_tenant_auth),
):
    """Anti-IDOR : la suppression cible la note ET le patient indiqué dans l'URL."""
    tenant_id = auth["tenant_id"]
    profile = get_cabinet_client_by_phone(tenant_id, phone)
    if not profile:
        raise HTTPException(404, "Patient not found")
    if not delete_patient_note(tenant_id, note_id, patient_phone=phone):
        raise HTTPException(404, "Note not found")
    return {"ok": True}


UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "patient_docs")


@router.post("/patients/{phone}/documents")
async def tenant_upload_patient_document(
    phone: str,
    file: UploadFile = File(...),
    auth: dict = Depends(require_tenant_auth),
):
    """Upload un document sur la fiche patient."""
    tenant_id = auth["tenant_id"]
    profile = get_cabinet_client_by_phone(tenant_id, phone)
    if not profile:
        raise HTTPException(404, "Patient not found")

    if not file.filename:
        raise HTTPException(400, "Fichier invalide")

    MAX_SIZE = 10 * 1024 * 1024  # 10 MB
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(413, "Fichier trop volumineux (max 10 Mo)")

    phone_norm = normalize_phone_number(phone) or phone.strip()
    safe_dir = os.path.join(UPLOAD_DIR, str(tenant_id), phone_norm)
    os.makedirs(safe_dir, exist_ok=True)

    import uuid as _uuid
    ext = os.path.splitext(file.filename)[1][:10]
    stored_name = f"{_uuid.uuid4().hex}{ext}"
    filepath = os.path.join(safe_dir, stored_name)
    with open(filepath, "wb") as f:
        f.write(content)

    doc = insert_patient_document(
        tenant_id, phone,
        filename=stored_name,
        original_name=file.filename,
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
    )
    return {"ok": True, "document": {"id": doc.get("id"), "original_name": file.filename,
            "mime_type": file.content_type, "size_bytes": len(content), "created_at": str(doc.get("created_at", ""))}}


@router.get("/patients/{phone}/documents/{doc_id}/download")
def tenant_download_patient_document(
    phone: str,
    doc_id: int,
    auth: dict = Depends(require_tenant_auth),
):
    """Télécharge un document patient."""
    tenant_id = auth["tenant_id"]
    docs = list_patient_documents(tenant_id, phone)
    doc = next((d for d in docs if d.get("id") == doc_id), None)
    if not doc:
        raise HTTPException(404, "Document not found")

    phone_norm = normalize_phone_number(phone) or phone.strip()
    filepath = os.path.join(UPLOAD_DIR, str(tenant_id), phone_norm, doc["filename"])
    if not os.path.isfile(filepath):
        raise HTTPException(404, "File not found on disk")

    return FileResponse(filepath, filename=doc["original_name"], media_type=doc.get("mime_type") or "application/octet-stream")


@router.delete("/patients/{phone}/documents/{doc_id}")
def tenant_delete_patient_document(
    phone: str,
    doc_id: int,
    auth: dict = Depends(require_tenant_auth),
):
    """Supprime un document patient."""
    tenant_id = auth["tenant_id"]
    docs = list_patient_documents(tenant_id, phone)
    doc = next((d for d in docs if d.get("id") == doc_id), None)
    if not doc:
        raise HTTPException(404, "Document not found")

    phone_norm = normalize_phone_number(phone) or phone.strip()
    filepath = os.path.join(UPLOAD_DIR, str(tenant_id), phone_norm, doc["filename"])
    if os.path.isfile(filepath):
        os.remove(filepath)

    # Anti-IDOR : la suppression DB cible aussi le patient_phone (pas seulement doc_id+tenant).
    delete_patient_document(tenant_id, doc_id, patient_phone=phone)
    return {"ok": True}


@router.post("/patients/{phone}/documents/{doc_id}/send")
def tenant_send_patient_document(
    phone: str,
    doc_id: int,
    auth: dict = Depends(require_tenant_auth),
):
    """Envoie un document au patient par email."""
    tenant_id = auth["tenant_id"]
    profile = get_cabinet_client_by_phone(tenant_id, phone)
    if not profile:
        raise HTTPException(404, "Patient not found")

    patient_email = (profile.get("email") or "").strip()
    if not patient_email:
        raise HTTPException(400, "Le patient n'a pas d'adresse email renseignée. Ajoutez-la d'abord sur sa fiche.")

    docs = list_patient_documents(tenant_id, phone)
    doc = next((d for d in docs if d.get("id") == doc_id), None)
    if not doc:
        raise HTTPException(404, "Document not found")

    phone_norm = normalize_phone_number(phone) or phone.strip()
    filepath = os.path.join(UPLOAD_DIR, str(tenant_id), phone_norm, doc["filename"])
    if not os.path.isfile(filepath):
        raise HTTPException(404, "Fichier introuvable sur le serveur")

    detail = _get_tenant_detail(tenant_id)
    cabinet_name = (detail or {}).get("name") or ""
    patient_name = profile.get("display_name") or profile.get("raw_name") or ""

    ok, err = send_patient_document_email(
        to=patient_email,
        patient_name=patient_name,
        cabinet_name=cabinet_name,
        doc_original_name=doc.get("original_name", "document"),
        doc_path=filepath,
        doc_mime_type=doc.get("mime_type", "application/octet-stream"),
    )
    if not ok:
        raise HTTPException(500, err or "Impossible d'envoyer l'email")

    return {"ok": True, "sent_to": patient_email}


@router.get("/handoffs")
def tenant_list_handoffs(
    auth: dict = Depends(require_tenant_auth),
    status: Optional[str] = Query(None),
    target: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=200),
):
    tenant_id = auth["tenant_id"]
    items = list_handoffs(tenant_id, status=status, target=target, limit=limit)
    return {"items": items, "total": len(items)}


@router.get("/handoffs/{handoff_id}")
def tenant_get_handoff(
    handoff_id: int,
    auth: dict = Depends(require_tenant_auth),
):
    tenant_id = auth["tenant_id"]
    item = get_handoff_by_id(tenant_id, handoff_id)
    if not item:
        raise HTTPException(404, "Handoff not found")
    return item


@router.patch("/handoffs/{handoff_id}")
def tenant_patch_handoff(
    handoff_id: int,
    body: TenantHandoffUpdateBody,
    auth: dict = Depends(require_tenant_auth),
):
    tenant_id = auth["tenant_id"]
    status = (body.status or "").strip().lower()
    if status and status not in {"processed", "cancelled"}:
        raise HTTPException(400, "Invalid handoff status")
    if not status and body.notes is None:
        raise HTTPException(400, "Nothing to update")
    item = update_handoff_status(tenant_id, handoff_id, status=status or None, notes=body.notes)
    if not item:
        raise HTTPException(404, "Handoff not found")
    return {"ok": True, "item": item}


def _build_agenda_day_payload(date_str: str, provider: str, external_connected: bool) -> Dict[str, Any]:
    return {
        "slots": [],
        "date": date_str,
        "total": 0,
        "done": 0,
        "remaining": 0,
        "provider": provider,
        "external_connected": external_connected,
    }


def _finalize_agenda_day_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    slots = list(payload.get("slots") or [])
    slots.sort(key=lambda item: item.get("hour") or "")
    done_count = sum(1 for item in slots if item.get("done"))
    payload["slots"] = slots
    payload["total"] = len(slots)
    payload["done"] = done_count
    payload["remaining"] = max(0, len(slots) - done_count)
    return payload


@router.get("/agenda")
def tenant_agenda(
    auth: dict = Depends(require_tenant_auth),
    date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    upcoming_days: int = Query(1, ge=1, le=366),
    compact: bool = Query(False),
):
    """Retourne les rendez-vous du jour ou à venir depuis Google Calendar ou le stockage local."""
    tenant_id = auth["tenant_id"]
    detail = _get_tenant_detail_for_agenda_cached(tenant_id)
    if not detail:
        raise HTTPException(404, "Tenant not found")
    params = detail.get("params") or {}
    tz_name = _tenant_timezone(detail)
    tz = _get_zoneinfo(tz_name)
    now_local = datetime.now(tz)
    if date:
        try:
            selected = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(400, "Invalid date format")
        day_start = selected.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=tz)
        day_end = day_start + timedelta(days=1)
    else:
        day_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=max(1, int(upcoming_days)))
    compact_mode = bool(compact and not date)
    slots: List[Dict[str, Any]] = []
    profile_cache: Dict[str, Optional[Dict[str, Any]]] = {}

    mirror_enabled = _google_mirror_enabled(detail)
    mirror_lookup: Optional[Dict[str, List[Dict[str, Any]]]] = None

    google_cal = (
        (params.get("calendar_provider") or "").strip() == "google"
        and bool((params.get("calendar_id") or "").strip())
    )
    if google_cal:
        try:
            cal_id = (params.get("calendar_id") or "").strip()
            executor: Optional[ThreadPoolExecutor] = None
            mirror_fut = None
            try:
                if mirror_enabled and not compact_mode:
                    executor = ThreadPoolExecutor(max_workers=1)
                    mirror_fut = executor.submit(
                        _load_local_appointments_for_window,
                        tenant_id,
                        day_start,
                        day_end,
                        tz_name,
                    )
                service = GoogleCalendarService(cal_id)
                result = _tenant_google_calendar_list_events_cached(
                    service,
                    calendar_id=cal_id,
                    time_min_iso=day_start.isoformat(),
                    time_max_iso=day_end.isoformat(),
                )
                if mirror_fut is not None:
                    try:
                        mirror_lookup = mirror_fut.result(timeout=120)
                    except Exception as mirror_exc:
                        logger.warning(
                            "tenant agenda mirror overlap failed tenant_id=%s: %s",
                            tenant_id,
                            mirror_exc,
                        )
                        mirror_lookup = _load_local_appointments_for_window(
                            tenant_id, day_start, day_end, tz_name
                        )
            finally:
                if executor is not None:
                    executor.shutdown(wait=True)
            google_events = result.get("items") or []
            _warm_profile_cache_google_event_descriptions(tenant_id, google_events, profile_cache)
            for event in google_events:
                raw_start = (event.get("start") or {}).get("dateTime") or (event.get("start") or {}).get("date")
                raw_end = (event.get("end") or {}).get("dateTime") or (event.get("end") or {}).get("date")
                start_dt = _parse_dt(raw_start, tz_name)
                end_dt = _parse_dt(raw_end, tz_name)
                if not start_dt:
                    continue
                start_local = start_dt.astimezone(tz)
                end_local = end_dt.astimezone(tz) if end_dt else start_local
                if not date and start_local < now_local:
                    continue
                summary = (event.get("summary") or "").strip()
                description = (event.get("description") or "").strip()
                patient = summary.replace("RDV - ", "", 1).strip() if summary.startswith("RDV - ") else (summary or "Patient")
                patient_contact = _extract_calendar_event_patient_contact(description)
                patient = _resolve_agenda_patient_name_cached(tenant_id, patient_contact, patient, profile_cache)
                motif = _extract_google_description_line(description, "Motif") or (summary if summary and not summary.startswith("RDV - ") else "Consultation")
                source = "UWI" if summary.startswith("RDV - ") or "Patient:" in description else "EXTERNAL"
                mirror_booking = None
                if mirror_enabled and not compact_mode and source == "UWI":
                    mirror_booking = _find_local_appointment_for_google_event(
                        tenant_id=tenant_id,
                        start_local=start_local,
                        patient_contact=patient_contact,
                        fallback_name=patient,
                        appointments_index=mirror_lookup,
                    )
                bo_origin = _agenda_resolve_booking_origin_google(description, mirror_booking)
                slots.append({
                    "date": start_local.strftime("%Y-%m-%d"),
                    "hour": start_local.strftime("%Hh"),
                    "start_iso": start_local.isoformat(),
                    "patient": patient,
                    "motif": motif,
                    "patient_phone": normalize_phone_number(patient_contact),
                    "type": motif,
                    "source": source,
                    "booking_origin": bo_origin,
                    "done": end_local <= now_local,
                    "current": start_local <= now_local < end_local,
                    "event_id": event.get("id") or "",
                    "appointment_id": int(mirror_booking.get("id") or 0) if mirror_booking else None,
                    "slot_id": int(mirror_booking.get("slot_id") or 0) if mirror_booking else None,
                    "can_cancel": bool(source == "UWI" and not compact_mode),
                    "can_reschedule": bool(mirror_booking) if not compact_mode else False,
                })
        except Exception as e:
            logger.warning("tenant agenda google failed tenant_id=%s: %s", tenant_id, e)
    else:
        url = os.environ.get("DATABASE_URL") or os.environ.get("PG_SLOTS_URL")
        if url:
            try:
                from backend.pg_pool import pg_connection
                from backend.pg_tenant_context import set_tenant_id_on_connection

                with pg_connection() as conn:
                    set_tenant_id_on_connection(conn, tenant_id)
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT a.id, a.slot_id, a.name, a.contact, a.motif, s.start_ts, a.booking_origin
                            FROM appointments a
                            JOIN slots s ON s.id = a.slot_id
                            WHERE a.tenant_id = %s
                              AND s.start_ts >= %s
                              AND s.start_ts < %s
                            ORDER BY s.start_ts ASC
                            """,
                            (tenant_id, day_start.astimezone(timezone.utc), day_end.astimezone(timezone.utc)),
                        )
                        agenda_rows_pg_day = cur.fetchall()
                        _warm_agenda_profiles_from_contact_strings(
                            tenant_id,
                            (r.get("contact") for r in agenda_rows_pg_day),
                            profile_cache,
                        )
                        for row in agenda_rows_pg_day:
                            start_local = _parse_dt(row.get("start_ts"), tz_name)
                            if not start_local:
                                continue
                            start_local = start_local.astimezone(tz)
                            if not date and start_local < now_local:
                                continue
                            end_local = start_local + timedelta(minutes=30)
                            patient_name = _resolve_agenda_patient_name_cached(
                                tenant_id,
                                row.get("contact"),
                                row.get("name"),
                                profile_cache,
                            )
                            slots.append({
                                "date": start_local.strftime("%Y-%m-%d"),
                                "hour": start_local.strftime("%Hh"),
                                "start_iso": start_local.isoformat(),
                                "patient": patient_name,
                                "patient_phone": normalize_phone_number(row.get("contact")),
                                "motif": row.get("motif") or "Consultation",
                                "type": row.get("motif") or "Consultation",
                                "source": "UWI",
                                "booking_origin": _agenda_booking_origin_from_local_row(row),
                                "done": end_local <= now_local,
                                "current": start_local <= now_local < end_local,
                                "event_id": str(row.get("id") or ""),
                                "appointment_id": int(row.get("id") or 0),
                                "slot_id": int(row.get("slot_id") or 0),
                                "can_cancel": True,
                                "can_reschedule": True,
                            })
            except Exception as e:
                logger.warning("tenant agenda pg failed tenant_id=%s: %s", tenant_id, e)
        else:
            ensure_tenant_config()
            conn = get_conn()
            try:
                _migrate_sqlite_add_booking_origin(conn)
                sqlite_agenda_day_rows = conn.execute(
                    """
                    SELECT a.id, a.slot_id, a.name, a.contact, a.motif, a.booking_origin, s.date, s.time
                    FROM appointments a
                    JOIN slots s ON s.id = a.slot_id
                    WHERE a.tenant_id = ? AND s.date = ?
                    ORDER BY s.time ASC
                    """,
                    (tenant_id, day_start.strftime("%Y-%m-%d")),
                ).fetchall()
                _warm_agenda_profiles_from_contact_strings(
                    tenant_id,
                    (row["contact"] for row in sqlite_agenda_day_rows),
                    profile_cache,
                )
                for row in sqlite_agenda_day_rows:
                    start_local = _parse_dt(f"{row['date']}T{row['time']}:00", tz_name)
                    if not start_local:
                        continue
                    if not date and start_local < now_local:
                        continue
                    end_local = start_local + timedelta(minutes=30)
                    patient_name = _resolve_agenda_patient_name_cached(tenant_id, row["contact"], row["name"], profile_cache)
                    slots.append({
                        "date": start_local.strftime("%Y-%m-%d"),
                        "hour": start_local.strftime("%Hh"),
                        "start_iso": start_local.isoformat(),
                        "patient": patient_name,
                        "patient_phone": normalize_phone_number(row["contact"]),
                        "motif": row["motif"] or "Consultation",
                        "type": row["motif"] or "Consultation",
                        "source": "UWI",
                        "booking_origin": _agenda_booking_origin_from_local_row(row),
                        "done": end_local <= now_local,
                        "current": start_local <= now_local < end_local,
                        "event_id": str(row["id"] or ""),
                        "appointment_id": int(row["id"] or 0),
                        "slot_id": int(row["slot_id"] or 0),
                        "can_cancel": True,
                        "can_reschedule": True,
                    })
            finally:
                conn.close()

    try:
        from backend.public_bookings_pg import fetch_public_bookings_for_agenda

        public_slots = fetch_public_bookings_for_agenda(
            tenant_id,
            day_start,
            day_end,
            tz_name,
            now_local,
            include_past_on_date=bool(date),
        )
        existing_ids = {str(item.get("event_id") or "") for item in slots}
        for item in public_slots:
            event_id = str(item.get("event_id") or "")
            if event_id and event_id in existing_ids:
                continue
            slots.append(item)
    except Exception as exc:
        logger.debug("tenant agenda public_bookings merge skipped tenant=%s: %s", tenant_id, exc)

    _warm_agenda_profiles_from_slots_patient_phone(tenant_id, slots, profile_cache)

    _decorate_agenda_slots_patient_has_file(tenant_id, slots, profile_cache)
    slots.sort(key=lambda item: item.get("hour") or "")
    done_count = sum(1 for item in slots if item.get("done"))
    return {
        "slots": slots,
        "date": day_start.strftime("%Y-%m-%d"),
        "total": len(slots),
        "done": done_count,
        "remaining": max(0, len(slots) - done_count),
        "provider": (params.get("calendar_provider") or "none").strip() or "none",
        "external_connected": bool(
            (params.get("calendar_provider") or "").strip() == "google"
            and (params.get("calendar_id") or "").strip()
            and not _looks_like_service_account_email(params.get("calendar_id"))
        ),
    }


@router.get("/agenda/bulk")
def tenant_agenda_bulk(
    auth: dict = Depends(require_tenant_auth),
    dates: str = Query(..., description="Liste CSV de dates YYYY-MM-DD"),
):
    """Retourne plusieurs jours d'agenda en une seule réponse pour limiter le fan-out frontend."""
    tenant_id = auth["tenant_id"]
    detail = _get_tenant_detail_for_agenda_cached(tenant_id)
    if not detail:
        raise HTTPException(404, "Tenant not found")

    requested_dates: List[str] = []
    for raw in str(dates or "").split(","):
        value = raw.strip()
        if not value or value in requested_dates:
            continue
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(400, f"Invalid date format: {value}")
        requested_dates.append(value)
    if not requested_dates:
        return {"dates": {}}

    requested_dates.sort()
    params = detail.get("params") or {}
    tz_name = _tenant_timezone(detail)
    tz = _get_zoneinfo(tz_name)
    now_local = datetime.now(tz)
    provider = (params.get("calendar_provider") or "none").strip() or "none"
    external_connected = bool(
        (params.get("calendar_provider") or "").strip() == "google"
        and (params.get("calendar_id") or "").strip()
        and not _looks_like_service_account_email(params.get("calendar_id"))
    )
    payloads = {
        date_str: _build_agenda_day_payload(date_str, provider, external_connected)
        for date_str in requested_dates
    }
    profile_cache: Dict[str, Optional[Dict[str, Any]]] = {}
    day_start = datetime.strptime(requested_dates[0], "%Y-%m-%d").replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=tz)
    day_end = (
        datetime.strptime(requested_dates[-1], "%Y-%m-%d").replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=tz)
        + timedelta(days=1)
    )

    mirror_enabled = _google_mirror_enabled(detail)
    mirror_lookup: Optional[Dict[str, List[Dict[str, Any]]]] = None

    google_cal_bulk = (
        (params.get("calendar_provider") or "").strip() == "google"
        and bool((params.get("calendar_id") or "").strip())
    )
    if google_cal_bulk:
        try:
            cal_id = (params.get("calendar_id") or "").strip()
            executor: Optional[ThreadPoolExecutor] = None
            mirror_fut = None
            try:
                if mirror_enabled:
                    executor = ThreadPoolExecutor(max_workers=1)
                    mirror_fut = executor.submit(
                        _load_local_appointments_for_window,
                        tenant_id,
                        day_start,
                        day_end,
                        tz_name,
                    )
                service = GoogleCalendarService(cal_id)
                result = _tenant_google_calendar_list_events_cached(
                    service,
                    calendar_id=cal_id,
                    time_min_iso=day_start.isoformat(),
                    time_max_iso=day_end.isoformat(),
                )
                if mirror_fut is not None:
                    try:
                        mirror_lookup = mirror_fut.result(timeout=120)
                    except Exception as mirror_exc:
                        logger.warning(
                            "tenant agenda bulk mirror overlap failed tenant_id=%s: %s",
                            tenant_id,
                            mirror_exc,
                        )
                        mirror_lookup = _load_local_appointments_for_window(
                            tenant_id, day_start, day_end, tz_name
                        )
            finally:
                if executor is not None:
                    executor.shutdown(wait=True)
            google_events = result.get("items") or []
            _warm_profile_cache_google_event_descriptions(tenant_id, google_events, profile_cache)
            for event in google_events:
                raw_start = (event.get("start") or {}).get("dateTime") or (event.get("start") or {}).get("date")
                raw_end = (event.get("end") or {}).get("dateTime") or (event.get("end") or {}).get("date")
                start_dt = _parse_dt(raw_start, tz_name)
                end_dt = _parse_dt(raw_end, tz_name)
                if not start_dt:
                    continue
                start_local = start_dt.astimezone(tz)
                end_local = end_dt.astimezone(tz) if end_dt else start_local
                date_key = start_local.strftime("%Y-%m-%d")
                if date_key not in payloads:
                    continue
                summary = (event.get("summary") or "").strip()
                description = (event.get("description") or "").strip()
                patient = summary.replace("RDV - ", "", 1).strip() if summary.startswith("RDV - ") else (summary or "Patient")
                patient_contact = _extract_calendar_event_patient_contact(description)
                patient = _resolve_agenda_patient_name_cached(tenant_id, patient_contact, patient, profile_cache)
                motif = _extract_google_description_line(description, "Motif") or (summary if summary and not summary.startswith("RDV - ") else "Consultation")
                source = "UWI" if summary.startswith("RDV - ") or "Patient:" in description else "EXTERNAL"
                mirror_booking = None
                if mirror_enabled and source == "UWI":
                    mirror_booking = _find_local_appointment_for_google_event(
                        tenant_id=tenant_id,
                        start_local=start_local,
                        patient_contact=patient_contact,
                        fallback_name=patient,
                        appointments_index=mirror_lookup,
                    )
                bo_origin = _agenda_resolve_booking_origin_google(description, mirror_booking)
                payloads[date_key]["slots"].append(
                    {
                        "date": start_local.strftime("%Y-%m-%d"),
                        "hour": start_local.strftime("%Hh"),
                        "start_iso": start_local.isoformat(),
                        "patient": patient,
                        "motif": motif,
                        "patient_phone": normalize_phone_number(patient_contact),
                        "type": motif,
                        "source": source,
                        "booking_origin": bo_origin,
                        "done": end_local <= now_local,
                        "current": start_local <= now_local < end_local,
                        "event_id": event.get("id") or "",
                        "appointment_id": int(mirror_booking.get("id") or 0) if mirror_booking else None,
                        "slot_id": int(mirror_booking.get("slot_id") or 0) if mirror_booking else None,
                        "can_cancel": bool(source == "UWI"),
                        "can_reschedule": bool(mirror_booking),
                    }
                )
        except Exception as e:
            logger.warning("tenant agenda bulk google failed tenant_id=%s: %s", tenant_id, e)
    else:
        url = os.environ.get("DATABASE_URL") or os.environ.get("PG_SLOTS_URL")
        if url:
            try:
                import psycopg
                from psycopg.rows import dict_row

                with psycopg.connect(url, row_factory=dict_row) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT a.id, a.slot_id, a.name, a.contact, a.motif, s.start_ts, a.booking_origin
                            FROM appointments a
                            JOIN slots s ON s.id = a.slot_id
                            WHERE a.tenant_id = %s
                              AND s.start_ts >= %s
                              AND s.start_ts < %s
                            ORDER BY s.start_ts ASC
                            """,
                            (tenant_id, day_start.astimezone(timezone.utc), day_end.astimezone(timezone.utc)),
                        )
                        agenda_rows_bulk_pg = cur.fetchall()
                        _warm_agenda_profiles_from_contact_strings(
                            tenant_id,
                            (row.get("contact") for row in agenda_rows_bulk_pg),
                            profile_cache,
                        )
                        for row in agenda_rows_bulk_pg:
                            start_local = _parse_dt(row.get("start_ts"), tz_name)
                            if not start_local:
                                continue
                            start_local = start_local.astimezone(tz)
                            date_key = start_local.strftime("%Y-%m-%d")
                            if date_key not in payloads:
                                continue
                            end_local = start_local + timedelta(minutes=30)
                            patient_name = _resolve_agenda_patient_name_cached(
                                tenant_id,
                                row.get("contact"),
                                row.get("name"),
                                profile_cache,
                            )
                            payloads[date_key]["slots"].append(
                                {
                                    "date": start_local.strftime("%Y-%m-%d"),
                                    "hour": start_local.strftime("%Hh"),
                                    "start_iso": start_local.isoformat(),
                                    "patient": patient_name,
                                    "patient_phone": normalize_phone_number(row.get("contact")),
                                    "motif": row.get("motif") or "Consultation",
                                    "type": row.get("motif") or "Consultation",
                                    "source": "UWI",
                                    "booking_origin": _agenda_booking_origin_from_local_row(row),
                                    "done": end_local <= now_local,
                                    "current": start_local <= now_local < end_local,
                                    "event_id": str(row.get("id") or ""),
                                    "appointment_id": int(row.get("id") or 0),
                                    "slot_id": int(row.get("slot_id") or 0),
                                    "can_cancel": True,
                                    "can_reschedule": True,
                                }
                            )
            except Exception as e:
                logger.warning("tenant agenda bulk pg failed tenant_id=%s: %s", tenant_id, e)
        else:
            ensure_tenant_config()
            conn = get_conn()
            try:
                _migrate_sqlite_add_booking_origin(conn)
                sqlite_agenda_bulk_rows = conn.execute(
                    """
                    SELECT a.id, a.slot_id, a.name, a.contact, a.motif, a.booking_origin, s.date, s.time
                    FROM appointments a
                    JOIN slots s ON s.id = a.slot_id AND s.tenant_id = a.tenant_id
                    WHERE a.tenant_id = ?
                      AND s.date >= ?
                      AND s.date <= ?
                    ORDER BY s.date ASC, s.time ASC
                    """,
                    (tenant_id, requested_dates[0], requested_dates[-1]),
                ).fetchall()
                _warm_agenda_profiles_from_contact_strings(
                    tenant_id,
                    (row["contact"] for row in sqlite_agenda_bulk_rows),
                    profile_cache,
                )
                for row in sqlite_agenda_bulk_rows:
                    start_local = _parse_dt(f"{row['date']}T{row['time']}:00", tz_name)
                    if not start_local:
                        continue
                    date_key = start_local.strftime("%Y-%m-%d")
                    if date_key not in payloads:
                        continue
                    end_local = start_local + timedelta(minutes=30)
                    patient_name = _resolve_agenda_patient_name_cached(tenant_id, row["contact"], row["name"], profile_cache)
                    payloads[date_key]["slots"].append(
                        {
                            "date": start_local.strftime("%Y-%m-%d"),
                            "hour": start_local.strftime("%Hh"),
                            "start_iso": start_local.isoformat(),
                            "patient": patient_name,
                            "patient_phone": normalize_phone_number(row["contact"]),
                            "motif": row["motif"] or "Consultation",
                            "type": row["motif"] or "Consultation",
                            "source": "UWI",
                            "booking_origin": _agenda_booking_origin_from_local_row(row),
                            "done": end_local <= now_local,
                            "current": start_local <= now_local < end_local,
                            "event_id": str(row["id"] or ""),
                            "appointment_id": int(row["id"] or 0),
                            "slot_id": int(row["slot_id"] or 0),
                            "can_cancel": True,
                            "can_reschedule": True,
                        }
                    )
            finally:
                conn.close()

    flat_slots_bulk = [slot for payload in payloads.values() for slot in (payload.get("slots") or [])]
    _warm_agenda_profiles_from_slots_patient_phone(tenant_id, flat_slots_bulk, profile_cache)

    for payload in payloads.values():
        _decorate_agenda_slots_patient_has_file(tenant_id, list(payload.get("slots") or []), profile_cache)

    return {"dates": {date_str: _finalize_agenda_day_payload(payload) for date_str, payload in payloads.items()}}


@router.get("/agenda/available-slots")
def tenant_agenda_available_slots(
    auth: dict = Depends(require_tenant_auth),
    limit: int = Query(8, ge=1, le=100),
    date: Optional[str] = Query(None),
    time: Optional[str] = Query(None),
):
    """Liste des créneaux libres pour déplacer un RDV local UWI."""
    tenant_id = auth["tenant_id"]
    detail = _get_tenant_detail(tenant_id)
    if not detail:
        raise HTTPException(404, "Tenant not found")
    params = detail.get("params") or {}
    if (params.get("calendar_provider") or "").strip() == "google" and not _google_mirror_enabled(detail):
        raise HTTPException(400, "Déplacement automatique indisponible avec Google Calendar")
    if date and time:
        slot_id = None
        if config.USE_PG_SLOTS:
            try:
                from backend.slots_pg import pg_find_slot_id_by_datetime

                slot_id = pg_find_slot_id_by_datetime(date, time, tenant_id=tenant_id)
            except Exception:
                slot_id = None
        if slot_id is None:
            slot_id = find_slot_id_by_datetime(date, time, tenant_id=tenant_id)
        if slot_id is None:
            return {"slots": [], "total": 0, "slot_id": None, "exact": True}
        return {
            "slots": [{"slot_id": int(slot_id), "date": date[:10], "time": (time or "")[:5], "label": f"{date[:10]} à {(time or '')[:5]}"}],
            "total": 1,
            "slot_id": int(slot_id),
            "exact": True,
        }
    if date and not time:
        from backend.db import get_conn as _get_conn
        conn = _get_conn()
        try:
            cur = conn.execute(
                "SELECT id, date, time FROM slots WHERE tenant_id = ? AND date = ? AND is_booked = 0 ORDER BY time ASC",
                (tenant_id, date[:10]),
            )
            items = [{"slot_id": int(r["id"]), "date": r["date"], "time": r["time"], "label": f"{r['date']} à {r['time']}"} for r in cur.fetchall()]
            return {"slots": items, "total": len(items)}
        finally:
            conn.close()
    raw_slots = list_free_slots(limit=limit, tenant_id=tenant_id) or []
    items = []
    for slot in raw_slots[:limit]:
        items.append(
            {
                "slot_id": int(slot.get("id") or 0),
                "date": slot.get("date") or "",
                "time": slot.get("time") or "",
                "label": f"{slot.get('date') or ''} à {slot.get('time') or ''}",
            }
        )
    return {"slots": items, "total": len(items)}


@router.get("/agenda/available-dates")
def tenant_agenda_available_dates(
    auth: dict = Depends(require_tenant_auth),
    month: str = Query(..., description="YYYY-MM"),
):
    """Retourne les dates du mois ayant au moins 1 créneau libre."""
    tenant_id = auth["tenant_id"]
    from backend.db import get_conn as _get_conn
    conn = _get_conn()
    try:
        cur = conn.execute(
            "SELECT date, COUNT(*) as cnt FROM slots WHERE tenant_id = ? AND date LIKE ? AND is_booked = 0 GROUP BY date ORDER BY date",
            (tenant_id, f"{month[:7]}%"),
        )
        dates = {r["date"]: int(r["cnt"]) for r in cur.fetchall()}
        return {"dates": dates, "month": month[:7]}
    finally:
        conn.close()


def _tenant_cabinet_booking_duration_minutes(tenant_id: int) -> int:
    try:
        from backend.cabinet_profile_pg import get_booking_rules

        rules = get_booking_rules(int(tenant_id)) or {}
        dm = int(rules.get("duration_minutes") or rules.get("default_appointment_duration_minutes") or 30)
        return max(5, min(dm, 180))
    except Exception:
        return 30


def _tenant_agenda_compute_end_iso(start_iso: str, tenant_id: int, end_iso_in: str) -> str:
    end = (end_iso_in or "").strip()
    if end:
        return end
    try:
        dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return (dt + timedelta(minutes=_tenant_cabinet_booking_duration_minutes(tenant_id))).isoformat()


@router.post("/agenda/bookings")
def tenant_agenda_create_booking(
    body: TenantAgendaCreateBookingBody,
    auth: dict = Depends(require_tenant_auth),
):
    """Crée un rendez-vous depuis le dashboard cabinet (Google Calendar ou créneaux UWI locaux)."""
    from backend.booking_origin import PRATICIEN as BO_PRAT

    tenant_id = auth["tenant_id"]
    detail = _get_tenant_detail(tenant_id)
    if not detail:
        raise HTTPException(404, "Tenant not found")

    pname = body.patient_name.strip()
    motif = body.motif.strip() or "Consultation"
    start_iso = body.start_iso.strip()
    params = detail.get("params") or {}
    phone_norm = normalize_phone_number(body.patient_phone) or ""
    email_part = (body.patient_email or "").strip()
    contact_bits = []
    if phone_norm:
        contact_bits.append(f"Tél. {phone_norm}")
    if email_part:
        contact_bits.append(f"Email {email_part}")
    contact_line = " · ".join(contact_bits) if contact_bits else "—"
    contact_for_qualif = phone_norm or email_part or contact_line
    qualif_contact_type = "phone" if phone_norm else ("email" if email_part else "phone")
    end_iso = _tenant_agenda_compute_end_iso(start_iso, tenant_id, body.end_iso)

    google_calendar = (
        (params.get("calendar_provider") or "").strip() == "google"
        and (params.get("calendar_id") or "").strip()
    )

    if google_calendar:
        cal_id = (params.get("calendar_id") or "").strip()
        if _looks_like_service_account_email(cal_id):
            raise HTTPException(
                400,
                "Utilisez l'identifiant du calendrier Google du cabinet (pas l'email du compte de service).",
            )
        if not end_iso:
            raise HTTPException(400, "Date ou heure de début invalide.")

        svc = GoogleCalendarService(cal_id)
        try:
            ev = svc.book_appointment(
                start_iso,
                end_iso,
                pname,
                contact_line,
                motif,
                booking_origin=BO_PRAT,
            )
        except GoogleCalendarPermissionError as e:
            logger.warning("tenant agenda create google permission tenant_id=%s err=%s", tenant_id, e)
            raise HTTPException(502, "Droits Google Calendar insuffisants pour créer le RDV.") from e
        if not ev:
            raise HTTPException(502, "Impossible de créer le RDV dans Google Calendar.")

        try:
            if _google_mirror_enabled(detail):
                from backend import tools_booking

                qs = SimpleNamespace(
                    tenant_id=tenant_id,
                    conv_id="cabinet-dashboard",
                    booking_origin=BO_PRAT,
                    qualif_data=SimpleNamespace(
                        name=pname,
                        contact=contact_for_qualif,
                        contact_type=qualif_contact_type,
                        motif=motif,
                        pref=None,
                    ),
                )
                threading.Thread(
                    target=tools_booking._mirror_google_booking_to_internal,
                    args=(qs, start_iso, ev),
                    daemon=True,
                ).start()
        except Exception as exc:
            logger.warning("mirror after tenant booking failed tenant_id=%s: %s", tenant_id, exc)

        _invalidate_tenant_agenda_detail_cache(tenant_id)
        return {"ok": True, "provider": "google", "event_id": ev}

    try:
        dt_parse = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        date_str = dt_parse.strftime("%Y-%m-%d")
        time_str = dt_parse.strftime("%H:%M")
    except ValueError:
        raise HTTPException(400, "Date ou heure de début invalide.") from None

    sid = ensure_slot_id_by_datetime(date_str, time_str, tenant_id=tenant_id)
    if sid is None:
        raise HTTPException(404, "Aucun créneau local disponible pour ce moment.")

    ok_atomic = book_slot_atomic(
        int(sid),
        pname,
        contact_line if contact_line != "—" else "",
        qualif_contact_type,
        motif,
        tenant_id=tenant_id,
        booking_origin=BO_PRAT,
    )
    if not ok_atomic:
        raise HTTPException(409, "Ce créneau est déjà pris.")

    _invalidate_tenant_agenda_detail_cache(tenant_id)
    return {"ok": True, "provider": "local", "slot_id": int(sid)}


@router.post("/agenda/appointments/{appointment_id}/cancel")
def tenant_agenda_cancel_appointment(
    appointment_id: str,
    body: TenantAgendaCancelBody,
    auth: dict = Depends(require_tenant_auth),
):
    """Annule un RDV UWI. Les événements externes restent non modifiables."""
    tenant_id = auth["tenant_id"]
    detail = _get_tenant_detail(tenant_id)
    if not detail:
        raise HTTPException(404, "Tenant not found")
    params = detail.get("params") or {}
    source = (body.source or "UWI").strip().upper()
    if source != "UWI":
        raise HTTPException(400, "Seuls les rendez-vous UWI sont modifiables depuis cet espace")

    if (params.get("calendar_provider") or "").strip() == "google":
        raw_appointment_id = (appointment_id or "").strip()
        google_event_id = (body.external_event_id or "").strip()
        local_booking = None
        local_appt_id = None

        if raw_appointment_id.isdigit():
            local_appt_id = int(raw_appointment_id)
            local_booking = _get_local_appointment_by_id(tenant_id, local_appt_id)
            if not local_booking:
                local_appt_id = None

        if not google_event_id and raw_appointment_id and not raw_appointment_id.isdigit():
            google_event_id = raw_appointment_id

        if not google_event_id and local_appt_id is None:
            raise HTTPException(400, "appointment_id ou event_id requis")

        google_cancelled = False
        local_cancelled = local_appt_id is None
        if google_event_id:
            try:
                service = GoogleCalendarService((params.get("calendar_id") or "").strip())
                ok = service.cancel_appointment(google_event_id)
            except Exception as e:
                logger.warning(
                    "tenant agenda cancel google failed tenant_id=%s event_id=%s err=%s",
                    tenant_id,
                    google_event_id,
                    e,
                )
                raise HTTPException(502, "Impossible d'annuler ce rendez-vous Google pour le moment")
            if not ok:
                raise HTTPException(400, "Annulation impossible")
            google_cancelled = True

        if local_appt_id is not None:
            local_cancelled = cancel_booking_sqlite(
                {"id": local_appt_id, "slot_id": local_booking.get("slot_id") if local_booking else None},
                tenant_id=tenant_id,
            )
            if not local_cancelled:
                logger.warning(
                    "tenant agenda cancel mirror failed tenant_id=%s appointment_id=%s event_id=%s",
                    tenant_id,
                    local_appt_id,
                    google_event_id,
                )

        logger.info(
            "tenant agenda cancel google ok tenant_id=%s appointment_id=%s event_id=%s local_cancelled=%s",
            tenant_id,
            local_appt_id,
            google_event_id,
            local_cancelled,
        )
        provider = "google+local" if google_cancelled and local_appt_id is not None else ("google" if google_cancelled else "local")
        return {
            "ok": True,
            "cancelled": True,
            "provider": provider,
            "google_cancelled": google_cancelled,
            "local_cancelled": local_cancelled,
        }

    try:
        appt_id = int(appointment_id)
    except Exception:
        raise HTTPException(400, "appointment_id invalide")
    booking = _get_local_appointment_by_id(tenant_id, appt_id)
    if not booking:
        raise HTTPException(404, "Rendez-vous introuvable")
    ok = cancel_booking_sqlite({"id": appt_id, "slot_id": booking.get("slot_id")}, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(400, "Annulation impossible")
    logger.info("tenant agenda cancel local ok tenant_id=%s appointment_id=%s", tenant_id, appt_id)
    return {"ok": True, "cancelled": True, "provider": "local"}


def _mark_pending_handoffs_processed(tenant_id: int, booking: dict) -> None:
    """Marque les handoffs en attente du patient comme traités après un reschedule."""
    patient_phone = normalize_phone_number(booking.get("contact") or "")
    if not patient_phone:
        return
    try:
        pending = list_handoffs(tenant_id, status="callback_created", limit=50)
        for h in (pending or []):
            hp = normalize_phone_number(h.get("patient_phone") or "")
            if hp == patient_phone:
                update_handoff_status(tenant_id, h["id"], status="processed", notes="RDV déplacé depuis le dashboard")
                logger.info("handoff %s marked processed after reschedule for %s", h["id"], patient_phone)
    except Exception as e:
        logger.warning("_mark_pending_handoffs_processed failed tenant_id=%s phone=%s: %s", tenant_id, patient_phone, e)


@router.post("/agenda/appointments/{appointment_id}/reschedule")
def tenant_agenda_reschedule_appointment(
    appointment_id: int,
    body: TenantAgendaRescheduleBody,
    auth: dict = Depends(require_tenant_auth),
):
    """Déplace un RDV UWI local vers un autre créneau libre (mode local uniquement)."""
    tenant_id = auth["tenant_id"]
    detail = _get_tenant_detail(tenant_id)
    if not detail:
        raise HTTPException(404, "Tenant not found")
    params = detail.get("params") or {}
    booking = _get_local_appointment_by_id(tenant_id, appointment_id)
    if not booking:
        raise HTTPException(404, "Rendez-vous introuvable")
    if (params.get("calendar_provider") or "").strip() == "google":
        if not _google_mirror_enabled(detail):
            raise HTTPException(400, "Déplacement automatique indisponible avec Google Calendar")
        event_id = (body.external_event_id or "").strip()
        if not event_id:
            raise HTTPException(400, "external_event_id requis pour déplacer ce rendez-vous")
        rules = get_booking_rules(tenant_id)
        duration_minutes = int(rules.get("duration_minutes") or 15)
        tz_name = _tenant_timezone(detail)
        old_window = _get_slot_window(tenant_id, int(booking.get("slot_id") or 0), tz_name, duration_minutes)
        new_window = _get_slot_window(tenant_id, int(body.new_slot_id), tz_name, duration_minutes)
        if not old_window or not new_window:
            raise HTTPException(400, "Créneau introuvable")

        old_start, old_end = old_window
        new_start, new_end = new_window
        service = GoogleCalendarService((params.get("calendar_id") or "").strip())
        try:
            moved = service.reschedule_appointment(event_id, new_start.isoformat(), new_end.isoformat())
        except Exception as e:
            logger.warning(
                "tenant agenda reschedule google failed tenant_id=%s appointment_id=%s event_id=%s err=%s",
                tenant_id,
                appointment_id,
                event_id,
                e,
            )
            raise HTTPException(502, "Impossible de déplacer ce rendez-vous Google pour le moment")
        if not moved:
            raise HTTPException(400, "Déplacement impossible")
        try:
            ok = reschedule_booking_atomic(appointment_id, int(body.new_slot_id), tenant_id=tenant_id)
        except Exception as e:
            logger.warning(
                "tenant agenda reschedule local mirror exception tenant_id=%s appointment_id=%s new_slot_id=%s err=%s",
                tenant_id,
                appointment_id,
                body.new_slot_id,
                e,
            )
            rollback_ok = service.reschedule_appointment(event_id, old_start.isoformat(), old_end.isoformat())
            if rollback_ok:
                raise HTTPException(409, "Le créneau sélectionné n'est plus disponible")
            raise HTTPException(502, "Le rendez-vous Google a été déplacé mais le miroir interne n'a pas pu être remis à jour")
        if ok is False:
            rollback_ok = service.reschedule_appointment(event_id, old_start.isoformat(), old_end.isoformat())
            logger.warning(
                "tenant agenda reschedule local mirror failed tenant_id=%s appointment_id=%s new_slot_id=%s rollback_ok=%s",
                tenant_id,
                appointment_id,
                body.new_slot_id,
                rollback_ok,
            )
            if rollback_ok:
                raise HTTPException(409, "Le créneau sélectionné n'est plus disponible")
            raise HTTPException(502, "Le rendez-vous Google a été déplacé mais le miroir interne n'a pas pu être remis à jour")
        logger.info(
            "tenant agenda reschedule google ok tenant_id=%s appointment_id=%s event_id=%s new_slot_id=%s",
            tenant_id,
            appointment_id,
            event_id,
            body.new_slot_id,
        )
        _mark_pending_handoffs_processed(tenant_id, booking)
        return {"ok": True, "rescheduled": True, "provider": "google+local"}
    ok = reschedule_booking_atomic(appointment_id, int(body.new_slot_id), tenant_id=tenant_id)
    if ok is False:
        raise HTTPException(409, "Le créneau sélectionné n'est plus disponible")
    logger.info(
        "tenant agenda reschedule local ok tenant_id=%s appointment_id=%s new_slot_id=%s",
        tenant_id,
        appointment_id,
        body.new_slot_id,
    )
    _mark_pending_handoffs_processed(tenant_id, booking)
    return {"ok": True, "rescheduled": True, "provider": "local"}


@router.patch("/params")
def tenant_patch_params(
    body: Dict[str, Any],
    auth: dict = Depends(require_tenant_owner),
):
    """
    Met à jour params du tenant connecté.
    """
    allowed = {
        "contact_email", "calendar_provider", "calendar_id", "timezone", "consent_mode", "business_name",
        "phone_number", "sector", "specialty_label", "address_line1", "postal_code", "city",
        "assistant_name", "plan_key", "agenda_software", "client_onboarding_completed",
        "dashboard_tour_completed",
        "transfer_number", "transfer_live_enabled", "transfer_callback_enabled",
        "transfer_cases", "transfer_hours", "transfer_always_urgent", "transfer_no_consultation",
        "transfer_config_confirmed_signature", "transfer_config_confirmed_at",
        "practitioner_name", "website_url", "languages", "accepts_new_patients", "practitioner_photo_url", "public_slug",
        "opening_hours_json", "temporary_closure_enabled", "temporary_closure_start", "temporary_closure_end", "temporary_closure_message",
        "default_appointment_duration_minutes", "minimum_booking_notice_hours", "appointment_reschedule_allowed",
        "appointment_reschedule_notice_hours", "appointment_cancel_allowed", "appointment_cancel_notice_hours",
        "emergency_instruction", "new_patient_instruction", "booking_notes", "appointment_reasons_json",
        "welcome_message", "documents_to_bring", "access_instructions", "payment_methods", "parking_info", "pmr_access",
        "sensitive_medical_instruction", "escalation_instruction", "human_handoff_instruction", "faq_items_json",
    }
    body = body or {}
    tenant_id = auth["tenant_id"]
    tenant_name = (body.get("tenant_name") or "").strip() if body.get("tenant_name") is not None else ""
    business_name = (body.get("business_name") or "").strip() if body.get("business_name") is not None else ""
    params = {k: v for k, v in body.items() if k in allowed and v is not None}
    synced_display_name = business_name or tenant_name
    if synced_display_name and "business_name" not in params:
        params["business_name"] = synced_display_name
    if synced_display_name:
        ok = pg_update_tenant_name(tenant_id, synced_display_name)
        if not ok:
            raise HTTPException(500, "Failed to update tenant name")
    if not params:
        return {"ok": True}
    pg_sync_normalized_from_params(tenant_id, params)
    if any(key in params for key in ("booking_days", "booking_start_hour", "booking_end_hour")):
        pg_sync_opening_hours_from_booking_rules(tenant_id, params)
    ok = pg_update_tenant_params(tenant_id, params)
    if not ok:
        set_params(tenant_id, params)
    return {"ok": True}


@router.get("/horaires")
def tenant_get_horaires(auth: dict = Depends(require_tenant_auth)):
    """Retourne les règles de booking du tenant connecté + texte horaires dérivé."""
    tenant_id = auth["tenant_id"]
    rules = get_booking_rules(tenant_id)
    payload = {
        "booking_days": rules.get("booking_days", [0, 1, 2, 3, 4]),
        "booking_start_hour": rules.get("start_hour", 9),
        "booking_end_hour": rules.get("end_hour", 18),
        "booking_duration_minutes": rules.get("duration_minutes", 15),
        "booking_buffer_minutes": rules.get("buffer_minutes", 0),
    }
    return {**payload, "horaires": derive_horaires_text(payload)}


@router.patch("/horaires")
def tenant_patch_horaires(
    body: HorairesBody,
    auth: dict = Depends(require_tenant_auth),
):
    """Met à jour les horaires structurés du tenant connecté."""
    tenant_id = auth["tenant_id"]
    rules = _validate_horaires_payload(body)
    horaires = derive_horaires_text(rules)
    ok = pg_update_tenant_params(tenant_id, {**rules, "horaires": horaires})
    if not ok:
        raise HTTPException(500, "Failed to update horaires")
    return {"ok": True, "horaires": horaires, **rules}


class ChangePasswordBody(BaseModel):
    new_password: str


class HorairesBody(BaseModel):
    booking_days: List[int]
    booking_start_hour: int
    booking_end_hour: int
    booking_duration_minutes: int
    booking_buffer_minutes: int


def _save_tenant_faq_payload(tenant_id: int, faq_payload: List[Dict[str, Any]]) -> bool:
    normalized = normalize_faq_payload(faq_payload)
    if config.USE_PG_TENANTS:
        return pg_update_tenant_params(tenant_id, {"faq_json": normalized})
    set_params(tenant_id, {"faq_json": normalized})
    return True


def _reset_tenant_faq_payload(tenant_id: int) -> bool:
    if config.USE_PG_TENANTS:
        return pg_delete_tenant_param_keys(tenant_id, ["faq_json"])
    reset_faq_params(tenant_id)
    return True


async def _sync_tenant_faq_to_vapi(tenant_id: int) -> None:
    try:
        await update_vapi_assistant_faq(tenant_id)
    except Exception as e:
        logger.error("tenant_faq_vapi_sync_failed tenant_id=%s error=%s", tenant_id, e)


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


@router.get("/faq")
def tenant_get_faq(auth: dict = Depends(require_tenant_auth)):
    return get_faq(auth["tenant_id"])


@router.put("/faq")
async def tenant_put_faq(
    body: List[Dict[str, Any]] = Body(...),
    auth: dict = Depends(require_tenant_auth),
):
    tenant_id = auth["tenant_id"]
    faq_payload = normalize_faq_payload(body)
    if not faq_payload:
        raise HTTPException(status_code=400, detail="FAQ invalide.")
    if not _save_tenant_faq_payload(tenant_id, faq_payload):
        raise HTTPException(status_code=500, detail="Impossible d'enregistrer la FAQ.")
    await _sync_tenant_faq_to_vapi(tenant_id)
    return {"ok": True, "faq": faq_payload}


@router.post("/faq/reset")
async def tenant_reset_faq(auth: dict = Depends(require_tenant_owner)):
    tenant_id = auth["tenant_id"]
    if not _reset_tenant_faq_payload(tenant_id):
        raise HTTPException(status_code=500, detail="Impossible de réinitialiser la FAQ.")
    await _sync_tenant_faq_to_vapi(tenant_id)
    return {"ok": True, "faq": get_faq(tenant_id)}


@router.patch("/auth/change-password")
def tenant_change_password(
    body: ChangePasswordBody,
    auth: dict = Depends(require_tenant_auth),
):
    """
    Met à jour le mot de passe du tenant connecté.
    """
    new_password = (body.new_password or "").strip()
    if len(new_password) < 8:
        raise HTTPException(400, "Le mot de passe doit contenir au moins 8 caractères")

    user_id = int(auth["sub"])
    password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    pg_update_password(user_id, password_hash)
    logger.info(
        "tenant_password_changed",
        extra={
            "tenant_id": auth["tenant_id"],
            "user_id": user_id,
            "role": auth.get("role", "owner"),
            "why": "manual_change",
        },
    )
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
    auth: dict = Depends(require_tenant_owner),
):
    """
    Vérifie l'accès au calendrier Google (get_free_slots test).
    Si OK : sauvegarde calendar_provider=google, calendar_id.
    """
    calendar_id = (body.calendar_id or "").strip()
    if not calendar_id:
        return {"ok": False, "reason": "calendar_id_required"}
    if _looks_like_service_account_email(calendar_id):
        return {
            "ok": False,
            "reason": "service_account_email",
            "message": "L'email du service account n'est pas l'ID du calendrier. Collez l'identifiant du calendrier Google du cabinet.",
        }
    tenant_id = auth["tenant_id"]
    try:
        adapter = _GoogleCalendarAdapter(calendar_id, tenant_id)
        adapter.get_free_slots(datetime.now(), duration_minutes=15, limit=1)
        pg_update_tenant_params(tenant_id, {"calendar_provider": "google", "calendar_id": calendar_id})
        logger.info("agenda_verify_google ok tenant_id=%s calendar_id=%s", tenant_id, calendar_id[:50])
        return {"ok": True}
    except GoogleCalendarPermissionError:
        return {
            "ok": False,
            "reason": "permission",
            "message": "Accès refusé. Vérifiez que le calendrier est bien partagé avec le service account.",
        }
    except GoogleCalendarNotFoundError:
        return {
            "ok": False,
            "reason": "not_found",
            "message": "Calendrier introuvable. Vérifiez l'ID du calendrier.",
        }
    except Exception as e:
        logger.error("verify-google error tenant_id=%s: %s", tenant_id, e)
        return {
            "ok": False,
            "reason": "error",
            "message": "Erreur technique. Réessayez dans quelques instants.",
        }


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
def tenant_agenda_activate_none(auth: dict = Depends(require_tenant_owner)):
    """Active le mode sans agenda externe (l'assistant gère les RDV dans son propre système)."""
    tenant_id = auth["tenant_id"]
    pg_update_tenant_params(tenant_id, {"calendar_provider": "none", "calendar_id": ""})
    return {"ok": True}
