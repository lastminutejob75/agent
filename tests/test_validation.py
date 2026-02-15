# tests/test_validation.py
"""
Tests de la couche validation avant TTS (critical / template / ai_generated).
- critical allowlist ok/fail -> fallback
- template exact ok/mismatch -> fallback
- ai_generated forbidden word -> fallback
- fallback = texte exact technical_transfer (prompts.py)
"""
import pytest
from backend import prompts
from backend.validation import validate_response
from backend.validation_config import STATE_VALIDATION_RULES


def test_critical_allowlist_ok():
    """Message exact dans l'allowlist (TRANSFERRED) -> valid, texte inchangé."""
    expected = prompts.get_message("technical_transfer", channel="vocal")
    valid, text = validate_response("TRANSFERRED", expected, channel="vocal")
    assert valid is True
    assert text.strip() == expected.strip()


def test_critical_allowlist_fail_fallback():
    """Message hors allowlist pour state critique -> invalid, fallback technical_transfer."""
    valid, text = validate_response(
        "TRANSFERRED",
        "Une phrase improvisée qui ne doit pas passer.",
        channel="vocal",
    )
    assert valid is False
    fallback = prompts.get_message("technical_transfer", channel="vocal")
    assert text.strip() == fallback.strip()


def test_template_exact_ok():
    """Template state avec candidat exact -> valid."""
    candidates = ["Quel est votre nom ?", "À quel nom ?"]
    valid, text = validate_response(
        "QUALIF_NAME",
        "Quel est votre nom ?",
        channel="vocal",
        template_candidates=candidates,
    )
    assert valid is True
    assert "nom" in text


def test_template_mismatch_fallback():
    """Template state avec texte qui ne matche pas -> invalid, fallback."""
    candidates = ["Quel est votre nom ?"]
    valid, text = validate_response(
        "QUALIF_NAME",
        "Texte qui ne matche pas le template.",
        channel="vocal",
        template_candidates=candidates,
    )
    assert valid is False
    fallback = prompts.get_message("technical_transfer", channel="vocal")
    assert text.strip() == fallback.strip()


def test_ai_forbidden_word_fallback():
    """ai_generated avec mot interdit (ex: prescription) -> invalid, fallback."""
    valid, text = validate_response(
        "COLLECT_REASON",
        "Je vous prescris un médicament pour la douleur.",
        channel="vocal",
    )
    assert valid is False
    fallback = prompts.get_message("technical_transfer", channel="vocal")
    assert text.strip() == fallback.strip()


def test_ai_ok_short():
    """ai_generated phrase courte sans interdit -> valid."""
    valid, text = validate_response(
        "COLLECT_REASON",
        "Pour un renouvellement.",
        channel="vocal",
    )
    assert valid is True
    assert "renouvellement" in text


def test_fallback_uses_technical_transfer_exact():
    """Fallback doit être exactement le message technical_transfer de prompts.py."""
    fallback_vocal = prompts.get_message("technical_transfer", channel="vocal")
    fallback_web = prompts.get_message("technical_transfer", channel="web")
    assert fallback_vocal and "conseiller" in fallback_vocal
    # Sur échec validation, on renvoie ce texte
    _, text = validate_response("TRANSFERRED", "n'importe quoi", channel="vocal")
    assert text.strip() == fallback_vocal.strip()
    _, text_web = validate_response("TRANSFERRED", "n'importe quoi", channel="web")
    assert text_web.strip() == fallback_web.strip()


def test_unknown_state_fallback():
    """État inconnu -> config default -> critical, fallback si texte pas dans allowlist."""
    valid, text = validate_response(
        "UNKNOWN_STATE_XYZ",
        "Un message quelconque.",
        channel="vocal",
    )
    assert valid is False
    fallback = prompts.get_message("technical_transfer", channel="vocal")
    assert text.strip() == fallback.strip()
