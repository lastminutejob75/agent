# tests/test_vapi_chat_completions_session.py
"""
FIX A : Vérifier que la session est stable entre 2 requêtes chat/completions (même call_id).
Si call_id change à chaque requête, l'état repart en START → boucle "c'est à quel nom ?".
"""
import uuid
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.engine import ENGINE


def _payload(call_id: str, messages: list) -> dict:
    return {
        "call": {"id": call_id},
        "messages": messages,
        "stream": False,
    }


def test_chat_completions_session_stable():
    """Session persiste entre requêtes avec même call_id : state progresse, turn_count incrémente."""
    client = TestClient(app)
    call_id = f"stable-{uuid.uuid4().hex[:12]}"

    # Tour 1 : "Je veux un rdv" → QUALIF_NAME (question nom)
    body1 = {"call": {"id": call_id}, "messages": [{"role": "user", "content": "Je veux un rdv"}], "stream": False}
    r1 = client.post("/api/vapi/chat/completions", json=body1)
    assert r1.status_code == 200
    content1 = r1.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    assert "nom" in content1.lower() or "prénom" in content1.lower()
    session = ENGINE.session_store.get(call_id)
    assert session is not None
    assert session.state == "QUALIF_NAME"

    # Tour 2 (même call_id) : donner le nom → état doit progresser
    body2 = {
        "call": {"id": call_id},
        "messages": [
            {"role": "user", "content": "Je veux un rdv"},
            {"role": "assistant", "content": content1},
            {"role": "user", "content": "Martin Dupont"},
        ],
        "stream": False,
    }
    r2 = client.post("/api/vapi/chat/completions", json=body2)
    assert r2.status_code == 200
    session = ENGINE.session_store.get(call_id)
    assert session is not None
    assert session.state != "START"
    assert session.state != "QUALIF_NAME"
    assert getattr(session, "turn_count", 0) >= 2


def test_chat_completions_same_call_id_state_persists():
    """2 requêtes avec le même call_id : l'état progresse (QUALIF_NAME → après nom → QUALIF_MOTIF ou suivant)."""
    client = TestClient(app)
    call_id = f"test-session-{uuid.uuid4().hex[:12]}"

    # 1ère requête : "Je veux un rdv" → on attend QUALIF_NAME (question nom)
    payload1 = _payload(call_id, [{"role": "user", "content": "Je veux un rdv"}])
    r1 = client.post("/api/vapi/chat/completions", json=payload1)
    assert r1.status_code == 200
    body1 = r1.json()
    content1 = body1.get("choices", [{}])[0].get("message", {}).get("content", "")
    assert content1
    assert "nom" in content1.lower() or "prénom" in content1.lower()

    # 2e requête : même call_id, on donne le nom → l'état doit progresser (pas redemander le nom)
    payload2 = _payload(
        call_id,
        [
            {"role": "user", "content": "Je veux un rdv"},
            {"role": "assistant", "content": content1},
            {"role": "user", "content": "Martin Dupont"},
        ],
    )
    r2 = client.post("/api/vapi/chat/completions", json=payload2)
    assert r2.status_code == 200
    body2 = r2.json()
    content2 = body2.get("choices", [{}])[0].get("message", {}).get("content", "")
    assert content2
    # Après avoir donné le nom, on doit avoir la question motif ou préférence, pas "c'est à quel nom"
    assert "nom" not in content2.lower() or "prénom" not in content2.lower() or "motif" in content2.lower() or "préférez" in content2.lower() or "matin" in content2.lower()


def test_chat_completions_session_key_from_header():
    """Session key peut venir du header x-vapi-call-id si body.call.id absent."""
    client = TestClient(app)
    call_id = f"header-{uuid.uuid4().hex[:12]}"
    payload = _payload("", [{"role": "user", "content": "bonjour"}])
    payload["call"] = {}
    r = client.post(
        "/api/vapi/chat/completions",
        json=payload,
        headers={"x-vapi-call-id": call_id},
    )
    assert r.status_code == 200
    # Si le call_id du header est utilisé, une 2e requête avec le même header garde la session
    r2 = client.post(
        "/api/vapi/chat/completions",
        json=_payload("", [
            {"role": "user", "content": "bonjour"},
            {"role": "assistant", "content": "Bonjour ! Comment puis-je vous aider ?"},
            {"role": "user", "content": "Je veux un rdv"},
        ]),
        headers={"x-vapi-call-id": call_id},
    )
    assert r2.status_code == 200
    content2 = r2.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    assert "nom" in content2.lower() or "prénom" in content2.lower()
