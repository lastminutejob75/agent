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
            max_size=5,
            timeout=10.0,
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


@contextmanager
def pg_connection():
    """
    Context manager that yields a psycopg connection.
    Uses the pool if available, falls back to direct connect.
    """
    pool = get_pool()
    if pool is not None:
        try:
            with pool.connection() as conn:
                yield conn
                return
        except Exception as e:
            logger.debug("Pool connection failed, falling back to direct: %s", e)

    url = _get_pg_url()
    if not url:
        raise RuntimeError("No PostgreSQL URL configured")
    import psycopg
    from psycopg.rows import dict_row
    with psycopg.connect(url, row_factory=dict_row) as conn:
        yield conn
