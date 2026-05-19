"""Tests sécurité Google SSO client."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-google-sso")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-google-client-secret")
os.environ["ALLOW_GOOGLE_SELF_SIGNUP"] = "false"


@pytest.fixture
def client():
    from backend.main import app

    return TestClient(app)


def _fake_id_token(email: str, sub: str):
    return {
        "email": email,
        "email_verified": True,
        "sub": sub,
        "name": "Test User",
    }


@patch("backend.routes.auth._verify_and_consume_oauth_state", return_value=True)
@patch("backend.routes.auth._exchange_code_for_tokens", return_value={"id_token": "fake"})
@patch("backend.routes.auth._verify_google_id_token")
@patch("backend.routes.auth.pg_get_tenant_user_by_google_sub")
@patch("backend.routes.auth.pg_get_tenant_user_by_email_for_google")
@patch("backend.routes.auth.pg_create_tenant")
def test_google_callback_unknown_email_rejected_when_signup_disabled(
    mock_create,
    mock_by_email,
    mock_by_sub,
    mock_verify_token,
    _mock_state,
    _mock_exchange,
    client,
):
    mock_verify_token.return_value = _fake_id_token("stranger@gmail.com", "sub-stranger-1")
    mock_by_sub.return_value = None
    mock_by_email.return_value = None

    r = client.post(
        "/api/auth/google/callback",
        json={
            "code": "c",
            "state": "s",
            "redirect_uri": "http://localhost:5173/auth/google/callback",
            "code_verifier": "v" * 43,
        },
    )

    assert r.status_code == 403
    mock_create.assert_not_called()


@patch("backend.routes.auth._verify_and_consume_oauth_state", return_value=True)
@patch("backend.routes.auth._exchange_code_for_tokens", return_value={"id_token": "fake"})
@patch("backend.routes.auth._verify_google_id_token")
@patch("backend.routes.auth.pg_get_tenant_user_by_google_sub")
@patch("backend.routes.auth.pg_get_tenant_user_by_email_for_google")
@patch("backend.routes.auth.pg_link_google_sub")
def test_google_callback_existing_sub_logs_into_linked_user_only(
    mock_link,
    mock_by_email,
    mock_by_sub,
    mock_verify_token,
    _mock_state,
    _mock_exchange,
    client,
):
    mock_verify_token.return_value = _fake_id_token("henigoutal@gmail.com", "sub-heni")
    mock_by_sub.return_value = {
        "tenant_id": 2,
        "user_id": 1,
        "role": "owner",
        "email": "henigoutal@gmail.com",
        "google_sub": "sub-heni",
    }

    r = client.post(
        "/api/auth/google/callback",
        json={
            "code": "c",
            "state": "s",
            "redirect_uri": "http://localhost:5173/auth/google/callback",
            "code_verifier": "v" * 43,
        },
    )

    assert r.status_code == 200
    assert r.json().get("ok") is True
    mock_by_email.assert_not_called()
    mock_link.assert_not_called()
