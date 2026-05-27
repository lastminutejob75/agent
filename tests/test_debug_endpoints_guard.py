"""Tests pour le middleware debug_endpoints_guard (audit securite 2026-05).

Verifie que les endpoints /debug/* et /api/stats/bookings sont bloques sauf si :
- ENABLE_DEBUG_ENDPOINTS=true (env)
- ADMIN_DEMO_MODE=true (mode demo)
- Auth admin (cookie session ou Bearer)

Verifie aussi /api/vapi/test-calendar et /api/vapi/test (depend par endpoint).
"""

from __future__ import annotations

import os

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
def _no_debug_flag(monkeypatch):
    """S'assure que ENABLE_DEBUG_ENDPOINTS et ADMIN_DEMO_MODE ne sont pas actifs.

    Les tests qui veulent tester le bypass via flag les reactivent eux-memes.
    On utilise setenv("") plutot que delenv() pour eviter que load_dotenv()
    (appele a l'import de backend.main) ne recharge la valeur depuis .env.
    """
    monkeypatch.setenv("ENABLE_DEBUG_ENDPOINTS", "")
    monkeypatch.setenv("ADMIN_DEMO_MODE", "")


# -----------------------------------------------------------------------------
# /debug/* sans auth → 403
# -----------------------------------------------------------------------------


def test_debug_config_blocked_without_auth(client):
    """GET /debug/config sans auth → 403."""
    r = client.get("/debug/config")
    assert r.status_code == 403
    assert "auth admin" in (r.json().get("detail") or "").lower() or "ENABLE_DEBUG_ENDPOINTS" in (r.json().get("detail") or "")


def test_debug_env_vars_blocked_without_auth(client):
    """GET /debug/env-vars (qui exposait des cles env) → 403."""
    r = client.get("/debug/env-vars")
    assert r.status_code == 403


def test_debug_force_load_credentials_blocked_without_auth(client):
    """GET /debug/force-load-credentials → 403 (exposait les chemins SA)."""
    r = client.get("/debug/force-load-credentials")
    assert r.status_code == 403


def test_stats_bookings_blocked_without_auth(client):
    """GET /api/stats/bookings → 403 (stats sessions sensibles)."""
    r = client.get("/api/stats/bookings")
    assert r.status_code == 403


# -----------------------------------------------------------------------------
# /debug/* avec ENABLE_DEBUG_ENDPOINTS=true → bypass (200/autre, pas 403)
# -----------------------------------------------------------------------------


def test_debug_config_open_with_env_flag(client, monkeypatch):
    """ENABLE_DEBUG_ENDPOINTS=true → bypass, l'endpoint repond normalement."""
    monkeypatch.setenv("ENABLE_DEBUG_ENDPOINTS", "true")
    r = client.get("/debug/config")
    assert r.status_code != 403
    # L'endpoint retourne du JSON metier
    assert r.status_code == 200


def test_debug_config_open_with_demo_mode(client, monkeypatch):
    """ADMIN_DEMO_MODE=true → bypass aussi (utile en local)."""
    monkeypatch.setenv("ADMIN_DEMO_MODE", "true")
    r = client.get("/debug/config")
    assert r.status_code != 403


def test_debug_flag_is_case_insensitive(client, monkeypatch):
    """ENABLE_DEBUG_ENDPOINTS accepte true/1/yes/on (insensible a la casse)."""
    for val in ("TRUE", "1", "yes", "On"):
        monkeypatch.setenv("ENABLE_DEBUG_ENDPOINTS", val)
        r = client.get("/debug/config")
        assert r.status_code != 403, f"value '{val}' should bypass"


def test_debug_flag_false_is_blocking(client, monkeypatch):
    """ENABLE_DEBUG_ENDPOINTS=false → toujours bloque."""
    for val in ("false", "0", "", "no"):
        monkeypatch.setenv("ENABLE_DEBUG_ENDPOINTS", val)
        r = client.get("/debug/config")
        assert r.status_code == 403, f"value '{val}' should block"


# -----------------------------------------------------------------------------
# /debug/* avec auth admin → bypass
# -----------------------------------------------------------------------------


def test_debug_config_with_admin_bearer_bypasses(client, admin_headers):
    """Bearer admin valide → bypass."""
    r = client.get("/debug/config", headers=admin_headers)
    assert r.status_code != 403


def test_debug_config_with_invalid_bearer_blocked(client):
    """Bearer invalide → 403."""
    r = client.get("/debug/config", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 403


# -----------------------------------------------------------------------------
# /api/vapi/test-calendar (Depends par endpoint, pas middleware)
# -----------------------------------------------------------------------------


def test_vapi_test_calendar_blocked_without_auth(client):
    """GET /api/vapi/test-calendar → 403 sans auth (exposait config Google)."""
    r = client.get("/api/vapi/test-calendar")
    assert r.status_code == 403


def test_vapi_test_calendar_open_with_env_flag(client, monkeypatch):
    monkeypatch.setenv("ENABLE_DEBUG_ENDPOINTS", "true")
    r = client.get("/api/vapi/test-calendar")
    assert r.status_code != 403


def test_vapi_test_calendar_with_admin_bypasses(client, admin_headers):
    r = client.get("/api/vapi/test-calendar", headers=admin_headers)
    assert r.status_code != 403


def test_vapi_test_blocked_without_auth(client):
    """GET /api/vapi/test → 403 sans auth."""
    r = client.get("/api/vapi/test")
    assert r.status_code == 403


# -----------------------------------------------------------------------------
# Endpoints non-debug ne sont PAS impactes
# -----------------------------------------------------------------------------


def test_health_not_affected(client):
    """GET /health doit toujours marcher (pas dans le scope du middleware)."""
    r = client.get("/health")
    assert r.status_code == 200


def test_root_not_affected(client):
    """GET / ne doit pas etre impacte."""
    r = client.get("/")
    assert r.status_code in (200, 404)  # selon la presence d'index


def test_admin_endpoints_not_affected_by_debug_guard(client):
    """Le middleware debug ne touche pas aux endpoints admin."""
    # /api/admin/tenants → 401 (auth admin requise), pas 403 (debug guard)
    r = client.get("/api/admin/tenants")
    assert r.status_code == 401
