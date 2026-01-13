# tests/test_vocal_email_min.py

from backend.guards import parse_vocal_email_min, looks_like_dictated_email


def test_parse_simple():
    """Test parsing basique"""
    result = parse_vocal_email_min("jean arobase gmail point com")
    assert result == "jean@gmail.com"


def test_parse_complex():
    """Test parsing avec point dans nom"""
    result = parse_vocal_email_min("jean point dupont arobase gmail point com")
    assert result == "jean.dupont@gmail.com"


def test_parse_variants():
    """Test variantes anglaises"""
    result = parse_vocal_email_min("test at example dot org")
    assert result == "test@example.org"


def test_looks_like_dictated():
    """Test détection email dicté"""
    assert looks_like_dictated_email("jean arobase gmail point com") is True
    assert looks_like_dictated_email("test at example dot org") is True
    assert looks_like_dictated_email("jean@gmail.com") is False
    assert looks_like_dictated_email("0612345678") is False


def test_no_false_positive():
    """Test pas de faux positif"""
    # "point" tout seul ne suffit pas (besoin arobase)
    result = parse_vocal_email_min("jean dupont")
    assert result == "jeandupont"  # Juste enlève espaces, pas de parsing

