"""
Dépendances FastAPI pour le multi-tenant (Jour 7).
- require_tenant_web : résout tenant_id depuis X-Tenant-Key, pose current_tenant_id (POST /chat, etc.).
- require_tenant_from_header : idem sans poser le context (pour autres routes).
- validate_tenant_id : valide qu'un tenant_id existe (routes admin).
"""
from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException


def require_tenant_from_header(
    x_tenant_key: Optional[str] = Header(None, alias="X-Tenant-Key"),
) -> int:
    """
    Dépendance FastAPI : résout tenant_id depuis le header X-Tenant-Key.
    - Absent ou vide → DEFAULT_TENANT_ID (rétrocompat).
    - Clé invalide → 401.
    """
    from backend.tenant_routing import resolve_tenant_from_api_key
    return resolve_tenant_from_api_key(x_tenant_key or "")


def require_tenant_web(
    x_tenant_key: Optional[str] = Header(None, alias="X-Tenant-Key"),
) -> int:
    """
    Comme require_tenant_from_header mais pose current_tenant_id pour le reste du pipeline.
    Utilisé par POST /chat.
    """
    from backend.tenant_routing import resolve_tenant_from_api_key, current_tenant_id
    tid = resolve_tenant_from_api_key(x_tenant_key or "")
    current_tenant_id.set(str(tid))
    return tid


# Alias pour les annotations de route (tenant_id: TenantIdWeb = Depends(require_tenant_web))
TenantIdWeb = int


def validate_tenant_id(tenant_id: int) -> int:
    """
    Valide qu'un tenant_id existe. PG : pg_get_tenant_full ; sinon on accepte (évite import admin).
    Retourne tenant_id si ok, 404 sinon.
    """
    if tenant_id < 1:
        raise HTTPException(status_code=404, detail="Tenant not found")
    from backend import config
    if config.USE_PG_TENANTS:
        try:
            from backend.tenants_pg import pg_get_tenant_full
            if pg_get_tenant_full(tenant_id) is None:
                raise HTTPException(status_code=404, detail="Tenant not found")
        except HTTPException:
            raise
        except Exception:
            pass
    return tenant_id
