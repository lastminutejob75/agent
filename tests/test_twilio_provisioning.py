"""Tests pour /api/admin/twilio/numbers (provisioning Twilio).

Couvre :
- Sans creds (SID/token vides) → retourne [].
- Erreur SDK (Client lève) → retourne [] (pas de 500).
- Liste OK + filtre `available` correct (numero non assigne = available).
- Numero deja en routing (`tenant_routing` channel='vocal') → available=False.
- Auth admin requise.

Le SDK Twilio est entierement mocke ; aucun appel reseau n'est fait.
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def admin_headers():
    return {"Authorization": f"Bearer {os.environ.get('ADMIN_API_TOKEN', 'test-admin-token-pytest')}"}


@pytest.fixture(autouse=True)
def _twilio_creds(monkeypatch):
    """Force des credentials Twilio fictifs valides (pour passer le check `if not sid or not token`).

    Les tests qui veulent tester l'absence de creds les vident eux-memes.
    """
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest_sid_for_pytest")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test_auth_token_for_pytest")


def _make_phone_number(num: str, friendly: str = ""):
    """Helper : objet avec attributs `phone_number` et `friendly_name` (comme l'objet Twilio)."""
    return SimpleNamespace(phone_number=num, friendly_name=friendly or num)


# -----------------------------------------------------------------------------
# Auth
# -----------------------------------------------------------------------------


def test_twilio_numbers_requires_admin(client):
    """Sans auth admin → 401."""
    r = client.get("/api/admin/twilio/numbers")
    assert r.status_code == 401


def test_twilio_numbers_with_invalid_admin_token(client):
    r = client.get(
        "/api/admin/twilio/numbers",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert r.status_code == 401


# -----------------------------------------------------------------------------
# Sans creds → []
# -----------------------------------------------------------------------------


def test_twilio_numbers_no_sid_returns_empty(client, admin_headers, monkeypatch):
    """SID absent → retourne [] (pas d'erreur)."""
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "")
    r = client.get("/api/admin/twilio/numbers", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_twilio_numbers_no_token_returns_empty(client, admin_headers, monkeypatch):
    """Token absent → retourne []."""
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "")
    r = client.get("/api/admin/twilio/numbers", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == []


# -----------------------------------------------------------------------------
# Erreur SDK → [] (graceful)
# -----------------------------------------------------------------------------


def test_twilio_numbers_sdk_error_returns_empty(client, admin_headers):
    """Si le SDK Twilio leve, l'endpoint repond 200 avec [] (pas 500)."""
    fake_client = MagicMock()
    fake_client.incoming_phone_numbers.list.side_effect = RuntimeError("Twilio API down")

    with patch("twilio.rest.Client", return_value=fake_client):
        r = client.get("/api/admin/twilio/numbers", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_twilio_numbers_sdk_import_error_returns_empty(client, admin_headers):
    """Si le module twilio ne peut pas etre importe, [] (degradation propre)."""
    # Simule un ImportError en patchant l'import depuis sys.modules
    import sys

    original = sys.modules.get("twilio.rest")
    sys.modules["twilio.rest"] = None  # forcer ImportError lors du `from twilio.rest import Client`
    try:
        r = client.get("/api/admin/twilio/numbers", headers=admin_headers)
        assert r.status_code == 200
        assert r.json() == []
    finally:
        if original is not None:
            sys.modules["twilio.rest"] = original
        else:
            sys.modules.pop("twilio.rest", None)


# -----------------------------------------------------------------------------
# Liste OK + filtre `available`
# -----------------------------------------------------------------------------


def test_twilio_numbers_returns_list_with_friendly(client, admin_headers):
    """Liste avec 3 numeros : tous disponibles si aucun routing."""
    numbers = [
        _make_phone_number("+33186111111", "Lille N°1"),
        _make_phone_number("+33186222222", "Lille N°2"),
        _make_phone_number("+33186333333", ""),
    ]
    fake_client = MagicMock()
    fake_client.incoming_phone_numbers.list.return_value = numbers

    with patch("twilio.rest.Client", return_value=fake_client), \
         patch("backend.routes.admin._get_assigned_voice_numbers", return_value=set()):
        r = client.get("/api/admin/twilio/numbers", headers=admin_headers)

    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    assert all(item["available"] is True for item in data)
    assert data[0]["number"] == "+33186111111"
    assert data[0]["friendly"] == "Lille N°1"
    # Friendly fallback sur le numero si vide
    assert data[2]["friendly"] == "+33186333333"


def test_twilio_numbers_filters_assigned(client, admin_headers):
    """Numeros deja en routing → available=False."""
    numbers = [
        _make_phone_number("+33186111111", "Disponible"),
        _make_phone_number("+33186222222", "Deja assigne"),
        _make_phone_number("+33186333333", "Disponible 2"),
    ]
    fake_client = MagicMock()
    fake_client.incoming_phone_numbers.list.return_value = numbers
    assigned = {"+33186222222"}

    with patch("twilio.rest.Client", return_value=fake_client), \
         patch("backend.routes.admin._get_assigned_voice_numbers", return_value=assigned):
        r = client.get("/api/admin/twilio/numbers", headers=admin_headers)

    data = r.json()
    by_num = {item["number"]: item for item in data}
    assert by_num["+33186111111"]["available"] is True
    assert by_num["+33186222222"]["available"] is False
    assert by_num["+33186333333"]["available"] is True


def test_twilio_numbers_empty_list(client, admin_headers):
    """Aucun numero sur le compte → []."""
    fake_client = MagicMock()
    fake_client.incoming_phone_numbers.list.return_value = []

    with patch("twilio.rest.Client", return_value=fake_client), \
         patch("backend.routes.admin._get_assigned_voice_numbers", return_value=set()):
        r = client.get("/api/admin/twilio/numbers", headers=admin_headers)

    assert r.status_code == 200
    assert r.json() == []


def test_twilio_numbers_truncates_friendly_at_80_chars(client, admin_headers):
    """Le champ friendly est tronque a 80 caracteres."""
    long_name = "Cabinet super tres tres tres tres tres tres tres tres tres tres tres tres long quelques chars"
    numbers = [_make_phone_number("+33186111111", long_name)]
    fake_client = MagicMock()
    fake_client.incoming_phone_numbers.list.return_value = numbers

    with patch("twilio.rest.Client", return_value=fake_client), \
         patch("backend.routes.admin._get_assigned_voice_numbers", return_value=set()):
        r = client.get("/api/admin/twilio/numbers", headers=admin_headers)

    data = r.json()
    assert len(data[0]["friendly"]) <= 80


def test_twilio_numbers_handles_missing_phone_number(client, admin_headers):
    """Si phone_number est None/vide, available=False (degradation)."""
    numbers = [
        _make_phone_number("", "Sans numero"),
        _make_phone_number("+33186111111", "OK"),
    ]
    fake_client = MagicMock()
    fake_client.incoming_phone_numbers.list.return_value = numbers

    with patch("twilio.rest.Client", return_value=fake_client), \
         patch("backend.routes.admin._get_assigned_voice_numbers", return_value=set()):
        r = client.get("/api/admin/twilio/numbers", headers=admin_headers)

    data = r.json()
    assert data[0]["available"] is False  # phone_number vide → False
    assert data[1]["available"] is True


# -----------------------------------------------------------------------------
# Mode demo
# -----------------------------------------------------------------------------


def test_twilio_numbers_demo_mode_returns_mock_list():
    """ADMIN_DEMO_MODE=true → 5 numeros factices, jamais d'appel SDK Twilio reel.

    On teste la fonction directement (sans HTTP) car le router demo n'est monte
    qu'au boot si ADMIN_DEMO_MODE etait actif. Le conftest force le mode hors demo
    pour la suite, donc le router demo n'est pas en place.
    """
    from unittest.mock import MagicMock
    from backend.admin_demo.router import demo_twilio_numbers

    data = demo_twilio_numbers(_=None)  # bypass Depends en passant directement None
    assert isinstance(data, list)
    assert len(data) == 5
    assert all("number" in item and "available" in item for item in data)
    # Tous des numeros francais fictifs +33...
    assert all(item["number"].startswith("+33") for item in data)
    assert all(item["available"] is True for item in data)
