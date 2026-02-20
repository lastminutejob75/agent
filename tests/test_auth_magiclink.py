"""
Tests auth client : cookie uwi_session uniquement (plus de magic link).
- GET /api/tenant/me sans cookie → 401
- GET /api/tenant/me avec cookie invalide / absent → 401
"""
from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-for-pytest")


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


def test_tenant_me_unauthorized(client):
    """GET /api/tenant/me sans cookie → 401."""
    r = client.get("/api/tenant/me")
    assert r.status_code == 401


def test_tenant_me_no_bearer_fallback(client):
    """GET /api/tenant/me avec Bearer invalide → 401 (cookie only, pas de fallback Bearer)."""
    r = client.get("/api/tenant/me", headers={"Authorization": "Bearer invalid-token"})
    assert r.status_code == 401
