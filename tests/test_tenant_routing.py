"""Tests tenant_routing (DID → tenant_id)."""
import pytest
from unittest.mock import patch
from backend.tenant_routing import (
    normalize_did,
    resolve_tenant_id_from_vocal_call,
    resolve_tenant_id_from_vapi_payload,
    extract_to_number_from_vapi_payload,
    extract_customer_phone_from_vapi_payload,
    add_route,
)
from backend import config, db


def test_normalize_did():
    assert normalize_did("+33 1 23 45 67 89") == "+33123456789"
    assert normalize_did("0033123456789") == "+33123456789"
    assert normalize_did("  +33 6 12 34 56 78  ") == "+33612345678"
    assert normalize_did("sip:+33612345678@sip.twilio.com;transport=tls") == "+33612345678"
    assert normalize_did("tel:+33612345678") == "+33612345678"
    assert normalize_did("") == ""
    assert normalize_did(None) == ""


def test_resolve_default_when_no_route():
    tid, source = resolve_tenant_id_from_vocal_call("+33999999999")
    assert tid == config.DEFAULT_TENANT_ID
    assert source == "default"


def test_resolve_route_when_mapped():
    db.ensure_tenant_config()
    add_route("vocal", "+33123456789", 1)
    add_route("vocal", "+33612345678", 2)
    add_route("vocal", "+33912345678", 3)

    tid, source = resolve_tenant_id_from_vocal_call("+33 1 23 45 67 89")
    assert tid == 1
    assert source == "route"

    tid, source = resolve_tenant_id_from_vocal_call("+33612345678")
    assert tid == 2
    assert source == "route"

    tid, source = resolve_tenant_id_from_vocal_call("sip:+33612345678@sip.twilio.com;transport=tls")
    assert tid == 2
    assert source == "route"

    tid, source = resolve_tenant_id_from_vocal_call("+33876543210")
    assert tid == config.DEFAULT_TENANT_ID
    assert source == "default"

    tid, source = resolve_tenant_id_from_vocal_call("09 12 34 56 78")
    assert tid == 3
    assert source == "route"


def test_extract_to_number_from_vapi_payload():
    # phoneNumber.number (top-level)
    p = {"phoneNumber": {"number": "+33123456789"}}
    assert extract_to_number_from_vapi_payload(p) == "+33123456789"

    # call.to must win over call.phoneNumber.number when both exist
    p = {"message": {"call": {"to": "+33765432109", "phoneNumber": {"number": "+33612345678"}}}}
    assert extract_to_number_from_vapi_payload(p) == "+33765432109"

    # call.phoneNumber.number
    p = {"call": {"phoneNumber": {"number": "+33612345678"}}}
    assert extract_to_number_from_vapi_payload(p) == "+33612345678"

    # call.to
    p = {"call": {"to": "+33765432109"}}
    assert extract_to_number_from_vapi_payload(p) == "+33765432109"

    # fallback
    assert extract_to_number_from_vapi_payload({}) is None
    assert extract_to_number_from_vapi_payload({"call": {}}) is None


def test_extract_customer_phone_from_vapi_payload():
    """Reconnaissance du numéro appelant (caller ID) pour QUALIF_CONTACT."""
    # call.customer.number
    p = {"call": {"customer": {"number": "+33612345678"}}}
    assert extract_customer_phone_from_vapi_payload(p) == "+33612345678"

    # customer.number (racine)
    p = {"customer": {"number": "0612345678"}}
    assert extract_customer_phone_from_vapi_payload(p) == "0612345678"

    # call.from
    p = {"call": {"from": "+33698765432"}}
    assert extract_customer_phone_from_vapi_payload(p) == "+33698765432"

    # customerNumber / callerNumber (racine)
    p = {"callerNumber": "0611223344"}
    assert extract_customer_phone_from_vapi_payload(p) == "0611223344"

    # fallback: aucun numéro valide (longueur >= 10)
    assert extract_customer_phone_from_vapi_payload({}) is None
    assert extract_customer_phone_from_vapi_payload({"call": {}}) is None


@patch("backend.tenants_pg.pg_find_tenant_id_by_vapi_assistant_id", return_value=7)
def test_resolve_vapi_payload_falls_back_to_assistant_id(mock_lookup):
    payload = {
        "message": {
            "call": {
                "assistantId": "asst_live_123",
            }
        }
    }

    with patch("backend.tenant_routing.config.USE_PG_TENANTS", True):
        tid, source = resolve_tenant_id_from_vapi_payload(payload, channel="vocal")

    assert tid == 7
    assert source == "assistant"
    mock_lookup.assert_called_once_with("asst_live_123")


def test_resolve_vapi_payload_prefers_did_over_fast_cache():
    payload = {
        "message": {
            "call": {
                "assistantId": "asst_default_1",
                "phoneNumber": {"number": "+33612345678"},
            }
        }
    }

    with patch("backend.tenant_routing._fast_resolve_assistant_id", return_value=1):
        tid, source = resolve_tenant_id_from_vapi_payload(payload, channel="vocal")

    assert tid == 2
    assert source == "route"


@patch("backend.tenants_pg.pg_tenant_exists", return_value=False)
def test_ensure_test_number_route_skips_missing_pg_tenant(mock_exists):
    from backend.tenant_routing import ensure_test_number_route

    with patch("backend.tenant_routing.config.USE_PG_TENANTS", True):
        with patch("backend.tenant_routing.config.TEST_VOCAL_NUMBER", "+33939240575"):
            with patch("backend.tenant_routing.config.TEST_TENANT_ID", 2):
                with patch("backend.tenant_routing.add_route") as mock_add_route:
                    with patch("backend.tenants_pg.pg_add_routing") as mock_pg_add_routing:
                        assert ensure_test_number_route() is True

    mock_add_route.assert_called_once()
    mock_pg_add_routing.assert_not_called()
