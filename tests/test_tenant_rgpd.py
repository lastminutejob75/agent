"""Tests GET /api/tenant/rgpd (protégé JWT)."""

import os
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient

os.environ["JWT_SECRET"] = "test-jwt-secret-for-tenant-rgpd-32ch"


def _make_jwt(tenant_id: int = 1, email: str = "test@example.com"):
    from datetime import datetime, timedelta
    exp = datetime.utcnow() + timedelta(days=7)
    return jwt.encode(
        {"sub": email, "tenant_id": tenant_id, "email": email, "role": "owner", "exp": exp},
        os.environ["JWT_SECRET"],
        algorithm="HS256",
    )


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


def test_tenant_rgpd_unauthorized(client):
    """GET /api/tenant/rgpd sans JWT → 401."""
    r = client.get("/api/tenant/rgpd")
    assert r.status_code == 401


@patch("backend.routes.tenant._get_kpis_daily")
def test_tenant_kpis_ok(mock_kpis, client):
    """GET /api/tenant/kpis avec JWT → days + trend."""
    mock_kpis.return_value = {
        "days": [
            {"date": "2026-02-01", "calls": 3, "bookings": 1, "transfers": 0},
            {"date": "2026-02-02", "calls": 5, "bookings": 2, "transfers": 1},
        ],
        "current": {"calls": 8, "bookings": 3, "transfers": 1},
        "previous": {"calls": 6, "bookings": 2, "transfers": 1},
        "trend": {"calls_pct": 33, "bookings_pct": 50, "transfers_pct": 0},
    }
    token = _make_jwt()
    r = client.get("/api/tenant/kpis?days=7", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert len(data["days"]) == 2
    assert data["trend"]["calls_pct"] == 33


@patch("backend.routes.tenant._get_rgpd_extended")
def test_tenant_rgpd_ok(mock_rgpd, client):
    """GET /api/tenant/rgpd avec JWT → consent_rate + last_consents."""
    mock_rgpd.return_value = {
        "tenant_id": 1,
        "start": "2026-01-27 00:00:00",
        "end": "2026-02-03 12:00:00",
        "consent_obtained": 5,
        "calls_total": 10,
        "consent_rate": 0.5,
        "last_consents": [
            {"call_id": "call-1", "at": "2026-02-03T10:00:00", "version": "2026-02-12_v1"},
        ],
    }
    token = _make_jwt()
    r = client.get("/api/tenant/rgpd", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["consent_rate"] == 0.5
    assert data["consent_obtained"] == 5
    assert data["calls_total"] == 10
    assert len(data["last_consents"]) == 1
    assert data["last_consents"][0]["call_id"] == "call-1"
