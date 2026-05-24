# tests/test_leads_sort.py
"""Tri leads : plus récents en premier."""

from backend.leads_pg import _lead_arrival_dt, _sort_rows


def test_sort_rows_created_desc_newest_first():
    rows = [
        {"created_at": "2026-01-10T10:00:00+00:00", "score": 90},
        {"created_at": "2026-05-20T08:00:00+00:00", "score": 10},
        {"created_at": "2026-03-01T12:00:00+00:00", "score": 50},
    ]
    out = _sort_rows(rows, "created_desc")
    assert out[0]["created_at"].startswith("2026-05-20")
    assert out[-1]["created_at"].startswith("2026-01-10")


def test_lead_arrival_dt_uses_last_submitted():
    older = "2020-01-01T10:00:00+00:00"
    recent = "2026-05-22T14:00:00+00:00"
    row = {"created_at": older, "last_submitted_at": recent, "updated_at": older}
    assert _lead_arrival_dt(row).isoformat().startswith("2026-05-22")
