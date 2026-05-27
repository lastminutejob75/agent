"""Tests securite pour les endpoints /api/pre-onboarding/* (audit 2026-05).

Verifie que :
- POST /commit retourne un token signe.
- GET /leads/{id}/email refuse l'acces sans token (401) ou avec un mauvais token (403).
- GET /leads/{id}/check idem.
- POST /leads/{id}/callback-booking idem.
- POST /leads/{id}/create-account idem.
- Token expire → 410.
- Bypass admin (Bearer ADMIN_API_TOKEN) fonctionne.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _ensure_secret(monkeypatch):
    monkeypatch.setenv("LEAD_TOKEN_SECRET", "test-lead-token-secret-32-bytes-min-ok")


@pytest.fixture
def client():
    """Client FastAPI partage par les tests."""
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def fake_lead():
    """Mock get_lead/lead_exists pour simuler un lead existant."""
    fake = {
        "id": "lead-test-1",
        "email": "user@example.com",
        "daily_call_volume": "10-25",
        "medical_specialty": "dentiste",
        "primary_pain_point": "Autre",
        "assistant_name": "Sophie",
        "voice_gender": "female",
        "opening_hours": {"0": {"start": "09:00", "end": "18:00", "closed": False}},
        "source": "landing_cta",
        "callback_phone": None,
        "notes_log": None,
        "is_enterprise": False,
    }
    return fake


# -----------------------------------------------------------------------------
# /check
# -----------------------------------------------------------------------------


def test_check_without_token_returns_401(client):
    """GET /leads/{id}/check sans token → 401 (token requis)."""
    r = client.get("/api/pre-onboarding/leads/some-uuid/check")
    assert r.status_code == 401
    assert "token" in (r.json().get("detail") or "").lower()


def test_check_with_invalid_token_returns_403(client):
    """Token bidon → 403."""
    r = client.get("/api/pre-onboarding/leads/some-uuid/check?token=garbage")
    assert r.status_code == 403


def test_check_with_expired_token_returns_410(client):
    """Token expire → 410 (recommencer l'inscription)."""
    from backend.lead_tokens import make_lead_token

    expired = make_lead_token("lead-x", ttl_seconds=-10)
    r = client.get(f"/api/pre-onboarding/leads/lead-x/check?token={expired}")
    assert r.status_code == 410


def test_check_with_token_for_different_lead_returns_403(client):
    """Token genere pour lead A, utilise sur lead B → 403."""
    from backend.lead_tokens import make_lead_token

    t = make_lead_token("lead-A")
    r = client.get(f"/api/pre-onboarding/leads/lead-B/check?token={t}")
    assert r.status_code == 403


def test_check_with_valid_token_passes_token_check(client, fake_lead):
    """Token valide → l'auth passe (la suite depend de la DB).

    On ne teste pas le retour metier (DB Postgres mockee), juste que le 401/403/410
    n'est PAS retourne.
    """
    from backend.lead_tokens import make_lead_token

    t = make_lead_token("lead-test-1")
    with patch("backend.routes.pre_onboarding.lead_exists", return_value=True):
        r = client.get(f"/api/pre-onboarding/leads/lead-test-1/check?token={t}")
        assert r.status_code == 200
        assert r.json().get("exists") is True


def test_check_with_admin_bearer_bypass(client):
    """Auth Bearer admin → bypass token requis."""
    admin_token = os.environ.get("ADMIN_API_TOKEN", "test-admin-token-pytest")
    with patch("backend.routes.pre_onboarding.lead_exists", return_value=True):
        r = client.get(
            "/api/pre-onboarding/leads/any-id/check",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200


def test_check_token_via_header_works(client):
    """Token passe via header X-Lead-Token (alternative a la query string)."""
    from backend.lead_tokens import make_lead_token

    t = make_lead_token("lead-header")
    with patch("backend.routes.pre_onboarding.lead_exists", return_value=True):
        r = client.get(
            "/api/pre-onboarding/leads/lead-header/check",
            headers={"X-Lead-Token": t},
        )
        assert r.status_code == 200


# -----------------------------------------------------------------------------
# /email
# -----------------------------------------------------------------------------


def test_email_without_token_returns_401(client):
    r = client.get("/api/pre-onboarding/leads/some-uuid/email")
    assert r.status_code == 401


def test_email_with_invalid_token_returns_403(client):
    r = client.get("/api/pre-onboarding/leads/some-uuid/email?token=bad")
    assert r.status_code == 403


def test_email_with_valid_token_returns_email(client, fake_lead):
    from backend.lead_tokens import make_lead_token

    t = make_lead_token("lead-test-1")
    with patch("backend.routes.pre_onboarding.get_lead", return_value=fake_lead):
        r = client.get(f"/api/pre-onboarding/leads/lead-test-1/email?token={t}")
        assert r.status_code == 200
        assert r.json().get("email") == "user@example.com"


# -----------------------------------------------------------------------------
# /callback-booking (POST)
# -----------------------------------------------------------------------------


def test_callback_booking_without_token_returns_401(client):
    r = client.post(
        "/api/pre-onboarding/leads/some-uuid/callback-booking",
        json={"date": "2026-06-01", "slot": "10:00", "phone": "0612345678"},
    )
    assert r.status_code == 401


def test_callback_booking_with_invalid_token_returns_403(client):
    r = client.post(
        "/api/pre-onboarding/leads/some-uuid/callback-booking?token=garbage",
        json={"date": "2026-06-01", "slot": "10:00", "phone": "0612345678"},
    )
    assert r.status_code == 403


# -----------------------------------------------------------------------------
# /create-account (POST) — endpoint critique (cree un tenant)
# -----------------------------------------------------------------------------


def test_create_account_without_token_returns_401(client):
    """POST /leads/{id}/create-account sans token → 401 (CRITIQUE)."""
    r = client.post(
        "/api/pre-onboarding/leads/some-uuid/create-account",
        json={"email": "fake@example.com"},
    )
    assert r.status_code == 401


def test_create_account_with_invalid_token_returns_403(client):
    r = client.post(
        "/api/pre-onboarding/leads/some-uuid/create-account?token=garbage",
        json={"email": "fake@example.com"},
    )
    assert r.status_code == 403


def test_create_account_with_expired_token_returns_410(client):
    from backend.lead_tokens import make_lead_token

    expired = make_lead_token("lead-x", ttl_seconds=-10)
    r = client.post(
        f"/api/pre-onboarding/leads/lead-x/create-account?token={expired}",
        json={"email": "fake@example.com"},
    )
    assert r.status_code == 410


# -----------------------------------------------------------------------------
# /commit retourne un token
# -----------------------------------------------------------------------------


def test_commit_returns_token(client):
    """POST /commit doit retourner un champ `token` non vide (HMAC signe)."""
    payload = {
        "email": "newuser@example.com",
        "medical_specialty": "dentiste",
        "daily_call_volume": "10-25",
        "primary_pain_point": "Autre",
        "opening_hours": {"0": {"start": "09:00", "end": "18:00", "closed": False}},
        "voice_gender": "female",
        "assistant_name": "Sophie",
        "source": "landing_cta",
    }
    with patch("backend.routes.pre_onboarding.upsert_lead", return_value="lead-new-uuid"), \
         patch("backend.routes.pre_onboarding.send_lead_founder_email", return_value=(True, None)), \
         patch("backend.routes.pre_onboarding.send_pre_onboarding_admin_notification_email", return_value=(True, None)):
        r = client.post("/api/pre-onboarding/commit", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        assert data.get("lead_id") == "lead-new-uuid"
        assert "token" in data
        assert data["token"]  # non vide
        # Le token doit etre verifiable
        from backend.lead_tokens import verify_lead_token
        ok, lead_id, _ = verify_lead_token(data["token"], expected_lead_id="lead-new-uuid")
        assert ok is True
        assert lead_id == "lead-new-uuid"
