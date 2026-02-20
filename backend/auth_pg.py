"""
Auth client: tenant_users (Postgres).
- lookup tenant_user par email (login, Google, admin)
- mot de passe oublié : token reset stocké sur tenant_users (password_reset_token_hash, password_reset_expires_at)
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
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


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def pg_create_password_reset(email: str, ttl_minutes: int = 60) -> Optional[str]:
    """
    Crée un token de réinitialisation mot de passe pour l'email.
    Stocke le hash du token + expires_at (TIMESTAMPTZ) sur tenant_users.
    Returns token brut (urlsafe) ou None si email inconnu / erreur.
    """
    url = _pg_url()
    if not url:
        return None
    email = email.strip().lower()
    if not email:
        return None
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = _now_utc() + timedelta(minutes=ttl_minutes)
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE tenant_users
                    SET password_reset_token_hash = %s, password_reset_expires_at = %s
                    WHERE email = %s
                    """,
                    (token_hash, expires_at, email),
                )
                if cur.rowcount == 0:
                    return None
                conn.commit()
                return token
    except Exception as e:
        logger.warning("pg_create_password_reset failed: %s", e)
    return None


def pg_get_tenant_user_for_reset_check(email: str) -> Optional[Dict[str, Any]]:
    """
    Récupère le tenant_user par email avec les champs nécessaires pour valider un reset.
    Returns { user_id, tenant_id, role, password_reset_token_hash, password_reset_expires_at } ou None.
    password_reset_expires_at est renvoyé en UTC (naive ou aware selon le driver).
    """
    url = _pg_url()
    if not url:
        return None
    email = email.strip().lower()
    if not email:
        return None
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, tenant_id, role, password_reset_token_hash, password_reset_expires_at
                    FROM tenant_users
                    WHERE email = %s
                    LIMIT 1
                    """,
                    (email,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                user_id, tenant_id, role, token_hash, expires_at = row
                return {
                    "user_id": int(user_id),
                    "tenant_id": int(tenant_id),
                    "role": role or "owner",
                    "password_reset_token_hash": token_hash,
                    "password_reset_expires_at": expires_at,
                }
    except Exception as e:
        logger.warning("pg_get_tenant_user_for_reset_check failed: %s", e)
    return None


def pg_update_password_and_clear_reset(user_id: int, password_hash: str) -> None:
    """
    Met à jour le mot de passe et efface le token reset (usage unique).
    """
    url = _pg_url()
    if not url:
        raise ValueError("DB not configured")
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE tenant_users
                    SET password_hash = %s, password_reset_token_hash = NULL, password_reset_expires_at = NULL
                    WHERE id = %s
                    """,
                    (password_hash, user_id),
                )
                conn.commit()
    except Exception as e:
        logger.warning("pg_update_password_and_clear_reset failed: %s", e)
        raise


def pg_reset_password_with_token(token: str, new_password_hash: str) -> bool:
    """
    Valide le token reset, met à jour le password_hash et efface le token/expiry.
    (Legacy: préférer pg_get_tenant_user_for_reset_check + pg_update_password_and_clear_reset avec email.)
    """
    url = _pg_url()
    if not url or not token or not new_password_hash:
        return False
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, tenant_id FROM tenant_users
                    WHERE password_reset_token_hash = %s
                      AND password_reset_expires_at > %s
                    """,
                    (token_hash, _now_utc()),
                )
                row = cur.fetchone()
                if not row:
                    return False
                user_id, _ = row
                cur.execute(
                    """
                    UPDATE tenant_users
                    SET password_hash = %s, password_reset_token_hash = NULL, password_reset_expires_at = NULL
                    WHERE id = %s
                    """,
                    (new_password_hash, user_id),
                )
                conn.commit()
                return True
    except Exception as e:
        logger.warning("pg_reset_password_with_token failed: %s", e)
    return False


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
