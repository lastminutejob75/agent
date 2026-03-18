# backend/vapi_calls_pg.py
"""
Persistance webhook Vapi : status-update → vapi_calls, transcript → call_transcripts.
Pour dashboard admin + client (appels en cours, durée, transcription, raison fin).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_TABLES_CREATED = False

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS vapi_calls (
    tenant_id INT NOT NULL,
    call_id TEXT NOT NULL,
    customer_number TEXT,
    assistant_id TEXT,
    phone_number_id TEXT,
    status TEXT NOT NULL DEFAULT 'unknown',
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    ended_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, call_id)
);
CREATE INDEX IF NOT EXISTS idx_vapi_calls_tenant_updated ON vapi_calls (tenant_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_vapi_calls_tenant_status ON vapi_calls (tenant_id, status) WHERE status IN ('ringing', 'in-progress');

CREATE TABLE IF NOT EXISTS call_transcripts (
    id BIGSERIAL PRIMARY KEY,
    tenant_id INT NOT NULL,
    call_id TEXT NOT NULL,
    role TEXT NOT NULL,
    transcript TEXT NOT NULL,
    is_final BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_call_transcripts_tenant_call ON call_transcripts (tenant_id, call_id, created_at);
"""


def _pg_url() -> Optional[str]:
    return os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")


def ensure_tables() -> bool:
    global _TABLES_CREATED
    if _TABLES_CREATED:
        return True
    url = _pg_url()
    if not url:
        return False
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                for stmt in _CREATE_SQL.strip().split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        cur.execute(stmt)
            conn.commit()
        _TABLES_CREATED = True
        logger.debug("vapi_calls_pg: tables created or already exist")
        return True
    except Exception as e:
        logger.warning("vapi_calls_pg: ensure tables failed: %s", e)
        return False


def upsert_vapi_call(
    tenant_id: int,
    call_id: str,
    *,
    customer_number: Optional[str] = None,
    assistant_id: Optional[str] = None,
    phone_number_id: Optional[str] = None,
    status: Optional[str] = None,
    started_at: Optional[datetime] = None,
    ended_at: Optional[datetime] = None,
    ended_reason: Optional[str] = None,
) -> bool:
    """Upsert une ligne vapi_calls (status-update)."""
    if not call_id or not (customer_number or assistant_id or phone_number_id or status or started_at or ended_at or ended_reason):
        return False
    url = _pg_url()
    if not url:
        return False
    if not ensure_tables():
        return False
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO vapi_calls (tenant_id, call_id, customer_number, assistant_id, phone_number_id, status, started_at, ended_at, ended_reason, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (tenant_id, call_id) DO UPDATE SET
                        customer_number = COALESCE(EXCLUDED.customer_number, vapi_calls.customer_number),
                        assistant_id = COALESCE(EXCLUDED.assistant_id, vapi_calls.assistant_id),
                        phone_number_id = COALESCE(EXCLUDED.phone_number_id, vapi_calls.phone_number_id),
                        status = CASE
                            WHEN EXCLUDED.status = 'unknown' THEN COALESCE(vapi_calls.status, 'unknown')
                            ELSE COALESCE(EXCLUDED.status, vapi_calls.status, 'unknown')
                        END,
                        started_at = COALESCE(EXCLUDED.started_at, vapi_calls.started_at),
                        ended_at = COALESCE(EXCLUDED.ended_at, vapi_calls.ended_at),
                        ended_reason = COALESCE(EXCLUDED.ended_reason, vapi_calls.ended_reason),
                        updated_at = now()
                    """,
                    (
                        tenant_id,
                        call_id,
                        customer_number,
                        assistant_id,
                        phone_number_id,
                        status or "unknown",
                        started_at,
                        ended_at,
                        ended_reason,
                    ),
                )
            conn.commit()
        return True
    except Exception as e:
        logger.warning("vapi_calls_pg: upsert failed tenant_id=%s call_id=%s: %s", tenant_id, (call_id or "")[:24], e)
        return False


def insert_call_transcript(
    tenant_id: int,
    call_id: str,
    role: str,
    transcript: str,
    is_final: bool = False,
) -> bool:
    """Insert une ligne call_transcripts (message type=transcript)."""
    if not call_id or not transcript:
        return False
    url = _pg_url()
    if not url:
        return False
    if not ensure_tables():
        return False
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO call_transcripts (tenant_id, call_id, role, transcript, is_final)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (tenant_id, call_id, (role or "user").lower()[:32], transcript[:65535], bool(is_final)),
                )
            conn.commit()
        return True
    except Exception as e:
        logger.warning("vapi_calls_pg: insert transcript failed tenant_id=%s call_id=%s: %s", tenant_id, (call_id or "")[:24], e)
        return False
