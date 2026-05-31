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


def list_patient_document_storage_keys(tenant_id: int, patient_phone: str) -> List[str]:
    """Liste les clés de stockage avant suppression RGPD."""
    phone = normalize_patient_phone(patient_phone)
    rows = fetch_all_pg(
        """
        SELECT storage_key FROM patient_documents_v2
        WHERE tenant_id = %s AND patient_phone = %s AND storage_key IS NOT NULL
        """,
        (tenant_id, phone),
    )
    if rows:
        return [str(r.get("storage_key") or "") for r in rows if r.get("storage_key")]
    conn = get_conn()
    try:
        raw = conn.execute(
            """
            SELECT storage_key FROM patient_documents_v2
            WHERE tenant_id = ? AND patient_phone = ? AND storage_key IS NOT NULL
            """,
            (tenant_id, phone),
        ).fetchall()
        return [str(r["storage_key"]) for r in raw if dict(r).get("storage_key")]
    finally:
        conn.close()


def delete_patient_v2_data(tenant_id: int, patient_phone: str) -> None:
    """Cascade RGPD : supprime toutes les données V2 d'un patient (+ fichiers stockés)."""
    phone = normalize_patient_phone(patient_phone)
    ensure_patient_v2_schema()
    storage_keys = list_patient_document_storage_keys(tenant_id, phone)
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

    if storage_keys:
        try:
            from backend.services.patient_document_storage import delete_storage_keys

            delete_storage_keys(storage_keys)
        except Exception:
            logger.warning(
                "delete_patient_v2_data storage purge failed tenant=%s phone=%s",
                tenant_id,
                phone[-4:],
                exc_info=True,
            )


def migrate_patient_phone_v2_data(
    tenant_id: int,
    old_phone: str,
    new_phone: str,
    *,
    old_keys: Optional[List[str]] = None,
) -> None:
    """Propage un changement de numéro dans les tables patient V2."""
    old = normalize_patient_phone(old_phone)
    new = normalize_patient_phone(new_phone)
    if not old or not new or old == new:
        return
    keys = list(dict.fromkeys(old_keys or [old]))
    if not keys:
        keys = [old]

    tables = (
        "patient_documents_v2",
        "questionnaire_responses",
        "questionnaire_requests",
        "patient_summaries",
        "patient_metrics",
        "patient_events",
    )

    conn = get_conn()
    try:
        for table in tables:
            placeholders = ",".join("?" for _ in keys)
            try:
                conn.execute(
                    f"UPDATE {table} SET patient_phone = ? WHERE tenant_id = ? AND patient_phone IN ({placeholders})",
                    (new, tenant_id, *keys),
                )
            except Exception:
                pass
        conn.commit()
    finally:
        conn.close()

    if pg_available():
        for table in tables:
            try:
                exec_pg(
                    f"UPDATE {table} SET patient_phone = %s WHERE tenant_id = %s AND patient_phone = ANY(%s)",
                    (new, tenant_id, keys),
                )
            except Exception:
                logger.debug("migrate_patient_phone_v2_data pg %s failed", table, exc_info=True)


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


def get_patient_document_v2(tenant_id: int, doc_id: str) -> Optional[Dict[str, Any]]:
    row = fetch_one_pg(
        """
        SELECT id, tenant_id, patient_phone, filename, storage_key, mime_type, is_health,
               questionnaire_response_id, questionnaire_request_id
        FROM patient_documents_v2
        WHERE tenant_id = %s AND id = %s::uuid
        """,
        (tenant_id, doc_id),
    )
    if row:
        return dict(row)
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT id, tenant_id, patient_phone, filename, storage_key, mime_type, is_health,
                   questionnaire_response_id, questionnaire_request_id
            FROM patient_documents_v2
            WHERE tenant_id = ? AND id = ?
            """,
            (tenant_id, doc_id),
        ).fetchone()
        return dict(cur) if cur else None
    finally:
        conn.close()


def delete_patient_document_v2(tenant_id: int, doc_id: str, *, patient_phone: Optional[str] = None) -> bool:
    """Supprime un document V2 (+ fichier S3/disque). Anti-IDOR si patient_phone fourni."""
    doc = get_patient_document_v2(tenant_id, doc_id)
    if not doc:
        return False

    phone = normalize_patient_phone(str(doc.get("patient_phone") or ""))
    if patient_phone and normalize_patient_phone(patient_phone) != phone:
        return False

    storage_key = str(doc.get("storage_key") or "")
    deleted_db = False

    conn = get_conn()
    try:
        if patient_phone:
            cur = conn.execute(
                """
                DELETE FROM patient_documents_v2
                WHERE tenant_id = ? AND id = ? AND patient_phone = ?
                """,
                (tenant_id, doc_id, phone),
            )
        else:
            cur = conn.execute(
                "DELETE FROM patient_documents_v2 WHERE tenant_id = ? AND id = ?",
                (tenant_id, doc_id),
            )
        conn.commit()
        deleted_db = cur.rowcount > 0
    finally:
        conn.close()

    if pg_available():
        if patient_phone:
            exec_pg(
                """
                DELETE FROM patient_documents_v2
                WHERE tenant_id = %s AND id = %s::uuid AND patient_phone = %s
                """,
                (tenant_id, doc_id, phone),
            )
        else:
            exec_pg(
                "DELETE FROM patient_documents_v2 WHERE tenant_id = %s AND id = %s::uuid",
                (tenant_id, doc_id),
            )

    if deleted_db and storage_key:
        try:
            from backend.services.patient_document_storage import delete_storage_object

            delete_storage_object(storage_key)
        except Exception:
            logger.warning(
                "delete_patient_document_v2 storage purge failed tenant=%s doc=%s",
                tenant_id,
                doc_id,
                exc_info=True,
            )

    return deleted_db


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
