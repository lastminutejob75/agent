#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys

from dotenv import load_dotenv


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    env_path = repo_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    # Import apres load_dotenv pour que backend.config lise les bonnes variables.
    import backend.config as config
    from backend.google_calendar import (
        GoogleCalendarNotFoundError,
        GoogleCalendarPermissionError,
        GoogleCalendarService,
    )

    parser = argparse.ArgumentParser(
        description="Teste localement la lecture de creneaux Google Calendar."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=3,
        help="Nombre de jours a sonder a partir de demain",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Nombre maximum de creneaux a afficher",
    )
    parser.add_argument(
        "--book",
        action="store_true",
        help="Reserve puis annule le premier creneau trouve pour verifier l'ecriture.",
    )
    args = parser.parse_args()

    print("== Test Google Calendar local ==")
    print(f".env charge: {env_path.exists()}")

    try:
        config.load_google_credentials()
    except Exception as exc:
        print(f"ERREUR credentials: {exc}")
        return 1

    calendar_id = (config.GOOGLE_CALENDAR_ID or "").strip()
    print(f"calendar_id_set: {bool(calendar_id)}")
    print(f"service_account_file: {config.SERVICE_ACCOUNT_FILE}")

    if not calendar_id:
        print("ERREUR: GOOGLE_CALENDAR_ID vide dans .env")
        return 1

    try:
        service = GoogleCalendarService(calendar_id)
        start_day = datetime.now() + timedelta(days=1)
        dates = [start_day + timedelta(days=i) for i in range(max(args.days, 1))]
        slots = service.get_free_slots_range(dates=dates, limit=max(args.limit, 1))
    except GoogleCalendarPermissionError as exc:
        print(f"ERREUR permission Google Calendar: {exc}")
        print("Verifier que le calendrier est partage avec le service account en mode writer.")
        return 2
    except GoogleCalendarNotFoundError as exc:
        print(f"ERREUR calendrier introuvable: {exc}")
        print("Verifier GOOGLE_CALENDAR_ID dans .env.")
        return 3
    except Exception as exc:
        print(f"ERREUR appel Google Calendar: {exc}")
        return 4

    print(f"slots_found: {len(slots)}")
    for idx, slot in enumerate(slots, start=1):
        print(
            f"{idx}. {slot.get('label')} | start={slot.get('start')} | end={slot.get('end')}"
        )

    if not slots:
        print("Aucun creneau remonte. Soit le calendrier est plein, soit la lecture echoue silencieusement.")
        return 5

    if not args.book:
        return 0

    first_slot = slots[0]
    print("Tentative de booking de test sur le premier creneau...")
    event_id = service.book_appointment(
        start_time=first_slot["start"],
        end_time=first_slot["end"],
        patient_name="Test Local UWI",
        patient_contact="local@test.invalid",
        motif="Verification locale Google Calendar",
    )
    if not event_id:
        print("ERREUR booking: aucun event_id retourne.")
        return 6

    print(f"booking_ok: {event_id}")
    cancelled = service.cancel_appointment(event_id)
    print(f"cancel_ok: {cancelled}")
    if not cancelled:
        print("ATTENTION: le RDV test a ete cree mais pas annule automatiquement.")
        return 7

    return 0


if __name__ == "__main__":
    sys.exit(main())
