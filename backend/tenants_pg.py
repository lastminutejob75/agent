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
