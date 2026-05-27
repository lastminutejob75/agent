from backend.routes.tenant import _looks_like_google_event_id


def test_looks_like_google_event_id():
    assert _looks_like_google_event_id("abc123xyz") is True
    assert _looks_like_google_event_id("42") is False
    assert _looks_like_google_event_id("") is False
    assert _looks_like_google_event_id(None) is False
