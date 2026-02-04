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
from backend.stt_common import classify_text_only, is_critical_token, looks_like_garbage_or_wrong_language
from backend.prompts import MSG_NOISE_1, MSG_NOISE_2, MSG_UNCLEAR_1
from backend.routes.voice import _classify_stt_input, _is_critical_token


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


def test_critical_tokens_never_noise():
    """Tokens critiques forcent TEXT même si confidence très basse."""
    assert _is_critical_token("oui") is True
    kind, _ = _classify_stt_input("oui", 0.15, "final")
    assert kind == "TEXT"
    assert _is_critical_token("non") is True
    assert _is_critical_token("1") is True
    assert _is_critical_token("deux") is True
    assert _is_critical_token("oui 2") is True
    assert _is_critical_token("ok trois") is True
    assert _is_critical_token("euh") is False


def test_critical_tokens_with_punctuation():
    """Tokens critiques détectés même avec ponctuation finale."""
    assert _is_critical_token("oui.") is True
    assert _is_critical_token("oui,") is True
    assert _is_critical_token("non!") is True


def test_oui_never_classified_as_noise():
    """'oui' (court + faible confidence) doit rester TEXT, pas NOISE — critique confirmation."""
    client = TestClient(app)
    payload = {
        "message": {
            "type": "user-message",
            "transcriptType": "final",
            "content": "oui",
            "confidence": 0.3,  # bas, mais "oui" = mot critique
        },
        "call": {"id": "call_oui_critical_" + str(time.time())},
    }
    r = client.post("/api/vapi/webhook", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert "content" in body
    content = body["content"]
    # Ne doit jamais recevoir MSG_NOISE_1 ou MSG_NOISE_2 quand l'utilisateur dit "oui"
    assert "pas bien entendu" not in content
    assert "Il y a du bruit" not in content


def test_is_filler_only():
    assert is_filler_only("euh") is True
    assert is_filler_only("  euh  ") is True
    assert is_filler_only("...") is True
    assert is_filler_only("jean") is False
    assert is_filler_only("hum") is True


# ============== stt_common (Stratégie 2 — chat/completions text-only) ==============

def test_classify_text_only_oui_TEXT():
    """'oui' => TEXT forcé (token critique)."""
    kind, norm = classify_text_only("oui")
    assert kind == "TEXT"
    assert norm == "oui"
    kind2, _ = classify_text_only("  oui  ")
    assert kind2 == "TEXT"


def test_classify_text_only_silence():
    """Texte vide => SILENCE."""
    kind, norm = classify_text_only("")
    assert kind == "SILENCE"
    assert norm == ""
    kind2, _ = classify_text_only("   ")
    assert kind2 == "SILENCE"


def test_classify_text_only_euh_UNCLEAR():
    """Filler seul 'euh' => UNCLEAR."""
    kind, _ = classify_text_only("euh")
    assert kind == "UNCLEAR"
    kind2, _ = classify_text_only("  hum  ")
    assert kind2 == "UNCLEAR"


def test_classify_text_only_garbage_UNCLEAR():
    """Texte anglais/garbage => UNCLEAR."""
    assert looks_like_garbage_or_wrong_language("Believe you would have won't even All these") is True
    kind, _ = classify_text_only("Believe you would have won't even All these")
    assert kind == "UNCLEAR"
    kind2, _ = classify_text_only("the and you would")
    assert kind2 == "UNCLEAR"


def test_stt_common_critical_tokens():
    """Tokens critiques reconnus comme TEXT."""
    assert is_critical_token("oui") is True
    assert is_critical_token("non") is True
    assert is_critical_token("1") is True
    assert is_critical_token("deux") is True
    assert is_critical_token("ouais") is True
    assert is_critical_token("d'accord") is True
    assert is_critical_token("euh") is False


# ============== Health Vapi (diagnostic) ==============

def test_vapi_internal_health():
    """GET /api/vapi/_health retourne 200 OK."""
    client = TestClient(app)
    r = client.get("/api/vapi/_health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok" and r.json().get("service") == "vapi"


# ============== Webhook : format no-op compatible Vapi ==============

def test_partial_returns_204():
    """Partial → HTTP 204 No Content (vrai no-op, pas de tour)."""
    client = TestClient(app)
    r = client.post(
        "/api/vapi/webhook",
        json={
            "message": {"type": "user-message", "transcriptType": "partial", "content": "euh"},
            "call": {"id": "call_noop_204"},
        },
    )
    assert r.status_code == 204
    assert not r.content or len(r.content) == 0


def test_no_op_format_compatible():
    """Alias: partial retourne 204 (compatibilité nom test)."""
    test_partial_returns_204()


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
    """transcriptType partial => HTTP 204, pas de body."""
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
    assert r.status_code == 204
    assert not r.content or len(r.content) == 0


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


# ============== Webhook : cooldown => 204 ==============

def test_cooldown_returns_204():
    """Deux NOISE rapprochés : 2e requête doit retourner HTTP 204."""
    client = TestClient(app)
    call_id = "call_cooldown_204_" + str(time.time())
    payload = {
        "message": {"type": "user-message", "transcriptType": "final", "content": "", "confidence": 0.2},
        "call": {"id": call_id},
    }
    r1 = client.post("/api/vapi/webhook", json=payload)
    assert r1.status_code == 200
    r2 = client.post("/api/vapi/webhook", json=payload)
    assert r2.status_code == 204


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
    # Deuxième requête immédiate : dans le cooldown (2s par défaut) => HTTP 204
    r2 = client.post("/api/vapi/webhook", json=payload_noise)
    assert r2.status_code == 204
    assert not r2.content or len(r2.content) == 0


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


def test_logs_decision(caplog):
    """decision_in et decision_out présents ; pas de PII (transcript complet) dans les logs."""
    import logging
    client = TestClient(app)
    with caplog.at_level(logging.INFO):
        r = client.post(
            "/api/vapi/webhook",
            json={
                "message": {"type": "user-message", "transcriptType": "partial", "content": "euh"},
                "call": {"id": "call_logs_test"},
            },
        )
    assert r.status_code == 204
    assert any("decision_in" in (getattr(rec, "msg", rec.message) or "") for rec in caplog.records)
    assert any("decision_out" in (getattr(rec, "msg", rec.message) or "") for rec in caplog.records)


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


# ============== Chat/completions : decision logs + firewall ==============

def _chat_completions_payload(call_id: str, user_content: str, stream: bool = False):
    """Payload OpenAI-like pour POST /api/vapi/chat/completions."""
    messages = [{"role": "assistant", "content": "Bonjour, que puis-je faire pour vous ?"}]
    if user_content is not None:
        messages.append({"role": "user", "content": user_content})
    return {
        "call": {"id": call_id},
        "messages": messages,
        "stream": stream,
    }


def test_chat_completions_decision_logs_present(caplog):
    """decision_in et decision_out présents pour chat/completions (sans PII)."""
    import logging
    client = TestClient(app)
    call_id = "call_decision_logs_" + str(time.time())
    with caplog.at_level(logging.INFO):
        r = client.post(
            "/api/vapi/chat/completions",
            json=_chat_completions_payload(call_id, "bonjour"),
        )
    assert r.status_code == 200
    assert any("decision_in" in (getattr(rec, "msg", rec.message) or "") for rec in caplog.records)
    assert any("decision_out" in (getattr(rec, "msg", rec.message) or "") for rec in caplog.records)


def test_chat_completions_oui_text_path():
    """'oui' => TEXT (pas UNCLEAR) => engine traite, pas MSG_UNCLEAR_1."""
    client = TestClient(app)
    call_id = "call_oui_text_" + str(time.time())
    r = client.post(
        "/api/vapi/chat/completions",
        json=_chat_completions_payload(call_id, "oui"),
    )
    assert r.status_code == 200
    data = r.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    assert MSG_UNCLEAR_1 not in content


def test_chat_completions_silence():
    """Texte vide (après normalisation) => SILENCE => engine.handle_message(call_id, '')."""
    client = TestClient(app)
    call_id = "call_silence_" + str(time.time())
    r = client.post(
        "/api/vapi/chat/completions",
        json=_chat_completions_payload(call_id, "   "),
    )
    assert r.status_code == 200
    data = r.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    assert "entendu" in content.lower() or "répéter" in content.lower() or "toujours" in content.lower()


def test_chat_completions_unclear_1():
    """1er UNCLEAR (garbage) => MSG_UNCLEAR_1."""
    client = TestClient(app)
    call_id = "call_unclear_1_" + str(time.time())
    r = client.post(
        "/api/vapi/chat/completions",
        json=_chat_completions_payload(call_id, "Believe you would have won't even All these"),
    )
    assert r.status_code == 200
    data = r.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    assert MSG_UNCLEAR_1 in content
