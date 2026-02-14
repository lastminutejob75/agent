# tests/test_vapi_chat_completions_streaming.py
"""
Anti-régression : stream=true → toujours SSE (Content-Type text/event-stream + data: ... + data: [DONE]).
Évite le "streaming mismatch" qui cause silence/hang côté Vapi TTS.
"""
import uuid
import pytest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from backend.main import app
from backend.routes.voice import _parse_stream_flag


# ---------- _parse_stream_flag ----------

def test_parse_stream_flag_bool():
    assert _parse_stream_flag({"stream": True}) is True
    assert _parse_stream_flag({"stream": False}) is False
    assert _parse_stream_flag({"streaming": True}) is True


def test_parse_stream_flag_string_not_truthy():
    """'false' string ne doit pas être traité comme True (bool('false') == True en Python)."""
    assert _parse_stream_flag({"stream": "false"}) is False
    assert _parse_stream_flag({"stream": "0"}) is False
    assert _parse_stream_flag({"stream": "no"}) is False
    assert _parse_stream_flag({"stream": " true "}) is True
    assert _parse_stream_flag({"stream": "1"}) is True
    assert _parse_stream_flag({"stream": "yes"}) is True


def test_parse_stream_flag_int():
    assert _parse_stream_flag({"stream": 1}) is True
    assert _parse_stream_flag({"stream": 0}) is False


# ---------- Stream=true → SSE (nominal) ----------

def test_stream_true_returns_sse_nominal():
    """stream=true : 200, Content-Type text/event-stream, body contient data: et [DONE]."""
    client = TestClient(app)
    call_id = f"stream-nominal-{uuid.uuid4().hex[:12]}"
    payload = {
        "call": {"id": call_id},
        "messages": [{"role": "user", "content": "TEST AUDIO 123"}],
        "stream": True,
    }
    response = client.post("/api/vapi/chat/completions", json=payload)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    body = response.text
    assert "data:" in body
    assert "[DONE]" in body
    assert body.strip().endswith("data: [DONE]")


# ---------- Stream=true + exception → SSE ----------

def test_stream_true_returns_sse_on_exception():
    """En cas d'exception, si stream=true on renvoie quand même du SSE (pas du JSON)."""
    client = TestClient(app)
    call_id = f"stream-except-{uuid.uuid4().hex[:12]}"
    payload = {
        "call": {"id": call_id},
        "messages": [{"role": "user", "content": "test"}],
        "stream": True,
    }

    with patch("backend.routes.voice._get_or_resume_voice_session", side_effect=RuntimeError("injected")):
        # Faire en sorte qu'on entre dans le else (user_message non vide) et qu'une erreur soit levée
        # après avoir lu payload (pour que _parse_stream_flag ait stream=true).
        # _get_or_resume_voice_session est appelé après _pg_lock_ok / lock → on peut faire échouer là.
        with patch("backend.routes.voice._pg_lock_ok", return_value=False):
            response = client.post("/api/vapi/chat/completions", json=payload)
    # Même en erreur, stream=true → SSE
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    assert "data:" in response.text
    assert "[DONE]" in response.text


# ---------- Stream=true + LockTimeout → SSE ----------

def test_stream_true_returns_sse_on_lock_timeout():
    """LockTimeout (concurrent webhook) : retour greeting en SSE quand stream=true."""
    from backend.session_pg import LockTimeout

    client = TestClient(app)
    call_id = f"stream-lock-{uuid.uuid4().hex[:12]}"
    payload = {
        "call": {"id": call_id},
        "messages": [{"role": "user", "content": "bonjour"}],
        "stream": True,
    }

    # Simuler un LockTimeout à l'entrée du lock
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(side_effect=LockTimeout())
    mock_cm.__exit__ = MagicMock(return_value=None)

    with patch("backend.routes.voice._pg_lock_ok", return_value=True):
        with patch("backend.session_pg.pg_lock_call_session", return_value=mock_cm):
            with patch("backend.routes.voice._call_journal_ensure"):
                response = client.post("/api/vapi/chat/completions", json=payload)

    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    body = response.text
    assert "data:" in body
    assert "[DONE]" in body


# ---------- stream=false → JSON ----------

def test_stream_false_returns_json():
    """stream=false ou absent : réponse application/json (pas SSE)."""
    client = TestClient(app)
    call_id = f"no-stream-{uuid.uuid4().hex[:12]}"
    payload = {
        "call": {"id": call_id},
        "messages": [{"role": "user", "content": "bonjour"}],
        "stream": False,
    }
    response = client.post("/api/vapi/chat/completions", json=payload)
    assert response.status_code == 200
    assert "application/json" in response.headers.get("content-type", "")
    data = response.json()
    assert "choices" in data
    assert data["choices"][0].get("message", {}).get("content")
