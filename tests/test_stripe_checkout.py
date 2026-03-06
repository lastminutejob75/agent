"""
Tests Stripe Checkout : POST /api/admin/tenants/{id}/stripe-checkout.
- Retourne checkout_url et envoie metadata tenant_id.
- Si customer absent → customer créé et stocké.
- plan_key sans PRICE en env → 400 PRICE_NOT_CONFIGURED.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ADMIN_API_TOKEN", "test-admin-token-pytest")


def _fake_stripe_module(session_url=None, customer_id=None):
    """Fake stripe module (évite import stripe en env de test)."""
    fake = MagicMock()
    fake.Customer.create = MagicMock(return_value=MagicMock(id=customer_id or "cus_new_xxx"))
    fake.checkout.Session.create = MagicMock(
        return_value=MagicMock(url=session_url or "https://checkout.stripe.com/c/pay/cs_xxx")
    )
    return fake


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def admin_headers():
    return {"Authorization": f"Bearer {os.environ.get('ADMIN_API_TOKEN', 'test-admin-token-pytest')}"}


@pytest.fixture
def env_checkout():
    return {
        "STRIPE_SECRET_KEY": "sk_test_fake",
        "STRIPE_CHECKOUT_SUCCESS_URL": "https://app.example.com/success",
        "STRIPE_CHECKOUT_CANCEL_URL": "https://app.example.com/cancel",
        "STRIPE_PRICE_BASE_STARTER": "price_starter_xxx",
        "STRIPE_PRICE_METERED_MINUTES": "price_metered_xxx",
    }


def test_stripe_checkout_returns_url_and_metadata(client, admin_headers, env_checkout):
    """POST stripe-checkout retourne checkout_url et envoie metadata tenant_id (session + subscription_data)."""
    fake = _fake_stripe_module(session_url="https://checkout.stripe.com/c/pay/cs_xxx")
    with patch("backend.config.USE_PG_TENANTS", False):
        with patch("backend.routes.admin._get_tenant_detail", return_value={"name": "Test Tenant", "tenant_id": 1}):
            with patch("backend.routes.admin.get_tenant_billing", return_value={"stripe_customer_id": "cus_xxx", "billing_status": ""}):
                with patch.dict("os.environ", env_checkout, clear=False):
                    with patch.dict("sys.modules", {"stripe": fake}):
                        r = client.post(
                            "/api/admin/tenants/1/stripe-checkout",
                            headers=admin_headers,
                            json={"plan_key": "starter"},
                        )
    assert r.status_code == 200
    data = r.json()
    assert "checkout_url" in data
    assert data["checkout_url"] == "https://checkout.stripe.com/c/pay/cs_xxx"
    call_kw = fake.checkout.Session.create.call_args[1]
    assert call_kw.get("metadata") == {"tenant_id": "1", "plan_key": "starter"}
    assert call_kw.get("subscription_data", {}).get("metadata") == {"tenant_id": "1", "plan_key": "starter"}


def test_stripe_checkout_creates_customer_if_absent(client, admin_headers, env_checkout):
    """Si customer absent → customer créé + stocké puis session créée."""
    fake = _fake_stripe_module(session_url="https://checkout.stripe.com/c/pay/cs_yyy", customer_id="cus_new_xxx")
    mock_set_customer = MagicMock(return_value=True)
    with patch("backend.config.USE_PG_TENANTS", False):
        with patch("backend.routes.admin._get_tenant_detail", return_value={"name": "Test Tenant", "tenant_id": 1}):
            with patch("backend.routes.admin.get_tenant_billing", return_value={}):
                with patch("backend.routes.admin.set_stripe_customer_id", mock_set_customer):
                    with patch.dict("os.environ", env_checkout, clear=False):
                        with patch.dict("sys.modules", {"stripe": fake}):
                            r = client.post(
                                "/api/admin/tenants/1/stripe-checkout",
                                headers=admin_headers,
                                json={"plan_key": "starter"},
                            )
    assert r.status_code == 200
    assert r.json().get("checkout_url") == "https://checkout.stripe.com/c/pay/cs_yyy"
    fake.Customer.create.assert_called_once()
    mock_set_customer.assert_called_once_with(1, "cus_new_xxx")


def test_stripe_checkout_400_price_not_configured(client, admin_headers):
    """plan_key sans STRIPE_PRICE_BASE_* en env → 400 PRICE_NOT_CONFIGURED."""
    env_no_price = {
        "STRIPE_SECRET_KEY": "sk_test_fake",
        "STRIPE_CHECKOUT_SUCCESS_URL": "https://app.example.com/success",
        "STRIPE_CHECKOUT_CANCEL_URL": "https://app.example.com/cancel",
        "STRIPE_PRICE_METERED_MINUTES": "price_metered_xxx",
    }
    with patch("backend.config.USE_PG_TENANTS", False):
        with patch("backend.routes.admin._get_tenant_detail", return_value={"name": "Test", "tenant_id": 1}):
            with patch("backend.routes.admin.get_tenant_billing", return_value={}):
                with patch.dict("os.environ", env_no_price, clear=False):
                    r = client.post(
                        "/api/admin/tenants/1/stripe-checkout",
                        headers=admin_headers,
                        json={"plan_key": "starter"},
                    )
    assert r.status_code == 400
    assert "PRICE_NOT_CONFIGURED" in (r.json().get("detail") or "")


def test_stripe_checkout_400_invalid_plan_key(client, admin_headers, env_checkout):
    """plan_key hors starter/growth/pro → 400."""
    with patch("backend.config.USE_PG_TENANTS", False):
        with patch("backend.routes.admin._get_tenant_detail", return_value={"name": "Test", "tenant_id": 1}):
            with patch("backend.routes.admin.get_tenant_billing", return_value={"billing_status": ""}):
                with patch.dict("os.environ", env_checkout, clear=False):
                    r = client.post(
                        "/api/admin/tenants/1/stripe-checkout",
                        headers=admin_headers,
                        json={"plan_key": "business"},
                    )
    assert r.status_code == 400
    assert "plan_key" in (r.json().get("detail") or "").lower()


def test_stripe_checkout_growth_uses_plan_specific_prices(client, admin_headers):
    """plan_key=growth utilise STRIPE_PRICE_BASE_GROWTH et STRIPE_PRICE_METERED_GROWTH."""
    env_growth = {
        "STRIPE_SECRET_KEY": "sk_test_fake",
        "STRIPE_CHECKOUT_SUCCESS_URL": "https://app.example.com/success",
        "STRIPE_CHECKOUT_CANCEL_URL": "https://app.example.com/cancel",
        "STRIPE_PRICE_BASE_GROWTH": "price_base_growth_xxx",
        "STRIPE_PRICE_METERED_GROWTH": "price_metered_growth_xxx",
    }
    fake = _fake_stripe_module(session_url="https://checkout.stripe.com/c/pay/cs_growth")
    with patch("backend.config.USE_PG_TENANTS", False):
        with patch("backend.routes.admin._get_tenant_detail", return_value={"name": "Test", "tenant_id": 1}):
            with patch("backend.routes.admin.get_tenant_billing", return_value={"stripe_customer_id": "cus_xxx", "billing_status": ""}):
                with patch.dict("os.environ", env_growth, clear=False):
                    with patch.dict("sys.modules", {"stripe": fake}):
                        r = client.post(
                            "/api/admin/tenants/1/stripe-checkout",
                            headers=admin_headers,
                            json={"plan_key": "growth"},
                        )
    assert r.status_code == 200
    call_kw = fake.checkout.Session.create.call_args[1]
    # Base : quantity=1 ; metered : pas de quantity (Stripe rejette quantity sur usage_type=metered)
    assert call_kw["line_items"] == [
        {"price": "price_base_growth_xxx", "quantity": 1},
        {"price": "price_metered_growth_xxx"},
    ]
    assert call_kw.get("metadata", {}).get("plan_key") == "growth"


def test_send_payment_link_setup_mode_existing_subscription(client, admin_headers):
    """Si la subscription existe déjà → send-payment-link crée un Checkout en mode setup et envoie l'email."""
    fake = _fake_stripe_module(session_url="https://checkout.stripe.com/c/pay/setup_xxx", customer_id="cus_existing")
    mock_send_email = MagicMock(return_value=(True, None))
    billing = {
        "stripe_customer_id": "cus_existing",
        "stripe_subscription_id": "sub_existing",
        "billing_status": "trialing",
        "plan_key": "starter",
        "trial_ends_at": "2026-04-05T10:00:00+00:00",
    }
    tenant = {"tenant_id": 1, "name": "Cabinet Test", "params": {"contact_email": "owner@test.fr", "phone_number": "+33600000001"}}
    env_payment = {
        "STRIPE_SECRET_KEY": "sk_test_fake",
        "CLIENT_APP_ORIGIN": "https://app.example.com",
    }
    with patch("backend.config.USE_PG_TENANTS", False):
        with patch("backend.routes.admin._get_tenant_detail", return_value=tenant):
            with patch("backend.routes.admin.get_tenant_billing", return_value=billing):
                with patch("backend.services.email_service.send_payment_link_email", mock_send_email):
                    with patch.dict("os.environ", env_payment, clear=False):
                        with patch.dict("sys.modules", {"stripe": fake}):
                            r = client.post("/api/admin/tenants/1/send-payment-link", headers=admin_headers)
    assert r.status_code == 200
    assert r.json().get("checkout_url") == "https://checkout.stripe.com/c/pay/setup_xxx"
    call_kw = fake.checkout.Session.create.call_args[1]
    assert call_kw["mode"] == "setup"
    assert call_kw["customer"] == "cus_existing"
    mock_send_email.assert_called_once()


def test_send_payment_link_subscription_mode_without_subscription(client, admin_headers):
    """Sans subscription existante → send-payment-link crée un Checkout subscription avec trial 30j."""
    fake = _fake_stripe_module(session_url="https://checkout.stripe.com/c/pay/sub_xxx", customer_id="cus_new_xxx")
    mock_send_email = MagicMock(return_value=(True, None))
    billing = {
        "stripe_customer_id": "cus_new_xxx",
        "stripe_subscription_id": "",
        "billing_status": "",
        "plan_key": "starter",
    }
    tenant = {"tenant_id": 1, "name": "Cabinet Test", "params": {"contact_email": "owner@test.fr"}}
    env_payment = {
        "STRIPE_SECRET_KEY": "sk_test_fake",
        "CLIENT_APP_ORIGIN": "https://app.example.com",
        "STRIPE_PRICE_BASE_STARTER": "price_starter_xxx",
        "STRIPE_PRICE_METERED_MINUTES": "price_metered_xxx",
    }
    with patch("backend.config.USE_PG_TENANTS", False):
        with patch("backend.routes.admin._get_tenant_detail", return_value=tenant):
            with patch("backend.routes.admin.get_tenant_billing", return_value=billing):
                with patch("backend.services.email_service.send_payment_link_email", mock_send_email):
                    with patch.dict("os.environ", env_payment, clear=False):
                        with patch.dict("sys.modules", {"stripe": fake}):
                            r = client.post("/api/admin/tenants/1/send-payment-link", headers=admin_headers)
    assert r.status_code == 200
    call_kw = fake.checkout.Session.create.call_args[1]
    assert call_kw["mode"] == "subscription"
    assert call_kw["subscription_data"]["trial_period_days"] == 30
    assert call_kw["line_items"] == [
        {"price": "price_starter_xxx", "quantity": 1},
        {"price": "price_metered_xxx"},
    ]
