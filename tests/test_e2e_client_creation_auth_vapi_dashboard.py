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
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient

# JWT pour les tests tenant
os.environ.setdefault("JWT_SECRET", "test-secret-e2e")


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def jwt_secret():
    return os.environ.get("JWT_SECRET", "test-secret-e2e")


def _make_client_jwt(tenant_id: int, email: str = "client@test.fr", role: str = "owner", secret: str = None):
    """Génère un JWT client (comme après magic link verify)."""
    secret = secret or os.environ.get("JWT_SECRET", "test-secret-e2e")
    exp = datetime.utcnow() + timedelta(days=7)
    payload = {
        "sub": email,
        "tenant_id": tenant_id,
        "email": email,
        "role": role,
        "exp": exp,
        "iat": datetime.utcnow(),
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


def test_e2e_connexion_et_dashboard_client(client, jwt_secret):
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

    # Dashboard client (même JWT)
    r_dash = client.get("/api/tenant/dashboard", headers=headers)
    assert r_dash.status_code == 200
    dash = r_dash.json()
    assert "tenant_id" in dash or "calls" in dash or "kpis" in dash or "business_name" in dash or "name" in dash


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


# ---------- 5. Auth magic link (comportement, sans DB réelle) ----------


def test_e2e_auth_request_link_always_200(client):
    """POST /api/auth/request-link retourne toujours 200 (anti enumeration)."""
    r = client.post("/api/auth/request-link", json={"email": "unknown@example.com"})
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_e2e_auth_verify_invalid_400(client):
    """GET /api/auth/verify?token=invalid → 400."""
    r = client.get("/api/auth/verify?token=invalid-token")
    assert r.status_code == 400
