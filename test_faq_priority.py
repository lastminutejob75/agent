# tests/test_faq_priority.py
"""
Tests pour le système de priorité FAQ.
"""

import pytest
from backend.tools_faq import default_faq_store


def test_faq_salutation_matches_when_included():
    """Test : "bonjour" seul doit matcher FAQ_SALUTATION si include_low=True"""
    store = default_faq_store()
    r = store.search("bonjour", include_low=True)
    assert r.match is True
    assert r.faq_id == "FAQ_SALUTATION"


def test_salutation_not_returned_when_low_excluded():
    """Test : "bonjour je veux un rdv" ne doit PAS matcher FAQ_SALUTATION si include_low=False"""
    store = default_faq_store()
    r = store.search("bonjour je veux un rdv", include_low=False)
    assert not (r.match and r.faq_id == "FAQ_SALUTATION")


def test_normal_faq_searchable_when_low_excluded():
    """Test : Les FAQs priority="normal" doivent être trouvées même avec include_low=False"""
    store = default_faq_store()
    r = store.search("quels sont vos horaires", include_low=False)
    assert r.match is True
    assert r.faq_id == "FAQ_HORAIRES"
