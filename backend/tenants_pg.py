# backend/tenants_pg.py
"""
Postgres tenants / tenant_config / tenant_routing.
PG-first read, SQLite fallback. Healthcheck au boot.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Cache healthcheck (évite hammering si PG down)
_PG_OK: Optional[bool] = None
_PG_LAST_CHECK: float = 0
_HEALTHCHECK_INTERVAL_SEC = 60


def _pg_url() -> Optional[str]:
    return os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL")


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
        with psycopg.connect(url) as conn:
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
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT tenant_id FROM tenant_routing WHERE channel = %s AND key = %s AND is_active = TRUE",
                    (channel, did_key),
                )
                row = cur.fetchone()
                if row:
                    return (int(row[0]), "pg")
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


def pg_get_tenant_flags(tenant_id: int) -> Optional[Tuple[dict, str]]:
    """
    Charge flags_json depuis PG tenant_config.
    Returns (flags_dict, "pg") ou None si échec.
    """
    url = _pg_url()
    if not url:
        return None

    def _query() -> Optional[Tuple[dict, str]]:
        import psycopg
        with psycopg.connect(url) as conn:
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
        import psycopg
        with psycopg.connect(url) as conn:
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


def pg_create_tenant(
    name: str,
    contact_email: str = "",
    calendar_provider: str = "none",
    calendar_id: str = "",
    timezone: str = "Europe/Paris",
) -> Optional[int]:
    """
    Crée un tenant + tenant_config dans PG.
    Returns tenant_id ou None si échec.
    """
    url = _pg_url()
    if not url:
        return None

    def _do() -> Optional[int]:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO tenants (name, timezone, status) VALUES (%s, %s, 'active') RETURNING tenant_id",
                    (name.strip() or "Nouveau", timezone),
                )
                row = cur.fetchone()
                if not row:
                    return None
                tid = int(row[0])
                params = {
                    "calendar_provider": calendar_provider or "none",
                    "calendar_id": calendar_id or "",
                    "contact_email": contact_email or "",
                }
                cur.execute(
                    "INSERT INTO tenant_config (tenant_id, flags_json, params_json) VALUES (%s, %s, %s)",
                    (tid, "{}", json.dumps(params)),
                )
                conn.commit()
                return tid

    try:
        return _do()
    except Exception as e:
        logger.warning("pg_create_tenant failed: %s", e)
        return None


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
    """Met à jour params_json (merge). Champs autorisés: calendar_provider, calendar_id, contact_email."""
    allowed = {"calendar_provider", "calendar_id", "contact_email"}
    filtered = {k: str(v) for k, v in params.items() if k in allowed and v is not None}
    if not filtered:
        return True
    url = _pg_url()
    if not url:
        return False
    try:
        import psycopg
        current, _ = pg_get_tenant_params(tenant_id) or ({}, "pg")
        merged = {**current, **filtered}
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE tenant_config SET params_json = %s, updated_at = now() WHERE tenant_id = %s",
                    (json.dumps(merged), tenant_id),
                )
                conn.commit()
                return cur.rowcount > 0
    except Exception as e:
        logger.warning("pg_update_tenant_params failed: %s", e)
        return False


def pg_add_routing(channel: str, key: str, tenant_id: int) -> bool:
    """Ajoute ou met à jour une route DID → tenant."""
    key = key.strip().replace(" ", "")
    if not key:
        return False
    if key.startswith("00"):
        key = "+" + key[2:]
    url = _pg_url()
    if not url:
        return False
    try:
        import psycopg
        with psycopg.connect(url) as conn:
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
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(url, row_factory=dict_row) as conn:
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


def pg_fetch_tenants(include_inactive: bool = False) -> Optional[Tuple[list, str]]:
    """
    Charge tous les tenants depuis PG.
    Returns ([{"tenant_id", "name", "status"}, ...], "pg") ou None si échec.
    """
    url = _pg_url()
    if not url:
        return None

    def _query() -> Optional[Tuple[list, str]]:
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                if include_inactive:
                    cur.execute(
                        "SELECT tenant_id, name, status FROM tenants ORDER BY tenant_id"
                    )
                else:
                    cur.execute(
                        "SELECT tenant_id, name, status FROM tenants WHERE COALESCE(status, 'active') = 'active' ORDER BY tenant_id"
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
