# tests/test_deps_require_tenant.py
"""Tests Depends require_tenant_web (Jour 7) : résolution tenant centralisée sur /chat."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app


@pytest.mark.asyncio
async def test_chat_without_tenant_key_returns_200():
    """POST /chat sans X-Tenant-Key → 200, tenant par défaut."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        r = await ac.post("/chat", json={"message": "test"})
    assert r.status_code == 200
    data = r.json()
    assert "conversation_id" in data


@pytest.mark.asyncio
async def test_chat_with_invalid_tenant_key_returns_401():
    """POST /chat avec X-Tenant-Key invalide → 401."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        r = await ac.post(
            "/chat",
            json={"message": "test"},
            headers={"X-Tenant-Key": "invalid-unknown-key"},
        )
    assert r.status_code == 401
    assert "X-Tenant-Key" in (r.json().get("detail") or r.text or "")


@pytest.mark.asyncio
async def test_chat_with_valid_tenant_key_returns_200(monkeypatch, tmp_path):
    """POST /chat avec X-Tenant-Key valide (route SQLite) → 200."""
    import backend.db as db
    import backend.config as config

    monkeypatch.setattr(config, "USE_PG_TENANTS", False)
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "agent.db"))
    db.init_db(days=0)
    db.ensure_tenant_config()
    conn = db.get_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO tenant_routing (channel, did_key, tenant_id) VALUES (?, ?, ?)",
            ("web", "valid-key-j7", 99),
        )
        conn.commit()
    finally:
        conn.close()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        r = await ac.post(
            "/chat",
            json={"message": "test", "conversation_id": "conv-j7"},
            headers={"X-Tenant-Key": "valid-key-j7"},
        )
    assert r.status_code == 200
    data = r.json()
    assert data.get("conversation_id") == "conv-j7"
