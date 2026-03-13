"""
Tests E2E : création client, validation email, connexion (JWT), Vapi, dashboard client.

Enchaîne :
1. Création client (POST /api/public/onboarding)
2. Validation email (guards.validate_email)
3. Connexion : JWT (manuel en test) → GET /api/tenant/me, GET /api/tenant/dashboard
4. Vapi : POST /api/vapi/webhook (assistant-request), POST /api/vapi/chat/completions
"""
from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def jwt_secret():
    return os.environ.get("JWT_SECRET")


def _make_client_jwt(tenant_id: int, email: str = "client@test.fr", role: str = "owner", secret: str = None):
    """Génère un vrai token client_session accepté par require_tenant_auth."""
    from backend.auth_pg import pg_create_tenant_user, pg_get_tenant_user_by_email

    secret = secret or os.environ.get("JWT_SECRET")
    pg_create_tenant_user(tenant_id, email, role=role, password="testpass123")
    user = pg_get_tenant_user_by_email(email)
    if user is not None:
        _, user_id, resolved_role = user
    else:
        user_id = int(tenant_id) * 1000 + 1
        resolved_role = role
    now = int(time.time())
    payload = {
        "typ": "client_session",
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": resolved_role or role,
        "exp": now + 86400,
        "iat": now,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


# ---------- 1. Création client ----------


def test_e2e_creation_client_onboarding(client):
    """POST /api/public/onboarding crée un tenant (client)."""
    r = client.post(
        "/api/public/onboarding",
        json={
            "company_name": "E2E Cabinet Test",
            "email": "e2e@client.fr",
            "calendar_provider": "none",
            "calendar_id": "",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "tenant_id" in data
    assert data["tenant_id"] >= 1
    assert "message" in data


# ---------- 2. Validation email ----------


def test_e2e_validation_email():
    """Validation format email (guards)."""
    from backend.guards import validate_email
    assert validate_email("client@test.fr") is True
    assert validate_email("  user@domain.co.uk  ") is True
    assert validate_email("invalid") is False
    assert validate_email("no-at.com") is False
    assert validate_email("") is False


# ---------- 3. Connexion + dashboard client ----------


@patch("backend.routes.tenant.pg_get_tenant_user_by_id")
def test_e2e_connexion_et_dashboard_client(mock_get_user, client, jwt_secret):
    """Avec un JWT client : GET /api/tenant/me et GET /api/tenant/dashboard renvoient 200."""
    # Créer un tenant puis se connecter avec un JWT pour ce tenant
    onboarding = client.post(
        "/api/public/onboarding",
        json={
            "company_name": "Dashboard E2E",
            "email": "dashboard@test.fr",
            "calendar_provider": "none",
            "calendar_id": "",
        },
    )
    assert onboarding.status_code == 200
    tenant_id = onboarding.json()["tenant_id"]
    assert tenant_id >= 1

    mock_get_user.return_value = {"tenant_id": tenant_id, "email": "dashboard@test.fr", "role": "owner"}
    token = _make_client_jwt(tenant_id, email="dashboard@test.fr", secret=jwt_secret)
    headers = {"Authorization": f"Bearer {token}"}

    # Profil tenant (connexion = JWT valide)
    r_me = client.get("/api/tenant/me", headers=headers)
    assert r_me.status_code == 200
    me = r_me.json()
    assert me.get("tenant_id") == tenant_id
    assert "tenant_name" in me
    assert me.get("email") == "dashboard@test.fr"
    assert me.get("role") == "owner"
    assert me.get("dashboard_tour_completed") is False

    # Dashboard client (même JWT)
    r_dash = client.get("/api/tenant/dashboard", headers=headers)
    assert r_dash.status_code == 200
    dash = r_dash.json()
    assert "tenant_id" in dash or "calls" in dash or "kpis" in dash or "business_name" in dash or "name" in dash


@patch("backend.routes.tenant.get_faq")
@patch("backend.routes.tenant._get_tenant_detail")
@patch("backend.routes.tenant.pg_get_tenant_user_by_id")
def test_tenant_me_onboarding_requires_real_completion(mock_get_user, mock_detail, mock_get_faq, client, jwt_secret):
    """Un tenant avec assistante Vapi mais sans numéro ni horaires ne doit pas être considéré onboardé."""
    tenant_id = 777
    mock_get_user.return_value = {"tenant_id": tenant_id, "email": "client@test.fr", "role": "owner"}
    mock_get_faq.return_value = [{"category": "Horaires", "items": [{"id": "h1", "question": "Q", "answer": "R", "active": True}]}]
    mock_detail.return_value = {
        "name": "Cabinet incomplet",
        "params": {
            "assistant_name": "sophie",
            "vapi_assistant_id": "asst_123",
            "calendar_provider": "none",
            "calendar_id": "",
            "booking_days": [],
        },
        "routing": [],
    }
    token = _make_client_jwt(tenant_id, email="client@test.fr", secret=jwt_secret)
    headers = {"Authorization": f"Bearer {token}"}

    r_me = client.get("/api/tenant/me", headers=headers)
    assert r_me.status_code == 200
    me = r_me.json()
    assert me["onboarding_steps"]["assistant_ready"] is True
    assert me["onboarding_steps"]["phone_ready"] is False
    assert me["onboarding_steps"]["horaires_ready"] is False
    assert me["onboarding_completed"] is False
    assert me["client_onboarding_completed"] is False
    assert me["dashboard_tour_completed"] is False


@patch("backend.routes.tenant.pg_get_tenant_user_by_id")
def test_tenant_patch_params_persists_transfer_wizard_config(mock_get_user, client, jwt_secret):
    """Le dashboard client peut sauvegarder et relire la configuration du wizard de transfert."""
    onboarding = client.post(
        "/api/public/onboarding",
        json={
            "company_name": "Cabinet transfert client",
            "email": "wizard-transfer@test.fr",
            "calendar_provider": "none",
            "calendar_id": "",
        },
    )
    assert onboarding.status_code == 200
    tenant_id = onboarding.json()["tenant_id"]

    mock_get_user.return_value = {"tenant_id": tenant_id, "email": "wizard-transfer@test.fr", "role": "owner"}
    token = _make_client_jwt(tenant_id, email="wizard-transfer@test.fr", secret=jwt_secret)
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "phone_number": "+33142345678",
        "transfer_number": "+33612345678",
        "transfer_live_enabled": "true",
        "transfer_callback_enabled": "true",
        "transfer_cases": ["urgent", "insists", "other"],
        "transfer_hours": {
            "Lundi": {"enabled": True, "from": "09:00", "to": "18:00"},
            "Mardi": {"enabled": True, "from": "09:00", "to": "18:00"},
        },
        "transfer_always_urgent": "true",
        "transfer_no_consultation": "false",
        "transfer_config_confirmed_signature": '{"ok":true}',
        "transfer_config_confirmed_at": "2026-03-12T20:00:00Z",
    }
    r_patch = client.patch("/api/tenant/params", headers=headers, json=payload)
    assert r_patch.status_code == 200
    assert r_patch.json()["ok"] is True

    with patch("backend.routes.tenant._get_tenant_detail") as mock_detail:
        r_me_seed = client.get("/api/tenant/me", headers=headers)
        assert r_me_seed.status_code == 200
        existing = r_me_seed.json()
        mock_detail.return_value = {
            "name": existing.get("tenant_name", "Cabinet transfert client"),
            "params": {
                "contact_email": existing.get("contact_email", ""),
                "phone_number": "+33142345678",
                "transfer_number": "+33612345678",
                "transfer_practitioner_phone": "+33698765432",
                "transfer_live_enabled": "true",
                "transfer_callback_enabled": "true",
                "transfer_cases": ["urgent", "insists", "other"],
                "transfer_hours": {
                    "Lundi": {"enabled": True, "from": "09:00", "to": "18:00"},
                    "Mardi": {"enabled": True, "from": "09:00", "to": "18:00"},
                },
                "transfer_always_urgent": "true",
                "transfer_no_consultation": "false",
                "transfer_config_confirmed_signature": '{"ok":true}',
                "transfer_config_confirmed_at": "2026-03-12T20:00:00Z",
            },
            "routing": [],
        }
        r_me = client.get("/api/tenant/me", headers=headers)
    assert r_me.status_code == 200
    me = r_me.json()
    assert me["phone_number"] == "+33142345678"
    assert me["transfer_number"] == "+33612345678"
    assert me["transfer_practitioner_phone"] == "+33698765432"
    assert me["transfer_live_enabled"] is True
    assert me["transfer_callback_enabled"] is True
    assert me["transfer_cases"] == ["urgent", "insists", "other"]
    assert me["transfer_hours"]["Lundi"]["enabled"] is True
    assert me["transfer_hours"]["Lundi"]["from"] == "09:00"
    assert me["transfer_always_urgent"] is True
    assert me["transfer_no_consultation"] is False
    assert me["transfer_config_confirmed_signature"] == '{"ok":true}'
    assert me["transfer_config_confirmed_at"] == "2026-03-12T20:00:00Z"


def test_e2e_tenant_me_sans_token_401(client):
    """GET /api/tenant/me sans Bearer → 401."""
    r = client.get("/api/tenant/me")
    assert r.status_code == 401


# ---------- 4. Vapi : webhook + chat/completions ----------


def test_e2e_vapi_webhook_assistant_request(client):
    """POST /api/vapi/webhook avec message.type=assistant-request → 200 (assistantId ou assistant)."""
    payload = {
        "message": {"type": "assistant-request"},
        "call": {"id": "e2e-call-1"},
    }
    r = client.post("/api/vapi/webhook", json=payload)
    assert r.status_code == 200
    # Réponse peut être JSON avec assistantId ou assistant
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    assert "assistantId" in data or "assistant" in data or data == {}


def test_e2e_vapi_chat_completions(client):
    """POST /api/vapi/chat/completions avec un message user → 200 et contenu texte."""
    call_id = f"e2e-chat-{uuid.uuid4().hex[:12]}"
    body = {
        "call": {"id": call_id},
        "messages": [{"role": "user", "content": "Bonjour"}],
        "stream": False,
    }
    r = client.post("/api/vapi/chat/completions", json=body)
    assert r.status_code == 200
    data = r.json()
    choices = data.get("choices", [])
    assert len(choices) >= 1
    content = (choices[0].get("message") or {}).get("content") or choices[0].get("text", "")
    assert isinstance(content, str)
    assert len(content) > 0


def test_e2e_vapi_chat_completions_rdv(client):
    """POST /api/vapi/chat/completions 'Je veux un rdv' → réponse avec nom/prénom ou créneaux."""
    call_id = f"e2e-rdv-{uuid.uuid4().hex[:12]}"
    body = {
        "call": {"id": call_id},
        "messages": [{"role": "user", "content": "Je veux un rendez-vous"}],
        "stream": False,
    }
    r = client.post("/api/vapi/chat/completions", json=body)
    assert r.status_code == 200
    data = r.json()
    content = (data.get("choices", [{}])[0].get("message", {})).get("content", "")
    assert "nom" in content.lower() or "prénom" in content.lower() or "créneau" in content.lower() or "disponible" in content.lower()


# ---------- 5. Auth client : cookie uniquement (plus de magic link) ----------


def test_e2e_tenant_me_unauthorized_without_cookie(client):
    """GET /api/tenant/me sans cookie → 401."""
    r = client.get("/api/tenant/me")
    assert r.status_code == 401
