# tests/test_llm_provider.py
import pytest

from backend.llm_provider import (
    resolve_llm_provider,
    default_model_for_provider,
    get_llm_pref_status,
    create_chat_client,
)


class TestResolveProvider:
    def test_auto_prefers_openai(self, monkeypatch):
        monkeypatch.setenv("LLM_PREF_PROVIDER", "auto")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert resolve_llm_provider("LLM_PREF_PROVIDER") == "openai"

    def test_auto_fallback_anthropic(self, monkeypatch):
        monkeypatch.setenv("LLM_PREF_PROVIDER", "auto")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        assert resolve_llm_provider("LLM_PREF_PROVIDER") == "anthropic"

    def test_explicit_openai(self, monkeypatch):
        monkeypatch.setenv("LLM_PREF_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        assert resolve_llm_provider("LLM_PREF_PROVIDER") == "openai"

    def test_openai_default_model(self, monkeypatch):
        monkeypatch.delenv("LLM_PREF_MODEL", raising=False)
        assert default_model_for_provider("openai") == "gpt-4o-mini"


class TestPrefStatus:
    def test_ready_with_openai(self, monkeypatch):
        monkeypatch.setenv("LLM_PREF_EXTRACT_ENABLED", "true")
        monkeypatch.setenv("LLM_PREF_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        st = get_llm_pref_status()
        assert st["ready"] is True
        assert st["provider"] == "openai"
