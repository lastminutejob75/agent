# backend/routes/tenant.py
"""
API tenant (client): dashboard, technical-status, me, params, agenda.
Protégé par cookie uwi_session uniquement (require_tenant_auth).
"""
from __future__ import annotations

import copy
import base64
import hashlib
import hmac
import json
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from types import SimpleNamespace
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Literal, Optional

import bcrypt
import jwt
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, validator

from backend.auth_pg import pg_get_tenant_user_by_id, pg_update_password
from backend.calendar_adapter import _GoogleCalendarAdapter
from backend import config
from backend.config import get_service_account_email
from backend.patient_insights import compute_patient_insights
from backend.patient_history import build_patient_history
from backend.db import (
    cancel_booking_sqlite,
    book_slot_atomic,
    delete_patient_note,
    delete_patient_document,
    delete_cabinet_client_by_phone,
    detect_patient_duplicate_conflicts,
    ensure_slot_id_by_datetime,
    ensure_tenant_config,
    get_cabinet_clients_by_phones,
    find_slot_id_by_datetime,
    get_cabinet_client_by_phone,
    get_call_followup,
    get_conn,
    insert_patient_note,
    is_valid_patient_phone,
    is_valid_contact_email,
    insert_patient_document,
    list_cabinet_clients,
    list_cabinet_clients_compact,
    search_cabinet_clients,
    search_cabinet_clients_with_fallback,
    list_free_slots,
    list_call_followups,
    list_patient_notes,
    list_patient_documents,
    normalize_phone_number,
    attach_appointment_google_event_id,
    reschedule_booking_atomic,
    _migrate_sqlite_add_booking_origin,
    _migrate_sqlite_add_google_event_id,
    update_patient_fields,
    upsert_cabinet_client,
    upsert_call_followup,
    change_cabinet_client_phone,
    PatientPhoneChangeError,
    _cabinet_client_phone_lookup_keys,
)
from backend.google_calendar import GoogleCalendarNotFoundError, GoogleCalendarPermissionError, GoogleCalendarService
from backend.handoffs import get_handoff_by_id, list_handoffs, update_handoff_status
from backend.routes.admin import (
    _get_call_detail,
    _get_calls_list,
    _get_dashboard_snapshot,
    _get_kpis_daily,
    _get_kpis_today,
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
from backend.services.email_service import (
    send_agenda_contact_request_email,
    send_patient_document_email,
    send_patient_message_email,
)
from backend.services.sms_service import send_sms_message
from backend.services.patient_document_storage import (
    content_disposition_attachment,
    delete_patient_dossier,
    patient_dossier_exists,
    patient_dossier_local_filepath,
    read_document,
    read_patient_dossier,
    save_patient_dossier_upload,
    use_s3_storage,
)
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
from backend.tenants_pg import (
    pg_delete_tenant_param_keys as _raw_pg_delete_tenant_param_keys,
    pg_update_tenant_name as _raw_pg_update_tenant_name,
    pg_update_tenant_params as _raw_pg_update_tenant_params,
)


def pg_update_tenant_params(tenant_id, params):
    """Wrapper : invalide les caches mémoire après toute écriture des params tenant."""
    res = _raw_pg_update_tenant_params(tenant_id, params)
    try:
        _invalidate_tenant_me_detail_cache(int(tenant_id))
        _invalidate_tenant_agenda_detail_cache(int(tenant_id))
    except Exception:
        pass
    return res


def pg_update_tenant_name(tenant_id, name):
    res = _raw_pg_update_tenant_name(tenant_id, name)
    try:
        _invalidate_tenant_me_detail_cache(int(tenant_id))
        _invalidate_tenant_agenda_detail_cache(int(tenant_id))
    except Exception:
        pass
    return res


def pg_delete_tenant_param_keys(tenant_id, keys):
    res = _raw_pg_delete_tenant_param_keys(tenant_id, keys)
    try:
        _invalidate_tenant_me_detail_cache(int(tenant_id))
        _invalidate_tenant_agenda_detail_cache(int(tenant_id))
    except Exception:
        pass
    return res
from backend.vapi_utils import update_vapi_assistant_faq

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore

logger = logging.getLogger(__name__)

# Réponses Google Calendar `events.list` pour l'agenda : cache court (souvent >200 ms / requête hors cache).
_AGENDA_GCAL_EVENTS_LOCK = threading.Lock()
_AGENDA_GCAL_EVENTS_CACHE: Dict[tuple, tuple[float, dict]] = {}


def _google_calendar_events_list_execute(calendar_svc: GoogleCalendarService, *, calendar_id: str, time_min_iso: str, time_max_iso: str) -> dict:
    return (
        calendar_svc.service.events()
        .list(
            calendarId=(calendar_id or "").strip(),
            timeMin=time_min_iso,
            timeMax=time_max_iso,
            singleEvents=True,
            orderBy="startTime",
            fields="items(id,summary,description,start,end)",
        )
        .execute()
    )


def _google_calendar_events_list_execute_with_timeout(
    calendar_svc: GoogleCalendarService,
    *,
    calendar_id: str,
    time_min_iso: str,
    time_max_iso: str,
    execute_timeout: Optional[float] = None,
) -> dict:
    """Borne ``events.list()`` même si le client HTTP Google n'a pas de timeout (fallback prod)."""
    if execute_timeout is not None:
        timeout = float(execute_timeout)
    else:
        try:
            timeout = float((os.environ.get("AGENDA_GOOGLE_EXECUTE_TIMEOUT_SECONDS") or "18").strip() or "18")
        except ValueError:
            timeout = 18.0
    if timeout <= 0:
        return _google_calendar_events_list_execute(
            calendar_svc,
            calendar_id=calendar_id,
            time_min_iso=time_min_iso,
            time_max_iso=time_max_iso,
        )
    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(
            _google_calendar_events_list_execute,
            calendar_svc,
            calendar_id=calendar_id,
            time_min_iso=time_min_iso,
            time_max_iso=time_max_iso,
        )
        try:
            return fut.result(timeout=timeout)
        except FuturesTimeoutError:
            logger.warning(
                "Google Calendar events.list timed out after %.1fs calendar=%s window=%s..%s",
                timeout,
                (calendar_id or "")[:48],
                time_min_iso,
                time_max_iso,
            )
            return {"items": []}


def _tenant_google_calendar_list_events_cached(
    calendar_svc: GoogleCalendarService,
    *,
    calendar_id: str,
    time_min_iso: str,
    time_max_iso: str,
    execute_timeout: Optional[float] = None,
) -> dict:
    """Même fenêtre temporelle dans les ~AGENDA_GOOGLE_CACHE_SECONDS s = pas d'appel Google répété."""
    cid = (calendar_id or "").strip()
    try:
        ttl = float((os.environ.get("AGENDA_GOOGLE_CACHE_SECONDS") or "90").strip() or "90")
    except ValueError:
        ttl = 30.0
    # Pytest définit cette variable pendant l'exécution d'un test : ne pas mutualiser les réponses google entre tests.
    if os.environ.get("PYTEST_CURRENT_TEST"):
        ttl = -1.0
    if ttl <= 0:
        return _google_calendar_events_list_execute_with_timeout(
            calendar_svc,
            calendar_id=cid,
            time_min_iso=time_min_iso,
            time_max_iso=time_max_iso,
            execute_timeout=execute_timeout,
        )

    key = (cid, time_min_iso, time_max_iso)
    now_mono = time.monotonic()
    with _AGENDA_GCAL_EVENTS_LOCK:
        hit = _AGENDA_GCAL_EVENTS_CACHE.get(key)
        if hit and hit[0] > now_mono:
            return copy.deepcopy(hit[1])

    executed = _google_calendar_events_list_execute_with_timeout(
        calendar_svc,
        calendar_id=cid,
        time_min_iso=time_min_iso,
        time_max_iso=time_max_iso,
        execute_timeout=execute_timeout,
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
_TENANT_AGENDA_BULK_LOCK = threading.Lock()
_TENANT_AGENDA_BULK_CACHE: Dict[tuple, tuple[float, dict]] = {}
_TENANT_PATIENTS_LIST_LOCK = threading.Lock()
_TENANT_PATIENTS_LIST_CACHE: Dict[tuple, tuple[float, list]] = {}


def _patients_list_cache_ttl_seconds() -> float:
    raw = (os.environ.get("TENANT_PATIENTS_LIST_CACHE_SECONDS") or "60").strip()
    try:
        ttl = float(raw or "60")
    except ValueError:
        ttl = 60.0
    return max(0.0, ttl)


def _invalidate_tenant_patients_list_cache(tenant_id: int) -> None:
    tid = int(tenant_id)
    with _TENANT_PATIENTS_LIST_LOCK:
        keys = [k for k in _TENANT_PATIENTS_LIST_CACHE if int(k[0]) == tid]
        for key in keys:
            _TENANT_PATIENTS_LIST_CACHE.pop(key, None)


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
    # Invalidation couplée: si la config agenda change, on invalide aussi les snapshots bulk.
    with _TENANT_AGENDA_BULK_LOCK:
        keys = [k for k in _TENANT_AGENDA_BULK_CACHE.keys() if int(k[0]) == int(tenant_id)]
        for k in keys:
            _TENANT_AGENDA_BULK_CACHE.pop(k, None)


def _invalidate_google_agenda_events_cache(calendar_id: Optional[str] = None) -> None:
    """Invalide le cache court ``events.list`` après mutation (create/cancel/reschedule)."""
    cid = str(calendar_id or "").strip()
    with _AGENDA_GCAL_EVENTS_LOCK:
        if not cid:
            _AGENDA_GCAL_EVENTS_CACHE.clear()
            return
        keys = [k for k in _AGENDA_GCAL_EVENTS_CACHE.keys() if str(k[0] or "").strip() == cid]
        for k in keys:
            _AGENDA_GCAL_EVENTS_CACHE.pop(k, None)


def _patient_delete_token_secret() -> bytes:
    raw = (
        os.environ.get("PATIENT_DELETE_TOKEN_SECRET")
        or os.environ.get("ADMIN_SESSION_SECRET")
        or os.environ.get("JWT_SECRET")
        or "uwi-dev-delete-secret"
    )
    return str(raw).encode("utf-8")


def _patient_delete_token_issue(tenant_id: int, phone_norm: str, *, ttl_sec: int = 900) -> tuple[str, int]:
    exp = int(time.time()) + max(60, int(ttl_sec))
    payload = {
        "tenant_id": int(tenant_id),
        "phone": phone_norm,
        "exp": exp,
        "nonce": uuid4().hex,
    }
    payload_raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_raw).decode("ascii").rstrip("=")
    sig = hmac.new(
        _patient_delete_token_secret(),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_b64}.{sig}", exp


def _patient_delete_token_verify(token: str, tenant_id: int, phone_norm: str) -> bool:
    raw = str(token or "").strip()
    if "." not in raw:
        return False
    payload_b64, sig = raw.rsplit(".", 1)
    expected_sig = hmac.new(
        _patient_delete_token_secret(),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        return False
    try:
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except Exception:
        return False
    if int(payload.get("tenant_id") or 0) != int(tenant_id):
        return False
    if normalize_phone_number(payload.get("phone") or "") != phone_norm:
        return False
    if int(payload.get("exp") or 0) < int(time.time()):
        return False
    return True


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


_TENANT_ME_DETAIL_LOCK = threading.Lock()
_TENANT_ME_DETAIL_CACHE: Dict[int, tuple[float, dict]] = {}


def _invalidate_tenant_me_detail_cache(tenant_id: Optional[int] = None) -> None:
    """À appeler après tout PATCH/PUT modifiant tenant_config ou tenant_routing.
    ``tenant_id=None`` vide tout le cache."""
    with _TENANT_ME_DETAIL_LOCK:
        if tenant_id is None:
            _TENANT_ME_DETAIL_CACHE.clear()
        else:
            _TENANT_ME_DETAIL_CACHE.pop(int(tenant_id), None)


def _get_tenant_me_detail(tenant_id: int) -> Optional[dict]:
    """Charge seulement les données nécessaires à /api/tenant/me.

    Cache mémoire 30s (configurable via TENANT_ME_DETAIL_CACHE_SECONDS) car cette
    fonction est appelée par ~14 endpoints du dashboard à chaque chargement
    (kpis, horaires, faq, profil, status, etc.). Sans cache, c'était 14
    requêtes PG sur tenants + tenant_config + tenant_routing par chargement.
    """
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        try:
            ttl = float((os.environ.get("TENANT_ME_DETAIL_CACHE_SECONDS") or "30").strip() or "30")
        except ValueError:
            ttl = 30.0
        if ttl > 0:
            now = time.monotonic()
            with _TENANT_ME_DETAIL_LOCK:
                hit = _TENANT_ME_DETAIL_CACHE.get(int(tenant_id))
                if hit and hit[0] > now:
                    return copy.deepcopy(hit[1])
            detail = _load_tenant_me_detail(tenant_id)
            if detail is not None:
                with _TENANT_ME_DETAIL_LOCK:
                    _TENANT_ME_DETAIL_CACHE[int(tenant_id)] = (now + ttl, copy.deepcopy(detail))
                    if len(_TENANT_ME_DETAIL_CACHE) > 500:
                        stale = [tid for tid, (exp, _) in _TENANT_ME_DETAIL_CACHE.items() if exp <= now]
                        for tid in stale[:200]:
                            _TENANT_ME_DETAIL_CACHE.pop(tid, None)
                return copy.deepcopy(detail)
            return None
    return _load_tenant_me_detail(tenant_id)


def _load_tenant_me_detail(tenant_id: int) -> Optional[dict]:
    """Implémentation non-cachée (chargement brut depuis PG/SQLite)."""
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


def _cabinet_patient_record_exists(profile: Optional[Dict[str, Any]]) -> bool:
    """True dès qu'une fiche patient existe pour ce numéro (même sans identité validée)."""
    return profile is not None


def _is_agenda_dummy_phone(phone_norm: str) -> bool:
    """Numéros factices (Google / page publique) qui ne doivent pas lier une fiche patient."""
    if not phone_norm:
        return True
    if not is_valid_patient_phone(phone_norm):
        return True
    digits = re.sub(r"\D", "", phone_norm)
    if not digits:
        return True
    if len(set(digits)) == 1 and digits[0] == "0":
        return True
    if digits in ("33000000000", "0000000000", "00000000"):
        return True
    return False


def _agenda_slot_contact_for_patient_phone(
    google_contact: str,
    mirror_booking: Optional[Dict[str, Any]],
) -> str:
    """Préfère le contact du RDV local miroir si le Google en affiche un numéro factice."""
    contact_norm = normalize_phone_number(google_contact or "")
    if mirror_booking:
        mirror_contact = normalize_phone_number(str(mirror_booking.get("contact") or ""))
        if mirror_contact and not _is_agenda_dummy_phone(mirror_contact):
            return mirror_contact
    if contact_norm and not _is_agenda_dummy_phone(contact_norm):
        return contact_norm
    return contact_norm


def _agenda_resolve_profile_phone_for_slot(
    tenant_id: int,
    item: Dict[str, Any],
    profile_cache: Dict[str, Optional[Dict[str, Any]]],
) -> str:
    """Téléphone métier pour lier ``patient_has_file`` (ignore numéros factices agenda)."""
    phone_norm = normalize_phone_number(item.get("patient_phone") or "")
    if phone_norm and not _is_agenda_dummy_phone(phone_norm):
        return phone_norm
    appt_id = int(item.get("appointment_id") or 0)
    if appt_id > 0:
        local = _get_local_appointment_by_id(tenant_id, appt_id)
        if local:
            contact_norm = normalize_phone_number(local.get("contact") or "")
            if contact_norm and not _is_agenda_dummy_phone(contact_norm):
                return contact_norm
    return ""


def _agenda_lookup_profile_by_patient_name(
    tenant_id: int,
    patient_name: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Une seule fiche si le nom affiché correspond exactement (évite les homonymes)."""
    name_clean = str(patient_name or "").strip()
    if len(name_clean) < 2:
        return None
    try:
        rows = search_cabinet_clients(tenant_id, name_clean, limit=8)
    except Exception:
        return None
    name_fold = name_clean.casefold()
    exact = [
        row
        for row in rows
        if any(
            str(row.get(key) or "").strip().casefold() == name_fold
            for key in ("display_name", "validated_name", "raw_name")
        )
    ]
    if len(exact) == 1:
        return exact[0]
    return None


def _agenda_uwi_can_reschedule(source: str, mirror_booking: Optional[Dict[str, Any]], event_id: Any) -> bool:
    """Déplacement autorisé : miroir local complet ou événement Google UWI (RDV page publique / Clara)."""
    if (source or "").strip().upper() != "UWI":
        return False
    if mirror_booking and int(mirror_booking.get("id") or 0) > 0 and int(mirror_booking.get("slot_id") or 0) > 0:
        return True
    return bool(str(event_id or "").strip())


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


def _apply_agenda_lightweight_slot_defaults(slots: List[Dict[str, Any]]) -> None:
    for item in slots or []:
        item.setdefault("patient_has_file", False)
        item.setdefault("patient_identity_validated", False)


def _decorate_agenda_slots_patient_has_file(
    tenant_id: int,
    slots: List[Dict[str, Any]],
    profile_cache: Dict[str, Optional[Dict[str, Any]]],
) -> None:
    """Ajoute ``patient_has_file`` si une ligne existe dans cabinet_clients pour ce numéro."""
    for item in slots:
        phone_norm = _agenda_resolve_profile_phone_for_slot(tenant_id, item, profile_cache)
        profile: Optional[Dict[str, Any]] = None
        if phone_norm:
            profile = _agenda_lookup_dashboard_patient_profile(tenant_id, phone_norm, profile_cache)
        if profile is None:
            profile = _agenda_lookup_profile_by_patient_name(tenant_id, item.get("patient"))
            if profile:
                pn = normalize_phone_number(profile.get("phone") or "")
                if pn:
                    profile_cache[pn] = profile
        item["patient_has_file"] = _cabinet_patient_record_exists(profile)
        item["patient_identity_validated"] = _dashboard_patient_file_has_validated_identity(profile)


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


def _agenda_slot_meta(
    *,
    start_local: datetime,
    end_local: datetime,
    contact_type: str = "",
    description: str = "",
) -> Dict[str, Any]:
    pref = _extract_google_description_line(description, "Préférence") or ""
    duration = 30
    if start_local and end_local:
        duration = max(5, int((end_local - start_local).total_seconds() // 60))
    return {
        "contact_type": str(contact_type or ""),
        "duration_minutes": duration,
        "time_preference": pref,
        "end_iso": end_local.isoformat() if end_local else "",
    }

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
                        SELECT a.id, a.slot_id, a.name, a.contact, a.contact_type, a.motif,
                               a.google_event_id, s.start_ts
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
                        "google_event_id": row.get("google_event_id") or "",
                        "date": date_str,
                        "time": time_str,
                        "start_ts": row.get("start_ts"),
                    }
        except Exception as e:
            logger.debug("local appointment lookup pg failed tenant_id=%s appointment_id=%s err=%s", tenant_id, appointment_id, e)

    ensure_tenant_config()
    conn = get_conn()
    try:
        _migrate_sqlite_add_google_event_id(conn)
        row = conn.execute(
            """
            SELECT a.id, a.slot_id, a.name, a.contact, a.contact_type, a.motif, a.google_event_id, s.date, s.time
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
            "google_event_id": row["google_event_id"] or "",
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


def _looks_like_google_event_id(raw: Optional[str]) -> bool:
    """Distinction id Google Calendar vs id numérique local (appointments.id)."""
    s = str(raw or "").strip()
    if not s:
        return False
    return not s.isdigit()


def _local_booking_start_local(
    local_booking: Dict[str, Any],
    tz_name: str,
) -> Optional[datetime]:
    start_ts = local_booking.get("start_ts")
    if start_ts is not None:
        parsed = _parse_dt(start_ts, tz_name)
        if parsed:
            return parsed.astimezone(_get_zoneinfo(tz_name))
    date_str = str(local_booking.get("date") or "").strip()
    time_str = str(local_booking.get("time") or "").strip()
    if date_str and time_str:
        parsed = _parse_dt(f"{date_str}T{time_str}:00", tz_name)
        if parsed:
            return parsed.astimezone(_get_zoneinfo(tz_name))
    return None


def _persist_appointment_google_event_id(
    tenant_id: int,
    appointment_id: int,
    google_event_id: str,
) -> None:
    """Enregistre le lien RDV local ↔ Google (best-effort)."""
    if not appointment_id or not _looks_like_google_event_id(google_event_id):
        return
    try:
        attach_appointment_google_event_id(
            tenant_id,
            google_event_id,
            appointment_id=int(appointment_id),
        )
    except Exception as e:
        logger.debug(
            "persist google_event_id failed tenant_id=%s appointment_id=%s err=%s",
            tenant_id,
            appointment_id,
            e,
        )


def _resolve_google_event_id_for_booking(
    tenant_id: int,
    detail: dict,
    *,
    explicit_event_id: Optional[str] = None,
    local_booking: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Retrouve l'id événement Google pour un RDV UWI (annulation / déplacement).
    Utilise external_event_id si fourni, sinon recherche par créneau + contact/nom.
    """
    explicit = str(explicit_event_id or "").strip()
    if _looks_like_google_event_id(explicit):
        if local_booking and int(local_booking.get("id") or 0) > 0:
            _persist_appointment_google_event_id(tenant_id, int(local_booking["id"]), explicit)
        return explicit

    if local_booking:
        stored = str(local_booking.get("google_event_id") or "").strip()
        if _looks_like_google_event_id(stored):
            return stored

    if not local_booking:
        return explicit or None

    params = (detail or {}).get("params") or {}
    cal_id = (params.get("calendar_id") or "").strip()
    if not cal_id:
        return None

    tz_name = _tenant_timezone(detail)
    start_local = _local_booking_start_local(local_booking, tz_name)
    if not start_local:
        return None

    win_start = start_local - timedelta(minutes=2)
    win_end = start_local + timedelta(minutes=45)
    try:
        service = GoogleCalendarService(cal_id)
        result = service.service.events().list(
            calendarId=cal_id,
            timeMin=win_start.isoformat(),
            timeMax=win_end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        events = result.get("items") or []
    except Exception as e:
        logger.warning(
            "resolve google event id list failed tenant_id=%s appointment_id=%s err=%s",
            tenant_id,
            local_booking.get("id"),
            e,
        )
        return None

    lookup_key = _appointment_lookup_key(start_local)
    patient_contact = local_booking.get("contact") or ""
    patient_name = local_booking.get("name") or ""

    for event in events:
        raw_start = (event.get("start") or {}).get("dateTime") or (event.get("start") or {}).get("date")
        ev_start = _parse_dt(raw_start, tz_name)
        if not ev_start:
            continue
        ev_start_local = ev_start.astimezone(_get_zoneinfo(tz_name))
        if _appointment_lookup_key(ev_start_local) != lookup_key:
            continue
        summary = (event.get("summary") or "").strip()
        description = (event.get("description") or "").strip()
        if not (summary.startswith("RDV - ") or "Patient:" in description):
            continue
        ev_contact = _extract_calendar_event_patient_contact(description)
        ev_name = summary.replace("RDV - ", "", 1).strip() if summary.startswith("RDV - ") else summary
        google_row = {"contact": ev_contact, "name": ev_name}
        if _appointment_matches_lookup(local_booking, ev_contact, ev_name):
            resolved = str(event.get("id") or "").strip() or None
            if resolved and int(local_booking.get("id") or 0) > 0:
                _persist_appointment_google_event_id(tenant_id, int(local_booking["id"]), resolved)
            return resolved
        if _appointment_matches_lookup(google_row, patient_contact, patient_name):
            resolved = str(event.get("id") or "").strip() or None
            if resolved and int(local_booking.get("id") or 0) > 0:
                _persist_appointment_google_event_id(tenant_id, int(local_booking["id"]), resolved)
            return resolved

    return None


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
                        SELECT a.id, a.slot_id, a.name, a.contact, a.contact_type, a.motif, a.google_event_id, s.start_ts,
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
                                "google_event_id": row.get("google_event_id") or "",
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
                   a.booking_origin, a.google_event_id, s.date, s.time
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
                    "google_event_id": row["google_event_id"] or "",
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


def _appointment_lookup_keys_near(start_local: Optional[datetime], *, radius_minutes: int = 3) -> List[str]:
    if not start_local:
        return [""]
    keys: List[str] = []
    for delta in range(-radius_minutes, radius_minutes + 1):
        key = _appointment_lookup_key(start_local + timedelta(minutes=delta))
        if key and key not in keys:
            keys.append(key)
    return keys or [_appointment_lookup_key(start_local)]


def _local_appointment_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": int(row.get("id") or 0),
        "slot_id": int(row.get("slot_id") or 0),
        "name": row.get("name") or "",
        "contact": row.get("contact") or "",
        "contact_type": row.get("contact_type") or "",
        "motif": row.get("motif") or "",
        "google_event_id": row.get("google_event_id") or "",
    }


def _find_local_appointment_by_google_event_id(
    tenant_id: int,
    google_event_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    event_id = str(google_event_id or "").strip()
    if not event_id or not _looks_like_google_event_id(event_id):
        return None

    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_SLOTS_URL")
    if url:
        try:
            import psycopg
            from psycopg.rows import dict_row

            with psycopg.connect(url, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT a.id, a.slot_id, a.name, a.contact, a.contact_type, a.motif, a.google_event_id
                        FROM appointments a
                        WHERE a.tenant_id = %s AND a.google_event_id = %s
                        LIMIT 1
                        """,
                        (tenant_id, event_id),
                    )
                    row = cur.fetchone()
                    if row and int(row.get("id") or 0) > 0:
                        return _local_appointment_from_row(row)
        except Exception as e:
            logger.debug(
                "local appointment google_event_id lookup pg failed tenant_id=%s err=%s",
                tenant_id,
                e,
            )

    ensure_tenant_config()
    conn = get_conn()
    try:
        _migrate_sqlite_add_google_event_id(conn)
        row = conn.execute(
            """
            SELECT a.id, a.slot_id, a.name, a.contact, a.contact_type, a.motif, a.google_event_id
            FROM appointments a
            WHERE a.tenant_id = ? AND a.google_event_id = ?
            LIMIT 1
            """,
            (tenant_id, event_id),
        ).fetchone()
        if not row:
            return None
        return _local_appointment_from_row(dict(row))
    finally:
        conn.close()


def _find_local_appointment_for_google_event(
    tenant_id: int,
    start_local: datetime,
    patient_contact: Optional[str],
    fallback_name: Optional[str],
    appointments_index: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    google_event_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    event_id = str(google_event_id or "").strip()
    by_event = _find_local_appointment_by_google_event_id(tenant_id, event_id)
    if by_event:
        return by_event

    if appointments_index is not None:
        if event_id:
            for appointments in appointments_index.values():
                for appointment in appointments:
                    if str(appointment.get("google_event_id") or "").strip() == event_id:
                        return appointment
        for key in _appointment_lookup_keys_near(start_local):
            for appointment in appointments_index.get(key, []):
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
            window_start = start_utc - timedelta(minutes=5)
            window_end = start_utc + timedelta(minutes=5)
            with psycopg.connect(url, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT a.id, a.slot_id, a.name, a.contact, a.contact_type, a.motif, a.google_event_id, s.start_ts
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
                        return _local_appointment_from_row(row)
        except Exception as e:
            logger.debug("local appointment mirror lookup pg failed tenant_id=%s err=%s", tenant_id, e)

    ensure_tenant_config()
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT a.id, a.slot_id, a.name, a.contact, a.contact_type, a.motif, a.google_event_id
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
        return _local_appointment_from_row(dict(row))
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

    @validator("patient_phone")
    def _validate_booking_phone(cls, v):
        raw = str(v or "").strip()
        if not raw:
            return ""
        if not is_valid_patient_phone(raw):
            raise ValueError(
                "Numéro de téléphone invalide (format attendu : 06 12 34 56 78 ou +33 6 12 34 56 78)."
            )
        return raw

    @validator("patient_email")
    def _validate_booking_email(cls, v):
        raw = str(v or "").strip()
        if not raw:
            return ""
        if not is_valid_contact_email(raw):
            raise ValueError("Email invalide (format attendu: prenom@domaine.fr)")
        return raw


class TenantCallFollowupBody(BaseModel):
    followup_state: str
    notes: str = ""


class TenantCallPatientBody(BaseModel):
    validated_name: str
    raw_name: str = ""
    patient_phone: str = ""
    patient_email: Optional[str] = Field(default=None, max_length=254)
    birth_date: Optional[str] = Field(default=None, max_length=10)
    treating_physician_name: Optional[str] = Field(default=None, max_length=200)
    treating_physician_city: Optional[str] = Field(default=None, max_length=120)

    @validator("patient_email")
    def _validate_call_patient_email(cls, v):
        if v is None:
            return None
        raw = str(v).strip()
        if not raw:
            return None
        if not is_valid_contact_email(raw):
            raise ValueError("Email invalide (format attendu: prenom@domaine.fr)")
        return raw

    @validator("birth_date")
    def _validate_call_patient_birth_date(cls, v):
        if v is None:
            return None
        v = v.strip()
        if v == "":
            return ""
        if len(v) != 10 or v[4] != "-" or v[7] != "-":
            raise ValueError("Date de naissance invalide (format attendu: AAAA-MM-JJ)")
        return v

    @validator("treating_physician_name")
    def _validate_call_treating_physician_name(cls, v):
        if v is None:
            return None
        return v.strip()[:200]

    @validator("treating_physician_city")
    def _validate_call_treating_physician_city(cls, v):
        if v is None:
            return None
        return v.strip()[:120]


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

    @validator("phone")
    def _validate_profile_phone(cls, v):
        if v is None:
            return None
        raw = str(v).strip()
        if not raw:
            return ""
        if not is_valid_patient_phone(raw):
            raise ValueError(
                "Numéro de téléphone invalide (format attendu : 06 12 34 56 78 ou +33 6 12 34 56 78)."
            )
        return raw

    @validator("email")
    def _validate_profile_email(cls, v):
        if v is None:
            return None
        raw = str(v).strip()
        if not raw:
            return ""
        if not is_valid_contact_email(raw):
            raise ValueError("Email invalide (format attendu: prenom@domaine.fr)")
        return raw


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
        "dashboard_team_note": params.get("dashboard_team_note", ""),
        "dashboard_team_note_updated_at": params.get("dashboard_team_note_updated_at", ""),
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
    detail = _get_tenant_detail(tenant_id) or {}
    tz_name = _tenant_timezone(detail)
    data = _get_kpis_daily(tenant_id, days=days)
    data["today"] = _get_kpis_today(tenant_id, tz_name)
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


_TENANT_STATS_FAST_CACHE: Dict[int, tuple] = {}
_TENANT_STATS_FAST_LOCK = threading.Lock()


def _tenant_stats_fast_cache_ttl() -> float:
    try:
        return float((os.environ.get("TENANT_STATS_FAST_CACHE_SECONDS") or "20").strip() or "20")
    except ValueError:
        return 20.0


def _tenant_dashboard_calls_light(
    tenant_id: int,
    detail: dict,
    tz_name: str,
    limit: int = 30,
    days: int = 7,
) -> List[Dict[str, Any]]:
    """Appels récents allégés pour le bandeau stats (annulations du jour)."""
    items = (_get_calls_list(tenant_id=tenant_id, days=days, limit=limit, tenant_detail=detail) or {}).get("items") or []
    calls: List[Dict[str, Any]] = []
    for item in items[:limit]:
        call_id = (item.get("call_id") or "").strip()
        if not call_id:
            continue
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
        call_context = _classify_call_context(status, detail_for_display)
        calls.append(
            {
                "id": call_id,
                "call_id": call_id,
                "started_at": item.get("started_at"),
                "last_event_at": item.get("last_event_at"),
                "created_at": item.get("started_at"),
                "summary": _call_summary_from_detail(status, detail_for_display),
                "result": item.get("result") or status,
                "status": status,
                "reason_category": call_context.get("reason_category") or "general",
            }
        )
    return calls


@router.get("/dashboard/stats-fast")
def tenant_dashboard_stats_fast(auth: dict = Depends(require_tenant_auth)):
    """KPI jour + créneaux libres (7j) + appels récents — une requête, parallélisée côté serveur."""
    tenant_id = int(auth["tenant_id"])
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        ttl = _tenant_stats_fast_cache_ttl()
        if ttl > 0:
            now_mono = time.monotonic()
            with _TENANT_STATS_FAST_LOCK:
                hit = _TENANT_STATS_FAST_CACHE.get(tenant_id)
                if hit and hit[0] > now_mono:
                    return copy.deepcopy(hit[1])

    detail = _get_tenant_me_detail(tenant_id)
    if not detail:
        raise HTTPException(404, "Tenant not found")
    tz_name = _tenant_timezone(detail)
    from backend.public_bookings_pg import dashboard_booking_horizon
    from backend.routes.admin import _get_kpis_today
    from backend.slots_pg import pg_count_free_slots_horizon

    today: dict = {}
    free_slots: dict = {}
    calls: List[Dict[str, Any]] = []
    booking_horizon: dict = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        f_today = pool.submit(_get_kpis_today, tenant_id, tz_name)
        f_free = pool.submit(pg_count_free_slots_horizon, tenant_id, 7, tz_name)
        f_calls = pool.submit(_tenant_dashboard_calls_light, tenant_id, detail, tz_name, 30, 7)
        f_booked = pool.submit(dashboard_booking_horizon, tenant_id, horizon_days=7, tz_name=tz_name)
        try:
            today = f_today.result(timeout=20) or {}
        except Exception as exc:
            logger.warning("stats-fast kpis failed tenant=%s: %s", tenant_id, exc)
        try:
            raw_free = f_free.result(timeout=10)
            free_slots = raw_free if isinstance(raw_free, dict) else {}
        except Exception as exc:
            logger.warning("stats-fast free slots failed tenant=%s: %s", tenant_id, exc)
        try:
            calls = f_calls.result(timeout=20) or []
        except Exception as exc:
            logger.warning("stats-fast calls failed tenant=%s: %s", tenant_id, exc)
        try:
            raw_horizon = f_booked.result(timeout=15) or {}
            booking_horizon = raw_horizon if isinstance(raw_horizon, dict) else {}
        except Exception as exc:
            logger.warning("stats-fast booking horizon failed tenant=%s: %s", tenant_id, exc)

    payload = {
        "today": today,
        "free_slots_by_date": free_slots,
        "calls": calls,
        "booked_starts": booking_horizon.get("booked_starts") or [],
        "appointments_today": int(booking_horizon.get("appointments_today") or 0),
    }
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        ttl = _tenant_stats_fast_cache_ttl()
        if ttl > 0:
            with _TENANT_STATS_FAST_LOCK:
                _TENANT_STATS_FAST_CACHE[tenant_id] = (time.monotonic() + ttl, copy.deepcopy(payload))
                if len(_TENANT_STATS_FAST_CACHE) > 200:
                    stale = [k for k, (exp, _) in _TENANT_STATS_FAST_CACHE.items() if exp <= time.monotonic()]
                    for k in stale[:50]:
                        _TENANT_STATS_FAST_CACHE.pop(k, None)
    return payload


@router.get("/bookings/today")
def tenant_bookings_today(auth: dict = Depends(require_tenant_auth)):
    """Confirmations de RDV enregistrées aujourd'hui (jour civil cabinet)."""
    from backend.routes.admin import _list_bookings_confirmed_today

    tenant_id = auth["tenant_id"]
    detail = _get_tenant_detail(tenant_id) or {}
    tz_name = _tenant_timezone(detail)
    return _list_bookings_confirmed_today(tenant_id, tz_name)


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
    if compact_mode and not items:
        return {
            "calls": [],
            "total": 0,
            "date": datetime.now(_get_zoneinfo(tz_name)).strftime("%Y-%m-%d"),
            "_debug_tenant_id": tenant_id,
        }
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
    if phone_from_body and not is_valid_patient_phone(body.patient_phone):
        raise HTTPException(
            400,
            "Numéro de téléphone invalide (format attendu : 06 12 34 56 78 ou +33 6 12 34 56 78).",
        )
    phone = phone_from_call or phone_from_body
    if not phone:
        raise HTTPException(400, "Numéro du patient introuvable pour cet appel")

    validated_name = (body.validated_name or "").strip()
    if len(validated_name) < 2:
        raise HTTPException(400, "validated_name too short")

    patient_email = (body.patient_email or "").strip()[:254] or None
    if patient_email and not is_valid_contact_email(patient_email):
        raise HTTPException(400, "Email invalide (format attendu: prenom@domaine.fr).")

    _raise_on_blocking_patient_duplicate(tenant_id, phone=phone, email=patient_email)

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

    profile_field_kwargs: dict = {}
    if patient_email:
        profile_field_kwargs["email"] = patient_email
    if body.birth_date is not None:
        profile_field_kwargs["birth_date"] = body.birth_date
    if body.treating_physician_name is not None:
        profile_field_kwargs["treating_physician_name"] = body.treating_physician_name
    if body.treating_physician_city is not None:
        profile_field_kwargs["treating_physician_city"] = body.treating_physician_city
    if profile_field_kwargs:
        profile = update_patient_fields(tenant_id, phone, **profile_field_kwargs) or profile

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
    compact: bool = Query(False, description="Colonnes minimales pour la sidebar (plus rapide)"),
):
    """Liste les fiches patient du tenant (dashboard client)."""
    tenant_id = auth["tenant_id"]
    qs = (q or "").strip()
    if qs:
        cap = min(limit, 100)
        items = search_cabinet_clients_with_fallback(tenant_id, qs, limit=cap)
        return {"items": items, "total": len(items), "mode": "search"}
    cache_key = (int(tenant_id), int(limit), int(offset), bool(compact))
    ttl = _patients_list_cache_ttl_seconds()
    if ttl > 0 and not os.environ.get("PYTEST_CURRENT_TEST"):
        now = time.monotonic()
        with _TENANT_PATIENTS_LIST_LOCK:
            hit = _TENANT_PATIENTS_LIST_CACHE.get(cache_key)
            if hit and hit[0] > now:
                items = copy.deepcopy(hit[1])
                return {"items": items, "total": len(items), "mode": "list", "cached": True}
    items = (
        list_cabinet_clients_compact(tenant_id, limit=limit, offset=offset)
        if compact
        else list_cabinet_clients(tenant_id, limit=limit, offset=offset)
    )
    if ttl > 0 and not os.environ.get("PYTEST_CURRENT_TEST"):
        with _TENANT_PATIENTS_LIST_LOCK:
            _TENANT_PATIENTS_LIST_CACHE[cache_key] = (time.monotonic() + ttl, copy.deepcopy(items))
            if len(_TENANT_PATIENTS_LIST_CACHE) > 400:
                stale_keys = [k for k, (exp, _) in _TENANT_PATIENTS_LIST_CACHE.items() if exp <= time.monotonic()]
                for key in stale_keys[:160]:
                    _TENANT_PATIENTS_LIST_CACHE.pop(key, None)
    return {"items": items, "total": len(items), "mode": "list"}


def _patient_duplicate_http_detail(conflicts: list) -> dict:
    phone_conflict = next((c for c in conflicts if c.get("field") == "phone"), None)
    email_conflict = next((c for c in conflicts if c.get("field") == "email"), None)
    if phone_conflict:
        name = (phone_conflict.get("display_name") or "un autre patient").strip()
        message = f"Ce numéro est déjà enregistré pour la fiche de {name}."
    elif email_conflict:
        name = (email_conflict.get("display_name") or "un autre patient").strip()
        message = f"Cet email est déjà utilisé par la fiche de {name}."
    else:
        message = "Ce numéro ou cet email est déjà associé à une fiche patient existante."
    return {
        "error": "patient_duplicate",
        "message": message,
        "has_conflict": True,
        "conflicts": conflicts,
    }


def _raise_on_blocking_patient_duplicate(
    tenant_id: int,
    *,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    exclude_phone: Optional[str] = None,
) -> None:
    """Bloque si le numéro ou l'email est déjà rattaché à une autre fiche patient."""
    dup = detect_patient_duplicate_conflicts(
        tenant_id,
        phone=phone,
        email=email,
        exclude_phone=exclude_phone,
    )
    conflicts = list(dup.get("conflicts") or [])
    if conflicts:
        raise HTTPException(409, detail=_patient_duplicate_http_detail(conflicts))


@router.get("/patients/duplicate-check")
def tenant_check_patient_duplicate(
    auth: dict = Depends(require_tenant_auth),
    phone: Optional[str] = Query(None, max_length=40),
    email: Optional[str] = Query(None, max_length=254),
    exclude_phone: Optional[str] = Query(None, max_length=40, description="Ignorer ce numéro (fiche en cours d'édition)"),
):
    """Vérifie si un téléphone ou un email est déjà rattaché à une fiche patient."""
    tenant_id = auth["tenant_id"]
    return detect_patient_duplicate_conflicts(
        tenant_id,
        phone=phone,
        email=email,
        exclude_phone=exclude_phone,
    )


@router.get("/patients/{phone}")
def tenant_get_patient(
    phone: str,
    auth: dict = Depends(require_tenant_auth),
    lightweight: bool = Query(False, description="Profil uniquement (plus rapide, sans appels/handoffs)"),
    include_documents: bool = Query(
        False,
        description="Inclure la liste des documents (défaut: non — charger via GET /patients/{phone}/documents)",
    ),
):
    """Fiche patient complète : profil, appels liés, handoffs liés."""
    tenant_id = auth["tenant_id"]
    profile = get_cabinet_client_by_phone(tenant_id, phone)
    if not profile:
        raise HTTPException(404, "Patient not found")

    if lightweight:
        docs = list_patient_documents(tenant_id, phone) if include_documents else []
        return {
            "patient": profile,
            "calls": [],
            "handoffs": [],
            "notes": [],
            "documents": [
                {"id": d.get("id"), "original_name": d.get("original_name"), "mime_type": d.get("mime_type"),
                 "size_bytes": d.get("size_bytes"), "created_at": str(d.get("created_at", ""))}
                for d in docs
            ],
            "insights": {"tags": [], "stats": {}, "recent_past_appointments": []},
        }

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
    insights = compute_patient_insights(tenant_id, phone, notes=notes)
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
        "insights": insights,
    }


class TenantPatientPracticeCreateBody(BaseModel):
    """Création ou complément d'une fiche patient sur le dashboard client (sans passer par un appel vocal)."""

    patient_phone: str = Field(..., max_length=40)
    validated_name: str = Field(..., min_length=2, max_length=160)
    raw_name: Optional[str] = Field(default=None, max_length=160)
    initial_note: Optional[str] = Field(default=None, max_length=4000)
    agenda_motif: Optional[str] = Field(default=None, max_length=240)
    patient_email: Optional[str] = Field(default=None, max_length=254)
    birth_date: Optional[str] = Field(default=None, max_length=10)
    treating_physician_name: Optional[str] = Field(default=None, max_length=200)
    treating_physician_city: Optional[str] = Field(default=None, max_length=120)

    @validator("patient_email")
    def _validate_register_email(cls, v):
        if v is None:
            return None
        raw = str(v).strip()
        if not raw:
            return None
        if not is_valid_contact_email(raw):
            raise ValueError("Email invalide (format attendu: prenom@domaine.fr)")
        return raw

    @validator("birth_date")
    def _validate_register_birth_date(cls, v):
        if v is None:
            return None
        v = v.strip()
        if v == "":
            return ""
        if len(v) != 10 or v[4] != "-" or v[7] != "-":
            raise ValueError("Date de naissance invalide (format attendu: AAAA-MM-JJ)")
        return v

    @validator("treating_physician_name")
    def _validate_register_treating_physician_name(cls, v):
        if v is None:
            return None
        return v.strip()[:200]

    @validator("treating_physician_city")
    def _validate_register_treating_physician_city(cls, v):
        if v is None:
            return None
        return v.strip()[:120]


@router.post("/patients")
def tenant_register_patient_practice(
    body: TenantPatientPracticeCreateBody,
    auth: dict = Depends(require_tenant_auth),
):
    """Enregistre une fiche patient sur le dashboard client (nom validé), ex. depuis l'agenda."""
    tenant_id = auth["tenant_id"]
    phone = normalize_phone_number(body.patient_phone)
    if not phone or not is_valid_patient_phone(body.patient_phone):
        raise HTTPException(
            400,
            "Numéro de téléphone invalide (format attendu : 06 12 34 56 78 ou +33 6 12 34 56 78).",
        )
    vn = body.validated_name.strip()
    if len(vn) < 2:
        raise HTTPException(400, "Nom valide trop court")
    motif = (body.agenda_motif or "").strip()[:240] or None
    rn = (body.raw_name or "").strip()[:160] or None
    patient_email = (body.patient_email or "").strip()[:254] or None
    if patient_email and not is_valid_contact_email(patient_email):
        raise HTTPException(400, "Email invalide (format attendu: prenom@domaine.fr).")

    _raise_on_blocking_patient_duplicate(tenant_id, phone=phone, email=patient_email)

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

    profile_field_kwargs: dict = {}
    if patient_email:
        profile_field_kwargs["email"] = patient_email
    if body.birth_date is not None:
        profile_field_kwargs["birth_date"] = body.birth_date
    if body.treating_physician_name is not None:
        profile_field_kwargs["treating_physician_name"] = body.treating_physician_name
    if body.treating_physician_city is not None:
        profile_field_kwargs["treating_physician_city"] = body.treating_physician_city
    if profile_field_kwargs:
        profile = update_patient_fields(tenant_id, phone, **profile_field_kwargs) or profile

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

    _invalidate_tenant_patients_list_cache(tenant_id)
    return {"ok": True, "patient": profile, "register_mode": register_mode}


class PatientUpdateBody(BaseModel):
    phone: Optional[str] = Field(default=None, max_length=40)
    email: Optional[str] = Field(default=None, max_length=254)
    validated_name: Optional[str] = Field(default=None, max_length=160)
    raw_name: Optional[str] = Field(default=None, max_length=160)
    birth_date: Optional[str] = Field(default=None, max_length=10)
    treating_physician_name: Optional[str] = Field(default=None, max_length=200)
    treating_physician_city: Optional[str] = Field(default=None, max_length=120)

    @validator("phone")
    def _validate_phone(cls, v):
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("Numéro de téléphone requis")
        if not is_valid_patient_phone(v):
            raise ValueError("Numéro de téléphone invalide")
        return v

    @validator("email")
    def _validate_email(cls, v):
        if v is None:
            return None
        v = v.strip()
        if v == "":
            return ""
        if not is_valid_contact_email(v):
            raise ValueError("Email invalide (format attendu: prenom@domaine.fr)")
        return v

    @validator("validated_name")
    def _validate_validated_name(cls, v):
        if v is None:
            return None
        value = str(v).strip()
        if value == "":
            raise ValueError("Nom affiché requis")
        if len(value) < 2:
            raise ValueError("Nom affiché trop court")
        return value[:160]

    @validator("raw_name")
    def _validate_raw_name(cls, v):
        if v is None:
            return None
        return str(v).strip()[:160]

    @validator("birth_date")
    def _validate_birth_date(cls, v):
        if v is None:
            return None
        v = v.strip()
        if v == "":
            return ""
        if len(v) != 10 or v[4] != "-" or v[7] != "-":
            raise ValueError("Date de naissance invalide (format attendu: AAAA-MM-JJ)")
        return v

    @validator("treating_physician_name")
    def _validate_treating_physician_name(cls, v):
        if v is None:
            return None
        return v.strip()[:200]

    @validator("treating_physician_city")
    def _validate_treating_physician_city(cls, v):
        if v is None:
            return None
        return v.strip()[:120]


class PatientMessageBody(BaseModel):
    channel: Literal["sms", "email"] = Field(..., description="Canal d'envoi")
    message: str = Field(..., min_length=1, max_length=4000)
    subject: Optional[str] = Field(default=None, max_length=180)

    @validator("message")
    def _validate_message(cls, v):
        value = str(v or "").strip()
        if not value:
            raise ValueError("Message vide")
        return value

    @validator("subject")
    def _validate_subject(cls, v):
        if v is None:
            return None
        return str(v).strip()[:180]


class PatientsBulkMessageBody(PatientMessageBody):
    phone_numbers: List[str] = Field(default_factory=list, description="Numéros patients ciblés")
    send_to_all: bool = Field(default=False, description="Envoyer à toutes les fiches patients du cabinet")

    @validator("phone_numbers", each_item=True)
    def _validate_phone_numbers(cls, v):
        clean = str(v or "").strip()
        if not clean:
            raise ValueError("Numéro patient vide")
        return clean


class PatientNoteCreateBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    author: Optional[str] = Field(default="Praticien", max_length=120)


class PatientDeleteConfirmBody(BaseModel):
    confirmation_token: str = Field(..., min_length=20, max_length=4096)
    confirmation_phrase: str = Field(..., min_length=1, max_length=40)


def _patient_docs_upload_root() -> str:
    from backend.services.patient_document_storage import LEGACY_PATIENT_DOSSIER_ROOT

    return LEGACY_PATIENT_DOSSIER_ROOT


def _patient_dossier_download_response(doc: dict, tenant_id: int, phone_norm: str):
    """Réponse HTTP pour télécharger un document fiche patient (S3, disque neuf ou legacy)."""
    filename_field = str(doc.get("filename") or "").strip()
    if not patient_dossier_exists(filename_field, tenant_id, phone_norm):
        raise HTTPException(404, "File not found on disk")

    original = str(doc.get("original_name") or "document")
    mime = str(doc.get("mime_type") or "application/octet-stream")

    if filename_field.startswith("patient_docs/") and use_s3_storage():
        content = read_document(filename_field)
        return Response(
            content=content,
            media_type=mime,
            headers={"Content-Disposition": content_disposition_attachment(original)},
        )
    if filename_field.startswith("patient_docs/"):
        filepath = patient_dossier_local_filepath(filename_field)
        return FileResponse(filepath, filename=original, media_type=mime)

    filepath = os.path.join(_patient_docs_upload_root(), str(tenant_id), phone_norm, filename_field)
    return FileResponse(filepath, filename=original, media_type=mime)


def _migrate_patient_docs_upload_dir(tenant_id: int, old_phone: str, new_phone: str) -> None:
    """Déplace le dossier local des pièces jointes patient après changement de numéro."""
    import shutil

    old_norm = normalize_phone_number(old_phone) or str(old_phone or "").strip()
    new_norm = normalize_phone_number(new_phone) or str(new_phone or "").strip()
    if not old_norm or not new_norm or old_norm == new_norm:
        return
    old_dir = os.path.join(_patient_docs_upload_root(), str(tenant_id), old_norm)
    new_dir = os.path.join(_patient_docs_upload_root(), str(tenant_id), new_norm)
    if not os.path.isdir(old_dir):
        return
    if os.path.isdir(new_dir):
        for name in os.listdir(old_dir):
            src = os.path.join(old_dir, name)
            dst = os.path.join(new_dir, name)
            if os.path.isfile(src) and not os.path.exists(dst):
                shutil.move(src, dst)
        try:
            os.rmdir(old_dir)
        except OSError:
            pass
    else:
        os.makedirs(os.path.dirname(new_dir), exist_ok=True)
        shutil.move(old_dir, new_dir)


@router.patch("/patients/{phone}")
def tenant_update_patient(
    phone: str,
    body: PatientUpdateBody,
    auth: dict = Depends(require_tenant_auth),
):
    """Met à jour les champs modifiables d'un patient (email, téléphone, etc.)."""
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

    payload = body.model_dump(exclude_unset=True)
    phone_changed = False
    previous_phone = profile.get("phone") or phone_norm
    current_phone = phone
    updated = profile

    if "phone" in payload:
        new_phone_raw = payload.pop("phone")
        new_phone_norm = normalize_phone_number(new_phone_raw or "")
        if new_phone_norm and new_phone_norm != phone_norm:
            dup = detect_patient_duplicate_conflicts(
                tenant_id,
                phone=new_phone_norm,
                exclude_phone=phone_norm,
            )
            phone_conflicts = [c for c in dup.get("conflicts") or [] if c.get("field") == "phone"]
            if phone_conflicts:
                raise HTTPException(409, detail=_patient_duplicate_http_detail(phone_conflicts))
            try:
                updated = change_cabinet_client_phone(tenant_id, phone, new_phone_raw)
            except PatientPhoneChangeError as exc:
                if exc.code == "not_found":
                    raise HTTPException(404, "Fiche patient introuvable pour ce cabinet.")
                if exc.code == "invalid_phone":
                    raise HTTPException(422, "Numéro de téléphone invalide")
                if exc.code == "phone_conflict":
                    raise HTTPException(
                        409,
                        detail=_patient_duplicate_http_detail(
                            [
                                {
                                    "field": "phone",
                                    "phone": new_phone_norm,
                                    "display_name": "Autre patient",
                                    "email": "",
                                }
                            ]
                        ),
                    )
                raise HTTPException(500, "Impossible de modifier le numéro de téléphone.")
            _migrate_patient_docs_upload_dir(tenant_id, phone_norm, new_phone_norm)
            phone_changed = True
            current_phone = updated.get("phone") or new_phone_norm
            phone_norm = normalize_phone_number(current_phone) or current_phone

    if "email" in payload:
        next_email = payload.get("email")
        if next_email is not None and str(next_email).strip():
            _raise_on_blocking_patient_duplicate(
                tenant_id,
                phone=phone_norm,
                email=str(next_email).strip(),
                exclude_phone=phone_norm,
            )

    validated_name = payload.pop("validated_name", None)
    raw_name = payload.pop("raw_name", None)
    if validated_name is not None:
        name_updated = upsert_cabinet_client(
            tenant_id,
            current_phone,
            validated_name=str(validated_name).strip(),
            raw_name=str(raw_name).strip() if raw_name is not None else str(validated_name).strip(),
        )
        if not name_updated:
            raise HTTPException(500, "Impossible de mettre à jour le nom du patient.")
        updated = name_updated

    if payload:
        field_updated = update_patient_fields(
            tenant_id,
            current_phone,
            email=payload.get("email"),
            birth_date=payload.get("birth_date"),
            treating_physician_name=payload.get("treating_physician_name"),
            treating_physician_city=payload.get("treating_physician_city"),
        )
        if field_updated:
            updated = field_updated
        elif not phone_changed:
            logger.error(
                "tenant_update_patient: update_patient_fields a renvoyé None tenant=%s phone=%s fields=%s",
                tenant_id,
                phone_norm,
                sorted(payload.keys()),
            )
            raise HTTPException(
                500,
                "Impossible de mettre à jour la fiche patient. "
                "Si le problème persiste, contactez le support (migration profil 040).",
            )
    logger.info(
        "tenant_update_patient ok tenant=%s phone=%s phone_changed=%s email_set=%s",
        tenant_id,
        phone_norm,
        phone_changed,
        bool((updated.get("email") or "").strip()),
    )
    _invalidate_tenant_patients_list_cache(tenant_id)
    resp: Dict[str, Any] = {"ok": True, "patient": updated}
    if phone_changed:
        resp["previous_phone"] = previous_phone
    return resp


def _patient_display_name(profile: Dict[str, Any]) -> str:
    return (
        str(
            profile.get("display_name")
            or profile.get("validated_name")
            or profile.get("raw_name")
            or "Patient"
        ).strip()
        or "Patient"
    )


def _tenant_cabinet_name_for_patient_messages(tenant_id: int) -> str:
    detail = _get_tenant_detail(tenant_id) or {}
    return str(detail.get("name") or "Votre cabinet").strip() or "Votre cabinet"


@router.post("/patients/{phone}/messages")
def tenant_send_patient_message(
    phone: str,
    body: PatientMessageBody,
    auth: dict = Depends(require_tenant_auth),
):
    """Envoie un message SMS ou email à un patient unique."""
    tenant_id = auth["tenant_id"]
    phone_norm = normalize_phone_number(phone) or phone.strip()
    profile = get_cabinet_client_by_phone(tenant_id, phone_norm)
    if not profile:
        raise HTTPException(404, "Patient not found")

    patient_name = _patient_display_name(profile)
    channel = body.channel
    message = body.message.strip()
    if channel == "sms":
        recipient = normalize_phone_number(str(profile.get("phone") or phone_norm))
        if not recipient:
            raise HTTPException(422, "Numéro patient invalide")
        ok, err = send_sms_message(recipient, message)
        if not ok:
            raise HTTPException(502, err or "Envoi SMS échoué")
        return {"ok": True, "channel": "sms", "sent_to": recipient}

    recipient_email = str(profile.get("email") or "").strip().lower()
    if not recipient_email:
        raise HTTPException(400, "Le patient n'a pas d'adresse email renseignée.")
    if not is_valid_contact_email(recipient_email):
        raise HTTPException(422, "Adresse email patient invalide.")
    ok, err = send_patient_message_email(
        to=recipient_email,
        patient_name=patient_name,
        cabinet_name=_tenant_cabinet_name_for_patient_messages(tenant_id),
        subject=(body.subject or "").strip() or "Message de votre cabinet",
        message=message,
    )
    if not ok:
        raise HTTPException(502, err or "Envoi email échoué")
    return {"ok": True, "channel": "email", "sent_to": recipient_email}


@router.post("/patients/messages/bulk")
def tenant_send_bulk_patient_message(
    body: PatientsBulkMessageBody,
    auth: dict = Depends(require_tenant_auth),
):
    """Envoi groupé SMS/email vers une sélection de patients ou tous les patients du cabinet."""
    tenant_id = auth["tenant_id"]
    send_to_all = bool(body.send_to_all)
    channel = body.channel
    message = body.message.strip()

    targets: List[Dict[str, Any]] = []
    if send_to_all:
        batch_size = 500
        max_recipients = 3000
        offset = 0
        while len(targets) < max_recipients:
            batch = list_cabinet_clients(tenant_id, limit=batch_size, offset=offset)
            if not batch:
                break
            targets.extend(batch)
            if len(batch) < batch_size:
                break
            offset += batch_size
        targets = targets[:max_recipients]
    else:
        normalized_phones: List[str] = []
        for raw in body.phone_numbers:
            norm = normalize_phone_number(raw)
            if norm:
                normalized_phones.append(norm)
        normalized_phones = list(dict.fromkeys(normalized_phones))
        if not normalized_phones:
            raise HTTPException(400, "Sélectionnez au moins un patient.")
        profiles_by_phone = get_cabinet_clients_by_phones(tenant_id, normalized_phones)
        for phone_norm in normalized_phones:
            profile = profiles_by_phone.get(phone_norm)
            if profile:
                targets.append(profile)
            else:
                row = get_cabinet_client_by_phone(tenant_id, phone_norm)
                if row:
                    targets.append(row)
                else:
                    targets.append({"phone": phone_norm, "display_name": "", "email": ""})

    if not targets:
        raise HTTPException(400, "Aucun patient trouvé pour cet envoi.")

    cabinet_name = _tenant_cabinet_name_for_patient_messages(tenant_id)
    requested_count = len(targets)
    sent_count = 0
    failed_count = 0
    skipped_count = 0
    results: List[Dict[str, Any]] = []

    for row in targets:
        phone_norm = normalize_phone_number(str(row.get("phone") or ""))
        patient_name = _patient_display_name(row)

        if channel == "sms":
            if not phone_norm:
                skipped_count += 1
                results.append(
                    {
                        "phone": str(row.get("phone") or ""),
                        "patient_name": patient_name,
                        "status": "skipped",
                        "reason": "numéro manquant",
                    }
                )
                continue
            ok, err = send_sms_message(phone_norm, message)
            if ok:
                sent_count += 1
                results.append({"phone": phone_norm, "patient_name": patient_name, "status": "sent"})
            else:
                failed_count += 1
                results.append(
                    {
                        "phone": phone_norm,
                        "patient_name": patient_name,
                        "status": "failed",
                        "reason": (err or "envoi sms échoué")[:220],
                    }
                )
            continue

        recipient_email = str(row.get("email") or "").strip().lower()
        if not recipient_email:
            skipped_count += 1
            results.append(
                {
                    "phone": phone_norm,
                    "patient_name": patient_name,
                    "status": "skipped",
                    "reason": "email manquant",
                }
            )
            continue
        if not is_valid_contact_email(recipient_email):
            skipped_count += 1
            results.append(
                {
                    "phone": phone_norm,
                    "patient_name": patient_name,
                    "status": "skipped",
                    "reason": "email invalide",
                }
            )
            continue
        ok, err = send_patient_message_email(
            to=recipient_email,
            patient_name=patient_name,
            cabinet_name=cabinet_name,
            subject=(body.subject or "").strip() or "Message de votre cabinet",
            message=message,
        )
        if ok:
            sent_count += 1
            results.append(
                {
                    "phone": phone_norm,
                    "patient_name": patient_name,
                    "email": recipient_email,
                    "status": "sent",
                }
            )
        else:
            failed_count += 1
            results.append(
                {
                    "phone": phone_norm,
                    "patient_name": patient_name,
                    "email": recipient_email,
                    "status": "failed",
                    "reason": (err or "envoi email échoué")[:220],
                }
            )

    logger.info(
        "tenant bulk patient message tenant=%s channel=%s scope=%s requested=%s sent=%s failed=%s skipped=%s",
        tenant_id,
        channel,
        "all" if send_to_all else "selected",
        requested_count,
        sent_count,
        failed_count,
        skipped_count,
    )
    return {
        "ok": failed_count == 0,
        "channel": channel,
        "scope": "all" if send_to_all else "selected",
        "requested_count": requested_count,
        "sent_count": sent_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "results": results[:200],
    }


def _build_patient_questionnaire_link(token: str) -> str:
    import os as _os

    base = (
        _os.getenv("PUBLIC_BASE_URL")
        or _os.getenv("CLIENT_APP_ORIGIN")
        or _os.getenv("FRONT_BASE_URL")
        or "https://www.uwiapp.com"
    ).strip().rstrip("/")
    return f"{base}/questionnaire/{token}"


class QuestionnaireSaveBody(BaseModel):
    answers: Dict[str, Any] = Field(default_factory=dict)


@router.get("/patients/{phone}/questionnaire")
def tenant_get_patient_questionnaire(
    phone: str,
    auth: dict = Depends(require_tenant_auth),
):
    """État du questionnaire médical d'onboarding du patient (+ schéma)."""
    from backend.patient_questionnaire import (
        get_questionnaire,
        merge_profile_into_answers,
        questionnaire_schema,
    )

    tenant_id = auth["tenant_id"]
    profile = get_cabinet_client_by_phone(tenant_id, phone)
    if not profile:
        raise HTTPException(404, "Fiche patient introuvable pour ce cabinet. Créez d'abord la fiche.")
    state = get_questionnaire(tenant_id, phone)
    # Pré-remplissage : on complète les champs profil vides avec ce que la fiche sait déjà.
    state["answers"] = merge_profile_into_answers(profile, state.get("answers"))
    return {"ok": True, "schema": questionnaire_schema(), "questionnaire": state}


@router.put("/patients/{phone}/questionnaire")
def tenant_save_patient_questionnaire(
    phone: str,
    body: QuestionnaireSaveBody,
    auth: dict = Depends(require_tenant_auth),
):
    """Le praticien remplit/enregistre lui-même le questionnaire depuis la fiche."""
    from backend.patient_questionnaire import (
        FILLED_BY_PRACTITIONER,
        STATUS_COMPLETED,
        apply_answers_to_patient,
        questionnaire_schema,
        sanitize_answers,
        save_questionnaire,
    )

    tenant_id = auth["tenant_id"]
    phone_norm = normalize_phone_number(phone) or phone.strip()
    profile = get_cabinet_client_by_phone(tenant_id, phone)
    if not profile:
        raise HTTPException(404, "Fiche patient introuvable pour ce cabinet. Créez d'abord la fiche.")

    answers = sanitize_answers(body.answers)
    state = save_questionnaire(
        tenant_id,
        phone_norm,
        answers=answers,
        status=STATUS_COMPLETED,
        filled_by=FILLED_BY_PRACTITIONER,
        mark_completed=True,
    )
    apply_answers_to_patient(
        tenant_id,
        phone_norm,
        answers,
        source_label="rempli par le praticien",
        add_context_note=False,
    )
    return {"ok": True, "schema": questionnaire_schema(), "questionnaire": state}


@router.post("/patients/{phone}/questionnaire/send")
def tenant_send_patient_questionnaire(
    phone: str,
    auth: dict = Depends(require_tenant_auth),
):
    """Génère un lien sécurisé et l'envoie au patient par email pour qu'il remplisse le questionnaire."""
    from backend.patient_questionnaire import (
        STATUS_SENT,
        get_questionnaire,
        make_questionnaire_token,
        save_questionnaire,
    )
    from backend.services.email_service import send_patient_questionnaire_email

    tenant_id = auth["tenant_id"]
    phone_norm = normalize_phone_number(phone) or phone.strip()
    profile = get_cabinet_client_by_phone(tenant_id, phone)
    if not profile:
        raise HTTPException(404, "Fiche patient introuvable pour ce cabinet. Créez d'abord la fiche.")

    to_email = (profile.get("email") or "").strip()
    if not to_email:
        raise HTTPException(400, "Ajoutez d'abord l'email du patient pour lui envoyer le questionnaire.")

    detail = _get_tenant_detail(tenant_id)
    cabinet_name = (detail or {}).get("name") or "votre cabinet"
    patient_name = (
        profile.get("display_name") or profile.get("validated_name") or profile.get("raw_name") or ""
    ).strip()

    token = make_questionnaire_token(tenant_id, phone_norm)
    link = _build_patient_questionnaire_link(token)
    ok, err = send_patient_questionnaire_email(to_email, patient_name, cabinet_name, link)
    if not ok:
        raise HTTPException(502, err or "Envoi de l'email échoué.")

    current = get_questionnaire(tenant_id, phone_norm)
    state = save_questionnaire(
        tenant_id,
        phone_norm,
        answers=current.get("answers") or {},
        status=STATUS_SENT,
        filled_by=current.get("filled_by") or "",
        sent_to_email=to_email,
    )
    return {"ok": True, "sent_to": to_email, "questionnaire": state}


@router.get("/patients/{phone}/history")
def tenant_patient_history(
    phone: str,
    auth: dict = Depends(require_tenant_auth),
    limit: int = Query(50, ge=1, le=100),
):
    """Timeline des interactions patient (appels, notes, documents, RDV passés, transferts)."""
    tenant_id = auth["tenant_id"]
    profile = get_cabinet_client_by_phone(tenant_id, phone)
    if not profile:
        raise HTTPException(404, "Patient not found")

    phone_norm = normalize_phone_number(phone)
    related_calls: List[Dict[str, Any]] = []
    detail = _get_tenant_detail(tenant_id)
    if detail:
        tz_name = _tenant_timezone(detail)
        raw = _get_calls_list(tenant_id=tenant_id, days=180, limit=80, tenant_detail=detail)
        for item in raw.get("items") or []:
            item_phone = normalize_phone_number(item.get("customer_number") or "")
            if item_phone != phone_norm:
                continue
            related_calls.append(
                {
                    "call_id": (item.get("call_id") or "").strip(),
                    "status": _resolve_call_status(item, None),
                    "summary": item.get("summary") or "",
                    "followup_state": item.get("followup_state") or "new",
                    "started_at": item.get("started_at") or item.get("last_event_at") or "",
                }
            )

    related_handoffs: List[Dict[str, Any]] = []
    try:
        for h in list_handoffs(tenant_id, status=None, target=None, limit=80):
            h_phone = normalize_phone_number(h.get("patient_phone") or "")
            if h_phone == phone_norm:
                related_handoffs.append(h)
    except Exception:
        pass

    notes = list_patient_notes(tenant_id, phone, limit=200)
    docs = list_patient_documents(tenant_id, phone)
    return build_patient_history(
        tenant_id,
        phone,
        calls=related_calls,
        handoffs=related_handoffs,
        notes=notes,
        documents=docs,
        limit=limit,
    )


@router.get("/patients/{phone}/appointments")
def tenant_patient_appointments(
    phone: str,
    auth: dict = Depends(require_tenant_auth),
    upcoming_days: int = Query(14, ge=1, le=366),
    skip_google: bool = Query(False, description="RDV locaux/public_bookings uniquement (affichage rapide)"),
):
    """RDV à venir d'un patient sans charger tout l'agenda cabinet."""
    tenant_id = auth["tenant_id"]
    profile = get_cabinet_client_by_phone(tenant_id, phone)
    if not profile:
        raise HTTPException(404, "Patient not found")
    slots = _collect_patient_upcoming_appointment_slots(
        tenant_id,
        phone,
        upcoming_days=upcoming_days,
        skip_google=skip_google,
    )
    return {"slots": slots, "upcoming_days": upcoming_days}


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



@router.get("/patients/{phone}/documents")
def tenant_list_patient_documents_route(
    phone: str,
    auth: dict = Depends(require_tenant_auth),
):
    """Liste les documents d'une fiche patient (chargement différé côté dashboard)."""
    tenant_id = auth["tenant_id"]
    profile = get_cabinet_client_by_phone(tenant_id, phone)
    if not profile:
        raise HTTPException(404, "Patient not found")
    docs = list_patient_documents(tenant_id, phone)
    return {
        "items": [
            {
                "id": d.get("id"),
                "original_name": d.get("original_name"),
                "mime_type": d.get("mime_type"),
                "size_bytes": d.get("size_bytes"),
                "created_at": str(d.get("created_at", "")),
            }
            for d in docs
        ],
    }


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
    mime_type = file.content_type or "application/octet-stream"

    try:
        storage_key, _stored_name = save_patient_dossier_upload(
            tenant_id,
            phone_norm,
            content,
            file.filename,
            mime_type,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    try:
        doc = insert_patient_document(
            tenant_id,
            phone,
            filename=storage_key,
            original_name=file.filename,
            mime_type=mime_type,
            size_bytes=len(content),
        )
    except Exception:
        delete_patient_dossier(storage_key, tenant_id, phone_norm)
        logger.exception(
            "tenant_upload_patient_document db insert failed tenant=%s phone=%s",
            tenant_id,
            phone_norm,
        )
        raise HTTPException(500, "Impossible d'enregistrer le document")

    doc_id = doc.get("id")
    if not doc_id:
        delete_patient_dossier(storage_key, tenant_id, phone_norm)
        raise HTTPException(500, "Impossible d'enregistrer le document")

    return {
        "ok": True,
        "document": {
            "id": doc_id,
            "original_name": file.filename,
            "mime_type": mime_type,
            "size_bytes": len(content),
            "created_at": str(doc.get("created_at", "")),
        },
    }


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
    return _patient_dossier_download_response(doc, tenant_id, phone_norm)


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
    delete_patient_dossier(str(doc.get("filename") or ""), tenant_id, phone_norm)

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
    filename_field = str(doc.get("filename") or "").strip()
    if not patient_dossier_exists(filename_field, tenant_id, phone_norm):
        raise HTTPException(404, "Fichier introuvable sur le serveur")

    detail = _get_tenant_detail(tenant_id)
    cabinet_name = (detail or {}).get("name") or ""
    patient_name = profile.get("display_name") or profile.get("raw_name") or ""

    import tempfile

    file_bytes = read_patient_dossier(filename_field, tenant_id, phone_norm)
    ext = os.path.splitext(str(doc.get("original_name") or "document"))[1] or ".bin"
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        ok, err = send_patient_document_email(
            to=patient_email,
            patient_name=patient_name,
            cabinet_name=cabinet_name,
            doc_original_name=doc.get("original_name", "document"),
            doc_path=tmp_path,
            doc_mime_type=doc.get("mime_type", "application/octet-stream"),
        )
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
    if not ok:
        raise HTTPException(500, err or "Impossible d'envoyer l'email")

    return {"ok": True, "sent_to": patient_email}


@router.post("/patients/{phone}/delete-request")
def tenant_request_delete_patient(
    phone: str,
    auth: dict = Depends(require_tenant_auth),
):
    """
    Étape 1: prépare une suppression de fiche patient.
    Retourne un récapitulatif + un token de confirmation court (15 min).
    """
    tenant_id = auth["tenant_id"]
    phone_norm = normalize_phone_number(phone) or phone.strip()
    profile = get_cabinet_client_by_phone(tenant_id, phone_norm)
    if not profile:
        raise HTTPException(404, "Patient not found")

    notes = list_patient_notes(tenant_id, phone_norm, limit=300)
    docs = list_patient_documents(tenant_id, phone_norm)
    token, exp = _patient_delete_token_issue(tenant_id, phone_norm, ttl_sec=900)
    display_name = (
        str(
            profile.get("display_name")
            or profile.get("validated_name")
            or profile.get("raw_name")
            or "Patient"
        ).strip()
        or "Patient"
    )
    return {
        "ok": True,
        "confirmation_token": token,
        "expires_at": datetime.fromtimestamp(exp, timezone.utc).isoformat(),
        "summary": {
            "phone": phone_norm,
            "display_name": display_name,
            "notes_count": len(notes),
            "documents_count": len(docs),
            "documents": [
                {
                    "id": d.get("id"),
                    "original_name": d.get("original_name"),
                }
                for d in docs[:5]
            ],
        },
    }


@router.post("/patients/{phone}/delete-confirm")
def tenant_confirm_delete_patient(
    phone: str,
    body: PatientDeleteConfirmBody,
    auth: dict = Depends(require_tenant_auth),
):
    """
    Étape 2: suppression définitive d'une fiche patient après confirmation explicite.
    Requiert:
    - confirmation_phrase == "SUPPRIMER"
    - confirmation_token valide (tenant + phone + expiration)
    """
    tenant_id = auth["tenant_id"]
    phone_norm = normalize_phone_number(phone) or phone.strip()
    profile = get_cabinet_client_by_phone(tenant_id, phone_norm)
    if not profile:
        raise HTTPException(404, "Patient not found")

    if str(body.confirmation_phrase or "").strip().upper() != "SUPPRIMER":
        raise HTTPException(
            400,
            "Confirmation invalide. Saisissez exactement SUPPRIMER pour confirmer.",
        )
    if not _patient_delete_token_verify(body.confirmation_token, tenant_id, phone_norm):
        raise HTTPException(400, "Token de confirmation invalide ou expiré.")

    notes = list_patient_notes(tenant_id, phone_norm, limit=300)
    docs = list_patient_documents(tenant_id, phone_norm)

    deleted_notes = 0
    for n in notes:
        nid = int(n.get("id") or 0)
        if nid and delete_patient_note(tenant_id, nid, patient_phone=phone_norm):
            deleted_notes += 1

    deleted_documents = 0
    for d in docs:
        did = int(d.get("id") or 0)
        if not did:
            continue
        filename = str(d.get("filename") or "").strip()
        if filename:
            delete_patient_dossier(filename, tenant_id, phone_norm)
        if delete_patient_document(tenant_id, did, patient_phone=phone_norm):
            deleted_documents += 1

    deleted_profile = delete_cabinet_client_by_phone(tenant_id, phone_norm)
    if not deleted_profile:
        raise HTTPException(500, "Suppression impossible (fiche non supprimée).")

    try:
        from backend.patient_v2_db import delete_patient_v2_data

        delete_patient_v2_data(tenant_id, phone_norm)
    except Exception:
        logger.warning("delete_patient_v2_data failed tenant=%s", tenant_id, exc_info=True)

    logger.info(
        "tenant_delete_patient_confirmed tenant=%s phone=%s notes=%s docs=%s",
        tenant_id,
        phone_norm,
        deleted_notes,
        deleted_documents,
    )
    return {
        "ok": True,
        "deleted": {
            "profile": True,
            "notes": deleted_notes,
            "documents": deleted_documents,
        },
    }


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


class TenantCallbackRequestUpdateBody(BaseModel):
    status: Optional[str] = None


@router.get("/callback-requests")
def tenant_list_callback_requests(
    auth: dict = Depends(require_tenant_auth),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    from backend.public_bookings_pg import list_callback_requests

    tenant_id = auth["tenant_id"]
    items = list_callback_requests(tenant_id, status=status, limit=limit)
    return {"items": items, "total": len(items)}


@router.patch("/callback-requests/{request_id}")
def tenant_patch_callback_request(
    request_id: str,
    body: TenantCallbackRequestUpdateBody,
    auth: dict = Depends(require_tenant_auth),
):
    from backend.public_bookings_pg import update_callback_request_status, sync_handoff_status_from_callback, get_callback_request_by_id

    tenant_id = auth["tenant_id"]
    status = (body.status or "").strip().lower()
    if status not in {"processed", "cancelled", "new"}:
        raise HTTPException(400, "Invalid callback request status")
    existing = get_callback_request_by_id(tenant_id, request_id)
    item = update_callback_request_status(
        tenant_id,
        request_id,
        status=status,
        handled_by=auth.get("email") or auth.get("sub") or "tenant",
    )
    if not item:
        raise HTTPException(404, "Callback request not found")
    handoff_id = (existing or item or {}).get("handoff_id")
    if handoff_id and status in {"processed", "cancelled"}:
        sync_handoff_status_from_callback(tenant_id, int(handoff_id), status)
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


def _patient_phone_lookup_keys(phone: str) -> List[str]:
    norm = normalize_phone_number(phone) or str(phone or "").strip()
    keys = list(dict.fromkeys(_cabinet_client_phone_lookup_keys(norm) or ([norm] if norm else [])))
    return [k for k in keys if k]


def _local_appointment_rows_for_patient(
    tenant_id: int,
    phone_keys: List[str],
    day_start: datetime,
    day_end: datetime,
    tz_name: str,
) -> List[Dict[str, Any]]:
    if not phone_keys:
        return []
    rows: List[Dict[str, Any]] = []
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_SLOTS_URL")
    if url:
        try:
            from backend.pg_pool import pg_connection_for

            with pg_connection_for(url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT a.id, a.slot_id, a.name, a.contact, a.contact_type, a.motif,
                               a.google_event_id, s.start_ts, a.booking_origin
                        FROM appointments a
                        JOIN slots s ON s.id = a.slot_id
                        WHERE a.tenant_id = %s
                          AND a.contact = ANY(%s)
                          AND s.start_ts >= %s
                          AND s.start_ts < %s
                        ORDER BY s.start_ts ASC
                        """,
                        (
                            tenant_id,
                            phone_keys,
                            day_start.astimezone(timezone.utc),
                            day_end.astimezone(timezone.utc),
                        ),
                    )
                    for row in cur.fetchall() or []:
                        start_local = _parse_dt(row.get("start_ts"), tz_name)
                        if not start_local:
                            continue
                        rows.append(
                            {
                                "id": int(row.get("id") or 0),
                                "slot_id": int(row.get("slot_id") or 0),
                                "name": row.get("name") or "",
                                "contact": row.get("contact") or "",
                                "contact_type": row.get("contact_type") or "",
                                "motif": row.get("motif") or "",
                                "booking_origin": row.get("booking_origin") or "",
                                "google_event_id": row.get("google_event_id") or "",
                                "date": start_local.strftime("%Y-%m-%d"),
                                "time": start_local.strftime("%H:%M"),
                            }
                        )
                    return rows
        except Exception as exc:
            logger.debug("patient appointments pg lookup failed tenant=%s: %s", tenant_id, exc)

    ensure_tenant_config()
    placeholders = ",".join("?" for _ in phone_keys)
    conn = get_conn()
    try:
        _migrate_sqlite_add_booking_origin(conn)
        sqlite_rows = conn.execute(
            f"""
            SELECT a.id, a.slot_id, a.name, a.contact, a.contact_type, a.motif,
                   a.booking_origin, a.google_event_id, s.date, s.time
            FROM appointments a
            JOIN slots s ON s.id = a.slot_id AND s.tenant_id = a.tenant_id
            WHERE a.tenant_id = ?
              AND a.contact IN ({placeholders})
              AND s.date >= ?
              AND s.date < ?
            ORDER BY s.date ASC, s.time ASC
            """,
            (tenant_id, *phone_keys, day_start.strftime("%Y-%m-%d"), day_end.strftime("%Y-%m-%d")),
        ).fetchall()
        for row in sqlite_rows:
            rows.append(dict(row))
    finally:
        conn.close()
    return rows


def _collect_patient_upcoming_appointment_slots(
    tenant_id: int,
    phone: str,
    *,
    upcoming_days: int,
    skip_google: bool = False,
) -> List[Dict[str, Any]]:
    """RDV à venir d'un patient sans charger tout l'agenda cabinet."""
    phone_keys = _patient_phone_lookup_keys(phone)
    if not phone_keys:
        return []

    detail = _get_tenant_detail_for_agenda_cached(tenant_id)
    if not detail:
        return []

    params = detail.get("params") or {}
    tz_name = _tenant_timezone(detail)
    tz = _get_zoneinfo(tz_name)
    now_local = datetime.now(tz)
    day_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=max(1, int(upcoming_days)))
    profile_cache: Dict[str, Optional[Dict[str, Any]]] = {}
    slots: List[Dict[str, Any]] = []
    seen_event_ids: set[str] = set()

    for row in _local_appointment_rows_for_patient(tenant_id, phone_keys, day_start, day_end, tz_name):
        start_local = _parse_dt(f"{row['date']}T{row['time']}:00", tz_name)
        if not start_local:
            continue
        if start_local < now_local:
            continue
        end_local = start_local + timedelta(minutes=30)
        patient_name = _resolve_agenda_patient_name_cached(
            tenant_id,
            row.get("contact"),
            row.get("name"),
            profile_cache,
        )
        meta = _agenda_slot_meta(
            start_local=start_local,
            end_local=end_local,
            contact_type=str(row.get("contact_type") or ""),
        )
        event_id = str(row.get("google_event_id") or row.get("id") or "")
        if event_id:
            seen_event_ids.add(event_id)
        slots.append(
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
                "done": False,
                "current": start_local <= now_local < end_local,
                "event_id": event_id,
                "appointment_id": int(row.get("id") or 0),
                "slot_id": int(row.get("slot_id") or 0),
                "can_cancel": True,
                "can_reschedule": True,
                **meta,
            }
        )

    try:
        from backend.public_bookings_pg import fetch_public_bookings_for_agenda

        public_slots = fetch_public_bookings_for_agenda(
            tenant_id,
            day_start,
            day_end,
            tz_name,
            now_local,
            include_past_on_date=False,
        )
        phone_key_set = set(phone_keys)
        for item in public_slots:
            pn = normalize_phone_number(item.get("patient_phone") or "")
            if pn and pn not in phone_key_set:
                continue
            event_id = str(item.get("event_id") or "")
            if event_id and event_id in seen_event_ids:
                continue
            if event_id:
                seen_event_ids.add(event_id)
            slots.append(item)
    except Exception as exc:
        logger.debug("patient appointments public_bookings skipped tenant=%s: %s", tenant_id, exc)

    google_cal = (
        not skip_google
        and (params.get("calendar_provider") or "").strip() == "google"
        and bool((params.get("calendar_id") or "").strip())
    )
    if google_cal:
        try:
            cal_id = (params.get("calendar_id") or "").strip()
            service = GoogleCalendarService(cal_id)
            search_terms = list(
                dict.fromkeys(
                    t
                    for t in (
                        phone_keys[0] if phone_keys else "",
                        (phone_keys[0][3:] if phone_keys and phone_keys[0].startswith("+33") else ""),
                        (f"0{phone_keys[0][3:]}" if phone_keys and phone_keys[0].startswith("+33") else ""),
                    )
                    if t
                )
            )[:2]
            for term in search_terms:
                result = (
                    service.service.events()
                    .list(
                        calendarId=cal_id,
                        timeMin=day_start.isoformat(),
                        timeMax=day_end.isoformat(),
                        singleEvents=True,
                        orderBy="startTime",
                        q=term,
                        fields="items(id,summary,description,start,end)",
                    )
                    .execute()
                )
                for event in result.get("items") or []:
                    event_id = str(event.get("id") or "")
                    if not event_id or event_id in seen_event_ids:
                        continue
                    description = (event.get("description") or "").strip()
                    patient_contact = _extract_calendar_event_patient_contact(description)
                    contact_norm = normalize_phone_number(patient_contact)
                    if contact_norm and contact_norm not in phone_key_set:
                        continue
                    raw_start = (event.get("start") or {}).get("dateTime") or (event.get("start") or {}).get("date")
                    start_dt = _parse_dt(raw_start, tz_name)
                    if not start_dt:
                        continue
                    start_local = start_dt.astimezone(tz)
                    if start_local < now_local:
                        continue
                    end_raw = (event.get("end") or {}).get("dateTime") or (event.get("end") or {}).get("date")
                    end_dt = _parse_dt(end_raw, tz_name)
                    end_local = end_dt.astimezone(tz) if end_dt else start_local + timedelta(minutes=30)
                    summary = (event.get("summary") or "").strip()
                    patient = summary.replace("RDV - ", "", 1).strip() if summary.startswith("RDV - ") else (summary or "Patient")
                    motif = _extract_google_description_line(description, "Motif") or "Consultation"
                    source = "UWI" if summary.startswith("RDV - ") or "Patient:" in description else "EXTERNAL"
                    meta = _agenda_slot_meta(
                        start_local=start_local,
                        end_local=end_local,
                        description=description,
                    )
                    seen_event_ids.add(event_id)
                    slots.append(
                        {
                            "date": start_local.strftime("%Y-%m-%d"),
                            "hour": start_local.strftime("%Hh"),
                            "start_iso": start_local.isoformat(),
                            "patient": patient,
                            "patient_phone": contact_norm or phone_keys[0],
                            "motif": motif,
                            "type": motif,
                            "source": source,
                            "booking_origin": "google",
                            "done": end_local <= now_local,
                            "current": start_local <= now_local < end_local,
                            "event_id": event_id,
                            "appointment_id": 0,
                            "slot_id": 0,
                            "can_cancel": source == "UWI",
                            "can_reschedule": source == "UWI",
                            **meta,
                        }
                    )
        except Exception as exc:
            logger.debug("patient appointments google search failed tenant=%s: %s", tenant_id, exc)

    slots.sort(key=lambda item: item.get("start_iso") or "")
    return slots


@router.get("/agenda")
def tenant_agenda(
    auth: dict = Depends(require_tenant_auth),
    date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    upcoming_days: int = Query(1, ge=1, le=366),
    compact: bool = Query(False),
    lightweight: bool = Query(False, description="Mode allégé (sans enrichissement profils patients)"),
    skip_google: bool = Query(
        False,
        description="Réponse immédiate DB (public_bookings + local) sans appel Google — enrichissement ensuite",
    ),
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
    fast_mode = compact_mode or lightweight
    slots: List[Dict[str, Any]] = []
    profile_cache: Dict[str, Optional[Dict[str, Any]]] = {}

    mirror_enabled = _google_mirror_enabled(detail) and not lightweight
    mirror_lookup: Optional[Dict[str, List[Dict[str, Any]]]] = None

    google_cal = (
        (params.get("calendar_provider") or "").strip() == "google"
        and bool((params.get("calendar_id") or "").strip())
    )
    google_cal_active = google_cal and not skip_google
    google_execute_timeout: Optional[float] = None
    if lightweight and google_cal_active:
        try:
            google_execute_timeout = float(
                (os.environ.get("AGENDA_LIGHTWEIGHT_GOOGLE_TIMEOUT_SECONDS") or "6").strip() or "6"
            )
        except ValueError:
            google_execute_timeout = 6.0
    if google_cal_active:
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
                    execute_timeout=google_execute_timeout,
                )
                if mirror_fut is not None:
                    try:
                        mirror_lookup = mirror_fut.result(timeout=5)
                    except Exception as mirror_exc:
                        logger.warning(
                            "tenant agenda mirror overlap failed tenant_id=%s: %s",
                            tenant_id,
                            mirror_exc,
                        )
                        mirror_lookup = {}
            finally:
                if executor is not None:
                    executor.shutdown(wait=True)
            google_events = result.get("items") or []
            if not fast_mode:
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
                if not fast_mode:
                    patient = _resolve_agenda_patient_name_cached(tenant_id, patient_contact, patient, profile_cache)
                motif = _extract_google_description_line(description, "Motif") or (summary if summary and not summary.startswith("RDV - ") else "Consultation")
                source = "UWI" if summary.startswith("RDV - ") or "Patient:" in description else "EXTERNAL"
                mirror_booking = None
                if mirror_enabled:
                    mirror_booking = _find_local_appointment_for_google_event(
                        tenant_id=tenant_id,
                        start_local=start_local,
                        patient_contact=patient_contact,
                        fallback_name=patient,
                        appointments_index=mirror_lookup,
                        google_event_id=str(event.get("id") or ""),
                    )
                bo_origin = _agenda_resolve_booking_origin_google(description, mirror_booking)
                contact_type = str((mirror_booking or {}).get("contact_type") or "")
                meta = _agenda_slot_meta(
                    start_local=start_local,
                    end_local=end_local,
                    contact_type=contact_type,
                    description=description,
                )
                slots.append({
                    "date": start_local.strftime("%Y-%m-%d"),
                    "hour": start_local.strftime("%Hh"),
                    "start_iso": start_local.isoformat(),
                    "patient": patient,
                    "motif": motif,
                    "patient_phone": _agenda_slot_contact_for_patient_phone(patient_contact, mirror_booking),
                    "type": motif,
                    "source": source,
                    "booking_origin": bo_origin,
                    "done": end_local <= now_local,
                    "current": start_local <= now_local < end_local,
                    "event_id": event.get("id") or "",
                    "appointment_id": int(mirror_booking.get("id") or 0) if mirror_booking else None,
                    "slot_id": int(mirror_booking.get("slot_id") or 0) if mirror_booking else None,
                    "can_cancel": bool(source == "UWI"),
                    "can_reschedule": _agenda_uwi_can_reschedule(source, mirror_booking, event.get("id")),
                    **meta,
                })
        except Exception as e:
            logger.warning("tenant agenda google failed tenant_id=%s: %s", tenant_id, e)
    elif not google_cal:
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
                            SELECT a.id, a.slot_id, a.name, a.contact, a.contact_type, a.motif, s.start_ts
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
                        if not fast_mode:
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
                            if fast_mode:
                                patient_name = str(row.get("name") or "").strip() or "Patient"
                            else:
                                patient_name = _resolve_agenda_patient_name_cached(
                                    tenant_id,
                                    row.get("contact"),
                                    row.get("name"),
                                    profile_cache,
                                )
                            meta = _agenda_slot_meta(
                                start_local=start_local,
                                end_local=end_local,
                                contact_type=str(row.get("contact_type") or ""),
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
                                **meta,
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
                    SELECT a.id, a.slot_id, a.name, a.contact, a.contact_type, a.motif, a.booking_origin, s.date, s.time
                    FROM appointments a
                    JOIN slots s ON s.id = a.slot_id
                    WHERE a.tenant_id = ? AND s.date = ?
                    ORDER BY s.time ASC
                    """,
                    (tenant_id, day_start.strftime("%Y-%m-%d")),
                ).fetchall()
                if not fast_mode:
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
                    if fast_mode:
                        patient_name = str(row["name"] or "").strip() or "Patient"
                    else:
                        patient_name = _resolve_agenda_patient_name_cached(tenant_id, row["contact"], row["name"], profile_cache)
                    meta = _agenda_slot_meta(
                        start_local=start_local,
                        end_local=end_local,
                        contact_type=str(row["contact_type"] or ""),
                    )
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
                        **meta,
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

    if lightweight:
        _apply_agenda_lightweight_slot_defaults(slots)
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


_AGENDA_BULK_MAX_DAYS = 42


@router.get("/agenda/bulk")
def tenant_agenda_bulk(
    auth: dict = Depends(require_tenant_auth),
    dates: str = Query(..., description="Liste CSV de dates YYYY-MM-DD (max 42)"),
    lightweight: bool = Query(False, description="Mode allégé (moins d'enrichissements, plus rapide)"),
    skip_google: bool = Query(
        False,
        description="Réponse immédiate DB sans Google (enrichissement Google ensuite)",
    ),
):
    """Retourne plusieurs jours d'agenda en une seule réponse pour limiter le fan-out frontend.

    Performance:
    - accepte jusqu'à 42 jours (grille mensuelle complète) pour éviter 3 appels concurrents
      côté frontend qui surchargeaient Google Calendar (8-20s/chunk observés).
    - met en cache la réponse finale quelques secondes pour absorber les refreshs rapprochés.
    """
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

    truncated = False
    if len(requested_dates) > _AGENDA_BULK_MAX_DAYS:
        truncated = True
        requested_dates.sort()
        keep = requested_dates[:_AGENDA_BULK_MAX_DAYS]
        logger.info(
            "agenda/bulk: %d dates demandées, limitées à %d (tenant=%s)",
            len(requested_dates),
            _AGENDA_BULK_MAX_DAYS,
            tenant_id,
        )
        requested_dates = keep

    requested_dates.sort()
    cache_key = (int(tenant_id), tuple(requested_dates))
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        try:
            bulk_ttl = float((os.environ.get("AGENDA_BULK_CACHE_SECONDS") or "90").strip() or "90")
        except ValueError:
            bulk_ttl = 18.0
        if bulk_ttl > 0:
            now = time.monotonic()
            with _TENANT_AGENDA_BULK_LOCK:
                hit = _TENANT_AGENDA_BULK_CACHE.get(cache_key)
                if hit and hit[0] > now:
                    return copy.deepcopy(hit[1])
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

    # Par défaut on désactive le mirror sur bulk (semaine/mois) pour privilégier
    # la vitesse d'affichage. Réactivable explicitement via env si besoin.
    mirror_enabled = _google_mirror_enabled(detail) and _is_truthy(
        os.environ.get("AGENDA_BULK_MIRROR_ENABLED") or "false"
    )
    mirror_lookup: Optional[Dict[str, List[Dict[str, Any]]]] = None

    google_cal_bulk = (
        (params.get("calendar_provider") or "").strip() == "google"
        and bool((params.get("calendar_id") or "").strip())
    )
    google_cal_bulk_active = google_cal_bulk and not skip_google
    google_bulk_timeout: Optional[float] = None
    if lightweight and google_cal_bulk_active:
        try:
            google_bulk_timeout = float(
                (os.environ.get("AGENDA_LIGHTWEIGHT_GOOGLE_TIMEOUT_SECONDS") or "6").strip() or "6"
            )
        except ValueError:
            google_bulk_timeout = 6.0
    if google_cal_bulk_active:
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
                    execute_timeout=google_bulk_timeout,
                )
                if mirror_fut is not None:
                    try:
                        mirror_lookup = mirror_fut.result(timeout=5)
                    except Exception as mirror_exc:
                        logger.warning(
                            "tenant agenda bulk mirror overlap failed tenant_id=%s: %s",
                            tenant_id,
                            mirror_exc,
                        )
                        mirror_lookup = {}
            finally:
                if executor is not None:
                    executor.shutdown(wait=True)
            google_events = result.get("items") or []
            if not lightweight:
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
                if not lightweight:
                    patient = _resolve_agenda_patient_name_cached(tenant_id, patient_contact, patient, profile_cache)
                motif = _extract_google_description_line(description, "Motif") or (summary if summary and not summary.startswith("RDV - ") else "Consultation")
                source = "UWI" if summary.startswith("RDV - ") or "Patient:" in description else "EXTERNAL"
                mirror_booking = None
                if mirror_enabled:
                    mirror_booking = _find_local_appointment_for_google_event(
                        tenant_id=tenant_id,
                        start_local=start_local,
                        patient_contact=patient_contact,
                        fallback_name=patient,
                        appointments_index=mirror_lookup,
                        google_event_id=str(event.get("id") or ""),
                    )
                bo_origin = _agenda_resolve_booking_origin_google(description, mirror_booking)
                payloads[date_key]["slots"].append(
                    {
                        "date": start_local.strftime("%Y-%m-%d"),
                        "hour": start_local.strftime("%Hh"),
                        "start_iso": start_local.isoformat(),
                        "patient": patient,
                        "motif": motif,
                        "patient_phone": _agenda_slot_contact_for_patient_phone(patient_contact, mirror_booking),
                        "type": motif,
                        "source": source,
                        "booking_origin": bo_origin,
                        "done": end_local <= now_local,
                        "current": start_local <= now_local < end_local,
                        "event_id": event.get("id") or "",
                        "appointment_id": int(mirror_booking.get("id") or 0) if mirror_booking else None,
                        "slot_id": int(mirror_booking.get("slot_id") or 0) if mirror_booking else None,
                        "can_cancel": bool(source == "UWI"),
                        "can_reschedule": _agenda_uwi_can_reschedule(source, mirror_booking, event.get("id")),
                    }
                )
        except Exception as e:
            logger.warning("tenant agenda bulk google failed tenant_id=%s: %s", tenant_id, e)
    elif not google_cal_bulk:
        url = os.environ.get("DATABASE_URL") or os.environ.get("PG_SLOTS_URL")
        if url:
            try:
                import psycopg
                from psycopg.rows import dict_row

                with psycopg.connect(url, row_factory=dict_row) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT a.id, a.slot_id, a.name, a.contact, a.motif, s.start_ts
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
                            if lightweight:
                                patient_name = str(row.get("name") or "").strip() or "Patient"
                            else:
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
                    if lightweight:
                        patient_name = str(row["name"] or "").strip() or "Patient"
                    else:
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

    """Merge des réservations publiques (page publique + chat public) — sans ça,
    les RDV pris hors Google Calendar / hors local mirror disparaissent dès qu'on
    quitte la vue jour (qui est la seule à appeler fetch_public_bookings_for_agenda).
    """
    try:
        from backend.public_bookings_pg import fetch_public_bookings_for_agenda

        public_slots = fetch_public_bookings_for_agenda(
            tenant_id,
            day_start,
            day_end,
            tz_name,
            now_local,
            include_past_on_date=True,
        )
        existing_ids_by_date: Dict[str, set] = {
            date_str: {str(slot.get("event_id") or "") for slot in (payload.get("slots") or [])}
            for date_str, payload in payloads.items()
        }
        for slot in public_slots:
            date_key = str(slot.get("date") or "")
            if date_key not in payloads:
                continue
            event_id = str(slot.get("event_id") or "")
            if event_id and event_id in existing_ids_by_date.get(date_key, set()):
                continue
            payloads[date_key]["slots"].append(slot)
            if event_id:
                existing_ids_by_date.setdefault(date_key, set()).add(event_id)
    except Exception as exc:
        logger.debug("tenant agenda/bulk public_bookings merge skipped tenant=%s: %s", tenant_id, exc)

    flat_slots_bulk = [slot for payload in payloads.values() for slot in (payload.get("slots") or [])]
    if lightweight:
        _apply_agenda_lightweight_slot_defaults(flat_slots_bulk)
    _warm_agenda_profiles_from_slots_patient_phone(tenant_id, flat_slots_bulk, profile_cache)
    for payload in payloads.values():
        _decorate_agenda_slots_patient_has_file(tenant_id, list(payload.get("slots") or []), profile_cache)

    response = {
        "dates": {date_str: _finalize_agenda_day_payload(payload) for date_str, payload in payloads.items()},
        "truncated": truncated,
        "max_days": _AGENDA_BULK_MAX_DAYS,
    }
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        try:
            bulk_ttl = float((os.environ.get("AGENDA_BULK_CACHE_SECONDS") or "90").strip() or "90")
        except ValueError:
            bulk_ttl = 18.0
        if bulk_ttl > 0:
            now = time.monotonic()
            with _TENANT_AGENDA_BULK_LOCK:
                _TENANT_AGENDA_BULK_CACHE[cache_key] = (now + bulk_ttl, copy.deepcopy(response))
                if len(_TENANT_AGENDA_BULK_CACHE) > 300:
                    stale = [k for k, (exp, _) in _TENANT_AGENDA_BULK_CACHE.items() if exp <= now]
                    for k in stale[:120]:
                        _TENANT_AGENDA_BULK_CACHE.pop(k, None)
    return response


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
        from backend import config

        if config.USE_PG_SLOTS:
            try:
                from backend.slots_pg import pg_cleanup_and_ensure_slots, pg_list_free_slots_for_date

                pg_cleanup_and_ensure_slots(tenant_id)
                raw = pg_list_free_slots_for_date(tenant_id, date[:10])
                if raw is not None:
                    items = [
                        {
                            "slot_id": int(row.get("id") or 0),
                            "date": row.get("date") or date[:10],
                            "time": row.get("time") or "",
                            "label": f"{row.get('date') or date[:10]} à {row.get('time') or ''}",
                        }
                        for row in raw
                        if int(row.get("id") or 0) > 0
                    ]
                    return {"slots": items, "total": len(items)}
            except Exception as e:
                logger.warning("tenant agenda available-slots pg failed tenant_id=%s date=%s err=%s", tenant_id, date, e)

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
    from backend import config

    if config.USE_PG_SLOTS:
        try:
            from backend.slots_pg import pg_count_free_slots_by_month

            dates = pg_count_free_slots_by_month(tenant_id, month)
            if dates is not None:
                return {"dates": dates, "month": month[:7]}
        except Exception as e:
            logger.warning("tenant agenda available-dates pg failed tenant_id=%s month=%s err=%s", tenant_id, month, e)

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


def _tenant_agenda_parse_start_local(start_iso: str, tz_name: str) -> tuple[str, str, datetime]:
    """Retourne (date YYYY-MM-DD, heure HH:MM, datetime aware fuseau cabinet) depuis start_iso."""
    raw = (start_iso or "").strip()
    if not raw:
        raise ValueError("start_iso empty")
    dt_parse = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    tz = _get_zoneinfo(tz_name)
    if dt_parse.tzinfo is None:
        dt_local = dt_parse.replace(tzinfo=tz)
    else:
        dt_local = dt_parse.astimezone(tz)
    return dt_local.strftime("%Y-%m-%d"), dt_local.strftime("%H:%M"), dt_local


def _tenant_agenda_compute_end_iso(start_iso: str, tenant_id: int, end_iso_in: str, tz_name: str = "Europe/Paris") -> str:
    end = (end_iso_in or "").strip()
    if end:
        return end
    try:
        _, _, dt_local = _tenant_agenda_parse_start_local(start_iso, tz_name)
    except ValueError:
        return ""
    end_local = dt_local + timedelta(minutes=_tenant_cabinet_booking_duration_minutes(tenant_id))
    # Google Calendar : dateTime sans offset + timeZone Europe/Paris (heure murale cabinet).
    return end_local.replace(tzinfo=None).isoformat(timespec="seconds")


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
    if (body.patient_phone or "").strip() and not is_valid_patient_phone(body.patient_phone):
        raise HTTPException(
            400,
            "Numéro de téléphone invalide (format attendu : 06 12 34 56 78 ou +33 6 12 34 56 78).",
        )
    phone_norm = normalize_phone_number(body.patient_phone) or ""
    email_part = (body.patient_email or "").strip()
    if email_part and not is_valid_contact_email(email_part):
        raise HTTPException(400, "Email invalide (format attendu: prenom@domaine.fr).")
    contact_bits = []
    if phone_norm:
        contact_bits.append(f"Tél. {phone_norm}")
    if email_part:
        contact_bits.append(f"Email {email_part}")
    contact_line = " · ".join(contact_bits) if contact_bits else "—"
    contact_for_qualif = phone_norm or email_part or contact_line
    qualif_contact_type = "phone" if phone_norm else ("email" if email_part else "phone")
    tz_name = _tenant_timezone(detail)
    try:
        start_local_iso = _tenant_agenda_parse_start_local(start_iso, tz_name)[2].replace(tzinfo=None).isoformat(
            timespec="seconds"
        )
    except ValueError:
        raise HTTPException(400, "Date ou heure de début invalide.") from None
    end_iso = _tenant_agenda_compute_end_iso(start_iso, tenant_id, body.end_iso, tz_name)

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
                start_local_iso,
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
                tools_booking._mirror_google_booking_to_internal(qs, start_local_iso, ev)
        except Exception as exc:
            logger.warning("mirror after tenant booking failed tenant_id=%s: %s", tenant_id, exc)

        _invalidate_tenant_agenda_detail_cache(tenant_id)
        return {"ok": True, "provider": "google", "event_id": ev}

    try:
        date_str, time_str, _ = _tenant_agenda_parse_start_local(start_iso, tz_name)
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

        google_event_id = _resolve_google_event_id_for_booking(
            tenant_id,
            detail,
            explicit_event_id=google_event_id,
            local_booking=local_booking,
        ) or ""

        if local_appt_id is None and google_event_id:
            mirrored = _find_local_appointment_by_google_event_id(tenant_id, google_event_id)
            if mirrored and int(mirrored.get("id") or 0) > 0:
                local_booking = mirrored
                local_appt_id = int(mirrored["id"])

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
        _invalidate_google_agenda_events_cache(params.get("calendar_id"))
        _invalidate_tenant_agenda_detail_cache(tenant_id)
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
    _invalidate_tenant_agenda_detail_cache(tenant_id)
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
    appointment_id: str,
    body: TenantAgendaRescheduleBody,
    auth: dict = Depends(require_tenant_auth),
):
    """Déplace un RDV UWI (local et/ou Google Calendar)."""
    tenant_id = auth["tenant_id"]
    detail = _get_tenant_detail(tenant_id)
    if not detail:
        raise HTTPException(404, "Tenant not found")
    params = detail.get("params") or {}
    raw_appointment_id = (appointment_id or "").strip()
    local_appt_id: Optional[int] = None
    booking: Optional[Dict[str, Any]] = None
    if raw_appointment_id.isdigit():
        local_appt_id = int(raw_appointment_id)
        booking = _get_local_appointment_by_id(tenant_id, local_appt_id)
        if not booking:
            local_appt_id = None

    if (params.get("calendar_provider") or "").strip() == "google":
        explicit_event_id = (body.external_event_id or "").strip()
        if not explicit_event_id and raw_appointment_id and not raw_appointment_id.isdigit():
            explicit_event_id = raw_appointment_id
        event_id = _resolve_google_event_id_for_booking(
            tenant_id,
            detail,
            explicit_event_id=explicit_event_id,
            local_booking=booking,
        )
        if not event_id:
            raise HTTPException(400, "Impossible de retrouver l'événement Google pour ce rendez-vous")
        rules = get_booking_rules(tenant_id)
        duration_minutes = int(rules.get("duration_minutes") or 15)
        tz_name = _tenant_timezone(detail)
        new_window = _get_slot_window(tenant_id, int(body.new_slot_id), tz_name, duration_minutes)
        if not new_window:
            raise HTTPException(400, "Créneau introuvable")
        new_start, new_end = new_window
        service = GoogleCalendarService((params.get("calendar_id") or "").strip())

        if booking and local_appt_id:
            if not _google_mirror_enabled(detail):
                raise HTTPException(400, "Déplacement automatique indisponible avec Google Calendar")
            old_window = _get_slot_window(tenant_id, int(booking.get("slot_id") or 0), tz_name, duration_minutes)
            if not old_window:
                raise HTTPException(400, "Créneau introuvable")
            old_start, old_end = old_window
            try:
                moved = service.reschedule_appointment(
                    event_id,
                    new_start.isoformat(),
                    new_end.isoformat(),
                    timezone=tz_name,
                )
            except Exception as e:
                logger.warning(
                    "tenant agenda reschedule google failed tenant_id=%s appointment_id=%s event_id=%s err=%s",
                    tenant_id,
                    local_appt_id,
                    event_id,
                    e,
                )
                raise HTTPException(502, "Impossible de déplacer ce rendez-vous Google pour le moment")
            if not moved:
                raise HTTPException(400, "Déplacement impossible")
            try:
                ok = reschedule_booking_atomic(local_appt_id, int(body.new_slot_id), tenant_id=tenant_id)
            except Exception as e:
                logger.warning(
                    "tenant agenda reschedule local mirror exception tenant_id=%s appointment_id=%s new_slot_id=%s err=%s",
                    tenant_id,
                    local_appt_id,
                    body.new_slot_id,
                    e,
                )
                rollback_ok = service.reschedule_appointment(
                    event_id,
                    old_start.isoformat(),
                    old_end.isoformat(),
                    timezone=tz_name,
                )
                if rollback_ok:
                    raise HTTPException(409, "Le créneau sélectionné n'est plus disponible")
                raise HTTPException(502, "Le rendez-vous Google a été déplacé mais le miroir interne n'a pas pu être remis à jour")
            if ok is False:
                rollback_ok = service.reschedule_appointment(
                    event_id,
                    old_start.isoformat(),
                    old_end.isoformat(),
                    timezone=tz_name,
                )
                logger.warning(
                    "tenant agenda reschedule local mirror failed tenant_id=%s appointment_id=%s new_slot_id=%s rollback_ok=%s",
                    tenant_id,
                    local_appt_id,
                    body.new_slot_id,
                    rollback_ok,
                )
                if rollback_ok:
                    raise HTTPException(409, "Le créneau sélectionné n'est plus disponible")
                raise HTTPException(502, "Le rendez-vous Google a été déplacé mais le miroir interne n'a pas pu être remis à jour")
            logger.info(
                "tenant agenda reschedule google ok tenant_id=%s appointment_id=%s event_id=%s new_slot_id=%s",
                tenant_id,
                local_appt_id,
                event_id,
                body.new_slot_id,
            )
            _mark_pending_handoffs_processed(tenant_id, booking)
            _invalidate_tenant_agenda_detail_cache(tenant_id)
            return {"ok": True, "rescheduled": True, "provider": "google+local", "google_synced": True}

        try:
            moved = service.reschedule_appointment(
                event_id,
                new_start.isoformat(),
                new_end.isoformat(),
                timezone=tz_name,
            )
        except Exception as e:
            logger.warning(
                "tenant agenda reschedule google-only failed tenant_id=%s event_id=%s err=%s",
                tenant_id,
                event_id,
                e,
            )
            raise HTTPException(502, "Impossible de déplacer ce rendez-vous Google pour le moment")
        if not moved:
            raise HTTPException(400, "Déplacement impossible")
        logger.info(
            "tenant agenda reschedule google-only ok tenant_id=%s event_id=%s new_slot_id=%s",
            tenant_id,
            event_id,
            body.new_slot_id,
        )
        _invalidate_tenant_agenda_detail_cache(tenant_id)
        return {"ok": True, "rescheduled": True, "provider": "google", "google_synced": True}

    if not booking or local_appt_id is None:
        raise HTTPException(404, "Rendez-vous introuvable")
    ok = reschedule_booking_atomic(local_appt_id, int(body.new_slot_id), tenant_id=tenant_id)
    if ok is False:
        raise HTTPException(409, "Le créneau sélectionné n'est plus disponible")
    logger.info(
        "tenant agenda reschedule local ok tenant_id=%s appointment_id=%s new_slot_id=%s",
        tenant_id,
        local_appt_id,
        body.new_slot_id,
    )
    _mark_pending_handoffs_processed(tenant_id, booking)
    _invalidate_tenant_agenda_detail_cache(tenant_id)
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
        "dashboard_team_note", "dashboard_team_note_updated_at",
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
