"""Tests des garde-fous sécurité (module backend.security)."""
import os
import time

import jwt
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from backend.main import app

    return TestClient(app)


def test_debug_routes_blocked_when_production(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("ENABLE_DEBUG_ROUTES", raising=False)
    from backend import security

    assert security.is_production() is True
    assert security.debug_routes_enabled() is False


def test_issue_and_verify_lead_access_token(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-lead-secret")
    from backend.security import issue_lead_access_token, verify_lead_access_token

    token = issue_lead_access_token("lead-abc")
    assert verify_lead_access_token("lead-abc", token)
    assert not verify_lead_access_token("lead-other", token)


def test_vapi_webhook_rejects_without_secret_in_production(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("VAPI_WEBHOOK_SECRET", "super-secret")
    from backend.security import verify_vapi_webhook

    class Req:
        headers = {}

    assert verify_vapi_webhook(Req()) is False

    class ReqOk:
        headers = {"x-vapi-secret": "super-secret"}

    assert verify_vapi_webhook(ReqOk()) is True


def test_google_redirect_allowlist(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "https://www.uwiapp.com/auth/google/callback")
    from backend.security import google_redirect_allowed

    assert google_redirect_allowed("https://www.uwiapp.com/auth/google/callback")
    assert not google_redirect_allowed("https://evil.example/callback")


def test_impersonate_jti_single_use():
    from backend.security import register_impersonate_jti

    jti = "test-jti-unique-1"
    assert register_impersonate_jti(jti) is True
    assert register_impersonate_jti(jti) is False


def test_debug_env_vars_404_in_production(client, monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("ENABLE_DEBUG_ROUTES", raising=False)
    r = client.get("/debug/env-vars")
    assert r.status_code == 404


def test_public_onboarding_never_returns_admin_token(client, monkeypatch):
    monkeypatch.setenv("USE_PG_TENANTS", "false")
    r = client.post(
        "/api/public/onboarding",
        json={
            "company_name": "Test Sec",
            "email": "sec-test@example.com",
            "calendar_provider": "none",
            "calendar_id": "",
        },
    )
    if r.status_code == 200:
        data = r.json()
        assert "admin_setup_token" not in data
