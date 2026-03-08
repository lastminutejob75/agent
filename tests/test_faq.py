from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.tenant_config import faq_to_prompt_text, get_faq


@pytest.fixture
def client():
    from backend.main import app

    return TestClient(app)


def _auth_override():
    return {
        "tenant_id": 12,
        "email": "owner@test.fr",
        "role": "owner",
        "sub": "42",
    }


def test_get_faq_default_medecin():
    with patch("backend.tenant_config.get_params", return_value={"sector": "medecin_generaliste"}):
        faq = get_faq(12)

    assert isinstance(faq, list)
    assert any(category["category"] == "Horaires" for category in faq)
    assert any(category["category"] == "Ordonnances" for category in faq)


def test_get_faq_custom():
    custom_faq = [
        {
            "category": "Contact",
            "items": [
                {
                    "id": "c1",
                    "question": "Quel est votre email ?",
                    "answer": "cabinet@test.fr",
                    "active": True,
                }
            ],
        }
    ]
    with patch("backend.tenant_config.get_params", return_value={"sector": "dentiste", "faq_json": custom_faq}):
        faq = get_faq(12)

    assert faq == custom_faq


def test_faq_to_prompt_text():
    faq = [
        {
            "category": "Horaires",
            "items": [
                {"id": "h1", "question": "Êtes-vous ouvert le samedi ?", "answer": "Non.", "active": True},
                {"id": "h2", "question": "Question inactive", "answer": "Ne pas afficher", "active": False},
            ],
        }
    ]

    text = faq_to_prompt_text(faq)

    assert "=== FAQ DU CABINET ===" in text
    assert "[HORAIRES]" in text
    assert "Q: Êtes-vous ouvert le samedi ?" in text
    assert "R: Non." in text
    assert "Question inactive" not in text
    assert "=== FIN FAQ ===" in text


def test_get_faq_tenant(client):
    from backend.main import app
    from backend.routes import tenant

    faq_payload = [{"category": "Contact", "items": []}]
    app.dependency_overrides[tenant.require_tenant_auth] = _auth_override
    with patch("backend.routes.tenant.get_faq", return_value=faq_payload):
        try:
            response = client.get("/api/tenant/faq")
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == faq_payload


def test_put_faq_tenant(client):
    from backend.main import app
    from backend.routes import tenant

    faq_payload = [
        {
            "category": "Contact",
            "items": [
                {
                    "id": "c1",
                    "question": "Quel est votre email ?",
                    "answer": "cabinet@test.fr",
                    "active": True,
                }
            ],
        }
    ]
    app.dependency_overrides[tenant.require_tenant_auth] = _auth_override
    with patch("backend.routes.tenant._save_tenant_faq_payload", return_value=True) as save_mock, patch(
        "backend.routes.tenant.update_vapi_assistant_faq",
        new=AsyncMock(),
    ) as sync_mock:
        try:
            response = client.put("/api/tenant/faq", json=faq_payload)
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"ok": True, "faq": faq_payload}
    save_mock.assert_called_once_with(12, faq_payload)
    sync_mock.assert_awaited_once_with(12)


def test_reset_faq_tenant(client):
    from backend.main import app
    from backend.routes import tenant

    reset_payload = [{"category": "Horaires", "items": []}]
    app.dependency_overrides[tenant.require_tenant_auth] = _auth_override
    with patch("backend.routes.tenant._reset_tenant_faq_payload", return_value=True) as reset_mock, patch(
        "backend.routes.tenant.get_faq",
        return_value=reset_payload,
    ), patch(
        "backend.routes.tenant.update_vapi_assistant_faq",
        new=AsyncMock(),
    ) as sync_mock:
        try:
            response = client.post("/api/tenant/faq/reset")
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"ok": True, "faq": reset_payload}
    reset_mock.assert_called_once_with(12)
    sync_mock.assert_awaited_once_with(12)
