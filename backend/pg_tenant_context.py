# backend/pg_tenant_context.py
"""
Contexte tenant pour RLS PostgreSQL.
Pose app.current_tenant_id sur la connexion pour que les policies RLS
ne retournent que les lignes du tenant courant.
À appeler juste après ouverture de la connexion, avant toute requête.
"""
from __future__ import annotations

import logging
import re
from typing import Optional
from uuid import UUID

logger = logging.getLogger(__name__)


def _is_strict_rls() -> bool:
    from backend.security import is_production

    return is_production()


def set_bypass_tenant_rls_on_connection(conn, *, enabled: bool = True) -> None:
    """Réservé aux routes admin authentifiées (liste cross-tenant)."""
    if getattr(conn, "_uwi_bypass_rls", None) is enabled:
        return
    value = "on" if enabled else "off"
    try:
        with conn.cursor() as cur:
            cur.execute(f"SET LOCAL app.bypass_tenant_rls = '{value}'")
        conn._uwi_bypass_rls = enabled
    except Exception as e:
        logger.warning("set_bypass_tenant_rls failed enabled=%s err=%s", enabled, e)
        try:
            conn.rollback()
        except Exception:
            pass


def set_tenant_id_on_connection(conn, tenant_id: Optional[int]) -> None:
    """
    Exécute SET LOCAL app.current_tenant_id sur la connexion.
    À appeler après psycopg.connect() pour les requêtes scopées par tenant.
    Si tenant_id est None ou < 1, n'appelle pas SET (opération globale ou non scopée).
    """
    if tenant_id is None or tenant_id < 1:
        return
    tid = int(tenant_id)
    if getattr(conn, "_uwi_current_tenant_id", None) == tid:
        return
    try:
        with conn.cursor() as cur:
            tenant_id_sql = str(tid)
            if not re.fullmatch(r"\d+", tenant_id_sql):
                return
            cur.execute(f"SET LOCAL app.current_tenant_id = '{tenant_id_sql}'")
        conn._uwi_current_tenant_id = tid
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        if _is_strict_rls():
            logger.error(
                "set_tenant_id_on_connection FAILED tenant_id=%s err=%s — risque fuite cross-tenant",
                tenant_id,
                e,
            )
            raise
        logger.debug("set_tenant_id_on_connection skipped tenant_id=%s err=%s", tenant_id, e)


def set_post_id_on_connection(conn, post_id: Optional[str | UUID]) -> None:
    """Pose le contexte RLS UUID d'un poste consulaire sur la transaction."""
    if post_id is None:
        return
    try:
        normalized_post_id = str(UUID(str(post_id)))
    except (TypeError, ValueError, AttributeError):
        raise ValueError("post_id must be a valid UUID") from None
    if getattr(conn, "_uwi_current_post_id", None) == normalized_post_id:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_post_id', %s, true)",
                (normalized_post_id,),
            )
        conn._uwi_current_post_id = normalized_post_id
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        if _is_strict_rls():
            logger.error(
                "set_post_id_on_connection FAILED post_id=%s err=%s — risque fuite cross-postes",
                normalized_post_id,
                e,
            )
            raise
        logger.debug(
            "set_post_id_on_connection skipped post_id=%s err=%s",
            normalized_post_id,
            e,
        )


def reset_pg_connection_session_state(conn) -> None:
    """Réinitialise le cache session (appelé au retour connexion → pool)."""
    for attr in ("_uwi_current_tenant_id", "_uwi_current_post_id", "_uwi_bypass_rls"):
        try:
            delattr(conn, attr)
        except AttributeError:
            pass
