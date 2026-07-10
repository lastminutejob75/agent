"""
Vérification du chemin de réservation Google Calendar :
- book_appointment() construit le bon body et appelle l'API
- book_slot_from_session() avec source google appelle _book_google_by_iso avec les bons paramètres
"""

import pytest
import hashlib

from backend.google_calendar import GoogleCalendarService


def test_book_appointment_calls_api_with_correct_body(monkeypatch):
    """book_appointment construit l'event avec summary, start/end Europe/Paris et appelle insert().execute()."""
    insert_calls = []

    def fake_insert(calendarId=None, body=None):
        insert_calls.append({"calendarId": calendarId, "body": body})

        class FakeExecute:
            def execute(self):
                return {"id": "evt_test_123"}

        return FakeExecute()

    def fake_events():
        class FakeEvents:
            def insert(self, calendarId=None, body=None):
                return fake_insert(calendarId=calendarId, body=body)
        return FakeEvents()

    class FakeService:
        def events(self):
            return fake_events()

    def fake_build_service(self):
        return FakeService()

    monkeypatch.setattr(GoogleCalendarService, "_build_service", fake_build_service)

    # config pour éviter erreur au constructeur (calendar_id utilisé dans log)
    service = GoogleCalendarService(calendar_id="test@group.calendar.google.com")

    event_id = service.book_appointment(
        start_time="2026-02-04T14:00:00",
        end_time="2026-02-04T14:15:00",
        patient_name="Jean Dupont",
        patient_contact="jean@example.com",
        motif="Consultation",
        timezone_name="America/Montreal",
    )

    assert event_id == "evt_test_123"
    assert len(insert_calls) == 1
    body = insert_calls[0]["body"]
    assert body["summary"] == "RDV - Jean Dupont"
    assert "Jean Dupont" in body["description"] and "jean@example.com" in body["description"] and "Consultation" in body["description"]
    assert body["start"]["dateTime"] == "2026-02-04T14:00:00"
    assert body["start"]["timeZone"] == "America/Montreal"
    assert body["end"]["dateTime"] == "2026-02-04T14:15:00"
    assert body["end"]["timeZone"] == "America/Montreal"
    assert insert_calls[0]["calendarId"] == "test@group.calendar.google.com"


def test_book_appointment_recovers_event_after_ambiguous_timeout(monkeypatch):
    contact = "jean@example.com"
    start = "2026-02-04T14:00:00"
    key = hashlib.sha256(f"{contact}|{start}".encode("utf-8")).hexdigest()
    calls = {"insert": 0, "list": 0}

    class FakeEvents:
        def insert(self, **kwargs):
            calls["insert"] += 1

            class Request:
                def execute(self):
                    raise TimeoutError("read timed out after commit")

            return Request()

        def list(self, **kwargs):
            calls["list"] += 1
            assert kwargs["privateExtendedProperty"] == [f"uwiIdempotencyKey={key}"]

            class Request:
                def execute(self):
                    return {
                        "items": [{
                            "id": "evt_recovered",
                            "status": "confirmed",
                            "extendedProperties": {"private": {"uwiIdempotencyKey": key}},
                        }]
                    }

            return Request()

    class FakeService:
        def events(self):
            return FakeEvents()

    monkeypatch.setattr(GoogleCalendarService, "_build_service", lambda self: FakeService())
    service = GoogleCalendarService("timeout@test.calendar.google.com")
    event_id = service.book_appointment(
        start_time=start,
        end_time="2026-02-04T14:15:00",
        patient_name="Jean",
        patient_contact=contact,
        motif="Consultation",
    )

    assert event_id == "evt_recovered"
    assert calls == {"insert": 1, "list": 1}
