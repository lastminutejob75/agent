"""
Fournisseurs LLM partagés (OpenAI / Anthropic) pour extraction et assist.

Sélection via LLM_PREF_PROVIDER ou LLM_ASSIST_PROVIDER : openai | anthropic | auto
(auto = OpenAI si OPENAI_API_KEY, sinon Anthropic si ANTHROPIC_API_KEY).
"""

from __future__ import annotations

import logging
import os
from typing import Optional, Protocol

logger = logging.getLogger(__name__)

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"


class ChatLLMClient(Protocol):
    """Complétion chat system + user → texte brut."""

    provider: str

    def complete(self, system: str, user: str, timeout_ms: int) -> str:
        ...


class OpenAIChatClient:
    provider = "openai"

    def __init__(self, api_key: str, model: str = DEFAULT_OPENAI_MODEL):
        self._api_key = api_key
        self._model = model

    def complete(self, system: str, user: str, timeout_ms: int) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=self._api_key, timeout=max(timeout_ms / 1000.0, 1.0))
        resp = client.chat.completions.create(
            model=self._model,
            max_tokens=512,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content if resp.choices else ""
        return (content or "").strip().replace("\n", " ").replace("\r", " ")


class AnthropicChatClient:
    provider = "anthropic"

    def __init__(self, api_key: str, model: str = DEFAULT_ANTHROPIC_MODEL):
        self._api_key = api_key
        self._model = model

    def complete(self, system: str, user: str, timeout_ms: int) -> str:
        from anthropic import Anthropic

        client = Anthropic(api_key=self._api_key)
        timeout_sec = max(timeout_ms / 1000.0, 1.0)
        msg = client.messages.create(
            model=self._model,
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": user}],
            timeout=timeout_sec,
        )
        out = ""
        for block in getattr(msg, "content", []):
            if getattr(block, "type", None) == "text":
                out += getattr(block, "text", "") or ""
        return (out.strip() or "").replace("\n", " ").replace("\r", " ")


def resolve_llm_provider(env_key: str = "LLM_PREF_PROVIDER") -> Optional[str]:
    """
    Retourne openai | anthropic | None.
    auto : OpenAI en priorité si OPENAI_API_KEY, sinon Anthropic.
    """
    raw = (os.getenv(env_key) or "auto").strip().lower()
    if raw == "openai":
        return "openai" if (os.getenv("OPENAI_API_KEY") or "").strip() else None
    if raw == "anthropic":
        return "anthropic" if (os.getenv("ANTHROPIC_API_KEY") or "").strip() else None
    if raw == "auto":
        if (os.getenv("OPENAI_API_KEY") or "").strip():
            return "openai"
        if (os.getenv("ANTHROPIC_API_KEY") or "").strip():
            return "anthropic"
    return None


def default_model_for_provider(provider: str, purpose: str = "pref") -> str:
    if purpose == "assist":
        if provider == "openai":
            return (os.getenv("LLM_ASSIST_MODEL") or DEFAULT_OPENAI_MODEL).strip()
        return (os.getenv("LLM_ASSIST_MODEL") or "claude-sonnet-4-20250514").strip()
    if provider == "openai":
        return (os.getenv("LLM_PREF_MODEL") or DEFAULT_OPENAI_MODEL).strip()
    return (os.getenv("LLM_PREF_MODEL") or DEFAULT_ANTHROPIC_MODEL).strip()


def create_chat_client(
    provider: Optional[str] = None,
    *,
    purpose: str = "pref",
    provider_env_key: str = "LLM_PREF_PROVIDER",
) -> Optional[ChatLLMClient]:
    """Instancie le client LLM selon le fournisseur résolu."""
    provider = provider or resolve_llm_provider(provider_env_key)
    if not provider:
        return None
    model = default_model_for_provider(provider, purpose=purpose)
    try:
        if provider == "openai":
            key = (os.getenv("OPENAI_API_KEY") or "").strip()
            if not key:
                return None
            return OpenAIChatClient(api_key=key, model=model)
        key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
        if not key:
            return None
        return AnthropicChatClient(api_key=key, model=model)
    except Exception as e:
        logger.warning("create_chat_client failed provider=%s: %s", provider, e)
        return None


def get_llm_pref_status() -> dict:
    """Statut pour health / debug (sans exposer les clés)."""
    enabled = (os.getenv("LLM_PREF_EXTRACT_ENABLED") or "true").lower() in ("true", "1", "yes")
    provider = resolve_llm_provider("LLM_PREF_PROVIDER")
    openai_set = bool((os.getenv("OPENAI_API_KEY") or "").strip())
    anthropic_set = bool((os.getenv("ANTHROPIC_API_KEY") or "").strip())
    model = default_model_for_provider(provider, purpose="pref") if provider else None
    ready = enabled and provider is not None and (
        (provider == "openai" and openai_set) or (provider == "anthropic" and anthropic_set)
    )
    return {
        "enabled": enabled,
        "provider": provider,
        "provider_config": (os.getenv("LLM_PREF_PROVIDER") or "auto").strip(),
        "model": model,
        "openai_api_key_set": openai_set,
        "anthropic_api_key_set": anthropic_set,
        "ready": ready,
    }
