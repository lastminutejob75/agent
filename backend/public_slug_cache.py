"""
Cache mémoire slug public → tenant_id + validation indexée (évite scan PG / résolution lourde).
Partagé entre fiche publique, chat et créneaux.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

_SLUG_TENANT: dict[str, int] = {}


def remember_slug_tenant(slug: str, tenant_id: int) -> None:
    s = (slug or "").strip().lower()
    if s and tenant_id:
        _SLUG_TENANT[s] = int(tenant_id)


def tenant_id_for_slug(slug: str, hint: Optional[int] = None) -> Optional[int]:
    """
    Résout tenant_id pour un slug public.
    - Cache mémoire process
    - hint validé par requête PG indexée (une fois), puis mis en cache
    - sinon get_tenant_id_by_public_slug (lru_cache)
    """
    from backend.cabinet_profile_pg import get_tenant_id_by_public_slug

    s = (slug or "").strip().lower()
    if not s:
        return None

    cached = _SLUG_TENANT.get(s)
    if cached is not None:
        if hint is None or int(hint) == int(cached):
            return int(cached)

    if hint is not None and int(hint) > 0:
        if _validate_slug_tenant_pair(s, int(hint)):
            remember_slug_tenant(s, int(hint))
            return int(hint)

    tid = get_tenant_id_by_public_slug(s)
    if tid:
        remember_slug_tenant(s, int(tid))
    return int(tid) if tid else None


@lru_cache(maxsize=512)
def _validate_slug_tenant_pair(slug: str, tenant_id: int) -> bool:
    """Validation rapide (index) : le tenant correspond bien au slug public."""
    try:
        from backend.cabinet_profile_pg import _pg_url
        from backend.tenants_pg import pg_tenants_connection
        from backend.pg_tenant_context import set_bypass_tenant_rls_on_connection
    except ImportError:
        return True

    if not _pg_url():
        return True

    try:
        with pg_tenants_connection() as conn:
            set_bypass_tenant_rls_on_connection(conn, enabled=True)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM tenant_profiles
                    WHERE tenant_id = %s AND LOWER(public_slug) = %s
                    LIMIT 1
                    """,
                    (int(tenant_id), slug),
                )
                if cur.fetchone():
                    return True
                cur.execute(
                    """
                    SELECT 1 FROM tenant_config
                    WHERE tenant_id = %s AND LOWER(params_json->>'public_slug') = %s
                    LIMIT 1
                    """,
                    (int(tenant_id), slug),
                )
                return cur.fetchone() is not None
    except Exception as e:
        logger.debug("validate_slug_tenant slug=%s tid=%s err=%s", slug, tenant_id, e)
        return False
