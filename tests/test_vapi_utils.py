import pytest

from backend import prompts
from backend.vapi_utils import (
    _build_function_tool_messages,
    get_public_backend_base_url,
    patch_vapi_function_tool,
)


def test_get_public_backend_base_url_prefers_explicit_vapi_backend(monkeypatch):
    monkeypatch.setenv("VAPI_PUBLIC_BACKEND_URL", "https://api.uwiapp.com")
    monkeypatch.setenv("APP_BASE_URL", "https://uwiapp.com")

    assert get_public_backend_base_url() == "https://api.uwiapp.com"


def test_get_public_backend_base_url_rejects_front_app_base_url(monkeypatch):
    monkeypatch.delenv("VAPI_PUBLIC_BACKEND_URL", raising=False)
    monkeypatch.delenv("PUBLIC_API_BASE_URL", raising=False)
    monkeypatch.delenv("API_BASE_URL", raising=False)
    monkeypatch.setenv("APP_BASE_URL", "https://uwiapp.com")

    with pytest.raises(ValueError):
        get_public_backend_base_url()


def test_get_public_backend_base_url_accepts_railway_fallback(monkeypatch):
    monkeypatch.delenv("VAPI_PUBLIC_BACKEND_URL", raising=False)
    monkeypatch.delenv("PUBLIC_API_BASE_URL", raising=False)
    monkeypatch.delenv("API_BASE_URL", raising=False)
    monkeypatch.setenv("APP_BASE_URL", "https://agent-production-c246.up.railway.app")

    assert get_public_backend_base_url() == "https://agent-production-c246.up.railway.app"


def test_build_function_tool_messages_uses_short_generic_holding():
    messages = _build_function_tool_messages()
    assert messages[0]["type"] == "request-start"
    assert messages[0]["content"] == prompts.get_invariant_vocal_phrase("tool_hold_start")
    assert messages[0]["blocking"] is True
    assert messages[1]["content"] == prompts.get_invariant_vocal_phrase("tool_hold_delay")
    assert messages[2]["content"] == prompts.get_invariant_vocal_phrase("agenda_unavailable")


def test_invariant_vocal_phrase_unknown_key_raises():
    with pytest.raises(KeyError):
        prompts.get_invariant_vocal_phrase("unknown_key")


@pytest.mark.asyncio
async def test_patch_vapi_function_tool_falls_back_to_discovery(monkeypatch):
    monkeypatch.setenv("VAPI_API_KEY", "test-key")
    monkeypatch.delenv("VAPI_FUNCTION_TOOL_ID", raising=False)
    monkeypatch.setenv("VAPI_PUBLIC_BACKEND_URL", "https://agent-production-c246.up.railway.app")

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.patch_payload = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None, timeout=None):
            class Resp:
                def __init__(self, data):
                    self._data = data

                def raise_for_status(self):
                    return None

                def json(self):
                    return self._data

            if url.endswith("/tool"):
                return Resp(
                    [
                        {"id": "tool_other", "type": "function", "function": {"name": "other"}},
                        {"id": "tool_123", "type": "function", "function": {"name": "function_tool"}},
                    ]
                )
            if url.endswith("/tool/tool_123"):
                return Resp(
                    {
                        "id": "tool_123",
                        "server": {"url": "https://old.example/api/vapi/tool", "timeoutSeconds": 25},
                        "messages": [],
                        "async": True,
                    }
                )
            raise AssertionError(f"Unexpected GET URL: {url}")

        async def patch(self, url, json=None, headers=None, timeout=None):
            class Resp:
                def __init__(self, data):
                    self._data = data

                def raise_for_status(self):
                    return None

                def json(self):
                    return self._data

            assert url.endswith("/tool/tool_123")
            self.patch_payload = json
            return Resp({"id": "tool_123", **(json or {})})

    fake_client = FakeClient()
    monkeypatch.setattr("backend.vapi_utils.httpx.AsyncClient", lambda *a, **k: fake_client)

    result = await patch_vapi_function_tool()

    assert result["after"]["server"]["url"] == "https://agent-production-c246.up.railway.app/api/vapi/tool"
    assert result["after"]["server"]["timeoutSeconds"] == 25
    assert result["after"]["async"] is False
