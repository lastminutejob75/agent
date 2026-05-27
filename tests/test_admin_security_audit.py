"""Tests pour les fixs de l'audit securite 2026-05.

Verifie :
- GET /api/admin/auth/status retourne un payload reduit sans auth (pas de leak config).
- GET /api/admin/auth/status enrichit le payload avec auth admin (cookie/Bearer).
- POST /api/public/onboarding ne retourne plus admin_setup_token.
- /api/admin/auth/logout reste accessible sans auth (clear cookie volontaire).
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def admin_headers():
    return {"Authorization": f"Bearer {os.environ.get('ADMIN_API_TOKEN', 'test-admin-token-pytest')}"}


# -----------------------------------------------------------------------------
# /api/admin/auth/status — payload reduit sans auth
# -----------------------------------------------------------------------------


def test_auth_status_unauthenticated_minimal_payload(client):
    """Sans auth : seul `login_configured` doit etre retourne (pas de leak config)."""
    r = client.get("/api/admin/auth/status")
    assert r.status_code == 200
    data = r.json()
    # Seul login_configured est attendu sans auth
    assert "login_configured" in data
    # Les details sensibles ne doivent PAS etre exposes
    assert "email_set" not in data
    assert "password_plain_set" not in data
    assert "password_hash_set" not in data
    assert "jwt_secret_set" not in data
    assert "admin_token_set" not in data


def test_auth_status_with_admin_bearer_returns_full_payload(client, admin_headers):
    """Avec auth admin Bearer : le payload detaille est expose (utile au debug)."""
    r = client.get("/api/admin/auth/status", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert "login_configured" in data
    # Avec auth, le payload detaille est present
    assert "email_set" in data
    assert "jwt_secret_set" in data
    assert "admin_token_set" in data


def test_auth_status_with_invalid_bearer_remains_minimal(client):
    """Bearer invalide → comme sans auth (pas de leak)."""
    r = client.get(
        "/api/admin/auth/status",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "login_configured" in data
    assert "email_set" not in data


# -----------------------------------------------------------------------------
# POST /api/public/onboarding — admin_setup_token retire
# -----------------------------------------------------------------------------


def test_public_onboarding_does_not_leak_admin_token(client):
    """La reponse /api/public/onboarding ne doit JAMAIS contenir admin_setup_token.

    Avant l'audit, ce champ exposait ADMIN_API_TOKEN au client public.
    """
    r = client.post(
        "/api/public/onboarding",
        json={
            "company_name": "Test Cabinet Audit",
            "email": "audit@test.fr",
            "calendar_provider": "none",
            "calendar_id": "",
        },
    )
    # On accepte 200 ou autre code (selon la DB mockee), on verifie juste l'absence du leak
    if r.status_code == 200:
        data = r.json()
        assert "admin_setup_token" not in data, (
            "REGRESSION SECURITE : admin_setup_token a ete reintroduit. "
            "Il ne doit JAMAIS etre expose au client public."
        )
        assert "tenant_id" in data
        assert "message" in data


def test_onboarding_response_model_no_admin_token_field():
    """Le modele Pydantic OnboardingResponse ne doit pas avoir admin_setup_token."""
    from backend.routes.admin import OnboardingResponse

    fields = OnboardingResponse.model_fields if hasattr(OnboardingResponse, "model_fields") else OnboardingResponse.__fields__
    field_names = set(fields.keys())
    assert "admin_setup_token" not in field_names, (
        "Le champ admin_setup_token a ete reintroduit dans OnboardingResponse. "
        "Cf. docs/AUDIT_SECURITE_2026-05.md."
    )
    # Champs attendus
    assert "tenant_id" in field_names
    assert "message" in field_names


# -----------------------------------------------------------------------------
# /auth/logout reste public (clear cookie OK)
# -----------------------------------------------------------------------------


def test_auth_logout_no_auth_required(client):
    """POST /api/admin/auth/logout : public, clear cookie cote client."""
    r = client.post("/api/admin/auth/logout")
    assert r.status_code in (200, 204)


# -----------------------------------------------------------------------------
# Endpoints admin /api/admin/* : require auth (smoke test)
# -----------------------------------------------------------------------------


def test_admin_tenants_requires_auth_smoke(client):
    """GET /api/admin/tenants sans auth → 401 (pas 200, pas 500)."""
    r = client.get("/api/admin/tenants")
    assert r.status_code == 401


def test_admin_leads_requires_auth_smoke(client):
    """GET /api/admin/leads sans auth → 401."""
    r = client.get("/api/admin/leads")
    assert r.status_code == 401


def test_admin_calls_requires_auth_smoke(client):
    """GET /api/admin/calls sans auth → 401."""
    r = client.get("/api/admin/calls")
    assert r.status_code == 401
