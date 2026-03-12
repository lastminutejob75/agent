# tests/test_admin_api.py
"""Tests API admin / onboarding (POST /public/onboarding, GET /admin/*)."""

import os
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ADMIN_API_TOKEN", "test-admin-token-pytest")


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def admin_headers():
    return {"Authorization": f"Bearer {os.environ.get('ADMIN_API_TOKEN')}"}


def test_public_onboarding_creates_tenant(client):
    """POST /api/public/onboarding crée un tenant."""
    r = client.post(
        "/api/public/onboarding",
        json={
            "company_name": "Test Cabinet",
            "email": "contact@test.fr",
            "calendar_provider": "none",
            "calendar_id": "",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "tenant_id" in data
    assert data["tenant_id"] >= 1
    assert "message" in data


def test_admin_tenants_requires_auth(client):
    """GET /api/admin/tenants sans token → 401."""
    r = client.get("/api/admin/tenants")
    assert r.status_code == 401


def test_admin_tenants_401_without_token(client):
    """Verrouille la règle : Bearer manquant → 401 (évite régression)."""
    r = client.get("/api/admin/tenants")
    assert r.status_code == 401
    assert "token" in (r.json().get("detail") or "").lower() or "credential" in (r.json().get("detail") or "").lower()


def test_admin_create_tenant_requires_auth(client):
    """POST /api/admin/tenants sans token → 401."""
    r = client.post(
        "/api/admin/tenants",
        json={"name": "Test", "contact_email": "a@b.fr", "timezone": "Europe/Paris"},
    )
    assert r.status_code == 401


def test_admin_tenants_401_with_invalid_token(client):
    """GET /api/admin/tenants avec Bearer invalide → 401 (pas 403, ne pas révéler validité token)."""
    r = client.get(
        "/api/admin/tenants",
        headers={"Authorization": "Bearer wrong-token-or-client-jwt"},
    )
    assert r.status_code == 401


@patch("backend.routes.admin.config.USE_PG_TENANTS", False)
def test_admin_create_tenant_sqlite_201(client, admin_headers):
    """POST /api/admin/tenants (SQLite) → 201, contact_email normalisé lower."""
    r = client.post(
        "/api/admin/tenants",
        headers=admin_headers,
        json={
            "name": "Cabinet Test",
            "contact_email": "  Dr@Cabinet.Fr  ",
            "timezone": "Europe/Paris",
            "business_type": "medical",
            "notes": "Note",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Cabinet Test"
    assert data["contact_email"] == "dr@cabinet.fr"
    assert data["timezone"] == "Europe/Paris"
    assert data.get("business_type") == "medical"
    assert "tenant_id" in data
    assert data["tenant_id"] >= 1
    assert "created_at" in data


@patch("backend.routes.admin.config.USE_PG_TENANTS", False)
def test_admin_create_tenant_sqlite_409_duplicate_email(client, admin_headers):
    """POST /api/admin/tenants (SQLite) même email deux fois → 409 EMAIL_ALREADY_ASSIGNED."""
    payload = {"name": "First", "contact_email": "same@example.com", "timezone": "Europe/Paris"}
    r1 = client.post("/api/admin/tenants", headers=admin_headers, json=payload)
    assert r1.status_code == 201
    r2 = client.post("/api/admin/tenants", headers=admin_headers, json={**payload, "name": "Second"})
    assert r2.status_code == 409
    data = r2.json()
    assert data.get("error_code") == "EMAIL_ALREADY_ASSIGNED"
    assert "detail" in data


def test_admin_tenants_with_token(client, admin_headers):
    """GET /api/admin/tenants avec token → 200."""
    r = client.get("/api/admin/tenants", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert "tenants" in data
    assert isinstance(data["tenants"], list)


@patch("backend.routes.admin.pg_deactivate_tenant", return_value=True)
@patch("backend.routes.admin._get_tenant_detail", return_value={"tenant_id": 42, "name": "Cabinet Test", "status": "active"})
@patch("backend.tenants_pg.pg_get_tenant_full", return_value={"tenant_id": 42, "name": "Cabinet Test", "status": "active"})
@patch("backend.routes.admin.config.USE_PG_TENANTS", True)
def test_admin_delete_tenant_requires_strong_confirmation(_mock_pg_tenant, _mock_detail, mock_deactivate, client, admin_headers):
    r = client.request(
        "DELETE",
        "/api/admin/tenants/42",
        headers=admin_headers,
        json={"tenant_name": "Cabinet Test", "confirmation_phrase": "SUPPRIMER"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    mock_deactivate.assert_called_once_with(42)


@patch("backend.routes.admin._get_tenant_detail", return_value={"tenant_id": 1, "name": "DEFAULT", "status": "active"})
@patch("backend.tenants_pg.pg_get_tenant_full", return_value={"tenant_id": 1, "name": "DEFAULT", "status": "active"})
@patch("backend.routes.admin.config.TEST_TENANT_ID", 2)
@patch("backend.routes.admin.config.DEFAULT_TENANT_ID", 1)
@patch("backend.routes.admin.config.USE_PG_TENANTS", True)
def test_admin_delete_tenant_blocks_default_account(_mock_pg_tenant, _mock_detail, client, admin_headers):
    r = client.request(
        "DELETE",
        "/api/admin/tenants/1",
        headers=admin_headers,
        json={"tenant_name": "DEFAULT", "confirmation_phrase": "SUPPRIMER"},
    )
    assert r.status_code == 403
    assert "compte système" in (r.json().get("detail") or "").lower()


def test_get_calls_list_merges_ivr_events_when_vapi_calls_exist(monkeypatch):
    """Ne pas masquer un appel récent si vapi_calls contient déjà d'anciens appels."""
    import psycopg
    from backend.routes import admin as admin_routes

    now = datetime.utcnow()
    vapi_rows = [
        {
            "tenant_id": 1,
            "call_id": "call_old",
            "started_at": now - timedelta(hours=2),
            "ended_at": now - timedelta(hours=1, minutes=57),
            "updated_at": now - timedelta(hours=1, minutes=57),
            "status": "ended",
            "ended_reason": "",
            "last_event": "booking_confirmed",
        }
    ]
    ivr_rows = [
        {
            "client_id": 1,
            "call_id": "call_new",
            "started_at": now - timedelta(minutes=10),
            "last_event_at": now - timedelta(minutes=7),
            "last_event": "booking_confirmed",
            "cs_started": now - timedelta(minutes=10),
            "cs_updated": now - timedelta(minutes=7),
        },
        {
            "client_id": 1,
            "call_id": "call_old",
            "started_at": now - timedelta(hours=2),
            "last_event_at": now - timedelta(hours=1, minutes=57),
            "last_event": "booking_confirmed",
            "cs_started": now - timedelta(hours=2),
            "cs_updated": now - timedelta(hours=1, minutes=57),
        },
    ]

    class FakeCursor:
        def __init__(self):
            self.exec_count = 0

        def execute(self, sql, params):
            self.exec_count += 1

        def fetchall(self):
            if self.exec_count == 1:
                return vapi_rows
            if self.exec_count == 2:
                return ivr_rows
            return []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeConn:
        def __init__(self):
            self.cursor_obj = FakeCursor()

        def cursor(self):
            return self.cursor_obj

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setenv("DATABASE_URL", "postgres://fake")
    monkeypatch.setattr(psycopg, "connect", lambda *args, **kwargs: FakeConn())
    monkeypatch.setattr(admin_routes, "_get_tenant_detail", lambda tenant_id: {"name": "Cabinet Test"})

    data = admin_routes._get_calls_list(tenant_id=1, days=1, limit=10)

    call_ids = [item["call_id"] for item in data["items"]]
    assert "call_new" in call_ids
    assert "call_old" in call_ids
    assert call_ids[0] == "call_new"


def test_get_call_detail_falls_back_to_vapi_calls_without_ivr_events(monkeypatch):
    import psycopg
    from backend.routes import admin as admin_routes

    now = datetime.utcnow()
    ivr_rows = []
    call_session_row = None
    vapi_row = {
        "customer_number": "+33612345678",
        "started_at": now - timedelta(minutes=12),
        "ended_at": now - timedelta(minutes=8),
        "updated_at": now - timedelta(minutes=8),
        "status": "ended",
        "ended_reason": "",
    }
    transcript_rows = []

    class FakeCursor:
        def __init__(self):
            self.exec_count = 0

        def execute(self, sql, params):
            self.exec_count += 1

        def fetchall(self):
            if self.exec_count == 1:
                return ivr_rows
            if self.exec_count == 4:
                return transcript_rows
            return []

        def fetchone(self):
            if self.exec_count == 2:
                return call_session_row
            if self.exec_count == 3:
                return vapi_row
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setenv("DATABASE_URL", "postgres://fake")
    monkeypatch.setattr(psycopg, "connect", lambda *args, **kwargs: FakeConn())

    data = admin_routes._get_call_detail(tenant_id=1, call_id="call_partial")

    assert data["call_id"] == "call_partial"
    assert data["customer_number"] == "+33612345678"
    assert data["events"] == []
    assert data["started_at"]
    assert data["last_event_at"]
    assert data["duration_min"] == 4


@patch("backend.routes.admin.config.USE_PG_TENANTS", True)
@patch("backend.routes.admin._get_stripe_price_ids_for_plan", return_value=("price_base", "price_meter"))
@patch("backend.leads_pg.update_lead", return_value=True)
@patch(
    "backend.leads_pg.get_lead",
    return_value={
        "id": "lead_123",
        "source": "landing_cta",
        "medical_specialty_label": "Médecin généraliste",
        "daily_call_volume": "25-50",
        "primary_pain_point": "Ne répond pas pendant les consultations",
        "opening_hours": {
            "0": {"open": "08:00", "close": "12:00"},
            "1": {"open": "09:00", "close": "18:00"},
            "4": {"open": "10:00", "close": "19:00"},
        },
        "notes_log": [],
    },
)
@patch("backend.routes.admin.pg_get_tenant_user_by_email", return_value=None)
@patch("backend.routes.admin.pg_create_tenant", return_value=321)
@patch("backend.routes.admin.pg_create_tenant_user", return_value=True)
@patch("backend.routes.admin.pg_update_tenant_flags", return_value=True)
@patch("backend.routes.admin.pg_update_tenant_params", return_value=True)
@patch("backend.routes.admin.upsert_billing_from_subscription", return_value=True)
@patch("backend.services.email_service.send_welcome_email", return_value=(True, None))
@patch("backend.vapi_utils.create_vapi_assistant", new_callable=AsyncMock, return_value={"id": "asst_123"})
@patch("stripe.Customer.create", return_value=SimpleNamespace(id="cus_123"))
@patch(
    "stripe.Subscription.create",
    return_value=SimpleNamespace(
        id="sub_123",
        status="trialing",
        current_period_start=None,
        current_period_end=None,
        trial_end=None,
    ),
)
def test_admin_create_tenant_full_prefills_params_from_lead(
    _mock_subscription,
    _mock_customer,
    _mock_vapi,
    _mock_email,
    _mock_billing,
    mock_update_params,
    _mock_flags,
    _mock_tenant_user,
    _mock_create_tenant,
    _mock_existing_email,
    _mock_get_lead,
    _mock_update_lead,
    _mock_prices,
    client,
    admin_headers,
):
    with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mocked"}, clear=False):
        r = client.post(
            "/api/admin/tenants/create",
            headers=admin_headers,
            json={
                "name": "Cabinet Lead Converti",
                "email": "lead@test.fr",
                "phone": "0611223344",
                "sector": "medecin_generaliste",
                "plan_key": "growth",
                "assistant_id": "sophie",
                "timezone": "Europe/Paris",
                "lead_id": "lead_123",
                "send_welcome": False,
            },
        )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["success"] is True
    assert data["tenant_id"] == 321

    payloads = [call.args[1] for call in mock_update_params.call_args_list]
    assert any(
        payload.get("contact_email") == "lead@test.fr"
        and payload.get("lead_id") == "lead_123"
        and payload.get("lead_daily_call_volume") == "25-50"
        and payload.get("lead_primary_pain_point") == "Ne répond pas pendant les consultations"
        and payload.get("specialty_label") == "Médecin généraliste"
        for payload in payloads
    )
    assert any(
        payload.get("booking_days") == [0, 1, 4]
        and payload.get("booking_start_hour") == 8
        and payload.get("booking_end_hour") == 19
        and payload.get("horaires") == "Lun, Mar, Ven · 8h–19h"
        for payload in payloads
    )


def test_admin_tenant_detail(client, admin_headers):
    """GET /api/admin/tenants/1 → détail avec flags, params, routing."""
    r = client.get("/api/admin/tenants/1", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert "tenant_id" in data
    assert "name" in data
    assert "flags" in data
    assert "params" in data
    assert "routing" in data


def test_admin_tenant_not_found(client, admin_headers):
    """GET /api/admin/tenants/999999 → 404."""
    r = client.get("/api/admin/tenants/999999", headers=admin_headers)
    assert r.status_code == 404


def test_admin_patch_flags(client, admin_headers):
    """PATCH /api/admin/tenants/1/flags → ok."""
    r = client.patch(
        "/api/admin/tenants/1/flags",
        headers=admin_headers,
        json={"flags": {"ENABLE_LLM_ASSIST_START": False}},
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_admin_patch_params(client, admin_headers):
    """PATCH /api/admin/tenants/1/params → ok."""
    r = client.patch(
        "/api/admin/tenants/1/params",
        headers=admin_headers,
        json={
            "params": {
                "calendar_provider": "google",
                "calendar_id": "test@group.calendar.google.com",
                "transfer_assistant_phone": "+33123456789",
                "transfer_practitioner_phone": "+33987654321",
                "transfer_live_enabled": "true",
                "transfer_callback_enabled": "true",
            }
        },
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_admin_add_routing(client, admin_headers):
    """POST /api/admin/routing → ok."""
    r = client.post(
        "/api/admin/routing",
        headers=admin_headers,
        json={"channel": "vocal", "key": "+33123456789", "tenant_id": 1},
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_admin_kpis_weekly(client, admin_headers):
    """GET /api/admin/kpis/weekly → digests."""
    r = client.get(
        "/api/admin/kpis/weekly",
        headers=admin_headers,
        params={"tenant_id": 1, "start": "2026-01-01", "end": "2026-01-08"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "tenant_id" in data
    assert "calls_total" in data
    assert "booking_confirmed" in data


def test_admin_rgpd(client, admin_headers):
    """GET /api/admin/rgpd → consent_rate."""
    r = client.get(
        "/api/admin/rgpd",
        headers=admin_headers,
        params={"tenant_id": 1, "start": "2026-01-01", "end": "2026-01-08"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "consent_obtained" in data
    assert "consent_rate" in data


def test_admin_technical_status(client, admin_headers):
    """GET /api/admin/tenants/1/technical-status → statut technique."""
    r = client.get("/api/admin/tenants/1/technical-status", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["tenant_id"] == 1
    assert "did" in data
    assert data["routing_status"] in ("active", "not_configured")
    assert data["calendar_status"] in ("connected", "incomplete", "not_configured")
    assert data["service_agent"] in ("online", "offline")
    assert "last_event_ago" in data


def test_admin_technical_status_404(client, admin_headers):
    """GET /api/admin/tenants/999999/technical-status → 404."""
    r = client.get("/api/admin/tenants/999999/technical-status", headers=admin_headers)
    assert r.status_code == 404


def test_admin_transfer_reasons(client, admin_headers):
    """GET /api/admin/tenants/1/transfer-reasons → top_transferred, top_prevented."""
    r = client.get("/api/admin/tenants/1/transfer-reasons", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert "top_transferred" in data
    assert "top_prevented" in data
    assert "days" in data
    assert isinstance(data["top_transferred"], list)
    assert isinstance(data["top_prevented"], list)
    for item in data["top_transferred"]:
        assert "reason" in item
        assert "count" in item


def test_admin_transfer_reasons_404(client, admin_headers):
    """GET /api/admin/tenants/999999/transfer-reasons → 404."""
    r = client.get("/api/admin/tenants/999999/transfer-reasons", headers=admin_headers)
    assert r.status_code == 404


@patch("backend.routes.admin.pg_add_tenant_user")
def test_admin_add_user_creates_row(mock_add, client, admin_headers):
    """POST /api/admin/tenants/1/users → crée tenant_user."""
    mock_add.return_value = {
        "ok": True,
        "tenant_id": 1,
        "email": "contact@client.com",
        "role": "owner",
        "created": True,
    }
    r = client.post(
        "/api/admin/tenants/1/users",
        headers=admin_headers,
        json={"email": "contact@client.com", "role": "owner"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["tenant_id"] == 1
    assert data["email"] == "contact@client.com"
    assert data["role"] == "owner"
    assert data["created"] is True


@patch("backend.routes.admin.pg_add_tenant_user")
def test_admin_add_user_idempotent_same_tenant(mock_add, client, admin_headers):
    """POST /api/admin/tenants/1/users avec email déjà sur ce tenant → 200 (no-op)."""
    mock_add.return_value = {
        "ok": True,
        "tenant_id": 1,
        "email": "contact@client.com",
        "role": "owner",
        "created": False,
    }
    r = client.post(
        "/api/admin/tenants/1/users",
        headers=admin_headers,
        json={"email": "contact@client.com", "role": "owner"},
    )
    assert r.status_code == 200
    assert r.json()["created"] is False


@patch("backend.routes.admin.pg_add_tenant_user")
def test_admin_add_user_email_conflict_other_tenant_409(mock_add, client, admin_headers):
    """POST /api/admin/tenants/2/users avec email déjà sur tenant 1 → 409."""
    mock_add.side_effect = ValueError("Email déjà associé à un autre tenant")
    r = client.post(
        "/api/admin/tenants/2/users",
        headers=admin_headers,
        json={"email": "contact@client.com", "role": "owner"},
    )
    assert r.status_code == 409


@patch("backend.routes.admin.pg_add_tenant_user")
def test_admin_add_user_creates_row(mock_add, client, admin_headers):
    """POST /api/admin/tenants/1/users → crée tenant_user."""
    mock_add.return_value = {
        "ok": True,
        "tenant_id": 1,
        "email": "contact@client.com",
        "role": "owner",
        "created": True,
    }
    r = client.post(
        "/api/admin/tenants/1/users",
        headers=admin_headers,
        json={"email": "contact@client.com", "role": "owner"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["tenant_id"] == 1
    assert data["email"] == "contact@client.com"
    assert data["role"] == "owner"
    assert data["created"] is True
    mock_add.assert_called_once_with(1, "contact@client.com", "owner")


@patch("backend.routes.admin.pg_add_tenant_user")
def test_admin_add_user_idempotent_same_tenant(mock_add, client, admin_headers):
    """POST /api/admin/tenants/1/users avec email déjà sur ce tenant → 200, created=False."""
    mock_add.return_value = {
        "ok": True,
        "tenant_id": 1,
        "email": "contact@client.com",
        "role": "owner",
        "created": False,
    }
    r = client.post(
        "/api/admin/tenants/1/users",
        headers=admin_headers,
        json={"email": "contact@client.com", "role": "owner"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["created"] is False


@patch("backend.routes.admin.pg_add_tenant_user")
def test_admin_add_user_email_conflict_other_tenant_409(mock_add, client, admin_headers):
    """POST /api/admin/tenants/2/users avec email sur tenant 1 → 409."""
    mock_add.side_effect = ValueError("Email déjà associé à un autre tenant")
    r = client.post(
        "/api/admin/tenants/2/users",
        headers=admin_headers,
        json={"email": "contact@client.com", "role": "owner"},
    )
    assert r.status_code == 409


# --- Quota (custom override) ---


@patch("backend.routes.admin._get_tenant_detail")
@patch("backend.routes.admin.get_tenant_billing")
@patch("backend.config.USE_PG_TENANTS", False)
def test_quota_custom_override(mock_billing, mock_detail, client, admin_headers):
    """plan_key=custom + custom_included_minutes_month=300 → included=300, quota_source=custom."""
    mock_detail.return_value = {
        "tenant_id": 1,
        "params": {"plan_key": "custom", "custom_included_minutes_month": "300"},
    }
    mock_billing.return_value = None
    r = client.get("/api/admin/tenants/1/quota", headers=admin_headers, params={"month": "2026-01"})
    assert r.status_code == 200
    data = r.json()
    assert data["plan_key"] == "custom"
    assert data["included_minutes_month"] == 300
    assert data["quota_source"] == "custom"


@patch("backend.routes.admin._get_tenant_detail")
@patch("backend.routes.admin.get_tenant_billing")
@patch("backend.config.USE_PG_TENANTS", False)
def test_quota_custom_no_value(mock_billing, mock_detail, client, admin_headers):
    """plan_key=custom sans custom_included_minutes_month → included=0, quota_source=plan."""
    mock_detail.return_value = {"tenant_id": 1, "params": {"plan_key": "custom"}}
    mock_billing.return_value = None
    r = client.get("/api/admin/tenants/1/quota", headers=admin_headers, params={"month": "2026-01"})
    assert r.status_code == 200
    data = r.json()
    assert data["plan_key"] == "custom"
    assert data["included_minutes_month"] == 0
    assert data["quota_source"] == "plan"


@patch("backend.routes.admin._get_tenant_detail")
@patch("backend.routes.admin.get_tenant_billing")
@patch("backend.config.USE_PG_TENANTS", False)
def test_quota_custom_zero(mock_billing, mock_detail, client, admin_headers):
    """plan_key=custom avec custom_included_minutes_month=0 → included=0, quota_source=plan."""
    mock_detail.return_value = {
        "tenant_id": 1,
        "params": {"plan_key": "custom", "custom_included_minutes_month": "0"},
    }
    mock_billing.return_value = None
    r = client.get("/api/admin/tenants/1/quota", headers=admin_headers, params={"month": "2026-01"})
    assert r.status_code == 200
    data = r.json()
    assert data["plan_key"] == "custom"
    assert data["included_minutes_month"] == 0
    assert data["quota_source"] == "plan"


# --- Priorité 2: Tests socle (UTC, résolution plan, auth) ---


def test_billing_plans_requires_admin(client):
    """GET /api/admin/billing/plans sans token → 401."""
    r = client.get("/api/admin/billing/plans")
    assert r.status_code == 401


@patch("backend.config.USE_PG_TENANTS", False)
def test_quota_requires_admin(client):
    """GET /api/admin/tenants/1/quota sans token → 401."""
    r = client.get("/api/admin/tenants/1/quota", params={"month": "2026-01"})
    assert r.status_code == 401


@patch("backend.routes.admin._get_tenant_detail")
@patch("backend.routes.admin.get_tenant_billing")
@patch("backend.config.USE_PG_TENANTS", False)
def test_quota_plan_resolution_order_params_wins(mock_billing, mock_detail, client, admin_headers):
    """Cas 1: params.plan_key=pro + tenant_billing.plan_key=starter → choisi pro (params > tenant_billing)."""
    mock_detail.return_value = {"tenant_id": 1, "params": {"plan_key": "pro"}}
    mock_billing.return_value = {"plan_key": "starter"}
    with patch("backend.routes.admin.get_plan_included_minutes") as mock_plan:
        mock_plan.return_value = 1500  # pro
        r = client.get("/api/admin/tenants/1/quota", headers=admin_headers, params={"month": "2026-01"})
    assert r.status_code == 200
    data = r.json()
    assert data["plan_key"] == "pro"
    assert data["included_minutes_month"] == 1500
    mock_plan.assert_called_with("pro")


@patch("backend.routes.admin._get_tenant_detail")
@patch("backend.routes.admin.get_tenant_billing")
@patch("backend.config.USE_PG_TENANTS", False)
def test_quota_plan_resolution_order_billing_fallback(mock_billing, mock_detail, client, admin_headers):
    """Cas 2: params absent + tenant_billing.plan_key=business → choisi business."""
    mock_detail.return_value = {"tenant_id": 1, "params": {}}
    mock_billing.return_value = {"plan_key": "business"}
    with patch("backend.routes.admin.get_plan_included_minutes") as mock_plan:
        mock_plan.return_value = 5000
        r = client.get("/api/admin/tenants/1/quota", headers=admin_headers, params={"month": "2026-01"})
    assert r.status_code == 200
    data = r.json()
    assert data["plan_key"] == "business"
    assert data["included_minutes_month"] == 5000
    mock_plan.assert_called_with("business")


@patch("backend.routes.admin._get_tenant_detail")
@patch("backend.routes.admin.get_tenant_billing")
@patch("backend.config.USE_PG_TENANTS", False)
def test_quota_plan_resolution_order_free_default(mock_billing, mock_detail, client, admin_headers):
    """Cas 3: aucun plan_key → free."""
    mock_detail.return_value = {"tenant_id": 1, "params": {}}
    mock_billing.return_value = None
    with patch("backend.routes.admin.get_plan_included_minutes") as mock_plan:
        mock_plan.return_value = 0
        r = client.get("/api/admin/tenants/1/quota", headers=admin_headers, params={"month": "2026-01"})
    assert r.status_code == 200
    data = r.json()
    assert data["plan_key"] == "free"
    assert data["included_minutes_month"] == 0
    mock_plan.assert_called_with("free")


@patch("backend.routes.admin._get_tenant_detail")
@patch("backend.routes.admin.get_tenant_billing")
@patch("backend.config.USE_PG_TENANTS", False)
def test_quota_month_utc_window(mock_billing, mock_detail, client, admin_headers):
    """
    Fenêtre mois UTC : [start, end[ avec end = 1er du mois suivant.
    ended_at 2026-02-01 00:00:00Z compte dans 2026-02, ended_at 2026-03-01 00:00:00Z ne compte pas dans 2026-02.
    Mock _get_quota_used_minutes : 5 min pour fév, 3 min pour mars.
    """
    mock_detail.return_value = {"tenant_id": 1, "params": {"plan_key": "starter"}}
    mock_billing.return_value = None

    def fake_used(tenant_id, start, end):
        if end == "2026-03-01 00:00:00":
            return 5.0  # février
        if end == "2026-04-01 00:00:00":
            return 3.0  # mars
        return 0.0

    with patch("backend.routes.admin.get_plan_included_minutes", return_value=500), patch(
        "backend.routes.admin._get_quota_used_minutes", side_effect=fake_used
    ):
        r_feb = client.get("/api/admin/tenants/1/quota", headers=admin_headers, params={"month": "2026-02"})
        r_mar = client.get("/api/admin/tenants/1/quota", headers=admin_headers, params={"month": "2026-03"})
    assert r_feb.status_code == 200
    assert r_mar.status_code == 200
    assert r_feb.json()["used_minutes_month"] == 5.0
    assert r_feb.json()["month_utc"] == "2026-02"
    assert r_mar.json()["used_minutes_month"] == 3.0
    assert r_mar.json()["month_utc"] == "2026-03"
