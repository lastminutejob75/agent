from datetime import datetime


def test_reconcile_recreates_safe_uwi_google_orphan(monkeypatch):
    from backend import reconcile_calendar
    from backend import tools_booking
    from backend.routes import admin, tenant

    detail = {
        "tenant_id": 12,
        "params": {
            "calendar_provider": "google",
            "calendar_id": "cabinet@test.calendar.google.com",
            "timezone": "America/Montreal",
        },
    }
    event = {
        "id": "evt_orphan",
        "summary": "RDV - Claire",
        "description": "Patient: Claire\nContact: +15145550123\nMotif: Suivi",
        "start": {"dateTime": "2026-07-15T10:00:00-04:00"},
        "end": {"dateTime": "2026-07-15T10:15:00-04:00"},
    }
    captured = {}

    monkeypatch.setattr(admin, "_get_tenant_detail", lambda tenant_id: detail)
    monkeypatch.setattr(tenant, "_tenant_timezone", lambda value: "America/Montreal")
    monkeypatch.setattr(reconcile_calendar, "_list_google_events", lambda *args, **kwargs: [event])
    monkeypatch.setattr(reconcile_calendar, "_list_local_mirror_appointments", lambda *args, **kwargs: {})

    def mirror(session, start_iso, event_id):
        captured["tenant_id"] = session.tenant_id
        captured["start_iso"] = start_iso
        captured["event_id"] = event_id
        captured["contact"] = session.qualif_data.contact
        return True

    monkeypatch.setattr(tools_booking, "_mirror_google_booking_to_internal", mirror)

    report = reconcile_calendar.reconcile_tenant(12, window_days=30)

    assert report["orphan_google_events"] == 1
    assert report["orphan_google_mirrors_recreated"] == 1
    assert captured == {
        "tenant_id": 12,
        "start_iso": "2026-07-15T10:00:00-04:00",
        "event_id": "evt_orphan",
        "contact": "+15145550123",
    }
