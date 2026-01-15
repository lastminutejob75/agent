# backend/google_calendar.py

from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Configuration
from backend import config

SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = config.GOOGLE_SERVICE_ACCOUNT_FILE


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
            credentials = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE,
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
        limit: int = 3
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
            # Définir plage horaire du jour
            day_start = date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
            day_end = date.replace(hour=end_hour, minute=0, second=0, microsecond=0)
            
            # Récupérer events existants
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=day_start.isoformat() + 'Z',
                timeMax=day_end.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
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
            
            # Filtrer créneaux occupés
            free_slots = []
            
            for slot in all_slots:
                is_free = True
                
                for event in events:
                    event_start = datetime.fromisoformat(
                        event['start'].get('dateTime', event['start'].get('date'))
                    )
                    event_end = datetime.fromisoformat(
                        event['end'].get('dateTime', event['end'].get('date'))
                    )
                    
                    # Check si overlap
                    if (slot['start'] < event_end and slot['end'] > event_start):
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
            
            logger.info(f"Found {len(free_slots)} free slots for {date.date()}")
            return free_slots
        
        except Exception as e:
            logger.error(f"Error getting free slots: {e}")
            return []
    
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
            logger.info(f"Appointment booked: {event_id}")
            
            return event_id
        
        except Exception as e:
            logger.error(f"Error booking appointment: {e}")
            return None
    
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
