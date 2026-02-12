"""
Audit events auth (RGPD, debug "je reçois pas l'email").
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def _pg_url() -> Optional[str]:
    return os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL")


def log_auth_event(tenant_id: Optional[int], email: str, event: str, context: Optional[str] = None) -> None:
    """Écrit auth event (silencieux si PG indisponible)."""
    url = _pg_url()
    if not url:
        return
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO auth_events (tenant_id, email, event, context)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (tenant_id, email.strip().lower(), event, context),
                )
                conn.commit()
    except Exception as e:
        logger.debug("auth_events: %s", e)
