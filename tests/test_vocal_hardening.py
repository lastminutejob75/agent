# tests/test_vocal_hardening.py
"""
Tests P1-P4 hardening vocal : CRITICAL_TOKENS centralisés, assistant-request 204, is_critical_token.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.stt_common import is_critical_token, CRITICAL_TOKENS, CRITICAL_OVERLAP


# --- P1 : is_critical_token (source unique stt_common) ---


def test_is_critical_token_non_true():
    """'non' est un token critique."""
    assert is_critical_token("non") is True


def test_is_critical_token_oui_true():
    """'oui' est un token critique."""
    assert is_critical_token("oui") is True


def test_is_critical_token_1_2_3_true():
    """'1', '2', '3' sont des tokens critiques."""
    assert is_critical_token("1") is True
    assert is_critical_token("2") is True
    assert is_critical_token("3") is True


def test_is_critical_token_confirme_true():
    """'confirme', 'je confirme', 'oui je confirme' sont des tokens critiques."""
    assert is_critical_token("confirme") is True
    assert is_critical_token("je confirme") is True
    assert is_critical_token("oui je confirme") is True


def test_is_critical_token_oui_1_combo():
    """'oui 1', 'oui 2' sont des tokens critiques (format choix créneau)."""
    assert is_critical_token("oui 1") is True
    assert is_critical_token("oui 2") is True


def test_is_critical_token_random_false():
    """Texte aléatoire n'est pas un token critique."""
    assert is_critical_token("bonjour") is False
    assert is_critical_token("pizza") is False
    assert is_critical_token("euh") is False


def test_critical_tokens_and_overlap_defined():
    """CRITICAL_TOKENS et CRITICAL_OVERLAP sont définis dans stt_common (source unique)."""
    assert len(CRITICAL_TOKENS) > 0
    assert len(CRITICAL_OVERLAP) > 0
    assert "oui" in CRITICAL_TOKENS or "oui" in CRITICAL_OVERLAP


# --- P2 : webhook Vapi assistant-request (body obligatoire pour éviter fallback anglais) ---


def test_assistant_request_returns_200_with_body():
    """Webhook : assistant-request doit retourner 200 avec body assistantId ou assistant (pas vide)."""
    client = TestClient(app)
    payload = {
        "call": {"id": "test-assistant-request"},
        "message": {"type": "assistant-request"},
    }
    response = client.post("/api/vapi/webhook", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "assistantId" in data or "assistant" in data
    if "assistant" in data:
        assert data["assistant"].get("firstMessage", "").strip()
        assert "Bonjour" in data["assistant"].get("firstMessage", "")


def test_assistant_request_with_vapi_assistant_id_returns_assistant_id(monkeypatch):
    """Quand VAPI_ASSISTANT_ID est défini, la réponse contient assistantId (Option A)."""
    monkeypatch.setenv("VAPI_ASSISTANT_ID", "78dd0e14-337e-40ab-96d9-7dbbe92cdf95")
    client = TestClient(app)
    payload = {"message": {"type": "assistant-request"}}
    response = client.post("/api/vapi/webhook", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data.get("assistantId") == "78dd0e14-337e-40ab-96d9-7dbbe92cdf95"


def test_assistant_request_detected_via_event_key():
    """assistant-request peut être dans message.event (pas seulement message.type)."""
    client = TestClient(app)
    payload = {"message": {"event": "assistant-request"}}
    response = client.post("/api/vapi/webhook", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "assistantId" in data or "assistant" in data


def test_assistant_request_transient_has_french_first_message(monkeypatch):
    """Sans VAPI_ASSISTANT_ID, le fallback transient a firstMessage en français (Option B)."""
    monkeypatch.delenv("VAPI_ASSISTANT_ID", raising=False)
    client = TestClient(app)
    payload = {"message": {"type": "assistant-request"}}
    response = client.post("/api/vapi/webhook", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "assistant" in data
    first = data["assistant"].get("firstMessage", "")
    assert "Bonjour" in first


def test_status_update_persists_customer_number_from_fallback_field():
    """status-update doit persister le numéro appelant même sans call.customer.number."""
    client = TestClient(app)
    payload = {
        "message": {
            "type": "status-update",
            "status": "in-progress",
            "call": {
                "id": "call-status-1",
                "from": "+33612345678",
                "phoneNumber": {"number": "+33912345678"},
                "startedAt": "2026-03-09T10:00:00Z",
            },
        }
    }
    fake_session = MagicMock()
    fake_session.customer_phone = None
    with patch("backend.routes.voice._get_or_resume_voice_session", return_value=fake_session):
        with patch("backend.routes.voice.ENGINE") as mock_engine:
            mock_engine.session_store = MagicMock()
            with patch("backend.tenant_routing.resolve_tenant_id_from_vapi_payload", return_value=(2, "route")):
                with patch("backend.vapi_calls_pg.upsert_vapi_call") as mock_upsert:
                    response = client.post("/api/vapi/webhook", json=payload)
    assert response.status_code == 200
    assert mock_upsert.call_count >= 1
    assert any(call.kwargs.get("customer_number") == "+33612345678" for call in mock_upsert.call_args_list)
