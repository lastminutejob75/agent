import os
from unittest.mock import patch

from fastapi.testclient import TestClient


os.environ.setdefault("JWT_SECRET", "test-secret")


def test_auth_login_returns_cookie_and_token():
    from backend.main import app

    client = TestClient(app)
    fake_hash = "$2b$12$abcdefghijklmnopqrstuuPFB5oXH8N0dwofsl2MvmFo0xSg6u40G"
    with patch("backend.routes.auth.pg_get_tenant_user_by_email_for_login", return_value={
        "tenant_id": 2,
        "user_id": 7,
        "role": "owner",
        "password_hash": fake_hash,
    }), patch("backend.routes.auth.bcrypt.checkpw", return_value=True):
        response = client.post("/api/auth/login", json={"email": "test@example.com", "password": "secret123"})

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["tenant_id"] == 2
    assert isinstance(data.get("token"), str) and data["token"]
    assert "uwi_session=" in response.headers.get("set-cookie", "")
