"""Tests tenant_routing (DID → tenant_id)."""
import pytest
from backend.tenant_routing import (
    normalize_did,
    resolve_tenant_id_from_vocal_call,
    extract_to_number_from_vapi_payload,
    add_route,
)
from backend import config, db


def test_normalize_did():
    assert normalize_did("+33 1 23 45 67 89") == "+33123456789"
    assert normalize_did("0033123456789") == "+33123456789"
    assert normalize_did("  +33 6 12 34 56 78  ") == "+33612345678"
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

    tid, source = resolve_tenant_id_from_vocal_call("+33 1 23 45 67 89")
    assert tid == 1
    assert source == "route"

    tid, source = resolve_tenant_id_from_vocal_call("+33612345678")
    assert tid == 2
    assert source == "route"

    tid, source = resolve_tenant_id_from_vocal_call("+33876543210")
    assert tid == config.DEFAULT_TENANT_ID
    assert source == "default"


def test_extract_to_number_from_vapi_payload():
    # phoneNumber.number (top-level)
    p = {"phoneNumber": {"number": "+33123456789"}}
    assert extract_to_number_from_vapi_payload(p) == "+33123456789"

    # call.phoneNumber.number
    p = {"call": {"phoneNumber": {"number": "+33612345678"}}}
    assert extract_to_number_from_vapi_payload(p) == "+33612345678"

    # call.to
    p = {"call": {"to": "+33765432109"}}
    assert extract_to_number_from_vapi_payload(p) == "+33765432109"

    # fallback
    assert extract_to_number_from_vapi_payload({}) is None
    assert extract_to_number_from_vapi_payload({"call": {}}) is None
