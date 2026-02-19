"""
Tests monétisation : blocage quota (100 %), included=0 ne bloque pas, idempotence push Stripe.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.routes.voice import _compute_voice_response_sync
from backend import prompts


# ---------- Quota block : included=100, used=100 → suspension hard + pas d'engine ----------


@patch("backend.routes.voice._get_engine")
@patch("backend.billing_pg.set_tenant_suspended")
@patch("backend.billing_pg.get_quota_snapshot_month")
@patch("backend.billing_pg.get_tenant_suspension")
def test_quota_block_included_100_used_100_suspension_hard_no_engine(
    mock_get_suspension,
    mock_get_quota_snapshot,
    mock_set_suspended,
    mock_get_engine,
):
    """included=100, used=100 → set_tenant_suspended(quota_exceeded, hard) + message suspendu, engine non appelé."""
    mock_get_suspension.return_value = (False, None, "hard")
    mock_get_quota_snapshot.return_value = (100, 100.0)
    mock_engine = MagicMock()
    mock_get_engine.return_value = mock_engine

    text, cancel = _compute_voice_response_sync(
        resolved_tenant_id=42,
        call_id="quota-block-call",
        user_message="Je veux un RDV",
        customer_phone=None,
        messages=[{"role": "user", "content": "Je veux un RDV"}],
    )

    mock_set_suspended.assert_called_once_with(42, reason="quota_exceeded", mode="hard")
    assert "suspendu" in text.lower() or "temporairement" in text.lower()
    assert cancel is True
    mock_engine.handle_message.assert_not_called()


# ---------- included=0 → ne pas bloquer ----------


@patch("backend.routes.voice._get_engine")
@patch("backend.billing_pg.set_tenant_suspended")
@patch("backend.billing_pg.get_quota_snapshot_month")
@patch("backend.billing_pg.get_tenant_suspension")
def test_quota_included_0_does_not_block(
    mock_get_suspension,
    mock_get_quota_snapshot,
    mock_set_suspended,
    mock_get_engine,
):
    """included=0 (quota non configuré) → pas de suspension, engine appelé."""
    mock_get_suspension.return_value = (False, None, "hard")
    mock_get_quota_snapshot.return_value = (0, 50.0)
    mock_engine = MagicMock()
    mock_engine.handle_message.return_value = [MagicMock(text="Quel est votre nom ?")]
    mock_get_engine.return_value = mock_engine

    text, cancel = _compute_voice_response_sync(
        resolved_tenant_id=43,
        call_id="quota-no-block-call",
        user_message="Je veux un rendez-vous",
        customer_phone=None,
        messages=[{"role": "user", "content": "Je veux un rendez-vous"}],
    )

    mock_set_suspended.assert_not_called()
    assert cancel is False
    mock_engine.handle_message.assert_called_once()
    assert "nom" in text.lower() or "prénom" in text.lower() or "Quel" in text


# ---------- Déjà suspendu → quota check ne s'exécute pas, set_tenant_suspended pas rappelé ----------


@patch("backend.routes.voice._get_engine")
@patch("backend.billing_pg.set_tenant_suspended")
@patch("backend.billing_pg.get_quota_snapshot_month")
@patch("backend.billing_pg.get_tenant_suspension")
def test_already_suspended_quota_check_never_called_no_resuspend(
    mock_get_suspension,
    mock_get_quota_snapshot,
    mock_set_suspended,
    mock_get_engine,
):
    """Si déjà suspendu (ex. quota_exceeded), on retourne avant le quota check → set_tenant_suspended pas rappelé."""
    mock_get_suspension.return_value = (True, "quota_exceeded", "hard")
    mock_engine = MagicMock()
    mock_get_engine.return_value = mock_engine

    text, cancel = _compute_voice_response_sync(
        resolved_tenant_id=44,
        call_id="already-suspended-call",
        user_message="Bonjour",
        customer_phone=None,
        messages=[],
    )

    assert "suspendu" in text.lower() or "temporairement" in text.lower()
    assert cancel is True
    mock_get_quota_snapshot.assert_not_called()
    mock_set_suspended.assert_not_called()
    mock_engine.handle_message.assert_not_called()


# ---------- Push usage idempotent : 2e run même jour → skip, UsageRecord.create une seule fois ----------


@patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test_fake"})
@patch("backend.billing_pg.get_tenant_billing")
@patch("backend.stripe_usage.try_acquire_usage_push")
@patch("backend.stripe_usage._aggregate_usage_by_tenant_for_day")
def test_push_daily_usage_idempotent_second_run_skips_stripe_call(
    mock_aggregate,
    mock_try_acquire,
    mock_get_billing,
):
    """1er run : try_acquire True → Stripe.UsageRecord.create appelé. 2e run : try_acquire False → create pas rappelé."""
    import sys
    from datetime import date
    from unittest.mock import MagicMock

    mock_stripe = MagicMock()
    mock_create = MagicMock()
    mock_stripe.UsageRecord.create = mock_create
    with patch.dict(sys.modules, {"stripe": mock_stripe}):
        from backend.stripe_usage import push_daily_usage_to_stripe

        d = date(2025, 6, 15)
        mock_aggregate.return_value = [(1, 10)]
        mock_get_billing.return_value = {
            "stripe_subscription_id": "sub_1",
            "stripe_metered_item_id": "si_1",
        }
        mock_try_acquire.side_effect = [True, False]

        out1 = push_daily_usage_to_stripe(d)
        out2 = push_daily_usage_to_stripe(d)

        assert out1["pushed"] == 1
        assert out2["pushed"] == 0
        assert mock_create.call_count == 1
