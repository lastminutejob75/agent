# tests/test_faq_horaires_shorthand.py
"""Questions horaires en langage chat (c quoi, typos)."""

from backend.intent_parser import Intent, detect_intent, detect_strong_intent, _is_repeat
from backend.tools_faq import default_faq_store


def test_c_quoi_horaires_not_repeat():
    assert _is_repeat("c quoi vos horraires") is False
    assert detect_intent("c quoi vos horraires", "START") == Intent.FAQ
    assert detect_strong_intent("c quoi vos horraires") == Intent.FAQ


def test_c_est_quoi_horaires_faq_intent():
    assert detect_intent("c'est quoi vos horaires", "START") == Intent.FAQ


def test_faq_search_c_quoi_horaires():
    store = default_faq_store()
    r = store.search("c quoi vos horraires", include_low=False)
    assert r.match is True
    assert r.faq_id == "FAQ_HORAIRES"
