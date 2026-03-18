import os
import time
from unittest.mock import patch

import jwt
from fastapi.testclient import TestClient


def _make_client_token(tenant_id: int, user_id: int = 1) -> str:
    secret = os.environ.get("JWT_SECRET")
    now = int(time.time())
    payload = {
        "typ": "client_session",
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": "owner",
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@patch("backend.routes.tenant.pg_get_tenant_user_by_id")
@patch("backend.routes.tenant.pg_update_tenant_params")
@patch("backend.routes.tenant.pg_update_tenant_name")
def test_tenant_patch_params_syncs_tenant_name_to_business_name(mock_update_name, mock_update_params, mock_get_user):
    from backend.main import app

    mock_get_user.return_value = {"tenant_id": 2, "email": "client@test.fr", "role": "owner"}
    mock_update_name.return_value = True
    mock_update_params.return_value = True

    client = TestClient(app)
    token = _make_client_token(2, user_id=7)
    response = client.patch(
        "/api/tenant/params",
        headers={"Authorization": f"Bearer {token}"},
        json={"tenant_name": "Cabinet Dupont"},
    )

    assert response.status_code == 200
    mock_update_name.assert_called_once_with(2, "Cabinet Dupont")
    mock_update_params.assert_called_once_with(2, {"business_name": "Cabinet Dupont"})
