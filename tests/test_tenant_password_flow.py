from __future__ import annotations

import os
import sys
import types
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-tenant-password-flow")


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


def test_pg_create_tenant_user_hashes_password():
    from backend import auth_pg

    executed = {}

    class FakeCursor:
        rowcount = 1

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, params):
            executed["query"] = query
            executed["params"] = params

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return FakeCursor()

        def commit(self):
            executed["committed"] = True

    fake_psycopg = types.SimpleNamespace(connect=lambda url: FakeConn())
    fake_bcrypt = types.SimpleNamespace(
        gensalt=lambda: b"salt",
        hashpw=lambda password, salt: b"hashed-password",
    )

    with patch.dict(sys.modules, {"psycopg": fake_psycopg, "bcrypt": fake_bcrypt}):
        with patch("backend.auth_pg._pg_url", return_value="postgres://test"):
            ok = auth_pg.pg_create_tenant_user(12, "Cabinet@Test.fr", role="owner", password="TempPass123")

    assert ok is True
    assert "password_hash" in executed["query"]
    assert executed["params"] == (12, "cabinet@test.fr", "owner", "hashed-password")
    assert executed["committed"] is True


def test_tenant_change_password_rejects_short_password(client):
    from backend.main import app
    from backend.routes import tenant

    app.dependency_overrides[tenant.require_tenant_auth] = lambda: {
        "tenant_id": 1,
        "email": "owner@test.fr",
        "role": "owner",
        "sub": "42",
    }
    try:
        r = client.patch("/api/tenant/auth/change-password", json={"new_password": "court"})
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 400
    assert "8 caractères" in r.json()["detail"]


def test_tenant_change_password_hashes_and_updates_password(client):
    from backend.main import app
    from backend.routes import tenant

    app.dependency_overrides[tenant.require_tenant_auth] = lambda: {
        "tenant_id": 7,
        "email": "owner@test.fr",
        "role": "owner",
        "sub": "42",
    }

    with patch("backend.routes.tenant.bcrypt.gensalt", return_value=b"salt"):
        with patch("backend.routes.tenant.bcrypt.hashpw", return_value=b"hashed-password"):
            with patch("backend.routes.tenant.pg_update_password") as mock_update:
                try:
                    r = client.patch(
                        "/api/tenant/auth/change-password",
                        json={"new_password": "NouveauMotDePasse123"},
                    )
                finally:
                    app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json() == {"ok": True}
    mock_update.assert_called_once_with(42, "hashed-password")
