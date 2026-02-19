"""
Anti-régression : quand un tenant est suspendu, l'engine (LLM/tools) n'est jamais appelé.
Vocal : _compute_voice_response_sync return immédiat avec phrase fixe.
Web : run_engine return immédiat après push_event(final), pas d'appel engine.handle_message.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from backend.routes.voice import _compute_voice_response_sync
from backend.main import run_engine
from backend import prompts


# ---------- Vocal : _compute_voice_response_sync ----------


@patch("backend.routes.voice._get_engine")
@patch("backend.billing_pg.get_tenant_suspension")
def test_voice_suspended_hard_returns_fixed_message_and_engine_never_called(
    mock_get_suspension,
    mock_get_engine,
):
    """Tenant suspendu (hard) → retour message fixe, engine.handle_message jamais appelé."""
    mock_get_suspension.return_value = (True, "past_due", "hard")
    mock_engine = MagicMock()
    mock_get_engine.return_value = mock_engine

    text, cancel = _compute_voice_response_sync(
        resolved_tenant_id=1,
        call_id="test-call-1",
        user_message="Je veux prendre rendez-vous",
        customer_phone=None,
        messages=[{"role": "user", "content": "Je veux prendre rendez-vous"}],
    )

    assert "suspendu" in text.lower() or "temporairement" in text.lower()
    assert cancel is True
    mock_engine.handle_message.assert_not_called()


@patch("backend.routes.voice._get_engine")
@patch("backend.billing_pg.get_tenant_suspension")
def test_voice_suspended_soft_returns_soft_message_and_engine_never_called(
    mock_get_suspension,
    mock_get_engine,
):
    """Tenant suspendu (soft) → retour message soft, engine.handle_message jamais appelé."""
    mock_get_suspension.return_value = (True, "manual", "soft")
    mock_engine = MagicMock()
    mock_get_engine.return_value = mock_engine

    text, cancel = _compute_voice_response_sync(
        resolved_tenant_id=1,
        call_id="test-call-2",
        user_message="Je veux un RDV",
        customer_phone=None,
        messages=[],
    )

    assert "informations pratiques" in text or "rendez-vous" in text.lower()
    assert cancel is True
    mock_engine.handle_message.assert_not_called()


# ---------- Web : run_engine ----------


@pytest.mark.asyncio
@patch("backend.main._get_engine")
@patch("backend.billing_pg.get_tenant_suspension")
@patch("backend.main.push_event", new_callable=AsyncMock)
@patch("backend.main.ENGINE")
async def test_web_suspended_push_final_and_engine_never_called(
    mock_engine_module,
    mock_push_event,
    mock_get_suspension,
    mock_get_engine,
):
    """Tenant suspendu sur canal web → push_event(final) appelé, engine.handle_message jamais appelé."""
    mock_get_suspension.return_value = (True, "manual", "hard")
    mock_engine = MagicMock()
    mock_get_engine.return_value = mock_engine

    mock_session = MagicMock()
    mock_session.tenant_id = 1
    mock_session.channel = "web"
    mock_engine_module.session_store.get_or_create.return_value = mock_session

    await run_engine("web-conv-1", "Bonjour je voudrais un RDV", "web")

    mock_get_suspension.assert_called_once_with(1)
    push_calls = [c[0][1] for c in mock_push_event.call_args_list if isinstance(c[0][1], dict)]
    assert any(
        c.get("type") == "final"
        and ("suspendu" in (c.get("text") or "").lower() or "temporairement" in (c.get("text") or "").lower())
        for c in push_calls
    )
    mock_engine.handle_message.assert_not_called()


@pytest.mark.asyncio
@patch("backend.main._get_engine")
@patch("backend.billing_pg.get_tenant_suspension")
@patch("backend.main.push_event", new_callable=AsyncMock)
@patch("backend.main.ENGINE")
async def test_web_suspended_soft_push_soft_message_and_engine_never_called(
    mock_engine_module,
    mock_push_event,
    mock_get_suspension,
    mock_get_engine,
):
    """Tenant suspendu (soft) sur web → message soft, engine jamais appelé."""
    mock_get_suspension.return_value = (True, "manual", "soft")
    mock_engine = MagicMock()
    mock_get_engine.return_value = mock_engine

    mock_session = MagicMock()
    mock_session.tenant_id = 1
    mock_session.channel = "web"
    mock_engine_module.session_store.get_or_create.return_value = mock_session

    await run_engine("web-conv-2", "hello", "web")

    push_calls = [c[0][1] for c in mock_push_event.call_args_list if isinstance(c[0][1], dict)]
    final_calls = [c for c in push_calls if c.get("type") == "final"]
    assert len(final_calls) == 1
    assert "informations pratiques" in (final_calls[0].get("text") or "")
    mock_engine.handle_message.assert_not_called()
