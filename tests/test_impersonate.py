"""
Tests impersonation (Option A).
- POST /api/admin/tenants/{id}/impersonate → token avec scope=impersonate, exp 5 min
- GET /api/auth/impersonate?token=... → accepte scope=impersonate, rejette JWT tenant normal
- Le endpoint d'échange retourne ensuite une vraie client_session pour /api/tenant/*
"""
from __future__ import annotations

import os
import time
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def admin_headers():
    token = os.environ.get("ADMIN_API_TOKEN")
    return {"Authorization": f"Bearer {token}"}


@patch("backend.routes.admin._get_tenant_detail")
@patch("backend.config.USE_PG_TENANTS", False)
def test_impersonate_token_scope_and_exp(mock_detail, client, admin_headers):
    """
    POST /api/admin/tenants/{id}/impersonate (admin auth) →
    token décodable, scope=impersonate, tenant_id correct, exp < now+6 min.
    """
    mock_detail.return_value = {"tenant_id": 1, "name": "Test Tenant"}
    r = client.post("/api/admin/tenants/1/impersonate", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert "token" in data
    assert "expires_at" in data

    secret = os.environ.get("JWT_SECRET", "")
    payload = jwt.decode(data["token"], secret, algorithms=["HS256"])
    assert payload.get("scope") == "impersonate"
    assert payload.get("tenant_id") == 1
    assert payload.get("impersonated_by") in ("admin", "test-admin@example.com") or "admin" in str(payload.get("impersonated_by", ""))
    exp = payload.get("exp")
    assert exp is not None
    # exp doit être dans les 6 prochaines minutes (5 min + marge)
    assert exp <= int(time.time()) + 360  # 6 min


def test_auth_impersonate_rejects_wrong_scope(client):
    """
    GET /api/auth/impersonate?token=... avec un JWT tenant normal (sans scope ou scope≠impersonate) → 400.
    """
    secret = os.environ.get("JWT_SECRET", "")
    # JWT "tenant normal" : pas de scope
    payload = {
        "sub": "user@example.com",
        "tenant_id": 1,
        "email": "user@example.com",
        "role": "owner",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    r = client.get(f"/api/auth/impersonate?token={token}")
    assert r.status_code == 400


@patch("backend.routes.auth.pg_get_tenant_user_for_impersonation")
@patch("backend.routes.auth._get_tenant_name")
@patch("backend.routes.admin._get_tenant_detail")
@patch("backend.config.USE_PG_TENANTS", False)
def test_auth_impersonate_accepts_valid_token(mock_detail, mock_tenant_name, mock_impersonation_user, client, admin_headers):
    """
    Token retourné par POST impersonate → GET /api/auth/impersonate accepte,
    retourne tenant_id, tenant_name et échange vers une vraie client_session.
    """
    mock_detail.return_value = {"tenant_id": 1, "name": "Cabinet Dupont"}
    mock_tenant_name.return_value = "Cabinet Dupont"
    mock_impersonation_user.return_value = {
        "user_id": 42,
        "tenant_id": 1,
        "email": "cabinet@example.com",
        "role": "owner",
    }
    r_post = client.post("/api/admin/tenants/1/impersonate", headers=admin_headers)
    assert r_post.status_code == 200
    token = r_post.json().get("token")
    assert token

    r_get = client.get(f"/api/auth/impersonate?token={token}")
    assert r_get.status_code == 200
    data = r_get.json()
    assert data.get("tenant_id") == 1
    assert data.get("tenant_name") == "Cabinet Dupont"
    assert "expires_at" in data
    assert "token" in data

    secret = os.environ.get("JWT_SECRET", "")
    session_payload = jwt.decode(data["token"], secret, algorithms=["HS256"])
    assert session_payload.get("typ") == "client_session"
    assert session_payload.get("tenant_id") == "1"
    assert session_payload.get("sub") == "42"
    assert session_payload.get("role") == "owner"
