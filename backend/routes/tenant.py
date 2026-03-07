# backend/routes/tenant.py
"""
API tenant (client): dashboard, technical-status, me, params, agenda.
Protégé par cookie uwi_session uniquement (require_tenant_auth).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from backend.auth_pg import pg_get_tenant_user_by_id, pg_update_password
from backend.calendar_adapter import _GoogleCalendarAdapter
from backend.config import get_service_account_email
from backend.db import ensure_tenant_config, get_conn
from backend.google_calendar import GoogleCalendarNotFoundError, GoogleCalendarPermissionError, GoogleCalendarService
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
from backend.tenant_config import derive_horaires_text, get_booking_rules
from backend.tenants_pg import pg_update_tenant_params

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


def _call_summary_from_detail(status: str, detail: dict) -> str:
    transcript = (detail.get("transcript") or "").strip()
    user_lines = []
    if transcript:
        for line in transcript.splitlines():
            clean = line.strip()
            if clean.startswith("Patient:"):
                user_lines.append(clean.replace("Patient:", "", 1).strip())
    latest_reason = None
    for event in reversed(detail.get("events") or []):
        meta = event.get("meta") or {}
        if meta.get("reason"):
            latest_reason = _humanize_reason(meta.get("reason"))
            break
    if status == "TRANSFERRED":
        return f"{latest_reason} — transfert humain" if latest_reason else "Transféré à un humain"
    if status == "CONFIRMED":
        return "Rendez-vous confirmé" if not user_lines else f"RDV confirmé — {user_lines[0][:72]}"
    if status == "ABANDONED":
        return "Appel interrompu par le patient"
    if user_lines:
        return user_lines[0][:96]
    return "Demande d'information traitée par l'assistant"


def _extract_google_description_line(description: str, prefix: str) -> Optional[str]:
    for line in (description or "").splitlines():
        if line.lower().startswith(prefix.lower()):
            return line.split(":", 1)[1].strip() if ":" in line else line.strip()
    return None


@router.get("/me")
def tenant_me(auth: dict = Depends(require_tenant_auth)):
    """Profil du tenant connecté."""
    tenant_id = auth["tenant_id"]
    d = _get_tenant_detail(tenant_id)
    if not d:
        raise HTTPException(404, "Tenant not found")
    params = d.get("params") or {}
    routing = d.get("routing") or []
    voice_number = next(
        ((r.get("key") or "").strip() for r in routing if (r.get("channel") or "").strip() == "vocal" and (r.get("key") or "").strip()),
        None,
    )
    vapi_assistant_id = (params.get("vapi_assistant_id") or "").strip()
    calendar_provider = (params.get("calendar_provider") or "none").strip() or "none"
    calendar_id = (params.get("calendar_id") or "").strip()
    assistant_name = (params.get("assistant_name") or "").strip()
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
        "assistant_ready": bool(vapi_assistant_id and assistant_name),
        "phone_ready": bool(voice_number),
        "calendar_ready": calendar_provider == "google" and bool(calendar_id),
        "horaires_ready": horaires_ready,
        "faq_ready": False,  # Placeholder produit: la FAQ client n'est pas encore disponible.
    }
    # La FAQ n'est pas encore implémentée, donc elle ne doit pas bloquer la disparition de la checklist.
    onboarding_completed = all(onboarding_steps[key] for key in ("assistant_ready", "phone_ready", "calendar_ready", "horaires_ready"))

    return {
        "tenant_id": tenant_id,
        "tenant_name": d.get("name", "N/A"),
        "email": auth.get("email"),
        "role": auth.get("role", "owner"),
        "contact_email": params.get("contact_email", ""),
        "timezone": params.get("timezone", "Europe/Paris"),
        "calendar_id": calendar_id,
        "calendar_provider": calendar_provider,
        "assistant_name": assistant_name or "sophie",
        "plan_key": params.get("plan_key", "growth"),
        "vapi_assistant_id": vapi_assistant_id,
        "voice_number": voice_number,
        "onboarding_steps": onboarding_steps,
        "onboarding_completed": onboarding_completed,
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
    days: int = Query(1, ge=1, le=30),
):
    """Retourne les derniers appels formatés pour le dashboard client."""
    tenant_id = auth["tenant_id"]
    detail = _get_tenant_detail(tenant_id)
    if not detail:
        raise HTTPException(404, "Tenant not found")
    tz_name = _tenant_timezone(detail)
    assistant_name = (((detail.get("params") or {}).get("assistant_name")) or "Sophie").strip().title()
    raw = _get_calls_list(tenant_id=tenant_id, days=days, limit=limit)
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
    calls = []
    for item in items[:limit]:
        call_id = (item.get("call_id") or "").strip()
        if not call_id:
            continue
        call_detail = _get_call_detail(tenant_id, call_id)
        status = STATUS_MAP.get((item.get("result") or "other").lower(), "FAQ")
        started_at = item.get("started_at") or item.get("last_event_at")
        calls.append({
            "id": call_id,
            "time": _format_hhmm(started_at, tz_name),
            "duration": _format_duration_short(call_detail.get("duration_min") or item.get("duration_min")),
            "patient_name": "Patient",
            "agent_name": assistant_name,
            "summary": _call_summary_from_detail(status, call_detail),
            "status": status,
            "call_id": call_id,
        })
    return {
        "calls": calls,
        "total": len(calls),
        "date": datetime.now(_get_zoneinfo(tz_name)).strftime("%Y-%m-%d"),
    }


@router.get("/agenda")
def tenant_agenda(auth: dict = Depends(require_tenant_auth)):
    """Retourne les rendez-vous du jour depuis Google Calendar ou le stockage local."""
    tenant_id = auth["tenant_id"]
    detail = _get_tenant_detail(tenant_id)
    if not detail:
        raise HTTPException(404, "Tenant not found")
    params = detail.get("params") or {}
    tz_name = _tenant_timezone(detail)
    tz = _get_zoneinfo(tz_name)
    now_local = datetime.now(tz)
    day_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    slots: List[Dict[str, Any]] = []

    if (params.get("calendar_provider") or "").strip() == "google" and (params.get("calendar_id") or "").strip():
        try:
            service = GoogleCalendarService((params.get("calendar_id") or "").strip())
            result = service.service.events().list(
                calendarId=(params.get("calendar_id") or "").strip(),
                timeMin=day_start.isoformat(),
                timeMax=day_end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
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
                summary = (event.get("summary") or "").strip()
                description = (event.get("description") or "").strip()
                patient = summary.replace("RDV - ", "", 1).strip() if summary.startswith("RDV - ") else (summary or "Patient")
                motif = _extract_google_description_line(description, "Motif") or (summary if summary and not summary.startswith("RDV - ") else "Consultation")
                source = "UWI" if summary.startswith("RDV - ") or "Patient:" in description else "EXTERNAL"
                slots.append({
                    "hour": start_local.strftime("%Hh"),
                    "patient": patient,
                    "type": motif,
                    "source": source,
                    "done": end_local <= now_local,
                    "current": start_local <= now_local < end_local,
                    "event_id": event.get("id") or "",
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
                            SELECT a.id, a.name, a.motif, s.start_ts
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
                            end_local = start_local + timedelta(minutes=30)
                            slots.append({
                                "hour": start_local.strftime("%Hh"),
                                "patient": row.get("name") or "Patient",
                                "type": row.get("motif") or "Consultation",
                                "source": "UWI",
                                "done": end_local <= now_local,
                                "current": start_local <= now_local < end_local,
                                "event_id": str(row.get("id") or ""),
                            })
            except Exception as e:
                logger.warning("tenant agenda pg failed tenant_id=%s: %s", tenant_id, e)
        else:
            ensure_tenant_config()
            conn = get_conn()
            try:
                rows = conn.execute(
                    """
                    SELECT a.id, a.name, a.motif, s.date, s.time
                    FROM appointments a
                    JOIN slots s ON s.id = a.slot_id
                    WHERE a.tenant_id = ? AND s.date = ?
                    ORDER BY s.time ASC
                    """,
                    (tenant_id, day_start.strftime("%Y-%m-%d")),
                ).fetchall()
                for row in rows:
                    start_local = _parse_dt(f"{row[3]}T{row[4]}:00", tz_name)
                    if not start_local:
                        continue
                    end_local = start_local + timedelta(minutes=30)
                    slots.append({
                        "hour": start_local.strftime("%Hh"),
                        "patient": row[1] or "Patient",
                        "type": row[2] or "Consultation",
                        "source": "UWI",
                        "done": end_local <= now_local,
                        "current": start_local <= now_local < end_local,
                        "event_id": str(row[0] or ""),
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
    }


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
