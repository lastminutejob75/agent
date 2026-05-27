"""Tests pour backend/vapi_security.py — verification signature webhooks Vapi.

Couvre :
- _get_secret / _is_disabled / is_strict_mode
- verify_vapi_signature : tous les modes (shared secret, HMAC, no_secret, missing, disabled)
- Integration avec les endpoints /api/vapi/webhook et /api/vapi/tool
- Mode souple (warning + accept) vs strict (401)
"""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient


# ---------- Helpers ----------


def _hmac_hex(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


@pytest.fixture
def secret(monkeypatch):
    """Configure un secret Vapi connu et reactive la verif (qu'on a desactivee dans conftest)."""
    s = "test-vapi-secret-1234567890"
    monkeypatch.setenv("VAPI_WEBHOOK_SECRET", s)
    monkeypatch.setenv("VAPI_SIGNATURE_DISABLED", "")  # reactive la verif
    return s


# ---------- Tests unitaires verify_vapi_signature ----------


class TestVerifyVapiSignature:
    def test_disabled_returns_ok_without_check(self, monkeypatch):
        monkeypatch.setenv("VAPI_SIGNATURE_DISABLED", "true")
        # Meme sans secret : OK avec reason=disabled
        monkeypatch.setenv("VAPI_WEBHOOK_SECRET", "")
        from backend.vapi_security import verify_vapi_signature, VERIFY_DISABLED
        ok, reason = verify_vapi_signature(b"{}", {})
        assert ok is True
        assert reason == VERIFY_DISABLED

    def test_no_secret_configured_returns_no_secret(self, monkeypatch):
        monkeypatch.setenv("VAPI_SIGNATURE_DISABLED", "")
        monkeypatch.setenv("VAPI_WEBHOOK_SECRET", "")
        from backend.vapi_security import verify_vapi_signature, VERIFY_NO_SECRET
        ok, reason = verify_vapi_signature(b"{}", {"x-vapi-secret": "anything"})
        assert ok is False
        assert reason == VERIFY_NO_SECRET

    def test_shared_secret_valid_returns_ok(self, secret):
        from backend.vapi_security import verify_vapi_signature, VERIFY_OK
        ok, reason = verify_vapi_signature(b"{}", {"x-vapi-secret": secret})
        assert ok is True
        assert reason == VERIFY_OK

    def test_shared_secret_invalid_returns_bad(self, secret):
        from backend.vapi_security import verify_vapi_signature, VERIFY_BAD_SHARED_SECRET
        ok, reason = verify_vapi_signature(b"{}", {"x-vapi-secret": "wrong"})
        assert ok is False
        assert reason == VERIFY_BAD_SHARED_SECRET

    def test_hmac_signature_valid_returns_ok(self, secret):
        from backend.vapi_security import verify_vapi_signature, VERIFY_OK
        body = b'{"hello":"world"}'
        sig = _hmac_hex(body, secret)
        ok, reason = verify_vapi_signature(body, {"x-vapi-signature": sig})
        assert ok is True
        assert reason == VERIFY_OK

    def test_hmac_signature_with_sha256_prefix_returns_ok(self, secret):
        """Vapi peut envoyer "sha256=<hex>" (style GitHub)."""
        from backend.vapi_security import verify_vapi_signature, VERIFY_OK
        body = b'{"a":1}'
        sig = "sha256=" + _hmac_hex(body, secret)
        ok, reason = verify_vapi_signature(body, {"x-vapi-signature": sig})
        assert ok is True
        assert reason == VERIFY_OK

    def test_hmac_signature_invalid_returns_bad(self, secret):
        from backend.vapi_security import verify_vapi_signature, VERIFY_BAD_HMAC
        ok, reason = verify_vapi_signature(b'{"a":1}', {"x-vapi-signature": "deadbeef"})
        assert ok is False
        assert reason == VERIFY_BAD_HMAC

    def test_hmac_signature_for_different_body_fails(self, secret):
        """Une signature valide pour un body A ne doit pas valider un body B."""
        from backend.vapi_security import verify_vapi_signature, VERIFY_BAD_HMAC
        sig_a = _hmac_hex(b'{"a":1}', secret)
        ok, reason = verify_vapi_signature(b'{"a":2}', {"x-vapi-signature": sig_a})
        assert ok is False
        assert reason == VERIFY_BAD_HMAC

    def test_no_header_returns_missing(self, secret):
        from backend.vapi_security import verify_vapi_signature, VERIFY_MISSING_HEADER
        ok, reason = verify_vapi_signature(b"{}", {})
        assert ok is False
        assert reason == VERIFY_MISSING_HEADER

    def test_shared_secret_takes_precedence_over_hmac_when_present(self, secret):
        """Si X-Vapi-Secret present : on l'utilise, on n'essaie pas HMAC en fallback."""
        from backend.vapi_security import verify_vapi_signature, VERIFY_BAD_SHARED_SECRET
        body = b'{"a":1}'
        valid_hmac = _hmac_hex(body, secret)
        ok, reason = verify_vapi_signature(
            body,
            {"x-vapi-secret": "wrong", "x-vapi-signature": valid_hmac},
        )
        assert ok is False
        assert reason == VERIFY_BAD_SHARED_SECRET

    def test_header_lookup_is_case_insensitive(self, secret):
        from backend.vapi_security import verify_vapi_signature, VERIFY_OK
        ok, reason = verify_vapi_signature(b"{}", {"X-Vapi-Secret": secret})
        assert ok is True

    def test_empty_body_with_valid_hmac_works(self, secret):
        from backend.vapi_security import verify_vapi_signature, VERIFY_OK
        sig = _hmac_hex(b"", secret)
        ok, reason = verify_vapi_signature(b"", {"x-vapi-signature": sig})
        assert ok is True


# ---------- Tests is_strict_mode ----------


class TestIsStrictMode:
    @pytest.mark.parametrize("val,expected", [
        ("true", True), ("True", True), ("TRUE", True),
        ("1", True), ("yes", True), ("on", True),
        ("false", False), ("0", False), ("", False),
        (" ", False), ("no", False),
    ])
    def test_strict_mode_parsing(self, monkeypatch, val, expected):
        monkeypatch.setenv("VAPI_REQUIRE_SIGNATURE", val)
        from backend.vapi_security import is_strict_mode
        assert is_strict_mode() is expected


# ---------- Tests integration avec /api/vapi/webhook ----------


class TestVapiWebhookSignatureIntegration:
    @pytest.fixture
    def client(self):
        from backend.main import app
        return TestClient(app)

    def test_webhook_without_signature_in_loose_mode_accepts(self, client, secret, monkeypatch):
        """Mode souple (defaut) : pas de signature → warning + accept."""
        monkeypatch.setenv("VAPI_REQUIRE_SIGNATURE", "")
        body = {"message": {"type": "status-update", "status": "ended"}}
        r = client.post("/api/vapi/webhook", json=body)
        # Mode souple : accepte (200), meme sans signature
        assert r.status_code == 200

    def test_webhook_without_signature_in_strict_mode_rejects(self, client, secret, monkeypatch):
        """Mode strict : pas de signature → 401."""
        monkeypatch.setenv("VAPI_REQUIRE_SIGNATURE", "true")
        body = {"message": {"type": "status-update", "status": "ended"}}
        r = client.post("/api/vapi/webhook", json=body)
        assert r.status_code == 401
        assert "signature" in r.json().get("detail", "").lower()

    def test_webhook_with_valid_shared_secret_in_strict_mode_accepts(
        self, client, secret, monkeypatch
    ):
        monkeypatch.setenv("VAPI_REQUIRE_SIGNATURE", "true")
        body = {"message": {"type": "status-update", "status": "ended"}}
        r = client.post(
            "/api/vapi/webhook",
            json=body,
            headers={"X-Vapi-Secret": secret},
        )
        assert r.status_code == 200

    def test_webhook_with_valid_hmac_in_strict_mode_accepts(self, client, secret, monkeypatch):
        monkeypatch.setenv("VAPI_REQUIRE_SIGNATURE", "true")
        body_dict = {"message": {"type": "status-update", "status": "ended"}}
        raw_body = json.dumps(body_dict).encode("utf-8")
        sig = _hmac_hex(raw_body, secret)
        r = client.post(
            "/api/vapi/webhook",
            content=raw_body,
            headers={
                "X-Vapi-Signature": sig,
                "Content-Type": "application/json",
            },
        )
        assert r.status_code == 200

    def test_webhook_with_invalid_signature_in_strict_mode_rejects(
        self, client, secret, monkeypatch
    ):
        monkeypatch.setenv("VAPI_REQUIRE_SIGNATURE", "true")
        body = {"message": {"type": "status-update", "status": "ended"}}
        r = client.post(
            "/api/vapi/webhook",
            json=body,
            headers={"X-Vapi-Signature": "deadbeef"},
        )
        assert r.status_code == 401

    def test_webhook_with_signature_disabled_flag_accepts_anything(self, client, monkeypatch):
        """`VAPI_SIGNATURE_DISABLED=true` : skip total, meme en strict."""
        monkeypatch.setenv("VAPI_SIGNATURE_DISABLED", "true")
        monkeypatch.setenv("VAPI_REQUIRE_SIGNATURE", "true")
        body = {"message": {"type": "status-update", "status": "ended"}}
        r = client.post("/api/vapi/webhook", json=body)
        assert r.status_code == 200


# ---------- Tests integration avec /api/vapi/tool ----------


class TestVapiToolSignatureIntegration:
    @pytest.fixture
    def client(self):
        from backend.main import app
        return TestClient(app)

    def test_tool_without_signature_in_strict_mode_rejects(self, client, secret, monkeypatch):
        monkeypatch.setenv("VAPI_REQUIRE_SIGNATURE", "true")
        body = {
            "message": {
                "type": "tool-calls",
                "toolCallList": [{
                    "id": "tc1",
                    "function": {"name": "faq", "arguments": {}},
                }],
            },
        }
        r = client.post("/api/vapi/tool", json=body)
        assert r.status_code == 401

    def test_tool_with_valid_hmac_in_strict_mode_accepts(self, client, secret, monkeypatch):
        monkeypatch.setenv("VAPI_REQUIRE_SIGNATURE", "true")
        body_dict = {
            "message": {
                "type": "tool-calls",
                "toolCallList": [{
                    "id": "tc1",
                    "function": {"name": "faq", "arguments": {}},
                }],
            },
        }
        raw_body = json.dumps(body_dict).encode("utf-8")
        sig = _hmac_hex(raw_body, secret)
        r = client.post(
            "/api/vapi/tool",
            content=raw_body,
            headers={
                "X-Vapi-Signature": sig,
                "Content-Type": "application/json",
            },
        )
        # On ne valide pas la logique metier, juste que la requete passe la signature
        assert r.status_code != 401

    def test_tool_loose_mode_accepts_unsigned(self, client, secret, monkeypatch):
        monkeypatch.setenv("VAPI_REQUIRE_SIGNATURE", "")
        body = {
            "message": {
                "type": "tool-calls",
                "toolCallList": [{
                    "id": "tc1",
                    "function": {"name": "faq", "arguments": {}},
                }],
            },
        }
        r = client.post("/api/vapi/tool", json=body)
        assert r.status_code != 401


# ---------- Test helper make_test_signature ----------


class TestMakeTestSignature:
    def test_helper_uses_env_secret_by_default(self, secret):
        from backend.vapi_security import make_test_signature, verify_vapi_signature, VERIFY_OK
        body = b'{"x":42}'
        sig = make_test_signature(body)
        ok, reason = verify_vapi_signature(body, {"x-vapi-signature": sig})
        assert ok is True
        assert reason == VERIFY_OK

    def test_helper_raises_when_no_secret(self, monkeypatch):
        monkeypatch.setenv("VAPI_WEBHOOK_SECRET", "")
        from backend.vapi_security import make_test_signature
        with pytest.raises(ValueError, match="secret"):
            make_test_signature(b"{}")

    def test_helper_accepts_explicit_secret(self):
        from backend.vapi_security import make_test_signature
        sig = make_test_signature(b"hello", secret="mysecret")
        expected = hmac.new(b"mysecret", b"hello", hashlib.sha256).hexdigest()
        assert sig == expected
