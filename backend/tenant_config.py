# backend/tenant_config.py
"""
Feature flags par tenant (client).
Permet d'activer/désactiver des features sans hotfix.
Source de vérité : tenant_config.flags_json (JSON).
Fallback : config.DEFAULT_FLAGS.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend import config, db

logger = logging.getLogger(__name__)

FLAG_KEYS = (
    "ENABLE_LLM_ASSIST_START",
    "ENABLE_BARGEIN_SLOT_CHOICE",
    "ENABLE_SEQUENTIAL_SLOTS",
    "ENABLE_NO_FAQ_GUARD",
    "ENABLE_YES_AMBIGUOUS_ROUTER",
)

DAY_LABELS_SHORT = {0: "Lun", 1: "Mar", 2: "Mer", 3: "Jeu", 4: "Ven", 5: "Sam", 6: "Dim"}
OPENING_DAY_MAP = {
    "monday": 0, "mon": 0, "lun": 0, "0": 0,
    "tuesday": 1, "tue": 1, "mar": 1, "1": 1,
    "wednesday": 2, "wed": 2, "mer": 2, "2": 2,
    "thursday": 3, "thu": 3, "jeu": 3, "3": 3,
    "friday": 4, "fri": 4, "ven": 4, "4": 4,
    "saturday": 5, "sat": 5, "sam": 5, "5": 5,
    "sunday": 6, "sun": 6, "dim": 6, "6": 6,
}


def _coerce_booking_days(raw_days: Any) -> List[int]:
    if isinstance(raw_days, (list, tuple)):
        booking_days = [int(x) for x in raw_days if str(x).strip().isdigit()]
    elif isinstance(raw_days, str):
        try:
            parsed = json.loads(raw_days)
            booking_days = [int(x) for x in parsed] if isinstance(parsed, (list, tuple)) else [0, 1, 2, 3, 4]
        except Exception:
            booking_days = [int(x.strip()) for x in raw_days.split(",") if x.strip().isdigit()]
    else:
        booking_days = [0, 1, 2, 3, 4]
    if not booking_days:
        booking_days = [0, 1, 2, 3, 4]
    return sorted({d for d in booking_days if 0 <= int(d) <= 6})


def derive_horaires_text(params: dict) -> str:
    """Génère un texte horaires lisible depuis les booking_rules / params structurés."""
    days = _coerce_booking_days((params or {}).get("booking_days"))
    start = int((params or {}).get("booking_start_hour") or (params or {}).get("start_hour") or 9)
    end = int((params or {}).get("booking_end_hour") or (params or {}).get("end_hour") or 18)
    days_str = ", ".join(DAY_LABELS_SHORT[d] for d in days if d in DAY_LABELS_SHORT)
    return f"{days_str} · {start}h–{end}h"


def convert_opening_hours_to_booking_rules(opening_hours: dict) -> Dict[str, Any]:
    """
    Convertit les horaires structurés du lead en booking_rules tenant.
    Accepte les variantes open/close ou start/end et clés monday..sunday / 0..6.
    """
    days: List[int] = []
    starts: List[int] = []
    ends: List[int] = []
    for day_name, val in (opening_hours or {}).items():
        if not isinstance(val, dict):
            continue
        day_idx = OPENING_DAY_MAP.get(str(day_name).strip().lower())
        if day_idx is None or val.get("closed"):
            continue
        days.append(day_idx)
        open_val = (val.get("open") or val.get("start") or "").strip()
        close_val = (val.get("close") or val.get("end") or "").strip()
        if open_val and ":" in open_val:
            try:
                starts.append(int(open_val.split(":")[0]))
            except Exception:
                pass
        if close_val and ":" in close_val:
            try:
                ends.append(int(close_val.split(":")[0]))
            except Exception:
                pass
    return {
        "booking_days": sorted(set(days)) or [0, 1, 2, 3, 4],
        "booking_start_hour": min(starts) if starts else 9,
        "booking_end_hour": max(ends) if ends else 18,
    }


@dataclass(frozen=True)
class TenantFlags:
    tenant_id: int
    flags: Dict[str, bool]
    source: str  # "db" | "default"
    updated_at: Optional[str] = None


def _parse_flags(raw: str) -> Dict[str, bool]:
    try:
        data = json.loads(raw or "{}")
        if not isinstance(data, dict):
            return {}
        out: Dict[str, bool] = {}
        for k, v in data.items():
            if k in FLAG_KEYS and isinstance(v, bool):
                out[k] = v
        return out
    except Exception:
        return {}


def load_tenant_flags(conn, tenant_id: Optional[int]) -> TenantFlags:
    """Charge les flags depuis la DB. Merge avec config.DEFAULT_FLAGS."""
    tid = int(tenant_id or config.DEFAULT_TENANT_ID)
    merged = dict(config.DEFAULT_FLAGS)
    try:
        row = conn.execute(
            "SELECT flags_json, updated_at FROM tenant_config WHERE tenant_id = ?",
            (tid,),
        ).fetchone()
        if row and row[0]:
            merged.update(_parse_flags(row[0]))
            return TenantFlags(tenant_id=tid, flags=merged, source="db", updated_at=row[1])
    except Exception as e:
        logger.debug("load_tenant_flags: %s (using defaults)", e)
    return TenantFlags(tenant_id=tid, flags=merged, source="default", updated_at=None)


def get_flags(tenant_id: Optional[int] = None) -> Dict[str, bool]:
    """
    Retourne les flags effectifs (sans cache).
    PG-first read, SQLite fallback.
    """
    tid = tenant_id if tenant_id is not None and tenant_id > 0 else config.DEFAULT_TENANT_ID
    if config.USE_PG_TENANTS:
        try:
            from backend.tenants_pg import pg_get_tenant_flags
            result = pg_get_tenant_flags(tid)
            if result is not None:
                flags_dict, _ = result
                merged = dict(config.DEFAULT_FLAGS)
                for k, v in flags_dict.items():
                    if k in FLAG_KEYS and isinstance(v, bool):
                        merged[k] = v
                logger.debug("TENANT_READ source=pg get_flags tenant_id=%s", tid)
                return merged
        except Exception as e:
            logger.debug("TENANT_READ pg get_flags failed: %s (fallback sqlite)", e)
    db.ensure_tenant_config()
    conn = db.get_conn()
    try:
        tf = load_tenant_flags(conn, tid)
        return tf.flags
    finally:
        conn.close()


def get_consent_mode(tenant_id: Optional[int] = None) -> str:
    """
    Retourne le mode consentement pour un tenant : "implicit" (défaut) ou "explicit".
    Utilisé uniquement pour le canal vocal.
    """
    params = get_params(tenant_id)
    raw = (params.get("consent_mode") or "").strip().lower()
    if raw in ("implicit", "explicit"):
        return raw
    return "implicit"


def get_tenant_display_config(tenant_id: Optional[int] = None) -> Dict[str, str]:
    """
    Retourne {business_name, transfer_phone, horaires} pour affichage / prompts.
    Lecture depuis params_json avec repli sur config (OPENING_HOURS_DEFAULT pour horaires).
    """
    params = get_params(tenant_id)
    horaires = (params.get("horaires") or "").strip()
    if not horaires and hasattr(config, "OPENING_HOURS_DEFAULT"):
        horaires = derive_horaires_text(params) if params else config.OPENING_HOURS_DEFAULT
    if not horaires:
        horaires = derive_horaires_text(params)
    return {
        "business_name": (params.get("business_name") or "").strip() or config.BUSINESS_NAME,
        "transfer_phone": (params.get("transfer_phone") or "").strip() or config.TRANSFER_PHONE,
        "horaires": horaires or "horaires d'ouverture",
    }


def get_booking_rules(tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Retourne les règles de réservation pour un tenant (params_json).
    Fallbacks : duration=15, start=9, end=18, buffer=0, days=[0..4].
    """
    params = get_params(tenant_id) or {}
    booking_days = _coerce_booking_days(params.get("booking_days"))
    return {
        "duration_minutes": int(params.get("booking_duration_minutes") or 15),
        "start_hour": int(params.get("booking_start_hour") or 9),
        "end_hour": int(params.get("booking_end_hour") or 18),
        "buffer_minutes": int(params.get("booking_buffer_minutes") or 0),
        "booking_days": booking_days,
    }


def get_params(tenant_id: Optional[int] = None) -> Dict[str, str]:
    """
    Retourne params_json pour un tenant (calendar_provider, calendar_id, etc.).
    PG-first read, SQLite fallback.
    """
    tid = tenant_id if tenant_id is not None and tenant_id > 0 else config.DEFAULT_TENANT_ID
    if config.USE_PG_TENANTS:
        try:
            from backend.tenants_pg import pg_get_tenant_params
            result = pg_get_tenant_params(tid)
            if result is not None:
                params_dict, _ = result
                if isinstance(params_dict, dict):
                    logger.debug("TENANT_READ source=pg get_params tenant_id=%s", tid)
                    return params_dict
        except Exception as e:
            logger.debug("TENANT_READ pg get_params failed: %s (fallback sqlite)", e)
    db.ensure_tenant_config()
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT params_json FROM tenant_config WHERE tenant_id = ?",
            (tid,),
        ).fetchone()
        if row and row[0]:
            data = json.loads(row[0])
            return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.debug("get_params: %s", e)
    finally:
        conn.close()
    return {}


def set_params(tenant_id: int, params: Dict[str, str]) -> None:
    """Met à jour params_json (merge shallow). Clés à plat."""
    allowed = (
        "calendar_provider", "calendar_id", "contact_email", "consent_mode", "business_name",
        "transfer_phone", "transfer_number", "horaires",
        "responsible_phone", "manager_name", "billing_email", "vapi_assistant_id", "plan_key", "notes",
        "custom_included_minutes_month",
        "booking_duration_minutes", "booking_start_hour", "booking_end_hour",
        "booking_buffer_minutes", "booking_days",
    )
    filtered = {}
    for k, v in params.items():
        if k not in allowed or v is None:
            continue
        if k == "booking_days":
            if isinstance(v, (list, tuple)):
                filtered[k] = [int(x) for x in v]
            elif isinstance(v, str):
                try:
                    parsed = json.loads(v)
                    filtered[k] = [int(x) for x in parsed] if isinstance(parsed, (list, tuple)) else [0, 1, 2, 3, 4]
                except Exception:
                    filtered[k] = [int(x.strip()) for x in v.split(",") if x.strip().isdigit()]
                if not filtered[k]:
                    filtered[k] = [0, 1, 2, 3, 4]
            else:
                filtered[k] = [0, 1, 2, 3, 4]
        else:
            filtered[k] = str(v)
    if any(k in filtered for k in ("booking_days", "booking_start_hour", "booking_end_hour")):
        horaires_params = {
            "booking_days": filtered.get("booking_days", params.get("booking_days")),
            "booking_start_hour": filtered.get("booking_start_hour", params.get("booking_start_hour")),
            "booking_end_hour": filtered.get("booking_end_hour", params.get("booking_end_hour")),
        }
        filtered["horaires"] = derive_horaires_text(horaires_params)
    if not filtered:
        return
    db.ensure_tenant_config()
    conn = db.get_conn()
    try:
        cur = conn.execute("SELECT params_json FROM tenant_config WHERE tenant_id = ?", (tenant_id,))
        row = cur.fetchone()
        current = json.loads(row[0]) if row and row[0] else {}
        merged = {**current, **filtered}
        cur2 = conn.execute("SELECT flags_json FROM tenant_config WHERE tenant_id = ?", (tenant_id,))
        row2 = cur2.fetchone()
        flags = row2[0] if row2 and row2[0] else "{}"
        conn.execute(
            """
            INSERT OR REPLACE INTO tenant_config (tenant_id, flags_json, params_json, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            """,
            (tenant_id, flags, json.dumps(merged)),
        )
        conn.commit()
    finally:
        conn.close()


def set_flags(tenant_id: int, flags: Dict[str, bool]) -> None:
    """Met à jour les flags d'un tenant (merge avec existant)."""
    filtered = {k: v for k, v in flags.items() if k in FLAG_KEYS and isinstance(v, bool)}
    if not filtered:
        return
    db.ensure_tenant_config()
    current = get_flags(tenant_id)
    merged = {**current, **filtered}
    conn = db.get_conn()
    try:
        cur = conn.execute("SELECT params_json FROM tenant_config WHERE tenant_id = ?", (tenant_id,))
        row = cur.fetchone()
        params = row[0] if row and row[0] else "{}"
        conn.execute(
            """
            INSERT OR REPLACE INTO tenant_config (tenant_id, flags_json, params_json, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            """,
            (tenant_id, json.dumps(merged), params),
        )
        conn.commit()
    finally:
        conn.close()
