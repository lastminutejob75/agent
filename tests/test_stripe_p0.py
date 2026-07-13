from types import SimpleNamespace
from unittest.mock import MagicMock

from backend import reports, stripe_usage
from backend.routes import stripe_webhook


def test_invoice_paid_resyncs_active_subscription_and_clears_past_due(monkeypatch):
    invoice = SimpleNamespace(customer="cus_paid", subscription="sub_paid")
    subscription = SimpleNamespace(status="active")

    monkeypatch.setattr(stripe_webhook, "tenant_id_by_stripe_customer_id", lambda _cid: 42)
    retrieve = MagicMock(return_value=subscription)
    sync = MagicMock(return_value=True)
    unsuspend = MagicMock(return_value=True)
    monkeypatch.setattr(stripe_webhook, "_retrieve_subscription_with_items", retrieve)
    monkeypatch.setattr(stripe_webhook, "_sync_subscription", sync)
    monkeypatch.setattr(
        stripe_webhook,
        "get_tenant_suspension",
        lambda _tenant_id: (True, "past_due", "hard"),
    )
    monkeypatch.setattr(stripe_webhook, "set_tenant_unsuspended", unsuspend)

    assert stripe_webhook._handle_invoice_paid(invoice) is True
    retrieve.assert_called_once_with("sub_paid")
    sync.assert_called_once_with(subscription)
    unsuspend.assert_called_once_with(42)


def test_invoice_paid_does_not_clear_manual_suspension(monkeypatch):
    invoice = SimpleNamespace(customer="cus_paid", subscription="sub_paid")
    subscription = SimpleNamespace(status="active")

    monkeypatch.setattr(stripe_webhook, "tenant_id_by_stripe_customer_id", lambda _cid: 42)
    monkeypatch.setattr(
        stripe_webhook,
        "_retrieve_subscription_with_items",
        lambda _sub_id: subscription,
    )
    monkeypatch.setattr(stripe_webhook, "_sync_subscription", lambda _subscription: True)
    monkeypatch.setattr(
        stripe_webhook,
        "get_tenant_suspension",
        lambda _tenant_id: (True, "manual", "hard"),
    )
    unsuspend = MagicMock()
    monkeypatch.setattr(stripe_webhook, "set_tenant_unsuspended", unsuspend)

    assert stripe_webhook._handle_invoice_paid(invoice) is True
    unsuspend.assert_not_called()


def test_invoice_subscription_id_supports_recent_parent_shape():
    invoice = {
        "parent": {
            "subscription_details": {
                "subscription": {"id": "sub_parent"},
            }
        }
    }

    assert stripe_webhook._invoice_subscription_id(invoice) == "sub_parent"


def test_usage_mode_defaults_to_meter_events_when_usage_record_is_unavailable(monkeypatch):
    monkeypatch.delenv("STRIPE_USE_METER_EVENTS", raising=False)
    modern_stripe = SimpleNamespace(billing=SimpleNamespace(MeterEvent=object()))
    monkeypatch.setitem(__import__("sys").modules, "stripe", modern_stripe)

    assert stripe_usage._stripe_use_meter_events() is True


def test_scheduler_registers_one_safe_daily_usage_job(monkeypatch):
    class FakeScheduler:
        def __init__(self):
            self.running = False
            self.added_jobs = []

        def scheduled_job(self, _trigger, **_kwargs):
            return lambda func: func

        def add_job(self, func, trigger, **kwargs):
            self.added_jobs.append((func, trigger, kwargs))

        def start(self):
            self.running = True

    scheduler = FakeScheduler()
    monkeypatch.setattr(
        "apscheduler.schedulers.background.BackgroundScheduler",
        lambda: scheduler,
    )
    monkeypatch.setattr(reports, "ReportGenerator", MagicMock)
    monkeypatch.setattr(reports, "_scheduler_instance", None)
    monkeypatch.setenv("STRIPE_USAGE_PUSH_ENABLED", "true")
    monkeypatch.setenv("STRIPE_USAGE_PUSH_HOUR_UTC", "99")
    monkeypatch.setenv("STRIPE_USAGE_PUSH_MINUTE_UTC", "7")
    monkeypatch.setenv("PUBLIC_SLOTS_PREWARM_ENABLED", "false")

    first = reports.setup_scheduler()
    second = reports.setup_scheduler()

    assert first is scheduler
    assert second is scheduler
    assert len(scheduler.added_jobs) == 1
    _func, trigger, options = scheduler.added_jobs[0]
    assert options == {
        "id": "stripe_daily_usage_push",
        "replace_existing": True,
        "max_instances": 1,
        "coalesce": True,
    }
    assert str(trigger.timezone) == "UTC"
    assert str(trigger.fields[5]) == "1"
    assert str(trigger.fields[6]) == "7"
