# backend/ivr_events_pg.py
"""
Postgres ivr_events (dual-write quand USE_PG_EVENTS=true).
Écriture seulement ; lecture = export_weekly_kpis.py.
- Idempotent : ON CONFLICT DO NOTHING (retry, backfill rejoué)
- Retry léger (1x) sur erreurs transitoires
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from backend.pg_tenant_context import set_tenant_id_on_connection

logger = logging.getLogger(__name__)

# Erreurs transitoires (réessayer 1x)
_TRANSIENT_ERRORS = (
    "connection",
    "timeout",
    "Connection refused",
    "could not connect",
    "server closed",
    "terminating connection",
)


def _pg_url() -> Optional[str]:
    return os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")


def _is_transient(e: Exception) -> bool:
    msg = str(e).lower()
    return any(x.lower() in msg for x in _TRANSIENT_ERRORS)


def create_ivr_event_pg(
    client_id: int,
    call_id: str,
    event: str,
    context: Optional[str] = None,
    reason: Optional[str] = None,
    created_at: Optional[str] = None,
) -> bool:
    """
    Insert dans Postgres ivr_events.
    ON CONFLICT DO NOTHING : idempotent (retry, backfill rejoué).
    created_at requis pour contrainte unique ; défaut now() si absent.
    Returns True si succès, False sinon (silencieux pour ne pas bloquer le flow).
    """
    url = _pg_url()
    if not url:
        return False
    call_id_val = call_id or ""

    def _do_insert() -> bool:
        import psycopg
        with psycopg.connect(url) as conn:
            set_tenant_id_on_connection(conn, client_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ivr_events (client_id, call_id, event, context, reason, created_at)
                    VALUES (%s, %s, %s, %s, %s, COALESCE(%s::timestamptz, now()))
                    ON CONFLICT (client_id, call_id, event, created_at) DO NOTHING
                    """,
                    (client_id, call_id_val, event, context, reason, created_at),
                )
                conn.commit()
        return True

    try:
        return _do_insert()
    except ImportError:
        logger.debug("ivr_events_pg: psycopg not installed")
        return False
    except Exception as e:
        if _is_transient(e):
            try:
                return _do_insert()
            except Exception as e2:
                logger.warning("ivr_events_pg: insert failed (retry): %s", e2)
                return False
        logger.warning("ivr_events_pg: insert failed: %s", e)
        return False


def consent_obtained_exists_pg(client_id: int, call_id: str) -> bool:
    """True si consent_obtained déjà persisté pour ce call (idempotence retry)."""
    url = _pg_url()
    if not url:
        return False
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            set_tenant_id_on_connection(conn, client_id)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM ivr_events WHERE client_id = %s AND call_id = %s AND event = 'consent_obtained' LIMIT 1",
                    (client_id, call_id or ""),
                )
                return cur.fetchone() is not None
    except Exception:
        return False


def is_pg_available() -> bool:
    """True si Postgres configuré et accessible."""
    url = _pg_url()
    if not url:
        return False
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception:
        return False
