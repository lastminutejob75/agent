"""Idempotence et rollback du provisioning self-serve depuis un lead."""

from contextlib import nullcontext

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from backend.main import app

    return TestClient(app)


@pytest.fixture
def provisioning(monkeypatch):
    from backend import auth_pg, cabinet_profile_pg, config, tenant_config, tenants_pg
    from backend.routes import pre_onboarding
    from backend.services import email_service

    monkeypatch.setattr(config, "USE_PG_TENANTS", True)
    monkeypatch.setattr("backend.security.assert_lead_access", lambda *args, **kwargs: None)
    monkeypatch.setattr(pre_onboarding, "lock_lead_conversion", lambda _lead_id: nullcontext())
    monkeypatch.setattr(auth_pg, "pg_get_tenant_user_by_email", lambda _email: None)
    monkeypatch.setattr(auth_pg, "pg_create_tenant_user", lambda *args, **kwargs: True)
    monkeypatch.setattr(tenants_pg, "pg_create_tenant", lambda **kwargs: 42)
    monkeypatch.setattr(tenants_pg, "pg_delete_tenant", lambda _tenant_id: True)
    monkeypatch.setattr(tenants_pg, "pg_update_tenant_flags", lambda *args, **kwargs: True)
    monkeypatch.setattr(tenants_pg, "pg_update_tenant_params", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        tenant_config,
        "convert_opening_hours_to_booking_rules",
        lambda _hours: {"timezone": "Europe/Paris"},
    )
    monkeypatch.setattr(tenant_config, "derive_horaires_text", lambda _rules: "Lun 09:00-18:00")
    monkeypatch.setattr(cabinet_profile_pg, "sync_normalized_from_params", lambda *args: None)
    monkeypatch.setattr(
        cabinet_profile_pg,
        "sync_opening_hours_from_booking_rules",
        lambda *args: None,
    )
    monkeypatch.setattr(email_service, "send_welcome_email", lambda **kwargs: (True, None))
    monkeypatch.setattr(pre_onboarding, "update_lead", lambda *args, **kwargs: True)

    return {
        "route": pre_onboarding,
        "auth": auth_pg,
        "tenants": tenants_pg,
    }


def _lead(**overrides):
    lead = {
        "id": "lead-1",
        "email": "cabinet@example.com",
        "status": "new",
        "tenant_id": None,
        "medical_specialty": "dentiste",
        "medical_specialty_label": "Dentiste",
        "assistant_name": "Sophie",
        "opening_hours": {"monday": {"start": "09:00", "end": "18:00"}},
        "source": "landing_cta",
        "notes_log": [],
    }
    lead.update(overrides)
    return lead


def test_converted_lead_returns_existing_account_without_recreating(
    client,
    provisioning,
    monkeypatch,
):
    route = provisioning["route"]
    tenants = provisioning["tenants"]
    monkeypatch.setattr(route, "get_lead", lambda _lead_id: _lead(status="converted", tenant_id=91))

    created = []
    monkeypatch.setattr(tenants, "pg_create_tenant", lambda **kwargs: created.append(kwargs))

    response = client.post(
        "/api/pre-onboarding/leads/lead-1/create-account?token=test",
        json={"email": "cabinet@example.com"},
    )

    assert response.status_code == 200
    assert response.json()["tenant_id"] == 91
    assert response.json()["message"] == "Compte déjà créé."
    assert created == []


@pytest.mark.parametrize(
    ("status", "tenant_id"),
    [
        ("converted", None),
        ("new", 91),
    ],
)
def test_incoherent_conversion_state_returns_conflict(
    client,
    provisioning,
    monkeypatch,
    status,
    tenant_id,
):
    route = provisioning["route"]
    monkeypatch.setattr(
        route,
        "get_lead",
        lambda _lead_id: _lead(status=status, tenant_id=tenant_id),
    )

    response = client.post(
        "/api/pre-onboarding/leads/lead-1/create-account?token=test",
        json={"email": "cabinet@example.com"},
    )

    assert response.status_code == 409
    assert "incohérent" in response.json()["detail"]


def test_user_creation_failure_deletes_new_tenant(
    client,
    provisioning,
    monkeypatch,
):
    route = provisioning["route"]
    auth = provisioning["auth"]
    tenants = provisioning["tenants"]
    monkeypatch.setattr(route, "get_lead", lambda _lead_id: _lead())
    monkeypatch.setattr(auth, "pg_create_tenant_user", lambda *args, **kwargs: False)

    deleted = []
    monkeypatch.setattr(tenants, "pg_delete_tenant", lambda tenant_id: deleted.append(tenant_id) or True)

    response = client.post(
        "/api/pre-onboarding/leads/lead-1/create-account?token=test",
        json={"email": "cabinet@example.com"},
    )

    assert response.status_code == 500
    assert deleted == [42]


def test_lead_association_failure_deletes_new_tenant(
    client,
    provisioning,
    monkeypatch,
):
    route = provisioning["route"]
    tenants = provisioning["tenants"]
    monkeypatch.setattr(route, "get_lead", lambda _lead_id: _lead())
    monkeypatch.setattr(route, "update_lead", lambda *args, **kwargs: False)

    deleted = []
    monkeypatch.setattr(tenants, "pg_delete_tenant", lambda tenant_id: deleted.append(tenant_id) or True)

    response = client.post(
        "/api/pre-onboarding/leads/lead-1/create-account?token=test",
        json={"email": "cabinet@example.com"},
    )

    assert response.status_code == 500
    assert deleted == [42]


def test_retry_after_success_creates_tenant_only_once(
    client,
    provisioning,
    monkeypatch,
):
    route = provisioning["route"]
    tenants = provisioning["tenants"]
    state = _lead()
    monkeypatch.setattr(route, "get_lead", lambda _lead_id: dict(state))

    created = []
    monkeypatch.setattr(
        tenants,
        "pg_create_tenant",
        lambda **kwargs: created.append(kwargs) or 42,
    )

    def mark_converted(_lead_id, **kwargs):
        state.update(status=kwargs["status"], tenant_id=kwargs["tenant_id"])
        return True

    monkeypatch.setattr(route, "update_lead", mark_converted)

    first = client.post(
        "/api/pre-onboarding/leads/lead-1/create-account?token=test",
        json={"email": "cabinet@example.com"},
    )
    second = client.post(
        "/api/pre-onboarding/leads/lead-1/create-account?token=test",
        json={"email": "cabinet@example.com"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["tenant_id"] == second.json()["tenant_id"] == 42
    assert len(created) == 1
