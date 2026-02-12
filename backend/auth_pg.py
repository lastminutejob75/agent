"""
Auth client: tenant_users, magic_links (Postgres).
- lookup tenant_user par email
- create magic_link (hash token)
- verify magic_link
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple

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


def pg_create_magic_link(tenant_id: int, email: str, ttl_minutes: int = 15) -> Optional[str]:
    """
    Crée un magic link token.
    Stocke hash SHA256 du token en DB.
    Returns token brut (32 bytes urlsafe) ou None.
    """
    url = _pg_url()
    if not url:
        return None
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = datetime.utcnow() + timedelta(minutes=ttl_minutes)
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO magic_links (token_hash, tenant_id, email, expires_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (token_hash, tenant_id, email.strip().lower(), expires_at),
                )
                conn.commit()
                return token
    except Exception as e:
        logger.warning("pg_create_magic_link failed: %s", e)
    return None


def pg_verify_magic_link(token: str) -> Optional[Tuple[int, str, str]]:
    """
    Vérifie token: hash existe, not expired, not used.
    Marque used_at.
    Returns (tenant_id, email, role) ou None.
    """
    url = _pg_url()
    if not url:
        return None
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tenant_id, email, used_at, expires_at
                    FROM magic_links
                    WHERE token_hash = %s
                    """,
                    (token_hash,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                tenant_id, email, used_at, expires_at = row
                if used_at:
                    return None
                now = datetime.utcnow()
                if expires_at and expires_at.tzinfo:
                    expires_at = expires_at.replace(tzinfo=None)
                if now > expires_at:
                    return None
                cur.execute(
                    "UPDATE magic_links SET used_at = %s WHERE token_hash = %s",
                    (now, token_hash),
                )
                conn.commit()
                # Get role from tenant_users
                cur.execute("SELECT role FROM tenant_users WHERE email = %s", (email,))
                r = cur.fetchone()
                role = r[0] if r else "owner"
                return (int(tenant_id), email, role)
    except Exception as e:
        logger.warning("pg_verify_magic_link failed: %s", e)
    return None


# Aliases pour compatibilité avec backend/routes/auth.py
auth_get_tenant_user_by_email = pg_get_tenant_user_by_email
auth_create_magic_link = pg_create_magic_link
auth_verify_magic_link = pg_verify_magic_link


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
