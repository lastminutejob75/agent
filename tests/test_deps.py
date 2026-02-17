# tests/test_deps.py
"""Tests des dépendances FastAPI multi-tenant (require_tenant_from_header, validate_tenant_id)."""
from __future__ import annotations

import pytest
from fastapi import HTTPException


def test_require_tenant_from_header_empty_returns_default(monkeypatch):
    """X-Tenant-Key absent/vide → DEFAULT_TENANT_ID."""
    import backend.deps as deps
    import backend.config as config
    import backend.tenant_routing as tr
    monkeypatch.setattr(tr.config, "USE_PG_TENANTS", False)
    assert deps.require_tenant_from_header(None) == config.DEFAULT_TENANT_ID
    assert deps.require_tenant_from_header("") == config.DEFAULT_TENANT_ID
    assert deps.require_tenant_from_header("   ") == config.DEFAULT_TENANT_ID


def test_require_tenant_from_header_unknown_raises_401(monkeypatch):
    """X-Tenant-Key fourni mais inconnu → 401."""
    import backend.deps as deps
    import backend.tenant_routing as tr
    monkeypatch.setattr(tr.config, "USE_PG_TENANTS", False)
    with pytest.raises(HTTPException) as exc:
        deps.require_tenant_from_header("unknown-key")
    assert exc.value.status_code == 401


def test_require_tenant_from_header_sqlite_route(monkeypatch, tmp_path):
    """Avec route SQLite web → tenant_id résolu."""
    import backend.deps as deps
    import backend.db as db
    import backend.tenant_routing as tr
    monkeypatch.setattr(tr.config, "USE_PG_TENANTS", False)
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "agent.db"))
    db.init_db(days=0)
    db.ensure_tenant_config()
    conn = db.get_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO tenant_routing (channel, did_key, tenant_id) VALUES (?, ?, ?)",
            ("web", "deps-test-key", 11),
        )
        conn.commit()
    finally:
        conn.close()
    assert deps.require_tenant_from_header("deps-test-key") == 11


def test_validate_tenant_id_negative_raises_404():
    """tenant_id < 1 → 404."""
    import backend.deps as deps
    with pytest.raises(HTTPException) as exc:
        deps.validate_tenant_id(0)
    assert exc.value.status_code == 404
    with pytest.raises(HTTPException):
        deps.validate_tenant_id(-1)


def test_validate_tenant_id_accepts_positive_when_no_pg(monkeypatch):
    """Sans PG (USE_PG_TENANTS=False), validate_tenant_id accepte tout tenant_id >= 1."""
    import backend.deps as deps
    import backend.config as config
    monkeypatch.setattr(config, "USE_PG_TENANTS", False)
    assert deps.validate_tenant_id(1) == 1
    assert deps.validate_tenant_id(99) == 99
