# backend/routes/tenant.py
"""
API tenant (client): dashboard, technical-status, me, params, agenda.
Protégé par cookie uwi_session uniquement (require_tenant_auth).
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import bcrypt
import jwt
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.auth_pg import pg_get_tenant_user_by_id, pg_update_password
from backend.calendar_adapter import _GoogleCalendarAdapter
from backend import config
from backend.config import get_service_account_email
from backend.db import (
    cancel_booking_sqlite,
    ensure_tenant_config,
    get_cabinet_clients_by_phones,
    find_slot_id_by_datetime,
    get_cabinet_client_by_phone,
    get_call_followup,
    get_conn,
    list_free_slots,
    list_call_followups,
    normalize_phone_number,
    reschedule_booking_atomic,
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
    _get_quota_used_minutes,
    _get_rgpd_extended,
    _get_technical_status,
    _get_tenant_detail,
)
from backend.services.email_service import send_agenda_contact_request_email
from backend.tenant_config import (
    DEFAULT_FAQ,
    derive_horaires_text,
    get_booking_rules,
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

router = APIRouter(prefix="/api/tenant", tags=["tenant"])

JWT_SECRET = os.environ.get("JWT_SECRET", "")
SESSION_COOKIE_NAME = os.environ.get("SESSION_COOKIE_NAME", "uwi_session")

STATUS_MAP = {
    "rdv": "CONFIRMED",
    "transfer": "TRANSFERRED",
    "abandoned": "ABANDONED",
    "other": "FAQ",
}


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


def _tenant_timezone(detail: Optional[dict]) -> str:
    params = (detail or {}).get("params") or {}
    return (params.get("timezone") or (detail or {}).get("timezone") or "Europe/Paris").strip() or "Europe/Paris"


def _is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on", "oui"}


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
    return dt.astimezone(_get_zoneinfo(tz_name)).strftime("%H:%M")


def _format_hour_slot(value: Any, tz_name: str) -> str:
    dt = _parse_dt(value, tz_name)
    if not dt:
        return "—"
    return dt.astimezone(_get_zoneinfo(tz_name)).strftime("%Hh")


def _format_duration_short(duration_min: Optional[int]) -> str:
    total_seconds = max(0, int((duration_min or 0) * 60))
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
            import psycopg
            from psycopg.rows import dict_row
            from backend.tenants_pg import _pg_url, set_tenant_id_on_connection

            url = _pg_url()
            if url:
                with psycopg.connect(url, row_factory=dict_row) as conn:
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

    if status == "CONFIRMED" or any(token in haystack for token in ("rdv", "rendez-vous", "agenda", "créneau", "creneau", "booking", "annuler", "déplacer", "deplacer")):
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
    if status == "CONFIRMED":
        return "Rendez-vous confirmé" if not user_lines else f"RDV confirmé — {user_lines[0][:72]}"
    if status == "ABANDONED":
        return "Appel interrompu par le patient"
    if user_lines:
        return user_lines[0][:96]
    return "Demande d'information traitée par l'assistant"


def _resolve_call_status(item: Optional[dict], detail: Optional[dict]) -> str:
    event_names = [str((event or {}).get("event") or "").strip().lower() for event in (detail or {}).get("events") or []]
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
    phone = normalize_phone_number(_call_display_phone(item, detail))
    profile = None
    if phone:
        if profile_cache is not None:
            profile = profile_cache.get(phone)
        else:
            profile = get_cabinet_client_by_phone(tenant_id, phone)
    raw_name = _derive_raw_patient_name(detail) or (profile or {}).get("raw_name") or ""
    validated_name = (profile or {}).get("validated_name") or ""
    display_name = validated_name or raw_name or "Patient"
    return {
        "phone": phone or "",
        "raw_name": raw_name,
        "validated_name": validated_name,
        "display_name": display_name,
        "validation_status": (profile or {}).get("validation_status") or ("validated" if validated_name else "pending"),
        "profile_exists": bool(profile),
        "is_validated": bool(validated_name),
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


def _extract_google_description_line(description: str, prefix: str) -> Optional[str]:
    for line in (description or "").splitlines():
        if line.lower().startswith(prefix.lower()):
            return line.split(":", 1)[1].strip() if ":" in line else line.strip()
    return None


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
    return provider and _is_truthy(params.get("mirror_google_bookings_to_internal"))


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
            import psycopg
            from psycopg.rows import dict_row

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
                            }
                        )
                    return index
        except Exception as e:
            logger.debug("local appointments window lookup pg failed tenant_id=%s err=%s", tenant_id, e)

    ensure_tenant_config()
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT a.id, a.slot_id, a.name, a.contact, a.contact_type, a.motif, s.date, s.time
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
                }
            )
        return index
    finally:
        conn.close()


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


class TenantCallFollowupBody(BaseModel):
    followup_state: str
    notes: str = ""


class TenantCallPatientBody(BaseModel):
    validated_name: str
    raw_name: str = ""


class TenantHandoffUpdateBody(BaseModel):
    status: Optional[str] = Field(default=None, max_length=32)
    notes: Optional[str] = Field(default=None, max_length=1000)


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

    onboarding_steps = {
        "assistant_ready": bool(assistant_name and vapi_assistant_id),
        "phone_ready": bool(voice_number),
        "calendar_ready": (calendar_provider == "google" and bool(calendar_id)) or calendar_provider == "none",
        "horaires_ready": horaires_ready,
        "faq_ready": faq_ready,
    }
    onboarding_completed = all(onboarding_steps.values())
    client_onboarding_completed = _explicit or onboarding_completed
    transfer_hours = _parse_dict_value(params.get("transfer_hours"))
    transfer_cases = _parse_string_list(params.get("transfer_cases"))

    return {
        "tenant_id": tenant_id,
        "tenant_name": d.get("name", "N/A"),
        "email": auth.get("email"),
        "role": auth.get("role", "owner"),
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
    followups_by_call = list_call_followups(tenant_id, [(item.get("call_id") or "").strip() for item in items])
    patient_profiles_by_phone = get_cabinet_clients_by_phones(
        tenant_id,
        [item.get("customer_number") or "" for item in items],
    )
    compact_mode = bool(compact)
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
                    "duration_min": raw_detail.get("duration_min") if raw_detail.get("duration_min") is not None else list_detail.get("duration_min"),
                    "result": raw_detail.get("result") or list_detail.get("result") or "other",
                    "events": raw_detail.get("events") or list_detail.get("events") or [],
                    "transcript": raw_detail.get("transcript") if raw_detail.get("transcript") is not None else list_detail.get("transcript"),
                }
                status = _resolve_call_status(item, detail_for_display)
                booking = _build_booking_payload(detail_for_display)
        call_context = _classify_call_context(status, detail_for_display)
        patient = _build_patient_payload(tenant_id, item, detail_for_display, patient_profiles_by_phone)
        calls.append({
            "id": call_id,
            "time": _format_hhmm(started_at, tz_name),
            "duration": _format_duration_short(detail_for_display.get("duration_min") or item.get("duration_min")),
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
        "duration": _format_duration_short(raw.get("duration_min")),
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
    """Valide/corrige le nom d'un patient et l'inscrit dans la fiche client cabinet liée au téléphone."""
    tenant_id = auth["tenant_id"]
    raw = _get_call_detail(tenant_id, call_id)
    if not raw:
        raise HTTPException(404, "Call not found")
    patient = _build_patient_payload(tenant_id, None, raw)
    phone = patient.get("phone") or ""
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

    logger.info("tenant patient validated tenant_id=%s call_id=%s phone=%s", tenant_id, call_id, phone)
    return {"ok": True, "call_id": call_id, "patient": _build_patient_payload(tenant_id, None, raw)}


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


@router.get("/agenda")
def tenant_agenda(
    auth: dict = Depends(require_tenant_auth),
    date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    upcoming_days: int = Query(1, ge=1, le=30),
    compact: bool = Query(False),
):
    """Retourne les rendez-vous du jour ou à venir depuis Google Calendar ou le stockage local."""
    tenant_id = auth["tenant_id"]
    detail = _get_tenant_detail(tenant_id)
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
    if mirror_enabled and not compact_mode:
        mirror_lookup = _load_local_appointments_for_window(tenant_id, day_start, day_end, tz_name)
    if (params.get("calendar_provider") or "").strip() == "google" and (params.get("calendar_id") or "").strip():
        try:
            service = GoogleCalendarService((params.get("calendar_id") or "").strip())
            result = service.service.events().list(
                calendarId=(params.get("calendar_id") or "").strip(),
                timeMin=day_start.isoformat(),
                timeMax=day_end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                fields="items(id,summary,description,start,end)",
            ).execute()
            for event in result.get("items", []):
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
                patient_contact = _extract_google_description_line(description, "Contact")
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
                slots.append({
                    "hour": start_local.strftime("%Hh"),
                    "patient": patient,
                    "patient_phone": normalize_phone_number(patient_contact),
                    "type": motif,
                    "source": source,
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
                        for row in cur.fetchall():
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
                                "hour": start_local.strftime("%Hh"),
                                "patient": patient_name,
                                "patient_phone": normalize_phone_number(row.get("contact")),
                                "type": row.get("motif") or "Consultation",
                                "source": "UWI",
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
                rows = conn.execute(
                    """
                    SELECT a.id, a.slot_id, a.name, a.contact, a.motif, s.date, s.time
                    FROM appointments a
                    JOIN slots s ON s.id = a.slot_id
                    WHERE a.tenant_id = ? AND s.date = ?
                    ORDER BY s.time ASC
                    """,
                    (tenant_id, day_start.strftime("%Y-%m-%d")),
                ).fetchall()
                for row in rows:
                    start_local = _parse_dt(f"{row[5]}T{row[6]}:00", tz_name)
                    if not start_local:
                        continue
                    if not date and start_local < now_local:
                        continue
                    end_local = start_local + timedelta(minutes=30)
                    patient_name = _resolve_agenda_patient_name_cached(tenant_id, row[3], row[2], profile_cache)
                    slots.append({
                        "hour": start_local.strftime("%Hh"),
                        "patient": patient_name,
                        "patient_phone": normalize_phone_number(row[3]),
                        "type": row[4] or "Consultation",
                        "source": "UWI",
                        "done": end_local <= now_local,
                        "current": start_local <= now_local < end_local,
                        "event_id": str(row[0] or ""),
                        "appointment_id": int(row[0] or 0),
                        "slot_id": int(row[1] or 0),
                        "can_cancel": True,
                        "can_reschedule": True,
                    })
            finally:
                conn.close()

    slots.sort(key=lambda item: item.get("hour") or "")
    done_count = sum(1 for item in slots if item.get("done"))
    return {
        "slots": slots,
        "date": day_start.strftime("%Y-%m-%d"),
        "total": len(slots),
        "done": done_count,
        "remaining": max(0, len(slots) - done_count),
        "provider": (params.get("calendar_provider") or "none").strip() or "none",
        "external_connected": bool((params.get("calendar_provider") or "").strip() == "google" and (params.get("calendar_id") or "").strip()),
    }


@router.get("/agenda/available-slots")
def tenant_agenda_available_slots(
    auth: dict = Depends(require_tenant_auth),
    limit: int = Query(8, ge=1, le=20),
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
    return {"ok": True, "rescheduled": True, "provider": "local"}


@router.patch("/params")
def tenant_patch_params(
    body: Dict[str, Any],
    auth: dict = Depends(require_tenant_auth),
):
    """
    Met à jour params du tenant connecté.
    """
    allowed = {
        "contact_email", "calendar_provider", "calendar_id", "timezone", "consent_mode",
        "phone_number", "sector", "specialty_label", "address_line1", "postal_code", "city",
        "assistant_name", "plan_key", "agenda_software", "client_onboarding_completed",
        "dashboard_tour_completed",
        "transfer_number", "transfer_live_enabled", "transfer_callback_enabled",
        "transfer_cases", "transfer_hours", "transfer_always_urgent", "transfer_no_consultation",
        "transfer_config_confirmed_signature", "transfer_config_confirmed_at",
    }
    body = body or {}
    tenant_id = auth["tenant_id"]
    tenant_name = (body.get("tenant_name") or "").strip() if body.get("tenant_name") is not None else ""
    params = {k: v for k, v in body.items() if k in allowed and v is not None}
    if tenant_name:
        ok = pg_update_tenant_name(tenant_id, tenant_name)
        if not ok:
            raise HTTPException(500, "Failed to update tenant name")
    if not params:
        return {"ok": True}
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
async def tenant_reset_faq(auth: dict = Depends(require_tenant_auth)):
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
def tenant_agenda_activate_none(auth: dict = Depends(require_tenant_auth)):
    """Active le mode sans agenda externe (l'assistant gère les RDV dans son propre système)."""
    tenant_id = auth["tenant_id"]
    pg_update_tenant_params(tenant_id, {"calendar_provider": "none", "calendar_id": ""})
    return {"ok": True}
