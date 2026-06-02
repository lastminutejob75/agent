"""Fuseau horaire : création RDV cabinet — l'heure choisie doit correspondre au créneau local."""

from backend.routes.tenant import (
    _tenant_agenda_compute_end_iso,
    _tenant_agenda_parse_start_local,
)


def test_parse_start_local_naive_wall_clock():
    date_str, time_str, dt = _tenant_agenda_parse_start_local("2026-06-26T14:45:00", "Europe/Paris")
    assert date_str == "2026-06-26"
    assert time_str == "14:45"
    assert dt.hour == 14 and dt.minute == 45


def test_parse_start_local_utc_converts_to_paris_summer():
    date_str, time_str, _dt = _tenant_agenda_parse_start_local(
        "2026-06-26T12:45:00+00:00",
        "Europe/Paris",
    )
    assert date_str == "2026-06-26"
    assert time_str == "14:45"


def test_compute_end_iso_preserves_local_wall_clock():
    end = _tenant_agenda_compute_end_iso("2026-06-26T14:45:00", tenant_id=1, end_iso_in="", tz_name="Europe/Paris")
    assert end.startswith("2026-06-26T15:15:00")
