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
    assert call_kw.get("metadata") == {"tenant_id": "1"}
    assert call_kw.get("subscription_data", {}).get("metadata") == {"tenant_id": "1"}


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
