from backend.booking_code import format_booking_code, normalize_booking_code
from backend.public_action_tokens import decode_public_action_token, issue_public_action_token
from backend.public_bookings_pg import _contact_email_matches, _contact_phone_matches


def test_public_action_token_roundtrip():
    token = issue_public_action_token(
        tenant_id=42,
        source_type="public_booking",
        source_id="abc-123",
        booking_code="A7K3M2",
    )
    payload = decode_public_action_token(token)
    assert payload is not None
    assert payload["tenant_id"] == 42
    assert payload["source_type"] == "public_booking"
    assert payload["source_id"] == "abc-123"
    assert payload["booking_code"] == "A7K3M2"


def test_contact_phone_matches_normalized():
    assert _contact_phone_matches("0612345678", "+33612345678")
    assert not _contact_phone_matches("0612345678", "+33698765432")


def test_contact_email_matches_case_insensitive():
    assert _contact_email_matches("Patient@Email.com", "patient@email.com")
    assert not _contact_email_matches("a@b.com", "c@d.com")


def test_format_booking_code_in_lookup_response():
    assert format_booking_code(normalize_booking_code("RDV-Z9X8Y7")) == "RDV-Z9X8Y7"
