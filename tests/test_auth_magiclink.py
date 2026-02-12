"""
Tests auth Magic Link + JWT.
- POST /api/auth/request-link (toujours 200)
- GET /api/auth/verify (token invalide → 400)
- GET /api/tenant/me (sans token → 401)
"""
from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient

# Mock PG pour tests sans DB
os.environ.setdefault("JWT_SECRET", "test-secret-for-pytest")


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


def test_request_link_always_200(client):
    """request-link retourne toujours 200 (anti user enumeration)."""
    r = client.post("/api/auth/request-link", json={"email": "unknown@example.com"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_request_link_empty_email(client):
    """email vide → 200."""
    r = client.post("/api/auth/request-link", json={"email": ""})
    assert r.status_code == 200


def test_verify_missing_token(client):
    """verify sans token → 400."""
    r = client.get("/api/auth/verify")
    assert r.status_code in (400, 422)


def test_verify_invalid_token(client):
    """verify avec token invalide → 400."""
    r = client.get("/api/auth/verify?token=invalid-token-xyz")
    assert r.status_code == 400


def test_tenant_me_unauthorized(client):
    """GET /api/tenant/me sans Bearer → 401."""
    r = client.get("/api/tenant/me")
    assert r.status_code == 401


def test_tenant_me_bad_token(client):
    """GET /api/tenant/me avec token invalide → 401."""
    r = client.get("/api/tenant/me", headers={"Authorization": "Bearer invalid"})
    assert r.status_code == 401
