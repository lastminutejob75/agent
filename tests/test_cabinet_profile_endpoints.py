"""
Tests pour les endpoints "Mon cabinet" (/api/tenant/profile, opening-hours,
booking-rules, availability-settings) et pour la whitelist élargie de
pg_update_tenant_params.

Couvre :
- PATCH /profile écrit dans BOTH tenant_profiles (PG) et params_json
- PATCH /opening-hours écrit dans BOTH opening_hours (PG) et params_json
- Whitelist pg_update_tenant_params accepte les nouvelles clés
  (practitioner_name, opening_hours_json, default_appointment_duration_minutes,
   etc.) avec normalisation correcte des types (bool/int/json).
- sync_normalized_from_params dispatche bien vers les upserts dédiés.
"""
import os
import sys
import time
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-cabinet-profile-endpoints")


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


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


# ============================================================
# 1. Whitelist pg_update_tenant_params
# ============================================================

def test_pg_update_tenant_params_accepts_practitioner_name_and_string_fields():
    from backend import tenants_pg

    captured = {}

    def _fake_psycopg_connect(url):
        class Cur:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def execute(self_inner, q, params):
                captured.setdefault("queries", []).append((q, params))

            @property
            def rowcount(self_inner):
                return 1

        class Conn:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def cursor(self_inner):
                return Cur()

            def commit(self_inner):
                captured["committed"] = True

        return Conn()

    fake_psycopg = type("M", (), {"connect": staticmethod(_fake_psycopg_connect)})()

    with patch.dict(sys.modules, {"psycopg": fake_psycopg}):
        with patch("backend.tenants_pg._pg_url", return_value="postgres://test"):
            with patch("backend.tenants_pg.pg_get_tenant_params", return_value=({}, "pg")):
                with patch("backend.tenants_pg.set_tenant_id_on_connection"):
                    ok = tenants_pg.pg_update_tenant_params(
                        42,
                        {
                            "practitioner_name": "Dr Test",
                            "website_url": "https://test.fr",
                            "public_slug": "dr-test",
                        },
                    )
    assert ok is True
    # Le merge contient bien nos clés (sérialisées dans le payload JSON d'écriture tenant_config).
    upd = [q for q in captured["queries"] if "INSERT INTO tenant_config" in q[0] or "UPDATE tenant_config" in q[0]]
    assert upd, "Une écriture tenant_config doit avoir été exécutée"
    payload_str = upd[0][1][-1]  # dernier param = json.dumps(merged)
    assert "practitioner_name" in payload_str
    assert "website_url" in payload_str
    assert "public_slug" in payload_str


def test_pg_update_tenant_params_normalizes_bools_and_ints():
    from backend import tenants_pg

    captured_payload = {}

    def _fake_connect(url):
        class Cur:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def execute(self_inner, q, params):
                if "INSERT INTO tenant_config" in q or "UPDATE tenant_config" in q:
                    captured_payload["merged"] = params[-1]

            @property
            def rowcount(self_inner):
                return 1

        class Conn:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def cursor(self_inner):
                return Cur()

            def commit(self_inner):
                pass

        return Conn()

    fake_psycopg = type("M", (), {"connect": staticmethod(_fake_connect)})()

    with patch.dict(sys.modules, {"psycopg": fake_psycopg}):
        with patch("backend.tenants_pg._pg_url", return_value="postgres://test"):
            with patch("backend.tenants_pg.pg_get_tenant_params", return_value=({}, "pg")):
                with patch("backend.tenants_pg.set_tenant_id_on_connection"):
                    tenants_pg.pg_update_tenant_params(
                        7,
                        {
                            "accepts_new_patients": "true",
                            "temporary_closure_enabled": 1,
                            "default_appointment_duration_minutes": "45",
                            "minimum_booking_notice_hours": 12.0,
                            "languages": ["fr", "en"],
                        },
                    )

    import json as _json
    merged = _json.loads(captured_payload["merged"])
    assert merged["accepts_new_patients"] is True
    assert merged["temporary_closure_enabled"] is True
    assert merged["default_appointment_duration_minutes"] == 45
    assert merged["minimum_booking_notice_hours"] == 12
    assert merged["languages"] == ["fr", "en"]


def test_canonicalize_cabinet_params_maps_legacy_wizard_keys():
    from backend.cabinet_profile_pg import canonicalize_cabinet_params

    out = canonicalize_cabinet_params(
        {
            "primary_practitioner_name": "Dr Legacy",
            "address": "12 rue Example",
            "current_phone_number": "+33123456789",
            "profession": "Médecine générale",
        }
    )
    assert out["practitioner_name"] == "Dr Legacy"
    assert out["address_line1"] == "12 rue Example"
    assert out["address_line"] == "12 rue Example"
    assert out["phone_number"] == "+33123456789"
    assert out["specialty_label"] == "Médecine générale"


def test_pg_update_tenant_params_canonicalizes_legacy_wizard_keys():
    from backend import tenants_pg

    captured_payload = {}

    def _fake_connect(url):
        class Cur:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def execute(self_inner, q, params):
                if "INSERT INTO tenant_config" in q or "UPDATE tenant_config" in q:
                    captured_payload["merged"] = params[-1]

            @property
            def rowcount(self_inner):
                return 1

        class Conn:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def cursor(self_inner):
                return Cur()

            def commit(self_inner):
                pass

        return Conn()

    fake_psycopg = type("M", (), {"connect": staticmethod(_fake_connect)})()

    with patch.dict(sys.modules, {"psycopg": fake_psycopg}):
        with patch("backend.tenants_pg._pg_url", return_value="postgres://test"):
            with patch("backend.tenants_pg.pg_get_tenant_params", return_value=({}, "pg")):
                with patch("backend.tenants_pg.set_tenant_id_on_connection"):
                    tenants_pg.pg_update_tenant_params(
                        11,
                        {
                            "primary_practitioner_name": "Dr Wizard",
                            "address": "1 avenue Test",
                            "current_phone_number": "+33987654321",
                        },
                    )

    import json as _json

    merged = _json.loads(captured_payload["merged"])
    assert merged["practitioner_name"] == "Dr Wizard"
    assert merged["address_line1"] == "1 avenue Test"
    assert merged["phone_number"] == "+33987654321"


def test_pg_update_tenant_params_drops_unknown_keys():
    from backend import tenants_pg

    captured_payload = {}

    def _fake_connect(url):
        class Cur:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def execute(self_inner, q, params):
                if "INSERT INTO tenant_config" in q or "UPDATE tenant_config" in q:
                    captured_payload["merged"] = params[-1]

            @property
            def rowcount(self_inner):
                return 1

        class Conn:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def cursor(self_inner):
                return Cur()

            def commit(self_inner):
                pass

        return Conn()

    fake_psycopg = type("M", (), {"connect": staticmethod(_fake_connect)})()

    with patch.dict(sys.modules, {"psycopg": fake_psycopg}):
        with patch("backend.tenants_pg._pg_url", return_value="postgres://test"):
            with patch("backend.tenants_pg.pg_get_tenant_params", return_value=({}, "pg")):
                with patch("backend.tenants_pg.set_tenant_id_on_connection"):
                    tenants_pg.pg_update_tenant_params(
                        9,
                        {
                            "practitioner_name": "Dr Z",
                            "evil_key": "should_be_dropped",
                            "another_unknown": 42,
                        },
                    )

    import json as _json
    merged = _json.loads(captured_payload["merged"])
    assert merged.get("practitioner_name") == "Dr Z"
    assert "evil_key" not in merged
    assert "another_unknown" not in merged


def test_pg_update_tenant_params_accepts_dashboard_team_note_keys():
    from backend import tenants_pg

    captured_payload = {}

    def _fake_connect(url):
        class Cur:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def execute(self_inner, q, params):
                if "INSERT INTO tenant_config" in q or "UPDATE tenant_config" in q:
                    captured_payload["merged"] = params[-1]

            @property
            def rowcount(self_inner):
                return 1

        class Conn:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def cursor(self_inner):
                return Cur()

            def commit(self_inner):
                pass

        return Conn()

    fake_psycopg = type("M", (), {"connect": staticmethod(_fake_connect)})()

    with patch.dict(sys.modules, {"psycopg": fake_psycopg}):
        with patch("backend.tenants_pg._pg_url", return_value="postgres://test"):
            with patch("backend.tenants_pg.pg_get_tenant_params", return_value=({}, "pg")):
                with patch("backend.tenants_pg.set_tenant_id_on_connection"):
                    tenants_pg.pg_update_tenant_params(
                        12,
                        {
                            "dashboard_team_note": "Note persistée",
                            "dashboard_team_note_updated_at": "2026-06-07T12:00:00Z",
                        },
                    )

    import json as _json

    merged = _json.loads(captured_payload["merged"])
    assert merged["dashboard_team_note"] == "Note persistée"
    assert merged["dashboard_team_note_updated_at"] == "2026-06-07T12:00:00Z"


# ============================================================
# 2. PATCH /api/tenant/profile : double écriture PG + params_json
# ============================================================

@patch("backend.routes.tenant.pg_get_tenant_user_by_id")
@patch("backend.routes.tenant.pg_update_tenant_params")
@patch("backend.routes.tenant.pg_update_tenant_name")
@patch("backend.routes.tenant.pg_upsert_profile")
def test_tenant_patch_profile_writes_both_pg_and_params(
    mock_upsert_profile, mock_update_name, mock_update_params, mock_get_user, client
):
    mock_get_user.return_value = {"tenant_id": 3, "email": "c@test.fr", "role": "owner"}
    mock_update_name.return_value = True
    mock_update_params.return_value = True
    mock_upsert_profile.return_value = True

    token = _make_client_token(3, user_id=11)
    payload = {
        "practitioner_name": "Dr Dupont",
        "cabinet_name": "Cabinet Dupont",
        "specialty": "ORL",
        "phone": "0102030405",
        "email": "contact@dupont.fr",
        "address_line": "1 rue Bleue",
        "postal_code": "75009",
        "city": "Paris",
        "website_url": "https://dupont.fr",
        "languages": ["fr"],
        "accepts_new_patients": True,
    }
    res = client.patch(
        "/api/tenant/profile",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert res.status_code == 200, res.text

    # PG normalized table updated
    mock_upsert_profile.assert_called_once()
    args, kwargs = mock_upsert_profile.call_args
    assert args[0] == 3
    pg_payload = args[1]
    assert pg_payload["practitioner_name"] == "Dr Dupont"
    assert pg_payload["cabinet_name"] == "Cabinet Dupont"
    assert pg_payload["languages"] == ["fr"]

    # params_json updated with mapped keys
    mock_update_params.assert_called_once()
    params_args = mock_update_params.call_args[0]
    assert params_args[0] == 3
    params_payload = params_args[1]
    assert params_payload["practitioner_name"] == "Dr Dupont"
    assert params_payload["business_name"] == "Cabinet Dupont"  # cabinet_name → business_name
    assert params_payload["specialty_label"] == "ORL"
    assert params_payload["address_line1"] == "1 rue Bleue"
    assert params_payload["website_url"] == "https://dupont.fr"


# ============================================================
# 3. PATCH /api/tenant/opening-hours : double écriture
# ============================================================

@patch("backend.routes.tenant.pg_get_tenant_user_by_id")
@patch("backend.routes.tenant.pg_update_tenant_params")
@patch("backend.routes.tenant.pg_replace_opening_hours")
def test_tenant_patch_opening_hours_writes_both_pg_and_params(
    mock_replace, mock_update_params, mock_get_user, client
):
    mock_get_user.return_value = {"tenant_id": 4, "email": "c@test.fr", "role": "owner"}
    mock_update_params.return_value = True
    mock_replace.return_value = True

    token = _make_client_token(4, user_id=22)
    body = {
        "opening_hours": [
            {"day": "monday", "is_open": True, "morning_start": "09:00", "morning_end": "12:00",
             "afternoon_start": "14:00", "afternoon_end": "18:00"},
            {"day": "tuesday", "is_open": True, "morning_start": "09:00", "morning_end": "12:00"},
            {"day": "wednesday", "is_open": False},
            {"day": "thursday", "is_open": False},
            {"day": "friday", "is_open": True, "morning_start": "09:00", "morning_end": "17:00"},
            {"day": "saturday", "is_open": False},
            {"day": "sunday", "is_open": False},
        ]
    }
    res = client.patch(
        "/api/tenant/opening-hours",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )
    assert res.status_code == 200, res.text

    mock_replace.assert_called_once()
    assert mock_replace.call_args[0][0] == 4

    mock_update_params.assert_called_once()
    params_payload = mock_update_params.call_args[0][1]
    # params_json doit recevoir opening_hours_json + dérivés booking_days/start/end
    assert "opening_hours_json" in params_payload
    assert isinstance(params_payload["booking_days"], list)
    # Lundi (0), Mardi (1), Vendredi (4) ouverts → triés
    assert sorted(params_payload["booking_days"]) == [0, 1, 4]
    assert params_payload["booking_start_hour"] == 9
    assert params_payload["booking_end_hour"] == 18


# ============================================================
# 4. sync_normalized_from_params dispatche correctement
# ============================================================

@patch("backend.cabinet_profile_pg.upsert_assistant_settings")
@patch("backend.cabinet_profile_pg.upsert_booking_rules")
@patch("backend.cabinet_profile_pg.upsert_availability_settings")
@patch("backend.cabinet_profile_pg.upsert_profile")
def test_sync_normalized_from_params_dispatches_to_correct_upserts(
    mock_profile, mock_avail, mock_booking, mock_assistant
):
    from backend.cabinet_profile_pg import sync_normalized_from_params

    sync_normalized_from_params(
        99,
        {
            "practitioner_name": "Dr Sync",
            "business_name": "Cabinet Sync",
            "phone_number": "0102030405",
            "default_appointment_duration_minutes": 30,
            "temporary_closure_enabled": True,
            "temporary_closure_start": "2026-08-01",
            "welcome_message": "Bienvenue",
            "documents_to_bring": "Carte vitale",
        },
    )

    mock_profile.assert_called_once()
    profile_args = mock_profile.call_args[0]
    assert profile_args[0] == 99
    assert profile_args[1]["practitioner_name"] == "Dr Sync"
    assert profile_args[1]["cabinet_name"] == "Cabinet Sync"

    mock_avail.assert_called_once()
    assert mock_avail.call_args[0][1]["temporary_closure_enabled"] is True

    mock_booking.assert_called_once()
    assert mock_booking.call_args[0][1]["default_appointment_duration_minutes"] == 30

    mock_assistant.assert_called_once()
    assert mock_assistant.call_args[0][1]["welcome_message"] == "Bienvenue"


# ============================================================
# 5. Sync n'appelle pas les upserts si rien à syncer
# ============================================================

@patch("backend.cabinet_profile_pg.upsert_assistant_settings")
@patch("backend.cabinet_profile_pg.upsert_booking_rules")
@patch("backend.cabinet_profile_pg.upsert_availability_settings")
@patch("backend.cabinet_profile_pg.upsert_profile")
def test_sync_normalized_from_params_skips_when_no_relevant_keys(
    mock_profile, mock_avail, mock_booking, mock_assistant
):
    from backend.cabinet_profile_pg import sync_normalized_from_params

    sync_normalized_from_params(99, {"unrelated_key": "x"})

    mock_profile.assert_not_called()
    mock_avail.assert_not_called()
    mock_booking.assert_not_called()
    mock_assistant.assert_not_called()
