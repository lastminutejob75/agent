# backend/tenant_flags_cache.py
"""
Cache TTL pour les flags tenant (évite SQLite à chaque tour).
"""
from __future__ import annotations

import time
from typing import Dict, Optional

from backend import db
from backend.tenant_config import TenantFlags, load_tenant_flags

_TTL_SECONDS = 60
_cache: Dict[int, tuple[float, TenantFlags]] = {}


def get_tenant_flags(tenant_id: Optional[int] = None) -> TenantFlags:
    """Retourne les flags avec cache TTL 60s."""
    tid = int(tenant_id or 1)
    now = time.time()

    hit = _cache.get(tid)
    if hit:
        ts, flags = hit
        if now - ts < _TTL_SECONDS:
            return flags

    db.ensure_tenant_config()
    conn = db.get_conn()
    try:
        tf = load_tenant_flags(conn, tid)
    finally:
        conn.close()

    _cache[tid] = (now, tf)
    return tf
