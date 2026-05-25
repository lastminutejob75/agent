"""
Audit log — accès aux dossiers patients (PHI).

Trace chaque lecture / écriture d'un dossier patient pour :
- Détection d'usages anormaux (un utilisateur qui consulte 200 fiches/jour, exfil)
- Conformité RGPD article 30 (registre des traitements) + HDS (auditabilité PHI)
- Investigation post-incident (qui a vu quoi, quand, depuis quelle IP)

Table : `patient_access_audit` (créée à la volée si absente).

Le log est best-effort : si la BDD est indisponible, on logue côté logger
sans faire échouer la requête métier.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

_TABLE_READY = False


def _pg_url() -> str:
    return (
        os.environ.get("PG_EVENTS_URL")
        or os.environ.get("DATABASE_URL")
        or ""
    ).strip()


def _ensure_audit_table_pg() -> bool:
    """Crée la table d'audit si absente. Retourne True si la table est utilisable."""
    global _TABLE_READY
    if _TABLE_READY:
        return True
    url = _pg_url()
    if not url:
        return False
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS patient_access_audit (
                        id BIGSERIAL PRIMARY KEY,
                        tenant_id INTEGER NOT NULL,
                        actor_user_id TEXT,
                        actor_email TEXT,
                        actor_role TEXT,
                        action TEXT NOT NULL,
                        patient_phone TEXT,
                        resource TEXT,
                        method TEXT,
                        path TEXT,
                        ip_address TEXT,
                        user_agent TEXT,
                        status_code INTEGER,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_patient_access_audit_tenant_created "
                    "ON patient_access_audit (tenant_id, created_at DESC)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_patient_access_audit_actor "
                    "ON patient_access_audit (actor_user_id, created_at DESC)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_patient_access_audit_patient "
                    "ON patient_access_audit (tenant_id, patient_phone, created_at DESC)"
                )
            conn.commit()
        _TABLE_READY = True
        return True
    except Exception as e:
        logger.warning("patient_access_audit: création table échouée: %s", e)
        return False


def log_patient_access(
    *,
    tenant_id: int,
    actor_user_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    actor_role: Optional[str] = None,
    action: str,
    patient_phone: Optional[str] = None,
    resource: Optional[str] = None,
    method: Optional[str] = None,
    path: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    status_code: Optional[int] = None,
) -> None:
    """
    Trace un accès patient. Best-effort : ne lève jamais d'exception qui casse la requête.

    `action` : view_profile, view_notes, write_note, delete_note,
               upload_doc, download_doc, delete_doc, view_calls, export, ...
    """
    line = (
        f"PATIENT_ACCESS tenant={tenant_id} actor={actor_user_id or '?'}"
        f" email={(actor_email or '?')[:80]} role={actor_role or '?'}"
        f" action={action} patient={(patient_phone or '?')[:24]}"
        f" path={method or '?'} {path or '?'} status={status_code or '?'} ip={ip_address or '?'}"
    )
    logger.info(line)

    if not _ensure_audit_table_pg():
        return

    url = _pg_url()
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO patient_access_audit
                    (tenant_id, actor_user_id, actor_email, actor_role, action,
                     patient_phone, resource, method, path, ip_address, user_agent, status_code, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        int(tenant_id),
                        (actor_user_id or "")[:64] or None,
                        (actor_email or "")[:255] or None,
                        (actor_role or "")[:32] or None,
                        action[:64],
                        (patient_phone or "")[:32] or None,
                        (resource or "")[:64] or None,
                        (method or "")[:8] or None,
                        (path or "")[:255] or None,
                        (ip_address or "")[:64] or None,
                        (user_agent or "")[:255] or None,
                        int(status_code) if status_code else None,
                        datetime.utcnow(),
                    ),
                )
            conn.commit()
    except Exception as e:
        logger.warning("patient_access_audit insert failed: %s", e)


__all__ = ["log_patient_access"]
