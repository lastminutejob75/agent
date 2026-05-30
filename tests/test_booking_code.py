from backend.booking_code import (
    BOOKING_CODE_ALPHABET,
    format_booking_code,
    generate_booking_code,
    normalize_booking_code,
)


def test_generate_booking_code_length_and_alphabet():
    code = generate_booking_code()
    assert len(code) == 6
    assert all(ch in BOOKING_CODE_ALPHABET for ch in code)


def test_normalize_booking_code_strips_prefix():
    assert normalize_booking_code("RDV-A7K3M2") == "A7K3M2"
    assert normalize_booking_code("rdv-a7k3m2") == "A7K3M2"
    assert normalize_booking_code("A7K3M2") == "A7K3M2"


def test_format_booking_code_adds_prefix():
    assert format_booking_code("A7K3M2") == "RDV-A7K3M2"
    assert format_booking_code("RDV-A7K3M2") == "RDV-A7K3M2"
