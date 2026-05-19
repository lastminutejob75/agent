"""Tests construction patch backfill profil."""
from scripts.backfill_tenant_profile_from_params import _build_patch, _parse_wizard_notes


def test_parse_wizard_notes_json():
    raw = '{"wizard":"tenant_create_v1","practitioner":"Dr Test","address":"12 rue X","city":"Lyon"}'
    w = _parse_wizard_notes(raw)
    assert w.get("practitioner") == "Dr Test"
    assert w.get("city") == "Lyon"


def test_build_patch_from_legacy_keys():
    params = {
        "primary_practitioner_name": "Dr Legacy",
        "address": "1 avenue Test",
        "current_phone_number": "+33123456789",
        "contact_email": "cab@test.fr",
    }
    patch = _build_patch(params, "Cabinet Nom")
    assert patch["practitioner_name"] == "Dr Legacy"
    assert patch["address_line1"] == "1 avenue Test"
    assert patch["phone_number"] == "+33123456789"
    assert patch["business_name"] == "Cabinet Nom"
