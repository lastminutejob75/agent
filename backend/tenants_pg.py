# backend/tenants_pg.py
"""
Postgres tenants / tenant_config / tenant_routing.
PG-first read, SQLite fallback. Healthcheck au boot.
"""
from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

from backend.pg_tenant_context import set_tenant_id_on_connection

logger = logging.getLogger(__name__)

# Cache healthcheck (évite hammering si PG down)
_PG_OK: Optional[bool] = None
_PG_LAST_CHECK: float = 0
_HEALTHCHECK_INTERVAL_SEC = 60
_TENANT_POOL = None
_TENANT_POOL_URL: Optional[str] = None


def _pg_url() -> Optional[str]:
    return os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL")


def _dict_row_factory():
    from psycopg.rows import dict_row

    return dict_row


def _get_tenant_pool():
    global _TENANT_POOL, _TENANT_POOL_URL
    url = _pg_url()
    if not url:
        return None
    if _TENANT_POOL is not None and _TENANT_POOL_URL == url:
        return _TENANT_POOL
    try:
        from psycopg_pool import ConnectionPool
        from backend.pg_pool import _reset_pooled_connection

        _TENANT_POOL = ConnectionPool(
            conninfo=url,
            min_size=1,
            max_size=5,
            timeout=3.0,
            max_idle=300.0,
            reset=_reset_pooled_connection,
            kwargs={"row_factory": _dict_row_factory()},
        )
        _TENANT_POOL_URL = url
        logger.info("PG tenant connection pool created (min=1, max=5)")
        return _TENANT_POOL
    except Exception as e:
        logger.debug("Failed to create tenant PG pool, fallback direct connect: %s", e)
        return None


@contextmanager
def pg_tenants_connection():
    from backend.timing_log import time_block, wrap_connection

    pool = _get_tenant_pool()
    if pool is not None:
        try:
            with time_block("PG.connect[tenants:pool]"):
                with pool.connection() as conn:
                    yield wrap_connection(conn, "pg:tenants")
                    return
        except Exception as e:
            logger.debug("Tenant PG pool connection failed, fallback direct: %s", e)

    url = _pg_url()
    if not url:
        raise RuntimeError("No tenant PostgreSQL URL configured")
    import psycopg

    with time_block("PG.connect[tenants:direct]"):
        with psycopg.connect(url, row_factory=_dict_row_factory(), connect_timeout=3) as conn:
            yield wrap_connection(conn, "pg:tenants")


def _is_transient(e: Exception) -> bool:
    msg = str(e).lower()
    return any(x in msg for x in ("connection", "timeout", "refused", "could not connect", "server closed"))


def check_pg_health(force: bool = False) -> bool:
    """
    Healthcheck PG. Log [PG_HEALTH] ok | down.
    Cache 60s pour éviter hammering.
    """
    global _PG_OK, _PG_LAST_CHECK
    import time
    now = time.time()
    if not force and _PG_OK is not None and (now - _PG_LAST_CHECK) < _HEALTHCHECK_INTERVAL_SEC:
        return _PG_OK
    url = _pg_url()
    if not url:
        logger.debug("PG_HEALTH: no DATABASE_URL, skip")
        return False
    try:
        import psycopg
        with psycopg.connect(url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        _PG_OK = True
        _PG_LAST_CHECK = now
        logger.info("PG_HEALTH ok")
        return True
    except Exception as e:
        _PG_OK = False
        _PG_LAST_CHECK = now
        logger.warning("PG_HEALTH down err=%s -> tenant read fallback sqlite", e)
        return False


def pg_resolve_tenant_id(channel: str, did_key: str) -> Optional[Tuple[int, str]]:
    """
    Résout tenant_id depuis PG tenant_routing.
    Returns (tenant_id, "pg") ou None si échec.
    PG utilise colonne 'key' (équivalent did_key).
    """
    url = _pg_url()
    if not url:
        return None

    def _query() -> Optional[Tuple[int, str]]:
        from backend.pg_pool import pg_connection
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT tenant_id FROM tenant_routing WHERE channel = %s AND key = %s AND is_active = TRUE",
                    (channel, did_key),
                )
                row = cur.fetchone()
                if row:
                    tenant_id = row.get("tenant_id") if isinstance(row, dict) else row[0]
                    return (int(tenant_id), "pg")
        return None

    try:
        return _query()
    except Exception as e:
        if _is_transient(e):
            try:
                return _query()
            except Exception:
                pass
        logger.warning("pg_resolve_tenant_id failed channel=%s key=%s err=%s", channel, did_key, str(e)[:120])
        return None


def pg_find_tenant_id_by_vapi_assistant_id(assistant_id: str) -> Optional[int]:
    """
    Retrouve un tenant_id à partir du vapi_assistant_id stocké dans tenant_config.params_json.
    Utilisé en fallback de routage quand Vapi ne renvoie pas le DID mais inclut encore l'assistant.
    """
    url = _pg_url()
    assistant_id = (assistant_id or "").strip()
    if not url or not assistant_id:
        return None

    def _query() -> Optional[int]:
        from backend.pg_pool import pg_connection
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tenant_id
                    FROM tenant_config
                    WHERE COALESCE(params_json->>'vapi_assistant_id', '') = %s
                    LIMIT 1
                    """,
                    (assistant_id,),
                )
                row = cur.fetchone()
                if row:
                    tenant_id = row.get("tenant_id") if isinstance(row, dict) else row[0]
                    return int(tenant_id)
        return None

    try:
        return _query()
    except Exception as e:
        if _is_transient(e):
            try:
                return _query()
            except Exception:
                pass
        logger.warning("pg_find_tenant_id_by_vapi_assistant_id failed assistant_id=%s err=%s", assistant_id[:24], str(e)[:120])
        return None


def pg_tenant_exists(tenant_id: int) -> bool:
    """Retourne True si le tenant existe dans PG."""
    url = _pg_url()
    if not url or int(tenant_id) < 1:
        return False

    def _query() -> bool:
        from backend.pg_pool import pg_connection
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM tenants WHERE tenant_id = %s LIMIT 1", (int(tenant_id),))
                return cur.fetchone() is not None

    try:
        return _query()
    except Exception as e:
        if _is_transient(e):
            try:
                return _query()
            except Exception:
                pass
        logger.warning("pg_tenant_exists failed tenant_id=%s err=%s", tenant_id, str(e)[:120])
        return False


def pg_get_tenant_flags(tenant_id: int) -> Optional[Tuple[dict, str]]:
    """
    Charge flags_json depuis PG tenant_config.
    Returns (flags_dict, "pg") ou None si échec.
    """
    url = _pg_url()
    if not url:
        return None

    def _query() -> Optional[Tuple[dict, str]]:
        with pg_tenants_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT flags_json FROM tenant_config WHERE tenant_id = %s",
                    (tenant_id,),
                )
                row = cur.fetchone()
                if row and row[0]:
                    data = row[0]
                    if hasattr(data, "copy"):
                        data = dict(data)
                    elif isinstance(data, str):
                        data = json.loads(data) if data else {}
                    return (data if isinstance(data, dict) else {}, "pg")
        return None

    try:
        return _query()
    except Exception as e:
        if _is_transient(e):
            try:
                return _query()
            except Exception:
                pass
        return None


def pg_get_tenant_params(tenant_id: int) -> Optional[Tuple[dict, str]]:
    """
    Charge params_json depuis PG tenant_config.
    Returns (params_dict, "pg") ou None si échec.
    """
    url = _pg_url()
    if not url:
        return None

    def _query() -> Optional[Tuple[dict, str]]:
        with pg_tenants_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT params_json FROM tenant_config WHERE tenant_id = %s",
                    (tenant_id,),
                )
                row = cur.fetchone()
                if row and row[0]:
                    data = row[0]
                    if hasattr(data, "copy"):
                        data = dict(data)
                    elif isinstance(data, str):
                        data = json.loads(data) if data else {}
                    return (data if isinstance(data, dict) else {}, "pg")
        return None

    try:
        return _query()
    except Exception as e:
        if _is_transient(e):
            try:
                return _query()
            except Exception:
                pass
        return None


def pg_load_tenant_params_bypass(tenant_id: int) -> dict:
    """Charge params_json en contournant le RLS tenant (merge sûr des patches)."""
    url = _pg_url()
    if not url:
        return {}
    try:
        import psycopg
        from backend.pg_tenant_context import set_bypass_tenant_rls_on_connection

        with psycopg.connect(url) as conn:
            set_bypass_tenant_rls_on_connection(conn, enabled=True)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT params_json FROM tenant_config WHERE tenant_id = %s",
                    (tenant_id,),
                )
                row = cur.fetchone()
                if not row or not row[0]:
                    return {}
                data = row[0]
                if isinstance(data, dict):
                    return dict(data)
                if isinstance(data, str):
                    return json.loads(data) if data else {}
        return {}
    except Exception as e:
        logger.warning("pg_load_tenant_params_bypass failed tenant_id=%s: %s", tenant_id, e)
        return {}


def pg_create_tenant(
    name: str,
    contact_email: str = "",
    calendar_provider: str = "none",
    calendar_id: str = "",
    timezone: str = "Europe/Paris",
    business_type: Optional[str] = None,
    notes: Optional[str] = None,
    status: str = "active",
    plan_key: Optional[str] = None,
    billing_email: Optional[str] = None,
) -> Optional[int]:
    """
    Crée un tenant + tenant_config dans PG.
    Returns tenant_id ou None si échec.
    """
    url = _pg_url()
    if not url:
        return None

    status_val = (status or "active").strip() or "active"

    def _do() -> Optional[int]:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO tenants (name, timezone, status) VALUES (%s, %s, %s) RETURNING tenant_id",
                    (name.strip() or "Nouveau", timezone, status_val),
                )
                row = cur.fetchone()
                if not row:
                    return None
                tid = int(row[0])
                params = {
                    "calendar_provider": calendar_provider or "none",
                    "calendar_id": calendar_id or "",
                    "contact_email": contact_email or "",
                    "business_type": (business_type or "").strip() or None,
                    "notes": (notes or "").strip() or None,
                    "plan_key": (plan_key or "").strip() or None,
                    "billing_email": (billing_email or "").strip() or None,
                }
                params = {k: v for k, v in params.items() if v is not None}
                cur.execute(
                    "INSERT INTO tenant_config (tenant_id, flags_json, params_json) VALUES (%s, %s, %s)",
                    (tid, "{}", json.dumps(params)),
                )
                # Créer tenant_user pour contact_email (login email+mdp ou Google)
                if contact_email and contact_email.strip():
                    try:
                        cur.execute(
                            """
                            INSERT INTO tenant_users (tenant_id, email, role)
                            VALUES (%s, %s, 'owner')
                            ON CONFLICT (email) DO UPDATE SET tenant_id = EXCLUDED.tenant_id
                            """,
                            (tid, contact_email.strip().lower()),
                        )
                    except Exception as eu:
                        logger.debug("tenant_user create during onboarding: %s", eu)
                conn.commit()
                return tid

    try:
        return _do()
    except Exception as e:
        logger.warning("pg_create_tenant failed: %s", e)
        return None


def pg_update_tenant_name(tenant_id: int, name: str) -> bool:
    """Met à jour le nom public du tenant dans la table tenants."""
    url = _pg_url()
    if not url:
        return False
    clean_name = (name or "").strip()
    if not clean_name:
        return True
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE tenants SET name = %s WHERE tenant_id = %s",
                    (clean_name, tenant_id),
                )
                conn.commit()
                return cur.rowcount > 0
    except Exception as e:
        logger.warning("pg_update_tenant_name failed: %s", e)
        return False


def pg_update_tenant_flags(tenant_id: int, flags: dict) -> bool:
    """Met à jour flags_json (merge)."""
    url = _pg_url()
    if not url:
        return False
    try:
        import psycopg
        current, _ = pg_get_tenant_flags(tenant_id) or ({}, "pg")
        merged = {**current, **{k: v for k, v in flags.items() if isinstance(v, bool)}}
        with psycopg.connect(url) as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE tenant_config SET flags_json = %s, updated_at = now() WHERE tenant_id = %s",
                    (json.dumps(merged), tenant_id),
                )
                conn.commit()
                return cur.rowcount > 0
    except Exception as e:
        logger.warning("pg_update_tenant_flags failed: %s", e)
        return False


def pg_update_tenant_params(tenant_id: int, params: dict) -> bool:
    """Met à jour params_json (merge shallow). Clés à plat pour éviter merge profond."""
    from backend.cabinet_profile_pg import canonicalize_cabinet_params

    params = canonicalize_cabinet_params(params or {})
    allowed = {
        "calendar_provider", "calendar_id", "contact_email", "timezone", "consent_mode", "business_name",
        "transfer_phone", "transfer_number", "horaires",
        "responsible_phone", "manager_name", "billing_email", "vapi_assistant_id", "plan_key", "notes",
        "custom_included_minutes_month",
        "assistant_name", "phone_number", "sector",
        "specialty_label", "address_line1", "postal_code", "city", "agenda_software",
        "client_onboarding_completed",
        "dashboard_team_note", "dashboard_team_note_updated_at",
        "hds_enabled",
        "faq_json",
        "booking_duration_minutes", "booking_start_hour", "booking_end_hour",
        "booking_buffer_minutes", "booking_days",
        "mirror_google_bookings_to_internal",
        "transfer_assistant_phone", "transfer_practitioner_phone",
        "transfer_live_enabled", "transfer_callback_enabled",
        "transfer_cases", "transfer_hours", "transfer_always_urgent", "transfer_no_consultation",
        "transfer_config_confirmed_signature", "transfer_config_confirmed_at",
        # --- "Mon cabinet" : champs profil ---
        "practitioner_name", "website_url", "languages", "accepts_new_patients",
        "practitioner_photo_url", "public_slug", "address_line",
        # --- "Mon cabinet" : horaires / fermetures ---
        "opening_hours_json",
        "temporary_closure_enabled", "temporary_closure_start", "temporary_closure_end",
        "temporary_closure_message",
        # --- "Mon cabinet" : règles RDV ---
        "default_appointment_duration_minutes", "minimum_booking_notice_hours",
        "appointment_reschedule_allowed", "appointment_reschedule_notice_hours",
        "appointment_cancel_allowed", "appointment_cancel_notice_hours",
        "emergency_instruction", "new_patient_instruction", "booking_notes",
        "appointment_reasons_json",
        # --- "Mon cabinet" : Clara / instructions assistant ---
        "welcome_message", "documents_to_bring", "access_instructions", "payment_methods",
        "parking_info", "pmr_access", "sensitive_medical_instruction",
        "escalation_instruction", "human_handoff_instruction", "faq_items_json",
        # --- meta lead (set à la création depuis l'admin) ---
        "lead_id", "lead_source", "lead_daily_call_volume", "lead_primary_pain_point",
        "lead_opening_hours",
    }
    bool_keys = {
        "accepts_new_patients",
        "temporary_closure_enabled",
        "appointment_reschedule_allowed", "appointment_cancel_allowed",
        "mirror_google_bookings_to_internal",
        "transfer_live_enabled", "transfer_callback_enabled",
        "transfer_always_urgent", "transfer_no_consultation",
        "client_onboarding_completed",
        "hds_enabled",
    }
    int_keys = {
        "default_appointment_duration_minutes", "minimum_booking_notice_hours",
        "appointment_reschedule_notice_hours", "appointment_cancel_notice_hours",
        "booking_duration_minutes", "booking_buffer_minutes",
        "custom_included_minutes_month",
    }
    json_keys = {
        "languages", "opening_hours_json", "appointment_reasons_json",
        "faq_items_json", "lead_opening_hours",
    }
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
                if not filtered.get(k):
                    filtered[k] = [0, 1, 2, 3, 4]
            else:
                filtered[k] = [0, 1, 2, 3, 4]
        elif k == "faq_json":
            if isinstance(v, str):
                try:
                    parsed = json.loads(v)
                    filtered[k] = parsed if isinstance(parsed, list) else []
                except Exception:
                    filtered[k] = []
            elif isinstance(v, list):
                filtered[k] = v
            else:
                filtered[k] = []
        elif k == "transfer_cases":
            if isinstance(v, (list, tuple)):
                filtered[k] = [str(x) for x in v if str(x).strip()]
            elif isinstance(v, str):
                try:
                    parsed = json.loads(v)
                    filtered[k] = [str(x) for x in parsed] if isinstance(parsed, (list, tuple)) else []
                except Exception:
                    filtered[k] = [x.strip() for x in v.split(",") if x.strip()]
            else:
                filtered[k] = []
        elif k == "transfer_hours":
            if isinstance(v, dict):
                filtered[k] = v
            elif isinstance(v, str):
                try:
                    parsed = json.loads(v)
                    filtered[k] = parsed if isinstance(parsed, dict) else {}
                except Exception:
                    filtered[k] = {}
            else:
                filtered[k] = {}
        elif k in bool_keys:
            if isinstance(v, bool):
                filtered[k] = v
            elif isinstance(v, (int, float)):
                filtered[k] = bool(v)
            elif isinstance(v, str):
                filtered[k] = v.strip().lower() in ("1", "true", "yes", "on", "oui")
            else:
                filtered[k] = bool(v)
        elif k in int_keys:
            try:
                filtered[k] = int(v)
            except (TypeError, ValueError):
                continue
        elif k in json_keys:
            if isinstance(v, (list, dict)):
                filtered[k] = v
            elif isinstance(v, str):
                try:
                    filtered[k] = json.loads(v)
                except Exception:
                    continue
            else:
                continue
        else:
            filtered[k] = str(v)
    if not filtered:
        return True
    url = _pg_url()
    if not url:
        return False
    try:
        import psycopg
        current, _ = pg_get_tenant_params(tenant_id) or ({}, "pg")
        if not isinstance(current, dict):
            current = {}
        if len(current) <= 1:
            bypass = pg_load_tenant_params_bypass(tenant_id)
            if len(bypass) > len(current):
                current = bypass
        merged = {**current, **filtered}
        protected = (
            "vapi_assistant_id",
            "calendar_id",
            "calendar_provider",
            "contact_email",
            "phone_number",
            "public_slug",
        )
        dropped = [k for k in protected if current.get(k) and not merged.get(k)]
        if dropped:
            logger.error(
                "pg_update_tenant_params blocked tenant_id=%s dropped=%s patch_keys=%s",
                tenant_id,
                dropped,
                list(filtered.keys()),
            )
            return False
        # timezone est dans tenants, pas params_json
        tz_val = merged.pop("timezone", None)
        with psycopg.connect(url) as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE tenant_config SET params_json = %s, updated_at = now() WHERE tenant_id = %s",
                    (json.dumps(merged), tenant_id),
                )
                if tz_val:
                    cur.execute(
                        "UPDATE tenants SET timezone = %s WHERE tenant_id = %s",
                        (tz_val, tenant_id),
                    )
                conn.commit()
                return cur.rowcount > 0
    except Exception as e:
        logger.warning("pg_update_tenant_params failed: %s", e)
        return False


def pg_delete_tenant_param_keys(tenant_id: int, keys: list[str]) -> bool:
    """Supprime des clés de params_json pour revenir aux fallbacks par défaut."""
    keys = [str(k).strip() for k in (keys or []) if str(k).strip()]
    if not keys:
        return True
    url = _pg_url()
    if not url:
        return False
    try:
        import psycopg

        current, _ = pg_get_tenant_params(tenant_id) or ({}, "pg")
        if not isinstance(current, dict):
            current = {}
        if len(current) <= 1:
            bypass = pg_load_tenant_params_bypass(tenant_id)
            if len(bypass) > len(current):
                current = bypass
        for key in keys:
            current.pop(key, None)
        with psycopg.connect(url) as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE tenant_config SET params_json = %s, updated_at = now() WHERE tenant_id = %s",
                    (json.dumps(current), tenant_id),
                )
                conn.commit()
                return cur.rowcount > 0
    except Exception as e:
        logger.warning("pg_delete_tenant_param_keys failed: %s", e)
        return False


def pg_add_routing(channel: str, key: str, tenant_id: int) -> bool:
    """Ajoute ou met à jour une route DID → tenant. Rejette la réassignation du numéro démo (voir tenant_routing.guard_demo_number_routing)."""
    key = key.strip().replace(" ", "")
    if not key:
        return False
    if key.startswith("00"):
        key = "+" + key[2:]
    from backend.tenant_routing import guard_demo_number_routing
    guard_demo_number_routing(channel=channel, did_key=key, tenant_id=tenant_id)
    url = _pg_url()
    if not url:
        return False
    if not pg_tenant_exists(tenant_id):
        logger.warning("pg_add_routing skipped: tenant_id=%s missing in tenants", tenant_id)
        return False
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tenant_routing (channel, key, tenant_id, is_active, updated_at)
                    VALUES (%s, %s, %s, TRUE, now())
                    ON CONFLICT (channel, key) DO UPDATE SET tenant_id = %s, is_active = TRUE, updated_at = now()
                    """,
                    (channel, key, tenant_id, tenant_id),
                )
                conn.commit()
                return True
    except Exception as e:
        logger.warning("pg_add_routing failed: %s", e)
        return False


def pg_get_routing_for_tenant(tenant_id: int) -> Optional[list]:
    """Liste les routes (channel, key) pour un tenant."""
    url = _pg_url()
    if not url:
        return None
    try:
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(url, row_factory=dict_row) as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT channel, key, is_active FROM tenant_routing WHERE tenant_id = %s ORDER BY channel, key",
                    (tenant_id,),
                )
                return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.warning("pg_get_routing_for_tenant failed: %s", e)
        return None


def pg_get_tenant_full(tenant_id: int) -> Optional[dict]:
    """Charge tenant + config + routing pour admin."""
    url = _pg_url()
    if not url:
        return None
    try:
        with pg_tenants_connection() as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute("SELECT tenant_id, name, timezone, status, created_at FROM tenants WHERE tenant_id = %s", (tenant_id,))
                t = cur.fetchone()
                if not t:
                    return None
                cur.execute("SELECT flags_json, params_json FROM tenant_config WHERE tenant_id = %s", (tenant_id,))
                c = cur.fetchone()
                flags = c["flags_json"] if c else {}
                params = c["params_json"] if c else {}
                flags = flags if isinstance(flags, dict) else (json.loads(flags) if isinstance(flags, str) else {})
                params = params if isinstance(params, dict) else (json.loads(params) if isinstance(params, str) else {})
                cur.execute("SELECT channel, key, is_active FROM tenant_routing WHERE tenant_id = %s", (tenant_id,))
                routes = [dict(r) for r in cur.fetchall()]
                return {
                    "tenant_id": t["tenant_id"],
                    "name": t["name"],
                    "timezone": t["timezone"],
                    "status": t["status"],
                    "created_at": str(t["created_at"]) if t.get("created_at") else None,
                    "flags": flags,
                    "params": params,
                    "routing": routes,
                }
    except Exception as e:
        logger.warning("pg_get_tenant_full failed: %s", e)
        return None


def pg_get_tenant_full_batch(tenant_ids: List[int]) -> Dict[int, Dict[str, Any]]:
    """
    Équivalent de plusieurs pg_get_tenant_full en 3 requêtes (tenants + config + routing).
    Utilisé par la file d'activation cockpit pour éviter N× aller-retour PG.
    """
    ids = sorted({int(x) for x in tenant_ids if x is not None})
    if not ids:
        return {}
    url = _pg_url()
    if not url:
        return {}
    out: Dict[int, Dict[str, Any]] = {}
    try:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tenant_id, name, timezone, status, created_at
                    FROM tenants WHERE tenant_id = ANY(%s)
                    """,
                    (ids,),
                )
                t_rows = cur.fetchall() or []
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT tenant_id, flags_json, params_json FROM tenant_config WHERE tenant_id = ANY(%s)",
                    (ids,),
                )
                cfg_by_tid: Dict[int, Dict[str, Dict]] = {}
                for c in cur.fetchall() or []:
                    tid = int(c["tenant_id"])
                    flags = c.get("flags_json") or {}
                    params = c.get("params_json") or {}
                    flags = flags if isinstance(flags, dict) else (json.loads(flags) if isinstance(flags, str) else {})
                    params = params if isinstance(params, dict) else (json.loads(params) if isinstance(params, str) else {})
                    cfg_by_tid[tid] = {"flags": flags, "params": params}
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tenant_id, channel, key, is_active FROM tenant_routing
                    WHERE tenant_id = ANY(%s) ORDER BY tenant_id, channel, key
                    """,
                    (ids,),
                )
                routes_by_tid: Dict[int, List[dict]] = {}
                for rr in cur.fetchall() or []:
                    tid = int(rr["tenant_id"])
                    routes_by_tid.setdefault(tid, []).append(
                        {
                            "channel": rr["channel"],
                            "key": rr["key"],
                            "is_active": rr.get("is_active", True),
                        }
                    )
            for tr in t_rows:
                tid = int(tr["tenant_id"])
                cfg = cfg_by_tid.get(tid, {"flags": {}, "params": {}})
                out[tid] = {
                    "tenant_id": tid,
                    "name": tr["name"],
                    "timezone": tr["timezone"],
                    "status": tr["status"],
                    "created_at": str(tr["created_at"]) if tr.get("created_at") else None,
                    "flags": cfg["flags"],
                    "params": cfg["params"],
                    "routing": routes_by_tid.get(tid, []),
                }
    except Exception as e:
        logger.warning("pg_get_tenant_full_batch failed: %s", e)
        return {}
    return out


def pg_fetch_tenants(include_inactive: bool = False) -> Optional[Tuple[list, str]]:
    """
    Charge tous les tenants depuis PG (+ champs utiles liste admin depuis tenant_config.params_json).
    Returns ([{"tenant_id", "name", "status", "contact_email", ...}, ...], "pg") ou None si échec.
    """
    url = _pg_url()
    if not url:
        return None

    def _query() -> Optional[Tuple[list, str]]:
        import psycopg
        from psycopg.rows import dict_row
        base_sql = """
            SELECT t.tenant_id,
                   t.name,
                   t.status,
                   COALESCE(tc.params_json->>'contact_email', '') AS contact_email,
                   COALESCE(tc.params_json->>'profession', '') AS profession,
                   COALESCE(tc.params_json->>'city', '') AS city,
                   COALESCE(tc.params_json->>'primary_practitioner_name', '') AS primary_practitioner_name,
                   COALESCE(tc.params_json->>'plan_key', '') AS plan_key_params
            FROM tenants t
            LEFT JOIN tenant_config tc ON tc.tenant_id = t.tenant_id
        """
        with psycopg.connect(url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                if include_inactive:
                    cur.execute(base_sql + " ORDER BY t.tenant_id")
                else:
                    cur.execute(
                        base_sql + " WHERE COALESCE(t.status, 'active') = 'active' ORDER BY t.tenant_id"
                    )
                rows = cur.fetchall()
                return ([dict(r) for r in rows], "pg")

    try:
        return _query()
    except Exception as e:
        if _is_transient(e):
            try:
                return _query()
            except Exception:
                pass
        return None


def pg_deactivate_tenant(tenant_id: int) -> bool:
    """Passe le tenant en status inactive (soft delete). Retourne True si OK."""
    url = _pg_url()
    if not url:
        return False
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE tenants SET status = 'inactive' WHERE tenant_id = %s", (tenant_id,))
                conn.commit()
                return cur.rowcount > 0
    except Exception as e:
        logger.warning("pg_deactivate_tenant failed: %s", e)
        return False


def pg_delete_tenant(tenant_id: int) -> bool:
    """
    Supprime un tenant et ses données liées créées pendant le provisioning.
    Suppression compensatoire utilisée uniquement pour rollback.
    """
    url = _pg_url()
    if not url:
        return False
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                for table in ("tenant_routing", "tenant_users", "tenant_config", "tenant_billing"):
                    try:
                        cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))
                    except Exception as e:
                        if "does not exist" not in str(e).lower():
                            raise
                cur.execute("DELETE FROM tenants WHERE tenant_id = %s", (tenant_id,))
                conn.commit()
                return True
    except Exception as e:
        logger.warning("pg_delete_tenant failed: %s", e)
        return False
