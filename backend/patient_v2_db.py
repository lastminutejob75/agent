"""Schéma V2 contexte patient + questionnaires (dual-write SQLite / Postgres)."""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

from backend.db import _pg_events_url, _pg_table_exists, get_conn, normalize_phone_number

logger = logging.getLogger(__name__)

# ===== DDL SQLite =====

_SQLITE_TABLES = """
CREATE TABLE IF NOT EXISTS patient_events (
    id TEXT PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    patient_phone TEXT NOT NULL,
    type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    statut TEXT,
    motif TEXT,
    payload_json TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_patient_events_lookup
    ON patient_events(tenant_id, patient_phone, occurred_at DESC);

CREATE TABLE IF NOT EXISTS patient_metrics (
    tenant_id INTEGER NOT NULL,
    patient_phone TEXT NOT NULL,
    nb_rdv INTEGER DEFAULT 0,
    nb_no_shows INTEGER DEFAULT 0,
    nb_annul_tardive INTEGER DEFAULT 0,
    taux_assiduite INTEGER,
    score_fiabilite INTEGER,
    dernier_rdv TEXT,
    prochain_rdv TEXT,
    recence_jours INTEGER,
    motifs_top_json TEXT DEFAULT '[]',
    updated_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (tenant_id, patient_phone)
);

CREATE TABLE IF NOT EXISTS patient_summaries (
    tenant_id INTEGER NOT NULL,
    patient_phone TEXT NOT NULL,
    sections_json TEXT NOT NULL DEFAULT '{}',
    inputs_hash TEXT NOT NULL,
    model TEXT,
    is_health INTEGER NOT NULL DEFAULT 0,
    generated_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (tenant_id, patient_phone)
);

CREATE TABLE IF NOT EXISTS questionnaire_templates (
    id TEXT PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    description TEXT,
    sections_json TEXT NOT NULL DEFAULT '[]',
    is_default INTEGER NOT NULL DEFAULT 0,
    is_health INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS questionnaire_requests (
    id TEXT PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    patient_phone TEXT NOT NULL,
    appointment_id TEXT,
    template_id TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    sent_by_user_id TEXT,
    sent_to_email TEXT,
    sent_to_phone TEXT,
    secure_token_hash TEXT NOT NULL,
    token_used INTEGER NOT NULL DEFAULT 0,
    expires_at TEXT,
    opened_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    integrated_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS questionnaire_responses (
    id TEXT PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    questionnaire_request_id TEXT NOT NULL,
    patient_phone TEXT NOT NULL,
    answers_json TEXT NOT NULL DEFAULT '{}',
    ai_summary TEXT,
    structured_summary_json TEXT DEFAULT '{}',
    consent_given INTEGER NOT NULL DEFAULT 0,
    is_health INTEGER NOT NULL DEFAULT 0,
    submitted_at TEXT DEFAULT (datetime('now')),
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS patient_documents_v2 (
    id TEXT PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    patient_phone TEXT NOT NULL,
    questionnaire_request_id TEXT,
    questionnaire_response_id TEXT,
    filename TEXT NOT NULL,
    storage_key TEXT NOT NULL,
    mime_type TEXT,
    is_health INTEGER NOT NULL DEFAULT 0,
    uploaded_by TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


def ensure_patient_v2_schema() -> None:
    """Crée les tables V2 en SQLite (dev) et Postgres si DATABASE_URL est défini."""
    conn = get_conn()
    try:
        conn.executescript(_SQLITE_TABLES)
        try:
            conn.execute(
                "ALTER TABLE patient_documents_v2 ADD COLUMN questionnaire_request_id TEXT"
            )
        except Exception:
            pass
        conn.commit()
    finally:
        conn.close()

    url = _pg_events_url()
    if not url:
        return
    try:
        import psycopg

        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "migrations", "042_patient_context_v2.sql"
        )
        if os.path.isfile(migration_path):
            sql = open(migration_path, encoding="utf-8").read()
            with psycopg.connect(url) as pg:
                with pg.cursor() as cur:
                    cur.execute(sql)
                pg.commit()
    except Exception:
        logger.debug("ensure_patient_v2_schema pg failed", exc_info=True)


def _new_id() -> str:
    return str(uuid.uuid4())


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_load(raw: Any, default: Any = None) -> Any:
    if raw is None:
        return default if default is not None else {}
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(str(raw))
    except (TypeError, json.JSONDecodeError):
        return default if default is not None else {}


def normalize_patient_phone(phone: str) -> str:
    return normalize_phone_number(phone) or (phone or "").strip()


def pg_available() -> bool:
    return bool(_pg_events_url())


def fetch_one_pg(sql: str, params: tuple) -> Optional[Dict[str, Any]]:
    url = _pg_events_url()
    if not url:
        return None
    try:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone()
    except Exception:
        logger.debug("fetch_one_pg failed", exc_info=True)
        return None


def fetch_all_pg(sql: str, params: tuple) -> List[Dict[str, Any]]:
    url = _pg_events_url()
    if not url:
        return []
    try:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return list(cur.fetchall() or [])
    except Exception:
        logger.debug("fetch_all_pg failed", exc_info=True)
        return []


def exec_pg(sql: str, params: tuple) -> None:
    url = _pg_events_url()
    if not url:
        return
    try:
        import psycopg

        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
            conn.commit()
    except Exception:
        logger.debug("exec_pg failed", exc_info=True)


def delete_patient_v2_data(tenant_id: int, patient_phone: str) -> None:
    """Cascade RGPD : supprime toutes les données V2 d'un patient."""
    phone = normalize_patient_phone(patient_phone)
    ensure_patient_v2_schema()
    conn = get_conn()
    try:
        for table in (
            "patient_documents_v2",
            "questionnaire_responses",
            "questionnaire_requests",
            "patient_summaries",
            "patient_metrics",
            "patient_events",
        ):
            conn.execute(
                f"DELETE FROM {table} WHERE tenant_id = ? AND patient_phone = ?",
                (tenant_id, phone),
            )
        conn.commit()
    finally:
        conn.close()

    if pg_available():
        exec_pg(
            """
            DELETE FROM patient_documents_v2 WHERE tenant_id = %s AND patient_phone = %s;
            DELETE FROM questionnaire_responses WHERE tenant_id = %s AND patient_phone = %s;
            DELETE FROM questionnaire_requests WHERE tenant_id = %s AND patient_phone = %s;
            DELETE FROM patient_summaries WHERE tenant_id = %s AND patient_phone = %s;
            DELETE FROM patient_metrics WHERE tenant_id = %s AND patient_phone = %s;
            DELETE FROM patient_events WHERE tenant_id = %s AND patient_phone = %s;
            """,
            (tenant_id, phone) * 6,
        )


def insert_patient_document_v2(
    tenant_id: int,
    patient_phone: str,
    *,
    questionnaire_request_id: str,
    filename: str,
    storage_key: str,
    mime_type: str = "",
    is_health: bool = True,
    uploaded_by: str = "patient",
) -> Dict[str, Any]:
    ensure_patient_v2_schema()
    doc_id = _new_id()
    phone = normalize_patient_phone(patient_phone)
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO patient_documents_v2 (
                id, tenant_id, patient_phone, questionnaire_request_id,
                filename, storage_key, mime_type, is_health, uploaded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc_id,
                tenant_id,
                phone,
                questionnaire_request_id,
                filename,
                storage_key,
                mime_type or "application/octet-stream",
                1 if is_health else 0,
                uploaded_by,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    exec_pg(
        """
        INSERT INTO patient_documents_v2 (
            id, tenant_id, patient_phone, questionnaire_request_id,
            filename, storage_key, mime_type, is_health, uploaded_by
        ) VALUES (%s::uuid, %s, %s, %s::uuid, %s, %s, %s, %s, %s)
        """,
        (
            doc_id,
            tenant_id,
            phone,
            questionnaire_request_id,
            filename,
            storage_key,
            mime_type or "application/octet-stream",
            is_health,
            uploaded_by,
        ),
    )
    return {
        "id": doc_id,
        "filename": filename,
        "mime_type": mime_type,
        "questionnaire_request_id": questionnaire_request_id,
    }


def count_documents_for_request(questionnaire_request_id: str) -> int:
    ensure_patient_v2_schema()
    row = fetch_one_pg(
        """
        SELECT COUNT(*) AS n FROM patient_documents_v2
        WHERE questionnaire_request_id = %s::uuid
          AND questionnaire_response_id IS NULL
        """,
        (questionnaire_request_id,),
    )
    if row:
        return int(row.get("n") or 0)
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT COUNT(*) AS n FROM patient_documents_v2
            WHERE questionnaire_request_id = ?
              AND (questionnaire_response_id IS NULL OR questionnaire_response_id = '')
            """,
            (questionnaire_request_id,),
        ).fetchone()
        return int(cur["n"] or 0) if cur else 0
    finally:
        conn.close()


def list_documents_for_request(questionnaire_request_id: str) -> List[Dict[str, Any]]:
    rows = fetch_all_pg(
        """
        SELECT id, filename, mime_type, created_at
        FROM patient_documents_v2
        WHERE questionnaire_request_id = %s::uuid
        ORDER BY created_at ASC
        """,
        (questionnaire_request_id,),
    )
    if rows:
        return [dict(r) for r in rows]
    conn = get_conn()
    try:
        raw = conn.execute(
            """
            SELECT id, filename, mime_type, created_at
            FROM patient_documents_v2
            WHERE questionnaire_request_id = ?
            ORDER BY created_at ASC
            """,
            (questionnaire_request_id,),
        ).fetchall()
        return [dict(r) for r in raw]
    finally:
        conn.close()


def list_documents_for_response(response_id: str) -> List[Dict[str, Any]]:
    rows = fetch_all_pg(
        """
        SELECT id, filename, mime_type, created_at
        FROM patient_documents_v2
        WHERE questionnaire_response_id = %s::uuid
        ORDER BY created_at ASC
        """,
        (response_id,),
    )
    if rows:
        return [dict(r) for r in rows]
    conn = get_conn()
    try:
        raw = conn.execute(
            """
            SELECT id, filename, mime_type, created_at
            FROM patient_documents_v2
            WHERE questionnaire_response_id = ?
            ORDER BY created_at ASC
            """,
            (response_id,),
        ).fetchall()
        return [dict(r) for r in raw]
    finally:
        conn.close()


def link_documents_to_response(questionnaire_request_id: str, response_id: str) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            UPDATE patient_documents_v2
            SET questionnaire_response_id = ?
            WHERE questionnaire_request_id = ?
            """,
            (response_id, questionnaire_request_id),
        )
        conn.commit()
    finally:
        conn.close()
    exec_pg(
        """
        UPDATE patient_documents_v2
        SET questionnaire_response_id = %s::uuid
        WHERE questionnaire_request_id = %s::uuid
        """,
        (response_id, questionnaire_request_id),
    )
