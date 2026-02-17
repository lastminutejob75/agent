# tests/test_tenant_resolution_web.py
"""Tests résolution tenant depuis X-Tenant-Key (canal web)."""
from __future__ import annotations

import pytest
from fastapi import HTTPException


def test_resolve_tenant_from_api_key_empty_returns_default(monkeypatch):
    """Clé vide ou absente → DEFAULT_TENANT_ID (rétrocompat)."""
    import backend.tenant_routing as tr
    import backend.config as config
    monkeypatch.setattr(tr.config, "USE_PG_TENANTS", False)
    assert tr.resolve_tenant_from_api_key("") == config.DEFAULT_TENANT_ID
    assert tr.resolve_tenant_from_api_key(None) == config.DEFAULT_TENANT_ID
    assert tr.resolve_tenant_from_api_key("   ") == config.DEFAULT_TENANT_ID


def test_resolve_tenant_from_api_key_unknown_raises_401(monkeypatch):
    """Clé fournie mais inconnue → 401."""
    import backend.tenant_routing as tr
    monkeypatch.setattr(tr.config, "USE_PG_TENANTS", False)
    # SQLite sans route web pour cette clé
    with pytest.raises(HTTPException) as exc:
        tr.resolve_tenant_from_api_key("unknown-widget-key")
    assert exc.value.status_code == 401
    assert "X-Tenant-Key" in (exc.value.detail or "")


def test_resolve_tenant_from_api_key_sqlite_route(monkeypatch, tmp_path):
    """Avec une route SQLite channel=web → tenant_id correct."""
    import backend.tenant_routing as tr
    import backend.db as db
    monkeypatch.setattr(tr.config, "USE_PG_TENANTS", False)
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "agent.db"))
    db.init_db(days=0)
    db.ensure_tenant_config()
    conn = db.get_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO tenant_routing (channel, did_key, tenant_id) VALUES (?, ?, ?)",
            ("web", "widget-key-tenant-42", 42),
        )
        conn.commit()
    finally:
        conn.close()

    assert tr.resolve_tenant_from_api_key("widget-key-tenant-42") == 42
    assert tr.resolve_tenant_from_api_key("  widget-key-tenant-42  ") == 42


def test_resolve_tenant_from_api_key_strips_whitespace(monkeypatch, tmp_path):
    """La clé est trimée avant lookup."""
    import backend.tenant_routing as tr
    import backend.db as db
    monkeypatch.setattr(tr.config, "USE_PG_TENANTS", False)
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "agent.db"))
    db.init_db(days=0)
    db.ensure_tenant_config()
    conn = db.get_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO tenant_routing (channel, did_key, tenant_id) VALUES (?, ?, ?)",
            ("web", "trimmed-key", 7),
        )
        conn.commit()
    finally:
        conn.close()

    assert tr.resolve_tenant_from_api_key("  trimmed-key  ") == 7
