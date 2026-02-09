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


def _to_iso(dt: Any) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    if isinstance(dt, datetime):
        return dt.isoformat()
    return None


def _start_plus_15min(start_iso: Optional[str]) -> Optional[str]:
    """Retourne start_iso + 15 min en ISO (pour end_iso si absent)."""
    if not start_iso:
        return None
    try:
        dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        end_dt = dt + timedelta(minutes=15)
        return end_dt.isoformat()
    except Exception:
        return None


def serialize_slots_for_session(slots: List[Any], source: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    P0: Sérialise EXACTEMENT les slots affichés pour que l'index 1/2/3
    pointe sur le même slot au booking (sans re-fetch).
    Compatible SlotDisplay ou dicts.
    """
    out: List[Dict[str, Any]] = []
    for s in slots or []:
        if isinstance(s, dict):
            start_iso = s.get("start_iso") or s.get("start") or s.get("start_time")
            end_iso = s.get("end_iso") or s.get("end") or s.get("end_time") or _start_plus_15min(start_iso)
            out.append({
                "source": s.get("source") or source,
                "label": s.get("label") or s.get("display") or s.get("text", ""),
                "start_iso": start_iso,
                "end_iso": end_iso,
                "event_id": s.get("event_id") or s.get("google_event_id"),
                "slot_id": s.get("slot_id") or s.get("id"),
            })
            continue
        label = getattr(s, "label", None) or getattr(s, "display", None) or getattr(s, "text", None) or ""
        event_id = getattr(s, "event_id", None) or getattr(s, "google_event_id", None)
        slot_id = getattr(s, "slot_id", None) or getattr(s, "id", None)
        start_dt = getattr(s, "start_dt", None) or getattr(s, "start", None) or getattr(s, "start_time", None)
        end_dt = getattr(s, "end_dt", None) or getattr(s, "end", None) or getattr(s, "end_time", None)
        start_iso = _to_iso(start_dt)
        end_iso = _to_iso(end_dt) or _start_plus_15min(start_iso)
        out.append({
            "source": getattr(s, "source", None) or source,
            "label": label,
            "start_iso": start_iso,
            "end_iso": end_iso,
            "event_id": event_id,
            "slot_id": slot_id,
        })
    return out

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
    
    if not config.SERVICE_ACCOUNT_FILE:
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
# RÈGLE 7 : filtre créneaux par contrainte horaire
# ============================================

def _slot_minute_of_day(slot) -> int:
    """
    Retourne la minute du jour (0-1439) pour le slot.
    SlotDisplay a .hour (int) et .start (str ISO) ; on déduit les minutes si possible.
    """
    # SlotDisplay : hour (int), start (str ISO)
    dt = getattr(slot, "start_dt", None)
    if dt is None and getattr(slot, "start", None):
        try:
            s = getattr(slot, "start", "") or ""
            if "T" in s:
                dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            elif s:
                dt = datetime.fromisoformat(s)
        except Exception:
            dt = None
    if dt is not None:
        return dt.hour * 60 + dt.minute
    hour = getattr(slot, "hour", 0) or 0
    return hour * 60


def filter_slots_by_time_constraint(slots: List, session) -> List:
    """
    RÈGLE 7: Filtre les créneaux selon la contrainte horaire explicite.
    - after: garder slots >= constraint
    - before: garder slots <= constraint
    """
    t = getattr(session, "time_constraint_type", "") or ""
    m = getattr(session, "time_constraint_minute", -1)
    if not t or m is None or m < 0:
        return slots

    out = []
    for s in slots or []:
        minute = _slot_minute_of_day(s)
        if minute < 0:
            out.append(s)
            continue
        if t == "after" and minute >= m:
            out.append(s)
        elif t == "before" and minute <= m:
            out.append(s)
    return out


# ============================================
# FONCTIONS PRINCIPALES
# ============================================

def get_slots_for_display(
    limit: int = 3,
    pref: Optional[str] = None,
    session: Optional[Any] = None,
) -> List[prompts.SlotDisplay]:
    """
    Récupère les créneaux disponibles, filtrés par préférence si fournie.
    
    pref: "matin" (9h-12h), "après-midi" (14h-18h), "soir" (18h+) — pour ne pas proposer
    un créneau à 10h quand l'utilisateur a dit "je finis à 17h".
    
    Utilise Google Calendar si configuré, sinon SQLite.
    Cache utilisé seulement si pref est None (sinon filtre spécifique).
    """
    import time
    t_start = time.time()
    
    # Cache uniquement sans filtre préférence (évite proposer 10h après "je finis à 17h")
    if pref is None:
        cached = _get_cached_slots(limit)
        if cached:
            logger.info(f"⚡ get_slots_for_display: cache hit ({(time.time() - t_start) * 1000:.0f}ms)")
            return cached
    
    calendar = _get_calendar_service()
    
    if calendar:
        slots = _get_slots_from_google_calendar(calendar, limit, pref=pref)
    else:
        slots = _get_slots_from_sqlite(limit, pref=pref)
    
    # Si préférence demandée mais aucun créneau trouvé, fallback sans filtre (ne pas bloquer)
    if pref and (not slots or len(slots) == 0):
        logger.info(f"⚠️ Aucun créneau pour pref={pref}, fallback sans filtre")
        if calendar:
            slots = _get_slots_from_google_calendar(calendar, limit, pref=None)
        else:
            slots = _get_slots_from_sqlite(limit, pref=None)
    
    if pref is None:
        _set_cached_slots(slots)

    # RÈGLE 7: filtrage selon contrainte horaire explicite (si présente)
    if session is not None:
        try:
            slots = filter_slots_by_time_constraint(slots, session)
        except Exception:
            pass

    logger.info(f"⏱️ get_slots_for_display: {(time.time() - t_start) * 1000:.0f}ms ({len(slots)} slots, pref={pref})")
    return slots


def _get_slots_from_google_calendar(calendar, limit: int, pref: Optional[str] = None) -> List[prompts.SlotDisplay]:
    """Récupère créneaux via Google Calendar, filtrés par préférence (matin/après-midi/soir)."""
    slots: List[prompts.SlotDisplay] = []
    # Plage horaire selon préférence (ne pas proposer 10h si user a dit "je finis à 17h")
    if pref == "matin":
        start_hour, end_hour = 9, 12
    elif pref == "après-midi":
        start_hour, end_hour = 14, 18
    elif pref == "soir":
        start_hour, end_hour = 18, 20
    else:
        start_hour, end_hour = 9, 18
    
    for day_offset in range(1, 8):
        if len(slots) >= limit:
            break
        date = datetime.now() + timedelta(days=day_offset)
        if date.weekday() >= 5:
            continue
        day_slots = calendar.get_free_slots(
            date=date,
            duration_minutes=15,
            start_hour=start_hour,
            end_hour=end_hour,
            limit=limit - len(slots)
        )
        days_fr = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
        for slot in day_slots:
            start_iso = slot.get('start', '')
            day_fr, hour, label_vocal = '', 0, ''
            try:
                dt = datetime.fromisoformat(start_iso.replace('Z', '+00:00'))
                if dt.tzinfo:
                    dt = dt.replace(tzinfo=None)
                day_fr = days_fr[dt.weekday()]
                hour = dt.hour
                label_vocal = f"{day_fr} à {hour}h"
            except Exception:
                pass
            slots.append(prompts.SlotDisplay(
                idx=len(slots) + 1,
                label=slot['label'],
                slot_id=len(slots),
                start=start_iso,
                day=day_fr,
                hour=hour,
                label_vocal=label_vocal or slot.get('label', ''),
            ))
            if len(slots) >= limit:
                break
    logger.info(f"Google Calendar: {len(slots)} créneaux trouvés (pref={pref})")
    return slots


def _get_slots_from_sqlite(limit: int, pref: Optional[str] = None) -> List[prompts.SlotDisplay]:
    """Fallback: récupère créneaux via SQLite, filtrés par préférence."""
    try:
        from backend.db import list_free_slots
        raw = list_free_slots(limit=limit, pref=pref)
        out: List[prompts.SlotDisplay] = []
        days_fr = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
        for i, r in enumerate(raw, start=1):
            label = _format_slot_label_vocal(r['date'], r['time'])
            day_fr, hour, start_iso, label_vocal = '', 0, '', ''
            try:
                dt = datetime.strptime(r['date'], "%Y-%m-%d")
                day_fr = days_fr[dt.weekday()]
                hour, minute = map(int, (r.get('time') or '9:00').split(':')[:2])
                start_iso = f"{r['date']}T{r.get('time', '09:00')}:00"
                label_vocal = f"{day_fr} à {hour}h"
            except Exception:
                pass
            out.append(prompts.SlotDisplay(
                idx=i,
                label=label,
                slot_id=int(r["id"]),
                start=start_iso,
                day=day_fr,
                hour=hour,
                label_vocal=label_vocal or label,
            ))
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

    # P0: ne pas re-fetch Google si on a déjà les slots affichés (pending_slots_display)
    if getattr(session, "pending_slots_display", None):
        return
    calendar = _get_calendar_service()
    if calendar:
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


def book_slot_from_session(session, choice_index_1based: int) -> tuple[bool, str | None]:
    """
    Réserve le créneau choisi par l'utilisateur.
    P0: utilise pending_slots_display (slots affichés) si présent, sinon fallback legacy.
    Returns (success, reason).
    - success=True -> reason=None
    - success=False, reason="slot_taken" -> créneau déjà pris (message adapté)
    - success=False, reason="technical" -> erreur technique / slots manquants (évite "plus dispo" à tort)
    """
    idx = choice_index_1based - 1
    slots = getattr(session, "pending_slots_display", None) or []

    if slots and 1 <= choice_index_1based <= len(slots):
        chosen = slots[choice_index_1based - 1]
        src = (chosen.get("source") or "").lower()
        if src == "google":
            start_iso = chosen.get("start_iso")
            end_iso = chosen.get("end_iso")
            if not start_iso or not end_iso:
                logger.warning("pending_slots_display: start_iso/end_iso manquants")
                return False, "technical"
            return _book_google_by_iso(session, start_iso, end_iso)
        if src == "sqlite":
            slot_id = chosen.get("slot_id")
            if slot_id is None:
                logger.warning("pending_slots_display: slot_id manquant")
                return False, "technical"
            ok = _book_sqlite_by_slot_id(session, int(slot_id))
            return (ok, None if ok else "slot_taken")

    # Pas de pending_slots_display alors qu'on confirme → ne pas dire "créneau pris"
    if session.pending_slot_choice is not None and not slots:
        logger.warning("book_slot_from_session: pending_slot_choice=%s mais pending_slots_display vide", choice_index_1based)
        return False, "technical"

    # Fallback legacy
    if idx < 0 or idx >= len(getattr(session, "pending_slot_ids", []) or []):
        logger.warning("Index invalide: %s", choice_index_1based)
        return False, "technical"
    calendar = _get_calendar_service()
    if calendar:
        ok = _book_via_google_calendar(session, idx)
        return (ok, None if ok else "slot_taken")
    ok = _book_via_sqlite(session, idx)
    return (ok, None if ok else "slot_taken")


def _book_google_by_iso(session, start_iso: str, end_iso: str) -> tuple[bool, str | None]:
    """
    Book Google Calendar à partir des timestamps ISO du slot affiché (sans re-fetch).
    Un retry est fait en cas d'échec (réseau / API) pour limiter les "plus dispo" à tort.
    Returns (success, reason) with reason in ("slot_taken", "technical", None).
    """
    calendar = _get_calendar_service()
    if not calendar:
        return False, "technical"

    def _try_once() -> bool:
        event_id = calendar.book_appointment(
            start_time=start_iso,
            end_time=end_iso,
            patient_name=session.qualif_data.name or "Client",
            patient_contact=session.qualif_data.contact or "",
            motif=session.qualif_data.motif or "Consultation",
        )
        if event_id:
            session.google_event_id = event_id
            logger.info("RDV Google Calendar créé: %s", event_id)
            return True
        return False

    try:
        if _try_once():
            return True, None
        # Un seul retry pour erreurs transitoires (réseau, quota, etc.)
        logger.info("Retry booking Google Calendar pour conv_id=%s", getattr(session, "conv_id", ""))
        if _try_once():
            return True, None
        return False, "slot_taken"
    except Exception as e:
        logger.error("Erreur book_google_by_iso: %s", e, exc_info=True)
        return False, "technical"


def _book_sqlite_by_slot_id(session, slot_id: int) -> bool:
    """Book SQLite à partir du slot_id du slot affiché."""
    try:
        from backend.db import book_slot_atomic
        return book_slot_atomic(
            slot_id=slot_id,
            name=session.qualif_data.name or "",
            contact=session.qualif_data.contact or "",
            contact_type=getattr(session.qualif_data, "contact_type", None) or "",
            motif=session.qualif_data.motif or "",
        )
    except Exception as e:
        logger.error(f"Erreur book_sqlite_by_slot_id: {e}")
        return False


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
    Annule une réservation (Google Calendar ou SQLite).
    Args:
        slot_or_session: Dict avec 'event_id' (Google) ou 'slot_id'/'id' (SQLite), ou objet avec attributs.
    Returns:
        True si annulation réussie.
    """
    event_id = None
    slot_id = None
    appt_id = None

    if isinstance(slot_or_session, dict):
        event_id = slot_or_session.get("event_id") or slot_or_session.get("google_event_id")
        slot_id = slot_or_session.get("slot_id")
        appt_id = slot_or_session.get("id")
    else:
        event_id = getattr(slot_or_session, "event_id", None) or getattr(slot_or_session, "google_event_id", None)
        slot_id = getattr(slot_or_session, "slot_id", None)
        appt_id = getattr(slot_or_session, "id", None)

    if event_id:
        calendar = _get_calendar_service()
        if not calendar:
            return False
        return calendar.cancel_appointment(event_id)

    if slot_id is not None or appt_id is not None:
        try:
            from backend.db import cancel_booking_sqlite
            return cancel_booking_sqlite({"slot_id": slot_id, "id": appt_id})
        except Exception as e:
            logger.error(f"Erreur annulation SQLite: {e}")
            return False

    logger.warning("Pas d'event_id ni slot_id pour annuler")
    return False


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
                "event_id": None,
                "slot_id": booking.get("slot_id"),
                "id": booking.get("id"),
                "label": f"{booking.get('date', '')} à {booking.get('time', '')}",
                "start": booking.get("date"),
                "end": None,
            }
        return None

    except Exception as e:
        logger.error(f"Erreur recherche SQLite: {e}")
        return None


def is_google_calendar_enabled() -> bool:
    """Vérifie si Google Calendar est configuré."""
    return _get_calendar_service() is not None
