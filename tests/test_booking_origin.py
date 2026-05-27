from backend.booking_origin import (
    PRATICIEN,
    PUBLIC_PAGE,
    VOICE,
    canonical,
    display_origin_label,
    normalize_for_agenda,
)


def test_canonical_aliases():
    assert canonical("vapi") == VOICE
    assert canonical("page_publique") == PUBLIC_PAGE
    assert canonical("cabinet_ui") == PRATICIEN


def test_display_origin_label_three_origins():
    assert display_origin_label(VOICE) == "Agent vocal"
    assert display_origin_label(PUBLIC_PAGE) == "Page publique"
    assert display_origin_label(PRATICIEN) == "Agenda UWi · praticien"
    assert display_origin_label("") == "Non précisée"


def test_normalize_for_agenda():
    assert normalize_for_agenda("voice") == VOICE
    assert normalize_for_agenda(None) == "unknown"
