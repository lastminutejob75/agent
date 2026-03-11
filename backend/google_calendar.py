# backend/google_calendar.py

from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
import logging
from googleapiclient.errors import HttpError

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore

CALENDAR_TZ = "Europe/Paris"

logger = logging.getLogger(__name__)

# Configuration
import backend.config as cfg  # Import du MODULE (pas from import)

SCOPES = ['https://www.googleapis.com/auth/calendar']


class GoogleCalendarError(Exception):
    """Erreur Google Calendar générique remontée à l'appelant."""

    def __init__(self, error: Exception):
        self.error = error
        self.http_error = error if isinstance(error, HttpError) else None
        self.status = getattr(getattr(error, "resp", None), "status", None)
        super().__init__(str(error))


class GoogleCalendarPermissionError(GoogleCalendarError):
    """403 Forbidden : le compte de service n'a pas les droits requis sur le calendrier."""


class GoogleCalendarNotFoundError(GoogleCalendarError):
    """404 Not Found : l'identifiant du calendrier est invalide ou introuvable."""


class GoogleCalendarService:
    """Service Google Calendar pour gérer les RDV."""

    def __init__(self, calendar_id: str):
        """
        Args:
            calendar_id: ID du Google Calendar (ex: xxx@group.calendar.google.com)
        """
        self.calendar_id = calendar_id
        self.service = self._build_service()

    def _build_service(self):
        """Crée le service Google Calendar."""
        try:
            if not cfg.SERVICE_ACCOUNT_FILE:
                raise Exception("❌ SERVICE_ACCOUNT_FILE not initialized - startup not run?")
            credentials = service_account.Credentials.from_service_account_file(
                cfg.SERVICE_ACCOUNT_FILE,
                scopes=SCOPES
            )
            service = build('calendar', 'v3', credentials=credentials)
            logger.info("Google Calendar service initialized")
            return service
        except Exception as e:
            logger.error(f"Failed to initialize Google Calendar: {e}")
            raise
    
    def get_free_slots(
        self,
        date: datetime,
        duration_minutes: int = 15,
        start_hour: int = 9,
        end_hour: int = 18,
        limit: int = 3,
        buffer_minutes: int = 0,
    ) -> List[Dict]:
        """
        Récupère les créneaux libres pour une date donnée.
        
        Args:
            date: Date pour chercher créneaux
            duration_minutes: Durée RDV (défaut: 15 min)
            start_hour: Heure début journée (défaut: 9h)
            end_hour: Heure fin journée (défaut: 18h)
            limit: Nombre max de créneaux à retourner
        
        Returns:
            Liste de créneaux libres
            [
                {
                    "start": "2026-01-15T10:00:00",
                    "end": "2026-01-15T10:15:00",
                    "label": "Mercredi 15 janvier à 10h00"
                },
                ...
            ]
        """
        try:
            # Fuseau calendrier (comparaison slot vs event cohérente)
            tz = ZoneInfo(CALENDAR_TZ) if ZoneInfo else timezone(timedelta(hours=1))
            day_start = date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
            day_end = date.replace(hour=end_hour, minute=0, second=0, microsecond=0)
            if day_start.tzinfo is None:
                day_start = day_start.replace(tzinfo=tz)
                day_end = day_end.replace(tzinfo=tz)

            # Récupérer events existants (API attend ISO avec timezone)
            time_min = day_start.isoformat().replace('+00:00', 'Z') if day_start.tzinfo else day_start.isoformat() + 'Z'
            time_max = day_end.isoformat().replace('+00:00', 'Z') if day_end.tzinfo else day_end.isoformat() + 'Z'
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            events_busy = len(events)

            # Créer liste de tous les créneaux possibles
            all_slots = []
            current = day_start

            while current < day_end:
                slot_end = current + timedelta(minutes=duration_minutes)
                if slot_end <= day_end:
                    all_slots.append({
                        'start': current,
                        'end': slot_end
                    })
                current += timedelta(minutes=duration_minutes)

            # Filtrer créneaux occupés (normaliser TZ event pour comparaison)
            free_slots = []

            buffer_td = timedelta(minutes=int(buffer_minutes or 0))
            for slot in all_slots:
                slot_start = slot['start']
                slot_end = slot['end']
                effective_end = slot_end + buffer_td
                if effective_end > day_end:
                    continue
                is_free = True

                for event in events:
                    raw_start = event['start'].get('dateTime', event['start'].get('date', ''))
                    raw_end = event['end'].get('dateTime', event['end'].get('date', ''))
                    event_start = datetime.fromisoformat(raw_start.replace('Z', '+00:00'))
                    event_end = datetime.fromisoformat(raw_end.replace('Z', '+00:00'))
                    if event_start.tzinfo is not None:
                        event_start = event_start.astimezone(tz)
                        event_end = event_end.astimezone(tz)
                    else:
                        event_start = event_start.replace(tzinfo=tz)
                        event_end = event_end.replace(tzinfo=tz)
                    # Check overlap: slot + buffer ne doit pas chevaucher un event
                    if (slot_start < event_end and effective_end > event_start):
                        is_free = False
                        break

                if is_free:
                    # Formater label français
                    label = self._format_slot_label(slot['start'])
                    free_slots.append({
                        'start': slot['start'].isoformat(),
                        'end': slot['end'].isoformat(),
                        'label': label
                    })

                if len(free_slots) >= limit:
                    break

            logger.info(
                "get_free_slots: date=%s start_hour=%s end_hour=%s events_busy=%s free_slots=%s",
                date.date(),
                start_hour,
                end_hour,
                events_busy,
                len(free_slots),
            )
            return free_slots
        except HttpError as e:
            status = getattr(e.resp, "status", None)
            err_txt = str(e)
            logger.error("Error getting free slots: HTTP %s - %s", status, err_txt)
            if status == 403 or "insufficientPermissions" in err_txt:
                raise GoogleCalendarPermissionError(e)
            if status == 404 or "notFound" in err_txt:
                raise GoogleCalendarNotFoundError(e)
            raise GoogleCalendarError(e)
        except Exception as e:
            logger.error("Error getting free slots: %s", e, exc_info=True)
            raise GoogleCalendarError(e)
    
    def _format_slot_label(self, dt: datetime) -> str:
        """Formate un créneau en français."""
        days_fr = [
            'Lundi', 'Mardi', 'Mercredi', 'Jeudi',
            'Vendredi', 'Samedi', 'Dimanche'
        ]
        months_fr = [
            'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
            'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'
        ]
        
        day_name = days_fr[dt.weekday()]
        month_name = months_fr[dt.month - 1]
        
        return f"{day_name} {dt.day} {month_name} à {dt.hour}h{dt.minute:02d}"
    
    def book_appointment(
        self,
        start_time: str,
        end_time: str,
        patient_name: str,
        patient_contact: str,
        motif: str
    ) -> Optional[str]:
        """
        Crée un RDV dans Google Calendar.
        
        Args:
            start_time: ISO format (ex: "2026-01-15T10:00:00")
            end_time: ISO format
            patient_name: Nom patient
            patient_contact: Email ou téléphone
            motif: Raison consultation
        
        Returns:
            Event ID si succès, None si erreur
        """
        # Log pour debug (sans données sensibles)
        cal_mask = (self.calendar_id[:20] + "…") if self.calendar_id and len(self.calendar_id) > 20 else (self.calendar_id or "None")
        logger.info(f"Booking: calendar_id={cal_mask} start={start_time} end={end_time} name={patient_name!r}")
        try:
            event = {
                'summary': f'RDV - {patient_name}',
                'description': (
                    f'Patient: {patient_name}\n'
                    f'Contact: {patient_contact}\n'
                    f'Motif: {motif}'
                ),
                'start': {
                    'dateTime': start_time,
                    'timeZone': 'Europe/Paris',
                },
                'end': {
                    'dateTime': end_time,
                    'timeZone': 'Europe/Paris',
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},  # J-1
                        {'method': 'popup', 'minutes': 60},       # 1h avant
                    ],
                },
            }
            
            created_event = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event
            ).execute()
            
            event_id = created_event.get('id')
            logger.info(f"Appointment booked: event_id={event_id} calendar_id={cal_mask}")
            
            return event_id
        
        except Exception as e:
            from googleapiclient.errors import HttpError
            if isinstance(e, HttpError):
                status = e.resp.status
                if status == 403:
                    label = "permission"
                elif status == 409:
                    label = "conflict"
                elif status == 400:
                    label = "format"
                else:
                    label = "other"
                logger.error(
                    "Error booking appointment: HTTP %s (%s) %s - %s",
                    status,
                    label,
                    e.resp.reason,
                    e,
                )
                # 403 = droits insuffisants (writer) → exception typée pour raison "permission"
                if status == 403:
                    raise GoogleCalendarPermissionError(e)
            else:
                logger.error("Error booking appointment: %s", e, exc_info=True)
            return None
    
    def list_upcoming_events(self, days: int = 30) -> List[Dict]:
        """
        Liste les events à venir (pour recherche par nom).
        Args:
            days: Nombre de jours à couvrir (défaut 30)
        Returns:
            Liste d'events (format API Google)
        """
        try:
            now = datetime.now(timezone.utc)
            time_min = now.isoformat()
            time_max = (now + timedelta(days=days)).isoformat()
            result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime',
            ).execute()
            return result.get('items', [])
        except Exception as e:
            logger.error("list_upcoming_events: %s", e)
            return []

    def cancel_appointment(self, event_id: str) -> bool:
        """
        Annule un RDV.
        
        Args:
            event_id: ID de l'event Google Calendar
        
        Returns:
            True si succès, False sinon
        """
        try:
            self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            
            logger.info(f"Appointment cancelled: {event_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error cancelling appointment: {e}")
            return False

    def reschedule_appointment(self, event_id: str, start_time: str, end_time: str) -> bool:
        """
        Déplace un RDV existant dans Google Calendar.

        Args:
            event_id: ID de l'event Google Calendar
            start_time: Nouveau début au format ISO
            end_time: Nouvelle fin au format ISO

        Returns:
            True si succès, False sinon
        """
        try:
            event = self.service.events().get(
                calendarId=self.calendar_id,
                eventId=event_id,
            ).execute()
            event["start"] = {
                "dateTime": start_time,
                "timeZone": "Europe/Paris",
            }
            event["end"] = {
                "dateTime": end_time,
                "timeZone": "Europe/Paris",
            }
            self.service.events().update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=event,
            ).execute()
            logger.info("Appointment rescheduled: %s", event_id)
            return True
        except Exception as e:
            logger.error("Error rescheduling appointment %s: %s", event_id, e)
            return False


# Helper pour tests
def test_calendar_integration():
    """Test basique de l'intégration."""
    
    # Utiliser le calendar ID depuis config
    CALENDAR_ID = config.GOOGLE_CALENDAR_ID
    
    if not CALENDAR_ID:
        print("❌ GOOGLE_CALENDAR_ID non configuré dans backend/config.py")
        print("   Veuillez ajouter votre Calendar ID dans config.py")
        return
    
    service = GoogleCalendarService(CALENDAR_ID)
    
    # Test 1: Lire créneaux demain
    tomorrow = datetime.now() + timedelta(days=1)
    slots = service.get_free_slots(tomorrow, limit=5)
    
    print(f"\n📅 Créneaux disponibles demain:")
    for i, slot in enumerate(slots, 1):
        print(f"{i}. {slot['label']}")
    
    if slots:
        # Test 2: Booker premier créneau
        first_slot = slots[0]
        event_id = service.book_appointment(
            start_time=first_slot['start'],
            end_time=first_slot['end'],
            patient_name="Test Patient",
            patient_contact="test@email.com",
            motif="Test booking"
        )
        
        if event_id:
            print(f"\n✅ RDV créé: {event_id}")
            print(f"   {first_slot['label']}")
            
            # Test 3: Annuler RDV
            cancelled = service.cancel_appointment(event_id)
            if cancelled:
                print(f"\n✅ RDV annulé")
        else:
            print("\n❌ Échec création RDV")
    else:
        print("\n❌ Aucun créneau disponible")


if __name__ == "__main__":
    test_calendar_integration()
