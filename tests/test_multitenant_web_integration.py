# tests/test_multitenant_web_integration.py
"""Test d'intégration : POST /chat avec X-Tenant-Key → session scopée tenant."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def db_sqlite_web_route(tmp_path, monkeypatch):
    """Base SQLite + route web pour tenant 5."""
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
            ("web", "integration-key-5", 5),
        )
        conn.commit()
    finally:
        conn.close()
    return None


def test_chat_with_x_tenant_key_resolves_tenant(client, db_sqlite_web_route):
    """POST /chat avec X-Tenant-Key valide → 200 et conversation_id."""
    r = client.post(
        "/chat",
        json={"message": "Bonjour", "conversation_id": "int-test-1", "channel": "web"},
        headers={"X-Tenant-Key": "integration-key-5"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "conversation_id" in data
    assert data["conversation_id"] == "int-test-1"


def test_chat_with_invalid_x_tenant_key_returns_401(client, db_sqlite_web_route):
    """POST /chat avec X-Tenant-Key inconnu → 401."""
    r = client.post(
        "/chat",
        json={"message": "Bonjour", "conversation_id": "int-test-2", "channel": "web"},
        headers={"X-Tenant-Key": "invalid-unknown-key"},
    )
    assert r.status_code == 401


def test_chat_without_x_tenant_key_uses_default_tenant(client, monkeypatch):
    """POST /chat sans header → DEFAULT_TENANT_ID, 200."""
    import backend.tenant_routing as tr
    monkeypatch.setattr(tr.config, "USE_PG_TENANTS", False)
    r = client.post(
        "/chat",
        json={"message": "Bonjour", "conversation_id": "int-test-3", "channel": "web"},
    )
    assert r.status_code == 200
    assert r.json().get("conversation_id") == "int-test-3"
