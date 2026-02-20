"""
Auth client: tenant_users (Postgres).
- lookup tenant_user par email (login, Google, admin)
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def _pg_url() -> Optional[str]:
    return os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL")


def pg_get_tenant_user_by_email(email: str) -> Optional[Tuple[int, int, str]]:
    """
    Lookup tenant_user par email.
    Returns (tenant_id, user_id, role) ou None.
    """
    url = _pg_url()
    if not url:
        return None
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT tenant_id, id, role FROM tenant_users WHERE email = %s",
                    (email.strip().lower(),),
                )
                row = cur.fetchone()
                if row:
                    return (int(row[0]), int(row[1]), row[2] or "owner")
    except Exception as e:
        logger.warning("pg_get_tenant_user_by_email failed: %s", e)
    return None


def pg_get_tenant_user_by_email_for_login(email: str) -> Optional[Dict[str, Any]]:
    """
    Lookup tenant_user par email avec password_hash (pour login email+mdp).
    Returns {"tenant_id", "user_id", "role", "password_hash"} ou None.
    password_hash nullable : si NULL → login password doit répondre 401 neutre.
    """
    url = _pg_url()
    if not url:
        return None
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT tenant_id, id AS user_id, role, password_hash FROM tenant_users WHERE email = %s LIMIT 1",
                    (email.strip().lower(),),
                )
                row = cur.fetchone()
                if row:
                    return {
                        "tenant_id": int(row[0]),
                        "user_id": int(row[1]),
                        "role": row[2] or "owner",
                        "password_hash": row[3],
                    }
    except Exception as e:
        logger.warning("pg_get_tenant_user_by_email_for_login failed: %s", e)
    return None


def pg_get_tenant_user_by_email_for_google(email: str) -> Optional[Dict[str, Any]]:
    """
    Lookup tenant_user par email avec google_sub (pour callback Google SSO).
    Returns {"tenant_id", "user_id", "role", "google_sub"} ou None.
    """
    url = _pg_url()
    if not url:
        return None
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT tenant_id, id, role, google_sub FROM tenant_users WHERE email = %s LIMIT 1",
                    (email.strip().lower(),),
                )
                row = cur.fetchone()
                if row:
                    return {
                        "tenant_id": int(row[0]),
                        "user_id": int(row[1]),
                        "role": row[2] or "owner",
                        "google_sub": row[3],
                    }
    except Exception as e:
        logger.warning("pg_get_tenant_user_by_email_for_google failed: %s", e)
    return None


def pg_link_google_sub(user_id: Any, google_sub: str, google_email: str) -> str:
    """
    Lie un tenant_user à un compte Google (google_sub, google_email, auth_provider).
    Returns: "linked" (mis à jour), "already_linked" (déjà le même sub), "conflict" (déjà lié à un autre Google).
    """
    url = _pg_url()
    if not url:
        return "conflict"
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT google_sub FROM tenant_users WHERE id = %s",
                    (int(user_id),),
                )
                row = cur.fetchone()
                if not row:
                    return "conflict"
                current_sub = row[0]
                if current_sub is not None and current_sub != google_sub:
                    return "conflict"
                if current_sub == google_sub:
                    return "already_linked"
                cur.execute(
                    """
                    UPDATE tenant_users
                    SET google_sub = %s, google_email = %s, auth_provider = %s, email_verified = TRUE
                    WHERE id = %s
                    """,
                    (google_sub, (google_email or "").strip().lower(), "google", int(user_id)),
                )
                conn.commit()
                return "linked"
    except Exception as e:
        logger.warning("pg_link_google_sub failed: %s", e)
        return "conflict"


def pg_get_tenant_user_by_id(user_id: Any) -> Optional[Dict[str, Any]]:
    """
    Lookup tenant_user par id (pour validation session).
    Returns {"tenant_id", "email", "role"} ou None.
    """
    url = _pg_url()
    if not url:
        return None
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT tenant_id, email, role FROM tenant_users WHERE id = %s LIMIT 1",
                    (int(user_id),),
                )
                row = cur.fetchone()
                if row:
                    return {
                        "tenant_id": int(row[0]),
                        "email": (row[1] or "").strip(),
                        "role": row[2] or "owner",
                    }
    except Exception as e:
        logger.warning("pg_get_tenant_user_by_id failed: %s", e)
    return None


def pg_create_tenant_user(tenant_id: int, email: str, role: str = "owner") -> bool:
    """Crée ou ignore (ON CONFLICT) un tenant_user."""
    url = _pg_url()
    if not url:
        return False
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tenant_users (tenant_id, email, role)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (email) DO NOTHING
                    """,
                    (tenant_id, email.strip().lower(), role),
                )
                conn.commit()
                return cur.rowcount > 0
    except Exception as e:
        logger.warning("pg_create_tenant_user failed: %s", e)
    return False


def pg_add_tenant_user(tenant_id: int, email: str, role: str = "owner") -> dict:
    """
    Ajoute un tenant_user (admin). Idempotent si même tenant.
    Returns {"ok": True, "tenant_id", "email", "role", "created": bool}
    Raises ValueError si email existe pour un autre tenant (conflit 409).
    """
    url = _pg_url()
    if not url:
        raise ValueError("Postgres not configured")
    email_norm = email.strip().lower()
    if not email_norm:
        raise ValueError("Email required")
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT tenant_id, email, role FROM tenant_users WHERE email = %s",
                    (email_norm,),
                )
                row = cur.fetchone()
                if row:
                    existing_tenant_id = int(row[0])
                    if existing_tenant_id == tenant_id:
                        return {
                            "ok": True,
                            "tenant_id": tenant_id,
                            "email": email_norm,
                            "role": row[2] or "owner",
                            "created": False,
                        }
                    raise ValueError("Email déjà associé à un autre tenant")
                cur.execute(
                    """
                    INSERT INTO tenant_users (tenant_id, email, role)
                    VALUES (%s, %s, %s)
                    """,
                    (tenant_id, email_norm, role),
                )
                conn.commit()
                return {
                    "ok": True,
                    "tenant_id": tenant_id,
                    "email": email_norm,
                    "role": role,
                    "created": True,
                }
    except ValueError:
        raise
    except Exception as e:
        logger.warning("pg_add_tenant_user failed: %s", e)
        raise ValueError(str(e))


def pg_get_tenant_name(tenant_id: int) -> Optional[str]:
    """Nom du tenant."""
    url = _pg_url()
    if not url:
        return None
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT name FROM tenants WHERE tenant_id = %s", (tenant_id,))
                row = cur.fetchone()
                if row:
                    return row[0]
    except Exception as e:
        logger.warning("pg_get_tenant_name failed: %s", e)
    return None
