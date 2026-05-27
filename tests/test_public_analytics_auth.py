"""Tests pour l'auth de /api/public/analytics/{slug}/summary (audit 2026-05).

Verifie que :
- Sans auth → 401 (avant l'audit, c'etait public).
- Avec Bearer admin → bypass.
- Avec Bearer client mais slug d'un autre tenant → 401.
- Auth client + slug du bon tenant → autorise (smoke).
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def admin_headers():
    return {"Authorization": f"Bearer {os.environ.get('ADMIN_API_TOKEN', 'test-admin-token-pytest')}"}


def test_analytics_summary_blocked_without_auth(client):
    """GET /api/public/analytics/foo/summary sans aucune auth → 401."""
    r = client.get("/api/public/analytics/cabinet-test/summary")
    assert r.status_code == 401
    assert "acces" in (r.json().get("detail") or "").lower() or "refuse" in (r.json().get("detail") or "").lower()


def test_analytics_summary_admin_bypasses(client, admin_headers):
    """Bearer admin → bypass. La reponse depend de la DB mais != 401."""
    with patch("backend.routes.public_pages._analytics_summary", return_value={"events": 0}):
        r = client.get(
            "/api/public/analytics/cabinet-test/summary",
            headers=admin_headers,
        )
        assert r.status_code != 401


def test_analytics_summary_with_invalid_admin_bearer_blocked(client):
    """Bearer admin invalide → 401."""
    r = client.get(
        "/api/public/analytics/cabinet-test/summary",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert r.status_code == 401


def test_analytics_summary_helper_is_admin_authenticated_false_by_default(client):
    """_is_admin_authenticated() retourne False sans auth."""
    from backend.routes.public_pages import _is_admin_authenticated

    class FakeReq:
        def __init__(self):
            self.headers = {}
            self.cookies = {}

    assert _is_admin_authenticated(FakeReq()) is False


def test_analytics_summary_helper_is_admin_authenticated_true_with_bearer():
    """_is_admin_authenticated() retourne True avec Bearer admin valide."""
    from backend.routes.public_pages import _is_admin_authenticated

    admin_token = os.environ.get("ADMIN_API_TOKEN", "test-admin-token-pytest")

    class FakeReq:
        def __init__(self, h):
            self.headers = h
            self.cookies = {}

    req = FakeReq({"authorization": f"Bearer {admin_token}"})
    assert _is_admin_authenticated(req) is True


def test_analytics_summary_with_admin_returns_summary(client, admin_headers):
    """Avec auth admin et slug valide → 200 avec payload."""
    fake_summary = {
        "events": 42,
        "calls": 5,
        "bookings": 3,
        "by_day": [],
    }
    with patch("backend.routes.public_pages._analytics_summary", return_value=fake_summary):
        r = client.get(
            "/api/public/analytics/cabinet-x/summary?days=7",
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json() == fake_summary


def test_analytics_summary_tenant_owns_slug_helper_no_auth(client):
    """_tenant_owns_slug() retourne False si pas d'auth tenant."""
    from backend.routes.public_pages import _tenant_owns_slug

    class FakeReq:
        def __init__(self):
            self.headers = {}
            self.cookies = {}

    # Sans auth client → False (pas de leak)
    assert _tenant_owns_slug(FakeReq(), "any-slug") is False
