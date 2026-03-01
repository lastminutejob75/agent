"""
Tests push usage Stripe : UsageRecord (legacy) vs MeterEvent (STRIPE_USE_METER_EVENTS).
- STRIPE_USE_METER_EVENTS=false => UsageRecord.create appelé.
- STRIPE_USE_METER_EVENTS=true => billing.MeterEvent.create appelé ; fallback UsageRecord si échec.
"""
from __future__ import annotations

import sys
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from backend import stripe_usage


@pytest.fixture
def mock_pg_and_billing():
    """Billing avec subscription + metered_item + customer pour push usage."""
    with patch("backend.stripe_usage._pg_url", return_value="postgresql://test"):
        with patch("backend.stripe_usage._pg_events_url", return_value="postgresql://test"):
            with patch("backend.stripe_usage.try_acquire_usage_push", return_value=True):
                with patch("backend.stripe_usage.mark_usage_push_sent"):
                    with patch("backend.stripe_usage.mark_usage_push_failed"):
                        yield


def test_push_daily_usage_uses_usage_record_when_meter_events_disabled(mock_pg_and_billing):
    """STRIPE_USE_METER_EVENTS=false => UsageRecord.create est appelé (legacy)."""
    from backend.stripe_usage import push_daily_usage_to_stripe

    mock_usage = MagicMock(return_value=MagicMock(id="ur_xxx"))
    mock_stripe = MagicMock(UsageRecord=MagicMock(create=mock_usage))

    with patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test_fake"}, clear=False):
        with patch.object(stripe_usage, "_stripe_use_meter_events", return_value=False):
            with patch("backend.stripe_usage._aggregate_usage_by_tenant_for_day", return_value=[(1, 30)]):
                with patch("backend.billing_pg.get_tenant_billing") as mock_billing:
                    mock_billing.return_value = {
                        "stripe_subscription_id": "sub_xxx",
                        "stripe_customer_id": "cus_xxx",
                        "stripe_metered_item_id": "si_xxx",
                    }
                    with patch.dict(sys.modules, {"stripe": mock_stripe}):
                        result = push_daily_usage_to_stripe(date(2025, 2, 1))
                    assert result.get("pushed") == 1
                    assert result.get("skipped") == 0
                    mock_usage.assert_called_once()
                    call_kw = mock_usage.call_args[1]
                    assert call_kw["subscription_item"] == "si_xxx"
                    assert call_kw["quantity"] == 30


def test_push_daily_usage_uses_meter_event_when_meter_events_enabled(mock_pg_and_billing):
    """STRIPE_USE_METER_EVENTS=true => push_usage_via_meter_events est appelé (meter events)."""
    from backend.stripe_usage import push_daily_usage_to_stripe

    with patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test_fake", "STRIPE_USE_METER_EVENTS": "true"}, clear=False):
        with patch.object(stripe_usage, "_stripe_use_meter_events", return_value=True):
            with patch("backend.stripe_usage._aggregate_usage_by_tenant_for_day", return_value=[(1, 25)]):
                with patch("backend.billing_pg.get_tenant_billing") as mock_billing:
                    mock_billing.return_value = {
                        "stripe_subscription_id": "sub_yyy",
                        "stripe_customer_id": "cus_yyy",
                        "stripe_metered_item_id": "si_yyy",
                    }
                    with patch("backend.stripe_usage.push_usage_via_meter_events", return_value=True) as mock_meter:
                        result = push_daily_usage_to_stripe(date(2025, 2, 2))
                    assert result.get("pushed") == 1
                    mock_meter.assert_called_once()
                    assert mock_meter.call_args[0][0] == 1
                    assert mock_meter.call_args[0][1] == 25
                    assert mock_meter.call_args[1].get("stripe_customer_id") == "cus_yyy"


def test_push_usage_via_meter_events_success():
    """push_usage_via_meter_events appelle stripe.billing.MeterEvent.create avec event_name et payload."""
    with patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test", "STRIPE_METER_EVENT_NAME": "uwi.minutes"}, clear=False):
        mock_create = MagicMock()
        mock_meter_event = MagicMock(create=mock_create)
        mock_billing = MagicMock(MeterEvent=mock_meter_event)
        mock_stripe = MagicMock(billing=mock_billing)
        with patch.dict(sys.modules, {"stripe": mock_stripe}):
            ok = stripe_usage.push_usage_via_meter_events(1, 42, date(2025, 2, 1), stripe_customer_id="cus_abc")
        assert ok is True
        mock_create.assert_called_once()
        call_kw = mock_create.call_args[1]
        assert call_kw["event_name"] == "uwi.minutes"
        assert call_kw["payload"] == {"stripe_customer_id": "cus_abc", "value": 42}
        assert "identifier" in call_kw
        assert "uwi_1_2025-02-01" in call_kw["identifier"]


def test_push_usage_via_meter_events_failure_returns_false():
    """push_usage_via_meter_events retourne False et log si Stripe lève."""
    with patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test"}, clear=False):
        mock_create = MagicMock(side_effect=Exception("Stripe error"))
        mock_meter_event = MagicMock(create=mock_create)
        mock_billing = MagicMock(MeterEvent=mock_meter_event)
        mock_stripe = MagicMock(billing=mock_billing)
        with patch.dict(sys.modules, {"stripe": mock_stripe}):
            ok = stripe_usage.push_usage_via_meter_events(2, 10, date(2025, 2, 1), stripe_customer_id="cus_xyz")
        assert ok is False
