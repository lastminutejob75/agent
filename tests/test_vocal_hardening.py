# tests/test_vocal_hardening.py
"""
Tests P1-P4 hardening vocal : CRITICAL_TOKENS centralisés, assistant-request 204, is_critical_token.
"""
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


# --- P2 : webhook Vapi retourne 200 (Option A : pas de traitement, évite saturation worker) ---


def test_assistant_request_returns_200():
    """Webhook Vapi : retourne 200 immédiat (fire-and-forget, pas de lecture du body)."""
    client = TestClient(app)
    payload = {
        "call": {"id": "test-assistant-request"},
        "message": {
            "role": "user",
            "type": "assistant-request",
            "transcript": "",
            "transcriptType": "final",
        },
    }
    response = client.post("/api/vapi/webhook", json=payload)
    assert response.status_code == 200
