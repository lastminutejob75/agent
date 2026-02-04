# tests/test_vapi_stt_phonecall.py
"""
Tests nova-2-phonecall : partial no-op, NOISE vs SILENCE, normalisation fillers, cooldown.
"""

import os
import time
import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend import config
from backend.stt_utils import normalize_transcript, is_filler_only
from backend.prompts import MSG_NOISE_1, MSG_NOISE_2


# ============== stt_utils ==============

def test_normalize_transcript_strip_and_fillers():
    assert normalize_transcript("  euh  jean dupont  ") == "jean dupont"
    assert normalize_transcript("heu hum oui") == "oui"
    assert normalize_transcript("...") == ""
    assert normalize_transcript("euh") == ""


def test_normalize_transcript_preserves_content():
    assert normalize_transcript("Je voudrais un rendez-vous") == "Je voudrais un rendez-vous"
    assert normalize_transcript("  bonjour  ") == "bonjour"


def test_filler_ok_preserved():
    """P0-3 : 'ok' et 'oui' ne sont jamais supprimés par normalize (intents critiques)."""
    assert normalize_transcript("ok") == "ok"
    assert normalize_transcript("oui") == "oui"
    assert normalize_transcript("euh ok") == "ok"
    assert normalize_transcript("euh oui") == "oui"


def test_is_filler_only():
    assert is_filler_only("euh") is True
    assert is_filler_only("  euh  ") is True
    assert is_filler_only("...") is True
    assert is_filler_only("jean") is False
    assert is_filler_only("hum") is True


# ============== Webhook : format no-op compatible Vapi ==============

def test_no_op_format_compatible():
    """P0-1 : Partial retourne format Vapi valide (content vide), pas {}."""
    client = TestClient(app)
    r = client.post(
        "/api/vapi/webhook",
        json={
            "message": {"type": "user-message", "transcriptType": "partial", "content": "euh"},
            "call": {"id": "call_noop_fmt"},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict) and "content" in body
    assert body["content"] == ""


def test_confidence_none_robustesse():
    """P0-2 : Confidence absent ne crash pas ; transcript vide + confidence None + pas type audio → SILENCE."""
    client = TestClient(app)
    payload = {
        "message": {
            "type": "status",  # pas user-message → SILENCE
            "content": "",
        },
        "call": {"id": "call_conf_none_" + str(time.time())},
    }
    r = client.post("/api/vapi/webhook", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert "content" in body
    assert "entendu" in body["content"].lower() or "toujours" in body["content"].lower()


def test_confidence_none_with_user_message_type_noise():
    """P1 : transcript vide + confidence None + type user-message → NOISE (audio détecté, pas transcrit)."""
    client = TestClient(app)
    payload = {
        "message": {
            "type": "user-message",
            "content": "",
            "transcriptType": "final",
        },
        "call": {"id": "call_p1_noise_" + str(time.time())},
    }
    r = client.post("/api/vapi/webhook", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert "content" in body
    assert "répéter" in body["content"].lower() or "bruit" in body["content"].lower()


# ============== Webhook : partial => no-op ==============

def test_webhook_partial_returns_empty():
    """transcriptType partial => ne pas appeler le moteur, retourner format Vapi vide."""
    client = TestClient(app)
    payload = {
        "message": {
            "type": "user-message",
            "transcriptType": "partial",
            "content": "euh je voudrais",
        },
        "call": {"id": "call_partial_test"},
    }
    r = client.post("/api/vapi/webhook", json=payload)
    assert r.status_code == 200
    body = r.json()
    # P0-1 : même format que réponse normale, mais vide (compatible Vapi)
    assert "content" in body
    assert body["content"] == ""


# ============== Webhook : NOISE (transcript vide + faible confidence) ==============

def test_webhook_empty_transcript_low_confidence_noise():
    """Transcript '' + confidence 0.2 => NOISE => MSG_NOISE_1."""
    with patch.dict(os.environ, {"NOISE_CONFIDENCE_THRESHOLD": "0.35"}, clear=False):
        client = TestClient(app)
        payload = {
            "message": {
                "type": "user-message",
                "transcriptType": "final",
                "content": "",
                "confidence": 0.2,
            },
            "call": {"id": "call_noise_empty_1"},
        }
        r = client.post("/api/vapi/webhook", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert "content" in body
        assert MSG_NOISE_1 in body["content"] or "répéter" in body["content"]


def test_webhook_euh_low_confidence_noise():
    """Transcript 'euh' + confidence 0.3 => NOISE."""
    client = TestClient(app)
    payload = {
        "message": {
            "type": "user-message",
            "transcriptType": "final",
            "content": "euh",
            "confidence": 0.3,
        },
        "call": {"id": "call_noise_euh_1"},
    }
    r = client.post("/api/vapi/webhook", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert "content" in body
    assert "répéter" in body["content"].lower() or "bruit" in body["content"].lower()


# ============== Webhook : cooldown => 2e NOISE no-op ==============

def test_webhook_noise_cooldown_second_no_op():
    """Deux NOISE rapprochés (même call_id) : 2e dans le cooldown => no-op (pas de message)."""
    client = TestClient(app)
    call_id = "call_cooldown_" + str(time.time())
    payload_noise = {
        "message": {
            "type": "user-message",
            "transcriptType": "final",
            "content": "",
            "confidence": 0.2,
        },
        "call": {"id": call_id},
    }
    r1 = client.post("/api/vapi/webhook", json=payload_noise)
    assert r1.status_code == 200
    body1 = r1.json()
    assert "content" in body1
    # Deuxième requête immédiate : dans le cooldown (2s par défaut) => no-op
    r2 = client.post("/api/vapi/webhook", json=payload_noise)
    assert r2.status_code == 200
    body2 = r2.json()
    assert "content" in body2 and body2["content"] == ""


# ============== Engine handle_noise (via webhook ou direct) ==============

def test_handle_noise_first_then_second_message():
    """1er NOISE => MSG_NOISE_1, 2e (après cooldown) => MSG_NOISE_2."""
    from backend.engine import ENGINE
    call_id = "call_noise_12_" + str(time.time())
    session = ENGINE.session_store.get_or_create(call_id)
    session.channel = "vocal"
    session.noise_detected_count = 0
    session.last_noise_ts = None

    events1 = ENGINE.handle_noise(session)
    assert len(events1) == 1
    assert MSG_NOISE_1 in events1[0].text or "répéter" in events1[0].text

    # Simuler passage du cooldown
    session.last_noise_ts = time.time() - (config.NOISE_COOLDOWN_SEC + 1)
    events2 = ENGINE.handle_noise(session)
    assert len(events2) == 1
    assert MSG_NOISE_2 in events2[0].text or "bruit" in events2[0].text.lower()


def test_noise_reset_on_confirmed():
    """P1-1 : noise_detected_count reset quand réponse webhook a conv_state CONFIRMED/TRANSFERRED."""
    from backend.engine import ENGINE
    client = TestClient(app)
    call_id = "call_reset_noise_" + str(time.time())
    session = ENGINE.session_store.get_or_create(call_id)
    session.channel = "vocal"
    session.noise_detected_count = 2
    session.last_noise_ts = time.time()
    payload = {
        "message": {"type": "user-message", "transcriptType": "final", "content": "je veux parler à un humain"},
        "call": {"id": call_id},
    }
    r = client.post("/api/vapi/webhook", json=payload)
    assert r.status_code == 200
    session2 = ENGINE.session_store.get_or_create(call_id)
    assert getattr(session2, "noise_detected_count", 0) == 0
    assert getattr(session2, "last_noise_ts", None) is None
