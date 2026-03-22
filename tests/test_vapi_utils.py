import pytest

from backend.vapi_utils import _build_function_tool_messages, get_public_backend_base_url


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
    assert messages[0]["content"] == "Un instant."
    assert messages[0]["blocking"] is True
    assert messages[1]["content"] == "Encore une seconde."
