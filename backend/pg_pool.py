"""
Singleton connection pool for PostgreSQL (psycopg_pool).
Eliminates per-request TCP+SSL connection overhead on Railway.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)

_pool = None
_pool_url: Optional[str] = None


def _get_pg_url() -> Optional[str]:
    return (os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL") or "").strip() or None


def get_pool():
    """Return the singleton ConnectionPool, creating it on first call."""
    global _pool, _pool_url
    url = _get_pg_url()
    if not url:
        return None
    if _pool is not None and _pool_url == url:
        return _pool
    try:
        from psycopg_pool import ConnectionPool
        _pool = ConnectionPool(
            conninfo=url,
            min_size=1,
            max_size=max(5, min(int(os.environ.get("PG_POOL_MAX_SIZE", "12") or "12"), 32)),
            timeout=3.0,
            max_idle=300.0,
            kwargs={"row_factory": _dict_row_factory()},
        )
        _pool_url = url
        logger.info("PG connection pool created (min=1, max=5)")
        return _pool
    except Exception as e:
        logger.warning("Failed to create PG pool, falling back to direct connect: %s", e)
        return None


def _dict_row_factory():
    from psycopg.rows import dict_row
    return dict_row


def _urls_equivalent(a: Optional[str], b: Optional[str]) -> bool:
    return bool(a and b and str(a).strip() == str(b).strip())


@contextmanager
def pg_connection():
    """
    Context manager that yields a psycopg connection.
    Uses the pool if available, falls back to direct connect.
    """
    url = _get_pg_url()
    if not url:
        raise RuntimeError("No PostgreSQL URL configured")
    with pg_connection_for(url) as conn:
        yield conn


@contextmanager
def pg_connection_for(url: Optional[str]):
    """
    Connexion PG pour une URL donnée.
    Réutilise le pool singleton quand l'URL correspond à DATABASE_URL / PG_EVENTS_URL
    (évite un handshake TCP+TLS par requête cockpit sur Railway).
    """
    target = (url or "").strip()
    if not target:
        raise RuntimeError("No PostgreSQL URL configured")

    from backend.timing_log import time_block, wrap_connection

    pool_url = _get_pg_url()
    pool = get_pool()
    if pool is not None and _urls_equivalent(target, pool_url):
        try:
            with time_block("PG.connect[events:pool]"):
                with pool.connection() as conn:
                    yield wrap_connection(conn, "pg:events")
                    return
        except Exception as e:
            logger.debug("Pool connection failed, falling back to direct: %s", e)

    import psycopg
    from psycopg.rows import dict_row

    with time_block("PG.connect[events:direct]"):
        with psycopg.connect(target, row_factory=dict_row, connect_timeout=3) as conn:
            yield wrap_connection(conn, "pg:events")
