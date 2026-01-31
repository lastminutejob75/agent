# backend/tools_booking.py
"""
Outils de réservation - Version Google Calendar.

Ce module gère les créneaux et réservations via Google Calendar API.
Fallback vers SQLite si Google Calendar n'est pas configuré.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging

from backend import prompts
from backend import config

logger = logging.getLogger(__name__)

# ============================================
# GOOGLE CALENDAR SERVICE (lazy loading)
# ============================================

_calendar_service = None

# ============================================
# CACHE SLOTS (évite appels répétés Google Calendar)
# ============================================

_slots_cache: Dict[str, Any] = {
    "slots": None,
    "timestamp": 0,
    "ttl_seconds": 60,  # Cache valide 60 secondes
}


def _get_cached_slots(limit: int) -> Optional[List[prompts.SlotDisplay]]:
    """
    Récupère les slots du cache si encore valides.
    
    Returns:
        Liste de SlotDisplay ou None si cache expiré
    """
    import time
    
    if _slots_cache["slots"] is None:
        return None
    
    age = time.time() - _slots_cache["timestamp"]
    if age > _slots_cache["ttl_seconds"]:
        logger.info(f"⏱️ Cache slots expiré ({age:.0f}s > {_slots_cache['ttl_seconds']}s)")
        return None
    
    logger.info(f"⚡ Cache slots HIT ({age:.0f}s)")
    return _slots_cache["slots"][:limit]


def _set_cached_slots(slots: List[prompts.SlotDisplay]) -> None:
    """Met à jour le cache de slots."""
    import time
    
    _slots_cache["slots"] = slots
    _slots_cache["timestamp"] = time.time()
    logger.info(f"⚡ Cache slots SET ({len(slots)} slots)")


def _get_calendar_service():
    """
    Récupère le service Google Calendar (lazy loading).
    
    Returns:
        GoogleCalendarService ou None si non configuré
    """
    global _calendar_service
    
    if _calendar_service is not None:
        return _calendar_service
    
    # Vérifier si Google Calendar est configuré
    if not config.GOOGLE_CALENDAR_ID:
        logger.warning("GOOGLE_CALENDAR_ID non configuré - utilisation SQLite")
        return None
    
    service_file = config.get_service_account_file()
    if not service_file:
        logger.warning("SERVICE_ACCOUNT_FILE non configuré - utilisation SQLite")
        return None
    
    try:
        from backend.google_calendar import GoogleCalendarService
        _calendar_service = GoogleCalendarService(config.GOOGLE_CALENDAR_ID)
        logger.info("✅ Google Calendar service initialisé")
        return _calendar_service
    except Exception as e:
        logger.error(f"❌ Erreur initialisation Google Calendar: {e}")
        return None


# ============================================
# FONCTIONS PRINCIPALES
# ============================================

def get_slots_for_display(limit: int = 3) -> List[prompts.SlotDisplay]:
    """
    Récupère les créneaux disponibles.
    
    Utilise Google Calendar si configuré, sinon SQLite.
    Cache les résultats pour 60 secondes (évite appels répétés).
    
    Args:
        limit: Nombre max de créneaux à retourner
        
    Returns:
        Liste de SlotDisplay pour affichage
    """
    import time
    t_start = time.time()
    
    # Vérifier le cache d'abord
    cached = _get_cached_slots(limit)
    if cached:
        logger.info(f"⚡ get_slots_for_display: cache hit ({(time.time() - t_start) * 1000:.0f}ms)")
        return cached
    
    calendar = _get_calendar_service()
    
    if calendar:
        slots = _get_slots_from_google_calendar(calendar, limit)
    else:
        slots = _get_slots_from_sqlite(limit)
    
    # Mettre en cache
    _set_cached_slots(slots)
    
    logger.info(f"⏱️ get_slots_for_display: {(time.time() - t_start) * 1000:.0f}ms ({len(slots)} slots)")
    return slots


def _get_slots_from_google_calendar(calendar, limit: int) -> List[prompts.SlotDisplay]:
    """Récupère créneaux via Google Calendar."""
    slots: List[prompts.SlotDisplay] = []
    
    # Chercher sur les 7 prochains jours
    for day_offset in range(1, 8):  # Commencer à demain
        if len(slots) >= limit:
            break
            
        date = datetime.now() + timedelta(days=day_offset)
        
        # Skip weekends (optionnel)
        if date.weekday() >= 5:  # Samedi = 5, Dimanche = 6
            continue
        
        day_slots = calendar.get_free_slots(
            date=date,
            duration_minutes=15,
            start_hour=9,
            end_hour=18,
            limit=limit - len(slots)
        )
        
        for i, slot in enumerate(day_slots):
            slots.append(prompts.SlotDisplay(
                idx=len(slots) + 1,
                label=slot['label'],
                slot_id=len(slots)  # Index pour référence
            ))
            
            if len(slots) >= limit:
                break
    
    logger.info(f"Google Calendar: {len(slots)} créneaux trouvés")
    return slots


def _get_slots_from_sqlite(limit: int) -> List[prompts.SlotDisplay]:
    """Fallback: récupère créneaux via SQLite."""
    try:
        from backend.db import list_free_slots
        raw = list_free_slots(limit=limit)
        out: List[prompts.SlotDisplay] = []
        for i, r in enumerate(raw, start=1):
            # Formater pour TTS
            label = _format_slot_label_vocal(r['date'], r['time'])
            out.append(prompts.SlotDisplay(idx=i, label=label, slot_id=int(r["id"])))
        return out
    except Exception as e:
        logger.error(f"Erreur SQLite slots: {e}")
        return []


def _format_slot_label_vocal(date_str: str, time_str: str) -> str:
    """
    Formate une date/heure pour le TTS.
    Ex: "2026-01-25", "14:00" → "samedi 25 janvier à 14 heures"
    """
    from datetime import datetime
    
    days_fr = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
    months_fr = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin',
                 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
    
    try:
        # Parser la date
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        day_name = days_fr[dt.weekday()]
        month_name = months_fr[dt.month - 1]
        
        # Parser l'heure
        hour, minute = map(int, time_str.split(':')[:2])
        
        if minute == 0:
            time_vocal = f"{hour} heures"
        elif minute == 30:
            time_vocal = f"{hour} heures trente"
        else:
            time_vocal = f"{hour} heures {minute}"
        
        return f"{day_name} {dt.day} {month_name} à {time_vocal}"
    except Exception:
        # Fallback si parsing échoue
        return f"{date_str} à {time_str}"


def store_pending_slots(session, slots: List[prompts.SlotDisplay]) -> None:
    """
    Stocke les créneaux proposés dans la session.
    
    Args:
        session: Session utilisateur
        slots: Liste des créneaux proposés
    """
    session.pending_slot_ids = [s.slot_id for s in slots]
    session.pending_slot_labels = [s.label for s in slots]
    session.pending_slots = slots  # Stocker les objets complets
    
    # Stocker aussi les données complètes pour Google Calendar
    calendar = _get_calendar_service()
    if calendar:
        # Récupérer les slots complets pour le booking
        _store_google_calendar_slots(session, slots)


def _store_google_calendar_slots(session, slots: List[prompts.SlotDisplay]) -> None:
    """Stocke les données Google Calendar pour le booking."""
    calendar = _get_calendar_service()
    if not calendar:
        return
    
    # Récupérer les créneaux complets
    full_slots: List[Dict[str, Any]] = []
    
    for day_offset in range(1, 8):
        if len(full_slots) >= len(slots):
            break
            
        date = datetime.now() + timedelta(days=day_offset)
        
        if date.weekday() >= 5:
            continue
        
        day_slots = calendar.get_free_slots(
            date=date,
            duration_minutes=15,
            start_hour=9,
            end_hour=18,
            limit=len(slots) - len(full_slots)
        )
        
        full_slots.extend(day_slots)
    
    session.pending_google_slots = full_slots[:len(slots)]


def book_slot_from_session(session, choice_index_1based: int) -> bool:
    """
    Réserve le créneau choisi par l'utilisateur.
    
    Utilise Google Calendar si configuré, sinon SQLite.
    
    Args:
        session: Session utilisateur avec les données de qualification
        choice_index_1based: Index du créneau (1-based)
        
    Returns:
        True si réservation réussie, False sinon
    """
    idx = choice_index_1based - 1
    
    if idx < 0 or idx >= len(session.pending_slot_ids):
        logger.warning(f"Index invalide: {choice_index_1based}")
        return False
    
    calendar = _get_calendar_service()
    
    if calendar:
        return _book_via_google_calendar(session, idx)
    else:
        return _book_via_sqlite(session, idx)


def _book_via_google_calendar(session, idx: int) -> bool:
    """Réserve via Google Calendar."""
    calendar = _get_calendar_service()
    if not calendar:
        return False
    
    # Récupérer le slot complet
    if not hasattr(session, 'pending_google_slots') or not session.pending_google_slots:
        logger.error("Pas de slots Google Calendar en session")
        return False
    
    if idx >= len(session.pending_google_slots):
        logger.error(f"Index {idx} hors limites Google slots")
        return False
    
    slot = session.pending_google_slots[idx]
    
    # Créer le RDV
    event_id = calendar.book_appointment(
        start_time=slot['start'],
        end_time=slot['end'],
        patient_name=session.qualif_data.name or "Client",
        patient_contact=session.qualif_data.contact or "",
        motif=session.qualif_data.motif or "Consultation"
    )
    
    if event_id:
        session.google_event_id = event_id
        logger.info(f"✅ RDV Google Calendar créé: {event_id}")
        return True
    
    logger.error("❌ Échec création RDV Google Calendar")
    return False


def _book_via_sqlite(session, idx: int) -> bool:
    """Fallback: réserve via SQLite."""
    try:
        from backend.db import book_slot_atomic
        
        slot_id = session.pending_slot_ids[idx]
        
        return book_slot_atomic(
            slot_id=slot_id,
            name=session.qualif_data.name or "",
            contact=session.qualif_data.contact or "",
            contact_type=session.qualif_data.contact_type or "",
            motif=session.qualif_data.motif or "",
        )
    except Exception as e:
        logger.error(f"Erreur SQLite booking: {e}")
        return False


def get_label_for_choice(session, choice_index_1based: int) -> Optional[str]:
    """
    Récupère le label d'un créneau choisi.
    
    Args:
        session: Session utilisateur
        choice_index_1based: Index du créneau (1-based)
        
    Returns:
        Label du créneau ou None si non trouvé
    """
    idx = choice_index_1based - 1
    
    if idx < 0 or idx >= len(session.pending_slot_labels):
        return None
    
    return session.pending_slot_labels[idx]


# ============================================
# UTILITAIRES
# ============================================

def cancel_booking(slot_or_session) -> bool:
    """
    Annule une réservation (si Google Calendar).
    
    Args:
        slot_or_session: Soit un dict avec 'event_id', soit une session avec google_event_id
        
    Returns:
        True si annulation réussie
    """
    # Déterminer l'event_id
    event_id = None
    
    if isinstance(slot_or_session, dict):
        event_id = slot_or_session.get('event_id')
    elif hasattr(slot_or_session, 'google_event_id'):
        event_id = slot_or_session.google_event_id
    
    if not event_id:
        logger.warning("Pas d'event_id Google Calendar à annuler")
        return False
    
    calendar = _get_calendar_service()
    if not calendar:
        return False
    
    return calendar.cancel_appointment(event_id)


def find_booking_by_name(name: str) -> Optional[Dict[str, Any]]:
    """
    Recherche un RDV existant par nom du patient.
    
    Args:
        name: Nom du patient
        
    Returns:
        Dict avec les infos du RDV ou None si non trouvé
        Format: {'event_id': str, 'label': str, 'start': datetime, 'end': datetime}
    """
    calendar = _get_calendar_service()
    
    if calendar:
        return _find_booking_google_calendar(calendar, name)
    else:
        return _find_booking_sqlite(name)


def _find_booking_google_calendar(calendar, name: str) -> Optional[Dict[str, Any]]:
    """Recherche un RDV dans Google Calendar."""
    try:
        # Chercher dans les 30 prochains jours
        events = calendar.list_upcoming_events(days=30)
        
        name_lower = name.lower()
        
        for event in events:
            # Chercher le nom dans le summary ou la description
            summary = event.get('summary', '').lower()
            description = event.get('description', '').lower()
            
            if name_lower in summary or name_lower in description:
                # Formater le label
                start = event.get('start', {}).get('dateTime', '')
                if start:
                    try:
                        dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                        label = dt.strftime('%A %d %B à %Hh%M').replace('Monday', 'lundi').replace('Tuesday', 'mardi').replace('Wednesday', 'mercredi').replace('Thursday', 'jeudi').replace('Friday', 'vendredi')
                        # Simplifier les mois
                        for en, fr in [('January', 'janvier'), ('February', 'février'), ('March', 'mars'), ('April', 'avril'), ('May', 'mai'), ('June', 'juin'), ('July', 'juillet'), ('August', 'août'), ('September', 'septembre'), ('October', 'octobre'), ('November', 'novembre'), ('December', 'décembre')]:
                            label = label.replace(en, fr)
                    except:
                        label = start
                else:
                    label = "votre rendez-vous"
                
                return {
                    'event_id': event.get('id'),
                    'label': label,
                    'start': start,
                    'end': event.get('end', {}).get('dateTime', ''),
                    'summary': event.get('summary', ''),
                }
        
        logger.info(f"Aucun RDV trouvé pour: {name}")
        return None
        
    except Exception as e:
        logger.error(f"Erreur recherche Google Calendar: {e}")
        return None


def _find_booking_sqlite(name: str) -> Optional[Dict[str, Any]]:
    """Recherche un RDV dans SQLite (fallback)."""
    try:
        from backend.db import find_booking_by_name as db_find
        
        booking = db_find(name)
        if booking:
            return {
                'event_id': None,
                'slot_id': booking.get('id'),
                'label': f"{booking.get('date', '')} à {booking.get('time', '')}",
                'start': booking.get('date'),
                'end': None,
            }
        return None
        
    except Exception as e:
        logger.error(f"Erreur recherche SQLite: {e}")
        return None


def is_google_calendar_enabled() -> bool:
    """Vérifie si Google Calendar est configuré."""
    return _get_calendar_service() is not None
