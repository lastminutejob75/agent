"""Capabilities tenant (HDS, etc.) — stubs prêts pour activation."""

from __future__ import annotations

import os
from typing import Any, Dict, Set


def get_tenant_capabilities(tenant_id: int, tenant_detail: Dict[str, Any] | None = None) -> Set[str]:
    """Retourne l'ensemble des capabilities actives pour un tenant."""
    caps: Set[str] = set()
    params = (tenant_detail or {}).get("params") or {}

    # HDS : désactivé par défaut ; activation explicite uniquement.
    hds_env = (os.environ.get("UWI_HDS_ENABLED") or "").strip().lower() in ("1", "true", "yes", "on")
    hds_param = bool(params.get("hds_enabled"))
    if hds_env and hds_param:
        caps.add("hds_enabled")

    return caps


def is_hds_active(tenant_id: int, tenant_detail: Dict[str, Any] | None = None) -> bool:
    return "hds_enabled" in get_tenant_capabilities(tenant_id, tenant_detail)


class RequesterContext:
    """Contexte utilisateur pour contrôle d'accès santé."""

    def __init__(self, user_id: str, role: str, *, is_soignant: bool | None = None):
        self.id = user_id
        self.role = (role or "owner").strip().lower()
        self.is_soignant = is_soignant if is_soignant is not None else self.role in ("owner", "member", "practitioner")


def requester_from_auth(auth: Dict[str, Any]) -> RequesterContext:
    return RequesterContext(
        user_id=str(auth.get("sub") or auth.get("user_id") or ""),
        role=str(auth.get("role") or "owner"),
    )
