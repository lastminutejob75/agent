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
from typing import Dict, Optional

from backend import config, db

logger = logging.getLogger(__name__)

FLAG_KEYS = (
    "ENABLE_LLM_ASSIST_START",
    "ENABLE_BARGEIN_SLOT_CHOICE",
    "ENABLE_SEQUENTIAL_SLOTS",
    "ENABLE_NO_FAQ_GUARD",
    "ENABLE_YES_AMBIGUOUS_ROUTER",
)


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
        horaires = config.OPENING_HOURS_DEFAULT
    return {
        "business_name": (params.get("business_name") or "").strip() or config.BUSINESS_NAME,
        "transfer_phone": (params.get("transfer_phone") or "").strip() or config.TRANSFER_PHONE,
        "horaires": horaires or "horaires d'ouverture",
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
    )
    filtered = {k: str(v) for k, v in params.items() if k in allowed and v is not None}
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
