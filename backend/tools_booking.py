# backend/tools_booking.py
"""
Outils de réservation - Version Google Calendar.

Ce module gère les créneaux et réservations via Google Calendar API.
Fallback vers SQLite si Google Calendar n'est pas configuré.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging

from backend import prompts
from backend import config
from backend.google_calendar import (
    GoogleCalendarError,
    GoogleCalendarNotFoundError,
    GoogleCalendarPermissionError,
)

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


def _slot_get(slot: Any, key: str, default: Any = None) -> Any:
    """Accès unifié slot (dict ou objet) pour label, start, day, etc."""
    if isinstance(slot, dict):
        return slot.get(key, default)
    return getattr(slot, key, default)


def _resolve_slot_id_from_start_iso(
    start_iso: str, source: str = "sqlite", tenant_id: int = 1
) -> Optional[int]:
    """
    Fallback: retrouve slot_id à partir de start_iso quand slot_id manque (session perdue).
    start_iso ex: "2026-02-16T09:00:00". Retourne None si non trouvé.
    """
    if not start_iso:
        return None
    try:
        dt = datetime.fromisoformat(str(start_iso).replace("Z", "+00:00"))
        date_str = dt.strftime("%Y-%m-%d")
        time_str = dt.strftime("%H:%M")
        if source == "pg":
            try:
                from backend.slots_pg import pg_find_slot_id_by_datetime
                return pg_find_slot_id_by_datetime(date_str, time_str, tenant_id=tenant_id)
            except Exception:
                pass
        from backend.db import find_slot_id_by_datetime
        return find_slot_id_by_datetime(date_str, time_str, tenant_id=tenant_id)
    except Exception as e:
        logger.debug("_resolve_slot_id_from_start_iso failed: %s", e)
        return None


def _ensure_local_slot_id_from_start_iso(start_iso: str, tenant_id: int = 1) -> Optional[int]:
    """
    Garantit l'existence d'un slot local à partir d'un ISO start pour le miroir interne.
    """
    if not start_iso:
        return None
    try:
        dt = datetime.fromisoformat(str(start_iso).replace("Z", "+00:00"))
        date_str = dt.strftime("%Y-%m-%d")
        time_str = dt.strftime("%H:%M")
        from backend.db import ensure_slot_id_by_datetime

        return ensure_slot_id_by_datetime(date_str, time_str, tenant_id=tenant_id)
    except Exception as e:
        logger.debug("_ensure_local_slot_id_from_start_iso failed: %s", e)
        return None


def _mirror_google_bookings_enabled(session: Any) -> bool:
    tenant_id = getattr(session, "tenant_id", None) or 1
    try:
        from backend.tenant_config import get_params

        params = get_params(tenant_id) or {}
        provider = str(params.get("calendar_provider") or "").strip().lower()
        raw = params.get("mirror_google_bookings_to_internal")
    except Exception:
        provider = ""
        raw = None
    if provider == "google" and raw is None:
        return True
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return False
    return str(raw).strip().lower() in {"1", "true", "yes", "on", "oui"}


def _mirror_google_booking_to_internal(session: Any, start_iso: str, event_id: str) -> bool:
    """
    Crée un RDV miroir dans l'agenda interne UWI après un booking Google réussi.
    Ne doit jamais faire échouer le booking Google principal.
    """
    tenant_id = getattr(session, "tenant_id", None) or 1
    slot_id = _ensure_local_slot_id_from_start_iso(start_iso, tenant_id=tenant_id)
    if slot_id is None:
        logger.warning(
            "BOOKING_MIRROR_INTERNAL_FAILED tenant_id=%s conv_id=%s reason=slot_unavailable start=%s event_id=%s",
            tenant_id,
            getattr(session, "conv_id", "")[:24],
            (start_iso or "")[:19],
            (event_id or "")[:24],
        )
        return False
    source = "pg" if config.USE_PG_SLOTS else "sqlite"
    ok = _book_local_by_slot_id(session, int(slot_id), source=source)
    if ok:
        logger.info(
            "BOOKING_MIRROR_INTERNAL_OK tenant_id=%s conv_id=%s slot_id=%s event_id=%s",
            tenant_id,
            getattr(session, "conv_id", "")[:24],
            slot_id,
            (event_id or "")[:24],
        )
        return True
    logger.warning(
        "BOOKING_MIRROR_INTERNAL_FAILED tenant_id=%s conv_id=%s reason=book_failed slot_id=%s event_id=%s",
        tenant_id,
        getattr(session, "conv_id", "")[:24],
        slot_id,
        (event_id or "")[:24],
    )
    return False


def _derive_day_from_start(start_iso: Optional[str]) -> str:
    """Dérive le jour en français (lundi, mardi...) depuis start ISO."""
    if not start_iso:
        return ""
    try:
        dt = datetime.fromisoformat(str(start_iso).replace("Z", "+00:00"))
        days_fr = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        return days_fr[dt.weekday()]
    except Exception:
        return ""


# Format canonique unique (Fix 3) : source de vérité pour pending_slots
# {"id": event_id|slot_id, "start": iso, "end": iso, "label": str, "label_vocal": str, "day": str, "source": "google"|"sqlite"|"pg"}
def to_canonical_slot(slot: Any, source: Optional[str] = None) -> Dict[str, Any]:
    """Convertit SlotDisplay ou dict → format canonique."""
    if isinstance(slot, dict):
        start_iso = slot.get("start_iso") or slot.get("start") or slot.get("start_time")
        end_iso = slot.get("end_iso") or slot.get("end") or slot.get("end_time") or _start_plus_15min(start_iso)
        src = (slot.get("source") or source or "sqlite").lower()
        event_id = slot.get("event_id") or slot.get("google_event_id")
        slot_id = slot.get("slot_id") or slot.get("id")
        slot_id_val = event_id if src == "google" else slot_id
        label = slot.get("label") or slot.get("display") or slot.get("text", "")
        label_vocal = slot.get("label_vocal") or label
        day = slot.get("day") or _derive_day_from_start(start_iso)
        return {
            "id": slot_id_val,
            "start": start_iso,
            "end": end_iso,
            "start_iso": start_iso,
            "end_iso": end_iso,
            "slot_id": slot_id,
            "event_id": event_id,
            "label": label,
            "label_vocal": label_vocal,
            "day": day,
            "source": src,
        }
    label = getattr(slot, "label", None) or getattr(slot, "display", None) or getattr(slot, "text", None) or ""
    label_vocal = getattr(slot, "label_vocal", None) or label
    event_id = getattr(slot, "event_id", None) or getattr(slot, "google_event_id", None)
    slot_id = getattr(slot, "slot_id", None) or getattr(slot, "id", None)
    src = (getattr(slot, "source", None) or source or "sqlite").lower()
    slot_id_val = event_id if src == "google" else slot_id
    start_dt = getattr(slot, "start_dt", None) or getattr(slot, "start", None) or getattr(slot, "start_time", None)
    end_dt = getattr(slot, "end_dt", None) or getattr(slot, "end", None) or getattr(slot, "end_time", None)
    start_iso = _to_iso(start_dt)
    end_iso = _to_iso(end_dt) or _start_plus_15min(start_iso)
    day = getattr(slot, "day", None) or _derive_day_from_start(start_iso)
    return {
        "id": slot_id_val,
        "start": start_iso,
        "end": end_iso,
        "start_iso": start_iso,
        "end_iso": end_iso,
        "slot_id": slot_id,
        "event_id": event_id,
        "label": label,
        "label_vocal": label_vocal,
        "day": day,
        "source": src,
    }


def to_canonical_slots(slots: List[Any], source: Optional[str] = None) -> List[Dict[str, Any]]:
    """Convertit une liste de slots (SlotDisplay ou dict) en format canonique."""
    return [to_canonical_slot(s, source) for s in (slots or [])]


def serialize_slots_for_session(slots: List[Any], source: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    P0: Sérialise EXACTEMENT les slots affichés pour que l'index 1/2/3
    pointe sur le même slot au booking (sans re-fetch).
    Compatible SlotDisplay ou dicts. Retourne format canonique (Fix 3).
    """
    return to_canonical_slots(slots, source)

# ============================================
# CALENDAR ADAPTER (multi-tenant: google/none par tenant)
# ============================================

_calendar_service = None  # Legacy fallback (global)

# ============================================
# CACHE SLOTS (évite appels répétés Google Calendar)
# ============================================

import os as _os

_DISABLE_SLOT_CACHE = _os.getenv("DISABLE_SLOT_CACHE", "").lower() in ("1", "true", "yes")

_slots_cache: Dict[str, Any] = {
    "by_key": {},  # (tenant_id, pref) -> {"slots": [...], "timestamp": float}
    "ttl_seconds": 150,
}


def _cache_key(tenant_id: int, pref: Optional[str] = None) -> tuple:
    return (tenant_id, pref or "__none__")


def _get_cached_slots(limit: int, tenant_id: int = 1, pref: Optional[str] = None) -> Optional[List[prompts.SlotDisplay]]:
    """Récupère les slots du cache si encore valides (scopé par tenant + pref)."""
    if _DISABLE_SLOT_CACHE:
        return None
    import time
    key = _cache_key(tenant_id, pref)
    entry = _slots_cache["by_key"].get(key)
    if not entry or entry.get("slots") is None:
        return None
    age = time.time() - entry.get("timestamp", 0)
    if age > _slots_cache["ttl_seconds"]:
        _slots_cache["by_key"].pop(key, None)
        return None
    logger.info(f"⚡ Cache slots HIT tenant={tenant_id} pref={pref} ({age:.0f}s)")
    return entry["slots"][:limit]


def _set_cached_slots(slots: List[prompts.SlotDisplay], tenant_id: int = 1, pref: Optional[str] = None) -> None:
    """Met à jour le cache de slots (scopé par tenant + pref)."""
    if _DISABLE_SLOT_CACHE:
        return
    import time
    key = _cache_key(tenant_id, pref)
    _slots_cache["by_key"][key] = {"slots": slots, "timestamp": time.time()}
    logger.info(f"⚡ Cache slots SET tenant={tenant_id} pref={pref} ({len(slots)} slots)")


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
# Écart minimum entre deux créneaux (fallback si pas assez via period buckets)
MIN_SLOT_GAP_MINUTES = 120  # 2h ou jour différent

# Fenêtre d'exclusion autour d'un créneau refusé (ne pas reproposer un "voisin")
REJECTED_SLOT_WINDOW_MINUTES = 90  # ±90 min

# Nombre de créneaux à récupérer avant étalement (pool pour diversifier).
# Réduit pour accélérer la réponse Vapi sur get_slots (moins d'appels Google).
SLOTS_POOL_SIZE = 9

# Périodes UX : 1 créneau par (jour, période) quand possible
# MORNING 8-12, AFTERNOON 13-18, EVENING 18+
_PERIOD_MORNING_END = 12 * 60    # 12h00
_PERIOD_AFTERNOON_END = 18 * 60  # 18h00


def _slot_start_dt(slot: Any) -> Optional[datetime]:
    """Retourne le datetime de début du slot (pour comparaison / écart)."""
    s = getattr(slot, "start", None) or (slot.get("start") if isinstance(slot, dict) else None)
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except Exception:
        return None


def _slot_minute_of_day_for_period(slot: Any) -> int:
    """Minute du jour (0-1439) pour déterminer la période."""
    dt = _slot_start_dt(slot)
    if dt is not None:
        return dt.hour * 60 + dt.minute
    return getattr(slot, "hour", 0) * 60


def _slot_period(slot: Any) -> str:
    """Période du créneau : MORNING (8-12), AFTERNOON (13-18), EVENING (18+)."""
    m = _slot_minute_of_day_for_period(slot)
    if m < _PERIOD_MORNING_END:
        return "MORNING"
    if m < _PERIOD_AFTERNOON_END:
        return "AFTERNOON"
    return "EVENING"


def slot_period(slot: Any) -> str:
    """Public : période du créneau (MORNING/AFTERNOON/EVENING) pour anti-spam jour/période."""
    return _slot_period(slot)


def _spread_slots(
    slots: List[prompts.SlotDisplay],
    limit: int = 3,
    min_gap_minutes: int = MIN_SLOT_GAP_MINUTES,
) -> List[prompts.SlotDisplay]:
    """
    Étale les créneaux pour une UX naturelle :
    1) Max 1 slot par (jour, période) : matin / après-midi / soir → ex. lun 9h, lun 14h, mar 9h
    2) Max 2 créneaux par jour dans les 3 proposés
    3) Si pas assez : compléter avec règle d'écart >= 2h (fallback)
    """
    if not slots or limit <= 0:
        return slots[:limit]
    ordered = sorted(slots, key=lambda s: _slot_start_dt(s) or datetime.max)

    def day_count(picked_list: List[Any], day: str) -> int:
        return sum(1 for x in picked_list if (getattr(x, "day", "") or "") == day)

    used_day_period: set = set()  # (day, period)
    picked: List[prompts.SlotDisplay] = []

    # Phase 1 : au plus 1 par (day, period), max 2 par jour
    for s in ordered:
        if len(picked) >= limit:
            break
        dt = _slot_start_dt(s)
        day = getattr(s, "day", "") or ""
        period = _slot_period(s)
        key = (day, period)
        if key in used_day_period:
            continue
        if day_count(picked, day) >= 2:
            continue
        picked.append(s)
        used_day_period.add(key)

    # Phase 2 : fallback 2h si pas assez (respecter écart par rapport au dernier déjà pické)
    remaining = [s for s in ordered if s not in picked]
    last_dt = _slot_start_dt(picked[-1]) if picked else None
    last_day = (getattr(picked[-1], "day", "") or "") if picked else None
    for s in remaining:
        if len(picked) >= limit:
            break
        dt = _slot_start_dt(s)
        day = getattr(s, "day", "") or ""
        if day_count(picked, day) >= 2:
            continue
        if last_dt is None:
            picked.append(s)
            last_dt = dt
            last_day = day
            continue
        if dt is None:
            picked.append(s)
            last_dt = dt
            last_day = day
            continue
        delta_min = (dt - last_dt).total_seconds() / 60 if last_dt else 0
        if day != last_day or delta_min >= min_gap_minutes:
            picked.append(s)
            last_dt = dt
            last_day = day

    # Phase 3 : si toujours insuffisant, compléter sans contrainte d'écart.
    # Priorité fiabilité vocale: mieux vaut 3 créneaux proches que 1 seul créneau.
    if len(picked) < limit:
        for s in remaining:
            if len(picked) >= limit:
                break
            if s in picked:
                continue
            picked.append(s)

    # Ré-indexer idx 1..limit — P0: préserver source (évite sqlite par défaut sur slots Google)
    out = []
    for i, s in enumerate(picked, start=1):
        out.append(prompts.SlotDisplay(
            idx=i,
            label=s.label,
            slot_id=getattr(s, "slot_id", i - 1),
            start=getattr(s, "start", ""),
            day=getattr(s, "day", ""),
            hour=getattr(s, "hour", 0),
            label_vocal=getattr(s, "label_vocal", "") or s.label,
            source=getattr(s, "source", "sqlite"),
        ))
    return out


def is_slot_far_from_rejected(
    start_iso: str,
    rejected_starts: Optional[List[str]],
    window_minutes: int = REJECTED_SLOT_WINDOW_MINUTES,
) -> bool:
    """Vrai si le créneau n'est pas dans une fenêtre ±window_minutes d'un refus (pour skip neighbors)."""
    if not start_iso:
        return True
    try:
        dt = datetime.fromisoformat(str(start_iso).replace("Z", "+00:00"))
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)
    except Exception:
        return True
    for r in (rejected_starts or []):
        if not r:
            continue
        try:
            ref = datetime.fromisoformat(str(r).replace("Z", "+00:00"))
            if ref.tzinfo:
                ref = ref.replace(tzinfo=None)
        except Exception:
            continue
        if abs((dt - ref).total_seconds() / 60) <= window_minutes:
            return False
    return True


def _filter_slots_away_from_rejected(
    slots: List[prompts.SlotDisplay],
    rejected_starts: List[str],
    window_minutes: int = REJECTED_SLOT_WINDOW_MINUTES,
) -> List[prompts.SlotDisplay]:
    """Exclut les créneaux dans une fenêtre de ±window_minutes autour des refus (ne pas reproposer un voisin)."""
    if not rejected_starts:
        return slots
    rejected_dts: List[datetime] = []
    for start_iso in rejected_starts:
        if not start_iso:
            continue
        try:
            dt = datetime.fromisoformat(str(start_iso).replace("Z", "+00:00"))
            rejected_dts.append(dt.replace(tzinfo=None) if dt.tzinfo else dt)
        except Exception:
            pass
    if not rejected_dts:
        return slots
    out = []
    for s in slots:
        dt = _slot_start_dt(s)
        if dt is None:
            out.append(s)
            continue
        ok = True
        for ref in rejected_dts:
            delta_min = abs((dt - ref).total_seconds() / 60)
            if delta_min <= window_minutes:
                ok = False
                break
        if ok:
            out.append(s)
    return out


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


def _sort_slots_by_target_minute(slots: List, target_minute: int) -> List:
    """Trie les créneaux par proximité avec une heure cible."""
    if target_minute is None or target_minute < 0:
        return list(slots or [])
    return sorted(
        slots or [],
        key=lambda s: (abs(_slot_minute_of_day(s) - target_minute), _slot_minute_of_day(s)),
    )


def filter_slots_by_time_constraint(slots: List, session) -> List:
    """
    RÈGLE 7: Filtre les créneaux selon la contrainte horaire explicite.
    - after: garder slots >= constraint
    - before: garder slots <= constraint
    - around: trier par proximité avec l'heure cible
    - exact: garder slots == constraint
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
        elif t == "exact" and minute == m:
            out.append(s)
        elif t == "around":
            out.append(s)
    if t == "around":
        return _sort_slots_by_target_minute(out, m)
    return out


# ============================================
# FONCTIONS PRINCIPALES
# ============================================

def prefetch_slots_for_pref_question(session: Any) -> None:
    """
    Précharge les créneaux matin/après-midi en arrière-plan pendant que l'utilisateur
    réfléchit à la question "matin ou après-midi". Fire-and-forget, ne bloque pas.
    """
    if _DISABLE_SLOT_CACHE:
        return
    now = time.time()
    ts = getattr(session, "_prefetch_slots_ts", 0) or 0
    if now - ts < 60:
        return
    session._prefetch_slots_ts = now

    def _run() -> None:
        try:
            session._prefetch_morning = get_slots_for_display(
                limit=3, pref="matin", session=session
            )
            session._prefetch_afternoon = get_slots_for_display(
                limit=3, pref="après-midi", session=session
            )
            logger.info(
                "prefetch_slots: morning=%s afternoon=%s",
                len(session._prefetch_morning or []),
                len(session._prefetch_afternoon or []),
            )
        except Exception as e:
            logger.debug("prefetch_slots failed: %s", e)
            session._prefetch_morning = None
            session._prefetch_afternoon = None

    threading.Thread(target=_run, daemon=True).start()


def _normalize_iso(s: Optional[str]) -> str:
    """Normalise un timestamp ISO pour comparaison (strip, Z -> +00:00)."""
    if not s:
        return ""
    s = (s or "").strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return s


def get_slots_for_display(
    limit: int = 3,
    pref: Optional[str] = None,
    session: Optional[Any] = None,
    exclude_start_iso: Optional[str] = None,
    exclude_end_iso: Optional[str] = None,
) -> List[prompts.SlotDisplay]:
    """
    Récupère les créneaux disponibles, filtrés par préférence si fournie.
    
    pref: "matin" (9h-12h), "après-midi" (14h-18h), "soir" (18h+) — pour ne pas proposer
    un créneau à 10h quand l'utilisateur a dit "je finis à 17h".
    
    exclude_start_iso / exclude_end_iso: si fournis, le créneau (start_iso, end_iso) égal
    est exclu du résultat (V3 retry après slot_taken).
    
    Utilise Google Calendar si configuré, sinon SQLite.
    Cache utilisé seulement si pref est None (sinon filtre spécifique).
    """
    import time
    t_start = time.time()
    tenant_id = getattr(session, "tenant_id", None) or 1
    preferred_minute = getattr(session, "time_constraint_minute", -1) if session is not None else -1
    has_time_constraint = bool(
        session is not None
        and (getattr(session, "time_constraint_type", "") or "")
        and getattr(session, "time_constraint_minute", -1) is not None
        and getattr(session, "time_constraint_minute", -1) >= 0
    )

    # Fast-path absolu : cache avant toute résolution adapter/tenant-config (évite overhead DB).
    rejected = getattr(session, "rejected_slot_starts", None) if session else None
    if not rejected and not has_time_constraint:
        cached = _get_cached_slots(limit, tenant_id, pref=pref)
        if cached:
            logger.info(f"⚡ get_slots_for_display: cache hit pref={pref} ({(time.time() - t_start) * 1000:.0f}ms)")
            return cached

    strict_google_mode = False
    try:
        from backend.tenant_config import get_params
        _params = get_params(tenant_id) or {}
        strict_google_mode = ((_params.get("calendar_provider") or "").strip().lower() == "google")
    except Exception:
        strict_google_mode = False

    # Adapter calendrier par tenant (google/none) — fallback config global
    from backend.calendar_adapter import get_calendar_adapter, is_local_only_adapter
    adapter = get_calendar_adapter(session)

    # provider=none : agenda externe absent, on bascule sur les créneaux locaux UWI.
    use_local_fallback = is_local_only_adapter(adapter)
    if use_local_fallback:
        logger.info("get_slots_for_display: tenant_id=%s provider=none → local fallback", tenant_id)

    # Source: adapter (google) ou legacy _get_calendar_service
    calendar_or_adapter = None if use_local_fallback else (adapter if adapter else _get_calendar_service())
    if strict_google_mode and not use_local_fallback and not calendar_or_adapter:
        logger.warning("GOOGLE_CALENDAR_STRICT_NO_SERVICE tenant_id=%s pref=%s", tenant_id, pref)
        return []

    # Récupérer le pool brut (pas encore étalé) pour pouvoir filtrer refus puis étaler
    if calendar_or_adapter:
        try:
            pool = _get_slots_from_google_calendar(
                calendar_or_adapter,
                limit,
                pref=pref,
                tenant_id=tenant_id,
                preferred_minute=preferred_minute if has_time_constraint else None,
                preferred_time_type=(getattr(session, "time_constraint_type", "") or "") if has_time_constraint else None,
            )
        except GoogleCalendarPermissionError as e:
            if strict_google_mode:
                logger.warning(
                    "GOOGLE_CALENDAR_PERMISSION_STRICT tenant_id=%s pref=%s error=%s",
                    tenant_id,
                    pref,
                    e,
                )
                return []
            logger.warning(
                "GOOGLE_CALENDAR_PERMISSION_FALLBACK tenant_id=%s pref=%s error=%s",
                tenant_id,
                pref,
                e,
            )
            pool = _get_slots_from_sqlite(limit, pref=pref, tenant_id=tenant_id)
        except (GoogleCalendarNotFoundError, GoogleCalendarError) as e:
            if strict_google_mode:
                logger.warning(
                    "GOOGLE_CALENDAR_READ_STRICT tenant_id=%s pref=%s error=%s",
                    tenant_id,
                    pref,
                    e,
                )
                return []
            logger.warning(
                "GOOGLE_CALENDAR_READ_FALLBACK tenant_id=%s pref=%s error=%s",
                tenant_id,
                pref,
                e,
            )
            pool = _get_slots_from_sqlite(limit, pref=pref, tenant_id=tenant_id)
    else:
        if strict_google_mode and not use_local_fallback:
            logger.warning("GOOGLE_CALENDAR_STRICT_NO_FALLBACK tenant_id=%s pref=%s", tenant_id, pref)
            return []
        pool = _get_slots_from_sqlite(limit, pref=pref, tenant_id=tenant_id)

    # Si préférence demandée mais aucun créneau trouvé, fallback sans filtre (ne pas bloquer)
    if pref and (not pool or len(pool) == 0):
        logger.info(f"⚠️ Aucun créneau pour pref={pref}, fallback sans filtre")
        if calendar_or_adapter:
            try:
                pool = _get_slots_from_google_calendar(
                    calendar_or_adapter,
                    limit,
                    pref=None,
                    tenant_id=tenant_id,
                    preferred_minute=preferred_minute if has_time_constraint else None,
                    preferred_time_type=(getattr(session, "time_constraint_type", "") or "") if has_time_constraint else None,
                )
            except GoogleCalendarPermissionError as e:
                if strict_google_mode:
                    logger.warning(
                        "GOOGLE_CALENDAR_PERMISSION_STRICT tenant_id=%s pref=%s error=%s",
                        tenant_id,
                        pref,
                        e,
                    )
                    return []
                logger.warning(
                    "GOOGLE_CALENDAR_PERMISSION_FALLBACK tenant_id=%s pref=%s error=%s",
                    tenant_id,
                    pref,
                    e,
                )
                pool = _get_slots_from_sqlite(limit, pref=None, tenant_id=tenant_id)
            except (GoogleCalendarNotFoundError, GoogleCalendarError) as e:
                if strict_google_mode:
                    logger.warning(
                        "GOOGLE_CALENDAR_READ_STRICT tenant_id=%s pref=%s error=%s",
                        tenant_id,
                        pref,
                        e,
                    )
                    return []
                logger.warning(
                    "GOOGLE_CALENDAR_READ_FALLBACK tenant_id=%s pref=%s error=%s",
                    tenant_id,
                    pref,
                    e,
                )
                pool = _get_slots_from_sqlite(limit, pref=None, tenant_id=tenant_id)
        else:
            if strict_google_mode and not use_local_fallback:
                logger.warning("GOOGLE_CALENDAR_STRICT_NO_FALLBACK tenant_id=%s pref=%s", tenant_id, pref)
                return []
            pool = _get_slots_from_sqlite(limit, pref=None, tenant_id=tenant_id)

    # Exclure créneaux "voisins" des refus (±90 min) pour ne pas reproposer la même plage
    if rejected:
        pool = _filter_slots_away_from_rejected(pool, rejected, REJECTED_SLOT_WINDOW_MINUTES)
        logger.info(f"🔄 get_slots_for_display: après exclusion refusés, {len(pool)} créneaux")
    # RÈGLE 7: contrainte horaire AVANT spread (sinon on casse la variété après coup)
    filtered_by_time_constraint = None
    if session is not None:
        try:
            t = getattr(session, "time_constraint_type", "") or ""
            if t:
                filtered_by_time_constraint = t
            pool = filter_slots_by_time_constraint(pool, session)
        except Exception:
            pass
    # Étaler : 1 par (jour, période) + max 2/jour, fallback 2h
    slots = _spread_slots(pool, limit=limit, min_gap_minutes=MIN_SLOT_GAP_MINUTES)

    # V3: exclure le créneau (start_iso, end_iso) si fourni (retry après slot_taken)
    if exclude_start_iso or exclude_end_iso:
        ex_start = _normalize_iso(exclude_start_iso)
        ex_end = _normalize_iso(exclude_end_iso)
        out = []
        for s in slots:
            d = s if isinstance(s, dict) else getattr(s, "__dict__", {})
            start = _normalize_iso(d.get("start_iso") or d.get("start"))
            end = _normalize_iso(d.get("end_iso") or d.get("end"))
            if ex_start and ex_end and start == ex_start and end == ex_end:
                continue
            out.append(s)
        slots = out
        if ex_start or ex_end:
            logger.info("get_slots_for_display: excluded slot %s..%s → %s slots", ex_start[:19], ex_end[:19], len(slots))

    if not rejected and not has_time_constraint:
        _set_cached_slots(slots, tenant_id, pref=pref)

    log_extra = ""
    if filtered_by_time_constraint:
        log_extra = f" filtered_by_time_constraint={filtered_by_time_constraint}"
    logger.info(
        f"⏱️ get_slots_for_display: {(time.time() - t_start) * 1000:.0f}ms ({len(slots)} slots, pref={pref}){log_extra}"
    )
    return slots


def _get_slots_from_google_calendar(
    calendar,
    limit: int,
    pref: Optional[str] = None,
    tenant_id: int = 1,
    preferred_minute: Optional[int] = None,
    preferred_time_type: Optional[str] = None,
) -> List[prompts.SlotDisplay]:
    """Récupère le pool de créneaux via Google Calendar (étalement fait dans get_slots_for_display)."""
    from backend.tenant_config import get_booking_rules

    rules = get_booking_rules(tenant_id)
    duration_minutes = rules["duration_minutes"]
    base_start = rules["start_hour"]
    base_end = rules["end_hour"]
    booking_days = rules["booking_days"]
    buffer_minutes = rules["buffer_minutes"]

    pool: List[prompts.SlotDisplay] = []
    has_explicit_time_constraint = preferred_minute is not None and preferred_minute >= 0
    # Avec une contrainte horaire explicite, il faut récupérer un pool plus large
    # avant filtrage ; sinon on peut éliminer à tort les 3 premiers créneaux.
    target_pool_size = max(3, limit)
    per_day_limit = 1
    if has_explicit_time_constraint:
        target_pool_size = max(12, limit * 4)
        per_day_limit = max(4, limit)
    # Plage horaire selon préférence (intersection avec règles tenant)
    if preferred_minute is not None and preferred_minute >= 0:
        preferred_hour = preferred_minute // 60
        constraint_type = (preferred_time_type or "").strip().lower()
        if constraint_type == "before":
            start_hour = base_start
            end_hour = min(base_end, max(base_start + 1, preferred_hour + 1))
        elif constraint_type == "exact":
            start_hour = max(base_start, preferred_hour)
            end_hour = min(base_end, max(start_hour + 1, preferred_hour + 1))
        elif constraint_type == "after":
            start_hour = max(base_start, preferred_hour)
            end_hour = base_end
        else:
            start_hour = max(base_start, preferred_hour)
            end_hour = min(base_end, max(start_hour + 1, preferred_hour + 3))
    elif pref == "matin":
        start_hour, end_hour = max(base_start, 9), min(12, base_end)
    elif pref == "après-midi":
        start_hour, end_hour = max(14, base_start), min(18, base_end)
    elif pref == "soir":
        start_hour, end_hour = max(18, base_start), min(20, base_end)
    else:
        start_hour, end_hour = base_start, base_end

    candidate_dates = []
    for day_offset in range(1, 8):
        date = datetime.now() + timedelta(days=day_offset)
        if date.weekday() not in booking_days:
            continue
        candidate_dates.append(date)

    batched_getter = getattr(calendar, "get_free_slots_range", None)
    if callable(batched_getter) and candidate_dates:
        batch_slots = batched_getter(
            dates=candidate_dates,
            duration_minutes=duration_minutes,
            start_hour=start_hour,
            end_hour=end_hour,
            limit=target_pool_size,
            buffer_minutes=buffer_minutes,
            per_day_limit=per_day_limit,
        )
        if batch_slots:
            days_fr = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
            for slot in batch_slots:
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
                pool.append(prompts.SlotDisplay(
                    idx=len(pool) + 1,
                    label=slot['label'],
                    slot_id=len(pool),
                    start=start_iso,
                    day=day_fr,
                    hour=hour,
                    label_vocal=label_vocal or slot.get('label', ''),
                    source="google",
                ))
            logger.info(f"Google Calendar: {len(pool)} créneaux en pool batch (pref={pref})")
            return pool

    days_fr = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
    for date in candidate_dates:
        if len(pool) >= target_pool_size:
            break
        day_slots = calendar.get_free_slots(
            date=date,
            duration_minutes=duration_minutes,
            start_hour=start_hour,
            end_hour=end_hour,
            limit=per_day_limit,
            buffer_minutes=buffer_minutes,
        )
        if not day_slots:
            continue
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
            pool.append(prompts.SlotDisplay(
                idx=len(pool) + 1,
                label=slot['label'],
                slot_id=len(pool),
                start=start_iso,
                day=day_fr,
                hour=hour,
                label_vocal=label_vocal or slot.get('label', ''),
                source="google",
            ))
            if len(pool) >= target_pool_size:
                break
    logger.info(f"Google Calendar: {len(pool)} créneaux en pool rapide (pref={pref})")
    return pool


def _get_slots_from_local(
    limit: int,
    pref: Optional[str] = None,
    tenant_id: int = 1,
) -> List[prompts.SlotDisplay]:
    """
    PG-first puis SQLite fallback : récupère le pool de créneaux local.
    Returns SlotDisplay avec source="pg" ou "sqlite".
    """
    days_fr = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']

    def _to_slot_display(r: dict, i: int, src: str) -> prompts.SlotDisplay:
        label = _format_slot_label_vocal(r.get('date', ''), r.get('time', '09:00'))
        day_fr, hour, start_iso, label_vocal = '', 0, '', ''
        try:
            dt = datetime.strptime(r.get('date', '')[:10], "%Y-%m-%d")
            day_fr = days_fr[dt.weekday()]
            hour, minute = map(int, (r.get('time') or '9:00').split(':')[:2])
            start_iso = f"{r.get('date', '')}T{r.get('time', '09:00')}:00"
            label_vocal = f"{day_fr} à {hour}h"
        except Exception:
            pass
        return prompts.SlotDisplay(
            idx=i,
            label=label,
            slot_id=int(r["id"]),
            start=start_iso,
            day=day_fr,
            hour=hour,
            label_vocal=label_vocal or label,
            source=src,
        )

    # PG-first
    if config.USE_PG_SLOTS:
        try:
            from backend.slots_pg import pg_list_free_slots, pg_cleanup_and_ensure_slots
            pg_cleanup_and_ensure_slots(tenant_id)
            raw = pg_list_free_slots(tenant_id, limit=SLOTS_POOL_SIZE, pref=pref)
            if raw:
                pool = [_to_slot_display(r, i, "pg") for i, r in enumerate(raw, start=1)]
                logger.info("SLOTS_READ source=pg tenant_id=%s (%s créneaux)", tenant_id, len(pool))
                return pool
        except Exception as e:
            logger.debug("SLOTS_READ pg failed: %s (fallback sqlite)", e)

    # Fallback SQLite
    try:
        from backend.db import list_free_slots
        raw = list_free_slots(limit=SLOTS_POOL_SIZE, pref=pref)
        pool = [_to_slot_display(dict(r), i, "sqlite") for i, r in enumerate(raw, start=1)]
        logger.info("SLOTS_READ source=sqlite tenant_id=%s (%s créneaux)", tenant_id, len(pool))
        return pool
    except Exception as e:
        logger.error("Erreur SQLite slots: %s", e)
        return []


def _get_slots_from_sqlite(limit: int, pref: Optional[str] = None, tenant_id: int = 1) -> List[prompts.SlotDisplay]:
    """Alias pour _get_slots_from_local (rétrocompat)."""
    return _get_slots_from_local(limit, pref, tenant_id)


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


def slot_to_vocal_label(slot: Any) -> str:
    """
    Retourne le libellé vocal complet pour un slot (format TTS).
    Ex: "jeudi 20 février à 14 heures".
    slot: dict canonique ou SlotDisplay (start_iso / start attendu).
    """
    start_iso = None
    if isinstance(slot, dict):
        start_iso = slot.get("start_iso") or slot.get("start") or slot.get("start_time")
    else:
        start_iso = getattr(slot, "start_iso", None) or getattr(slot, "start", None) or getattr(slot, "start_time", None)
    if not start_iso:
        return getattr(slot, "label_vocal", None) or (slot.get("label_vocal") if isinstance(slot, dict) else None) or ""
    # start_iso type "2026-01-25T14:00:00" ou "2026-01-25 14:00:00"
    parts = str(start_iso).replace(" ", "T").split("T")
    date_str = parts[0] if parts else ""
    time_str = (parts[1][:5] if len(parts) > 1 and parts[1] else "") or "09:00"  # HH:MM
    return _format_slot_label_vocal(date_str, time_str)


def store_pending_slots(session, slots: List[Any], enrich_google: bool = True) -> None:
    """
    Stocke les créneaux proposés dans la session (Fix 3: format canonique unique).
    slots: SlotDisplay ou dicts → convertis en format canonique.
    """
    source = None
    if slots:
        s0 = slots[0]
        source = (s0.get("source") if isinstance(s0, dict) else getattr(s0, "source", None)) or "sqlite"
    canonical = to_canonical_slots(slots, source)
    session.pending_slots = canonical
    session._slots_source = source or "sqlite"
    # Instrumentation slot lifecycle (debug prod)
    ids_preview = [_slot_get(s, "id") or _slot_get(s, "slot_id") for s in canonical[:3]]
    logger.info(
        "[SLOTS_SET] conv_id=%s count=%s source=%s ids=%s",
        getattr(session, "conv_id", "")[:20],
        len(canonical),
        session._slots_source,
        ids_preview,
    )

    from backend.calendar_adapter import get_calendar_adapter
    adapter = get_calendar_adapter(session)
    calendar = None if (adapter and not adapter.can_propose_slots()) else (adapter or _get_calendar_service())
    if enrich_google and calendar and slots and (source or "").lower() == "google":
        _store_google_calendar_slots(session, slots, calendar)


def _store_google_calendar_slots(session, slots: List[prompts.SlotDisplay], calendar=None) -> None:
    """Stocke les données Google Calendar pour le booking (calendar = adapter ou service)."""
    if calendar is None:
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
        
        try:
            day_slots = calendar.get_free_slots(
                date=date,
                duration_minutes=15,
                start_hour=9,
                end_hour=18,
                limit=len(slots) - len(full_slots)
            )
        except GoogleCalendarPermissionError as e:
            logger.warning("pending_google_slots skipped: permission tenant_id=%s error=%s", getattr(session, "tenant_id", None) or 1, e)
            return
        except (GoogleCalendarNotFoundError, GoogleCalendarError) as e:
            logger.warning("pending_google_slots skipped: google error tenant_id=%s error=%s", getattr(session, "tenant_id", None) or 1, e)
            return
        
        full_slots.extend(day_slots)
    
    session.pending_google_slots = full_slots[:len(slots)]


def book_slot_from_session(session, choice_index_1based: int) -> tuple[bool, str | None]:
    """
    Réserve le créneau choisi par l'utilisateur.
    Fix 3: utilise pending_slots (format canonique) comme seule source de vérité.
    Returns (success, reason).
    - success=True -> reason=None
    - success=False, reason="slot_taken" -> créneau déjà pris (message adapté)
    - success=False, reason="technical" -> erreur technique / slots manquants (évite "plus dispo" à tort)
    """
    conv_id = getattr(session, "conv_id", "")
    slots = getattr(session, "pending_slots", None) or []
    t0 = time.perf_counter()

    logger.info(
        "[BOOKING_ENTER] conv_id=%s choice=%s pending_len=%s first_keys=%s",
        conv_id,
        choice_index_1based,
        len(slots),
        list(slots[0].keys()) if slots else [],
    )

    # Normaliser: si pending_slots contient des SlotDisplay (legacy), convertir en canonique
    if slots and not isinstance(slots[0], dict):
        slots = to_canonical_slots(slots)
        session.pending_slots = slots

    if slots and 1 <= choice_index_1based <= len(slots):
        chosen = slots[choice_index_1based - 1]
        slot_id_val = chosen.get("id") or chosen.get("slot_id")
        logger.info(
            "[SLOT_CHOSEN] conv_id=%s choice=%s slot_id=%s",
            conv_id[:20],
            choice_index_1based,
            slot_id_val,
        )
        src = (chosen.get("source") or "").lower()
        if src == "google":
            start_iso = chosen.get("start_iso") or chosen.get("start")
            end_iso = chosen.get("end_iso") or chosen.get("end")
            if not start_iso or not end_iso:
                logger.warning(
                    "[BOOKING_TECH_REASON] conv_id=%s reason=start_iso_end_iso_missing chosen=%s",
                    conv_id,
                    {k: v for k, v in chosen.items() if k != "label"},
                )
                logger.info("[SLOT_BOOK_RESULT] conv_id=%s success=False reason=technical slot_id=%s", conv_id[:20], slot_id_val)
                return False, "technical"
            logger.info(
                "[BOOKING_CHOSEN_SLOT] choice=%s start_iso=%s end_iso=%s source=google pending_len=%s",
                choice_index_1based,
                start_iso,
                end_iso,
                len(slots),
            )
            t_google_0 = time.perf_counter()
            ok, reason = _book_google_by_iso(session, start_iso, end_iso)
            logger.info(
                "[BOOKING_SEGMENTS] conv_id=%s source=google t_book_provider_ms=%s t_total_ms=%s success=%s reason=%s",
                conv_id[:20],
                round((time.perf_counter() - t_google_0) * 1000, 0),
                round((time.perf_counter() - t0) * 1000, 0),
                ok,
                reason,
            )
            logger.info("[SLOT_BOOK_RESULT] conv_id=%s success=%s reason=%s slot_id=%s", conv_id[:20], ok, reason, slot_id_val)
            return (ok, reason)
        if src in ("sqlite", "pg"):
            slot_id = chosen.get("id") or chosen.get("slot_id")
            # Fallback: slot_id manquant mais start présent → lookup par date+time (session perdue)
            start_val = chosen.get("start_iso") or chosen.get("start")
            if slot_id is None and start_val:
                tenant_id = getattr(session, "tenant_id", None) or 1
                slot_id = _resolve_slot_id_from_start_iso(start_val, source=src, tenant_id=tenant_id)
            if slot_id is None:
                logger.warning(
                    "[BOOKING_TECH_REASON] conv_id=%s reason=slot_id_missing chosen=%s",
                    conv_id,
                    {k: v for k, v in chosen.items() if k != "label"},
                )
                logger.info("[SLOT_BOOK_RESULT] conv_id=%s success=False reason=technical slot_id=missing", conv_id[:20])
                return False, "technical"
            t_local_0 = time.perf_counter()
            ok = _book_local_by_slot_id(session, int(slot_id), source=src)
            logger.info(
                "[BOOKING_SEGMENTS] conv_id=%s source=%s t_book_provider_ms=%s t_total_ms=%s success=%s reason=%s",
                conv_id[:20],
                src,
                round((time.perf_counter() - t_local_0) * 1000, 0),
                round((time.perf_counter() - t0) * 1000, 0),
                ok,
                None if ok else "slot_taken",
            )
            logger.info("[SLOT_BOOK_RESULT] conv_id=%s success=%s reason=%s slot_id=%s", conv_id[:20], ok, None if ok else "slot_taken", slot_id)
            return (ok, None if ok else "slot_taken")

    # Pas de slots : fallback dernier recours = re-fetch et book (session perdue entre requêtes)
    fresh_slots = []
    if session.pending_slot_choice is not None and not slots:
        logger.warning(
            "book_slot_from_session: conv_id=%s pending_slot_choice=%s mais slots vides (pending=%s) -> re-fetch",
            conv_id,
            choice_index_1based,
            len(getattr(session, "pending_slots", None) or []),
        )
        fresh_count = 0
        try:
            fresh_slots = get_slots_for_display(
                limit=3,
                pref=getattr(session.qualif_data, "pref", None),
                session=session,
            )
            fresh_count = len(fresh_slots or [])
            if fresh_slots and 1 <= choice_index_1based <= len(fresh_slots):
                from backend.calendar_adapter import get_calendar_adapter
                adapter = get_calendar_adapter(session)
                source = "google" if (adapter and adapter.can_propose_slots()) else "sqlite"
                slots = to_canonical_slots(fresh_slots, source)
                session.pending_slots = slots
                logger.info("[BOOKING_REFETCH] conv_id=%s re-fetched %s slots, booking choice %s", conv_id, len(slots), choice_index_1based)
                chosen = slots[choice_index_1based - 1]
                src = (chosen.get("source") or "").lower()
                if src == "google":
                    start_iso = chosen.get("start_iso") or chosen.get("start")
                    end_iso = chosen.get("end_iso") or chosen.get("end")
                    if start_iso and end_iso:
                        ok, reason = _book_google_by_iso(session, start_iso, end_iso)
                        logger.info("[SLOT_BOOK_RESULT] conv_id=%s success=%s reason=%s (refetch)", conv_id[:20], ok, reason)
                        return (ok, reason)
                if src in ("sqlite", "pg"):
                    slot_id = chosen.get("id") or chosen.get("slot_id")
                    if slot_id is not None:
                        ok = _book_local_by_slot_id(session, int(slot_id), source=src)
                        logger.info("[SLOT_BOOK_RESULT] conv_id=%s success=%s reason=%s slot_id=%s (refetch)", conv_id[:20], ok, None if ok else "slot_taken", slot_id)
                        return (ok, None if ok else "slot_taken")
        except Exception as e:
            logger.error("book_slot_from_session re-fetch failed: %s", e, exc_info=True)
        logger.warning(
            "[BOOKING_TECH_REASON] conv_id=%s reason=refetch_empty_or_failed fresh_len=%s",
            conv_id,
            len(fresh_slots),
        )
        return False, "technical"

    # Fallback legacy (sessions très anciennes avec pending_slot_ids)
    legacy_ids = getattr(session, "pending_slot_ids", None) or []
    if legacy_ids and 1 <= choice_index_1based <= len(legacy_ids):
        idx = choice_index_1based - 1
        from backend.calendar_adapter import get_calendar_adapter
        adapter = get_calendar_adapter(session)
        calendar = None if (adapter and not adapter.can_propose_slots()) else (adapter or _get_calendar_service())
        if calendar:
            ok = _book_via_google_calendar(session, idx, calendar)
            logger.info("[SLOT_BOOK_RESULT] conv_id=%s success=%s reason=%s (legacy)", conv_id[:20], ok, None if ok else "slot_taken")
            return (ok, None if ok else "slot_taken")
        ok = _book_via_sqlite(session, idx)
        logger.info("[SLOT_BOOK_RESULT] conv_id=%s success=%s reason=%s (legacy)", conv_id[:20], ok, None if ok else "slot_taken")
        return (ok, None if ok else "slot_taken")

    logger.warning("[BOOKING_TECH_REASON] conv_id=%s reason=no_slots_or_invalid_index choice=%s", conv_id, choice_index_1based)
    logger.info("[SLOT_BOOK_RESULT] conv_id=%s success=False reason=technical", conv_id[:20])
    return False, "technical"


def _book_google_by_iso(session, start_iso: str, end_iso: str) -> tuple[bool, str | None]:
    """
    Book Google Calendar à partir des timestamps ISO du slot affiché (sans re-fetch).
    Utilise get_calendar_adapter(session) pour multi-tenant.
    Returns (success, reason) with reason in ("slot_taken", "technical", "permission", None).
    """
    t0 = time.perf_counter()
    from backend.calendar_adapter import get_calendar_adapter
    t_adapter_0 = time.perf_counter()
    adapter = get_calendar_adapter(session)
    t_adapter_ms = round((time.perf_counter() - t_adapter_0) * 1000, 0)
    if adapter is not None and not adapter.can_propose_slots():
        logger.warning("[BOOKING_TECH_REASON] adapter.can_propose_slots=False")
        return False, "technical"
    calendar = adapter if adapter else _get_calendar_service()
    if not calendar:
        logger.warning("[BOOKING_TECH_REASON] no calendar service")
        return False, "technical"

    def _try_once() -> tuple[bool, str | None]:
        try:
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
                if _mirror_google_bookings_enabled(session):
                    # Non bloquant : le miroir interne est auxiliaire et ne doit pas rallonger la confirmation vocale.
                    threading.Thread(
                        target=_mirror_google_booking_to_internal,
                        args=(session, start_iso, event_id),
                        daemon=True,
                    ).start()
                return True, None
            return False, "slot_taken"
        except GoogleCalendarPermissionError as e:
            logger.error("Erreur book_google_by_iso: 403 permission (writer) - %s", e)
            return False, "permission"
        except Exception:
            raise

    try:
        t_try1_0 = time.perf_counter()
        ok, reason = _try_once()
        t_try1_ms = round((time.perf_counter() - t_try1_0) * 1000, 0)
        if ok:
            logger.info(
                "[BOOKING_GOOGLE_SEGMENTS] conv_id=%s t_adapter_ms=%s t_try1_ms=%s retried=%s t_total_ms=%s success=%s",
                getattr(session, "conv_id", "")[:20],
                t_adapter_ms,
                t_try1_ms,
                False,
                round((time.perf_counter() - t0) * 1000, 0),
                True,
            )
            return True, None
        # Pas de retry pour permission ni technical (403 / timeouts / 5xx / 400)
        if reason in ("technical", "permission"):
            logger.info(
                "[BOOKING_GOOGLE_SEGMENTS] conv_id=%s t_adapter_ms=%s t_try1_ms=%s retried=%s t_total_ms=%s success=%s reason=%s",
                getattr(session, "conv_id", "")[:20],
                t_adapter_ms,
                t_try1_ms,
                False,
                round((time.perf_counter() - t0) * 1000, 0),
                False,
                reason,
            )
            return False, reason
        logger.info("Retry booking Google Calendar pour conv_id=%s", getattr(session, "conv_id", ""))
        t_try2_0 = time.perf_counter()
        ok2, reason2 = _try_once()
        t_try2_ms = round((time.perf_counter() - t_try2_0) * 1000, 0)
        logger.info(
            "[BOOKING_GOOGLE_SEGMENTS] conv_id=%s t_adapter_ms=%s t_try1_ms=%s t_try2_ms=%s retried=%s t_total_ms=%s success=%s reason=%s",
            getattr(session, "conv_id", "")[:20],
            t_adapter_ms,
            t_try1_ms,
            t_try2_ms,
            True,
            round((time.perf_counter() - t0) * 1000, 0),
            ok2,
            None if ok2 else (reason2 or "slot_taken"),
        )
        if ok2:
            return True, None
        return False, reason2 or "slot_taken"
    except Exception as e:
        logger.error(
            "[BOOKING_TECH_REASON] _book_google_by_iso exception type=%s msg=%s",
            type(e).__name__,
            str(e),
            exc_info=True,
        )
        return False, "technical"


def _book_local_by_slot_id(session, slot_id: int, source: str = "sqlite") -> bool:
    """Book local (PG ou SQLite) à partir du slot_id du slot affiché."""
    tenant_id = getattr(session, "tenant_id", None) or 1
    if source == "pg":
        try:
            from backend.slots_pg import pg_book_slot_atomic
            result = pg_book_slot_atomic(
                tenant_id=tenant_id,
                slot_id=slot_id,
                name=session.qualif_data.name or "",
                contact=session.qualif_data.contact or "",
                contact_type=getattr(session.qualif_data, "contact_type", None) or "",
                motif=session.qualif_data.motif or "",
            )
            return result is True
        except Exception as e:
            logger.error("Erreur PG booking: %s", e)
            return False
    try:
        from backend.db import book_slot_atomic
        return book_slot_atomic(
            slot_id=slot_id,
            name=session.qualif_data.name or "",
            contact=session.qualif_data.contact or "",
            contact_type=getattr(session.qualif_data, "contact_type", None) or "",
            motif=session.qualif_data.motif or "",
            tenant_id=tenant_id,
        )
    except Exception as e:
        logger.error(f"Erreur book_sqlite_by_slot_id: {e}")
        return False


def _book_via_google_calendar(session, idx: int, calendar=None) -> bool:
    """Réserve via Google Calendar (calendar = adapter ou service)."""
    if calendar is None:
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
    """Fallback: réserve via PG ou SQLite (selon source des slots). Fix 3: utilise pending_slots si disponible."""
    try:
        pending = getattr(session, "pending_slots", None) or []
        if 0 <= idx < len(pending):
            slot = pending[idx]
            slot_id = _slot_get(slot, "id") or _slot_get(slot, "slot_id")
            source = (_slot_get(slot, "source") or getattr(session, "_slots_source", None) or "sqlite").lower()
            if slot_id is not None:
                return _book_local_by_slot_id(session, int(slot_id), source=source)
        # Legacy: pending_slot_ids
        legacy_ids = getattr(session, "pending_slot_ids", None) or []
        if 0 <= idx < len(legacy_ids):
            slot_id = legacy_ids[idx]
            source = getattr(session, "_slots_source", None) or "sqlite"
            return _book_local_by_slot_id(session, int(slot_id), source=source)
    except Exception as e:
        logger.error("Erreur local booking: %s", e)
    return False


def get_label_for_choice(session, choice_index_1based: int) -> Optional[str]:
    """
    Récupère le label d'un créneau choisi.
    Fix 3: utilise pending_slots (format canonique) comme source principale.
    """
    idx = choice_index_1based - 1
    pending = getattr(session, "pending_slots", None) or []

    if 0 <= idx < len(pending):
        slot = pending[idx]
        return _slot_get(slot, "label_vocal") or _slot_get(slot, "label")

    # Fallback legacy
    labels = getattr(session, "pending_slot_labels", None) or []
    if 0 <= idx < len(labels):
        return labels[idx]
    return None


# ============================================
# UTILITAIRES
# ============================================

def cancel_booking(slot_or_session, session: Any = None) -> bool:
    """
    Annule une réservation (Google Calendar via adapter ou SQLite).
    Args:
        slot_or_session: Dict avec 'event_id' (Google) ou 'slot_id'/'id' (SQLite), ou objet avec attributs.
        session: Session pour résoudre l'adapter tenant (calendar_id). Si None, fallback legacy global.
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
        from backend.calendar_adapter import get_calendar_adapter
        adapter = get_calendar_adapter(session) if session else None
        if adapter and adapter.can_propose_slots():
            return adapter.cancel_booking(event_id)
        # Legacy: pas de session ou adapter SQLite
        calendar = _get_calendar_service()
        if not calendar:
            return False
        return calendar.cancel_appointment(event_id)

    if slot_id is not None or appt_id is not None:
        try:
            from backend.db import cancel_booking_sqlite
            tenant_id = getattr(session, "tenant_id", None) or 1
            return cancel_booking_sqlite({"slot_id": slot_id, "id": appt_id}, tenant_id=tenant_id)
        except Exception as e:
            logger.error("Erreur annulation local: %s", e)
            return False

    logger.warning("Pas d'event_id ni slot_id pour annuler")
    return False


def find_booking_by_name(name: str, session: Any = None) -> Optional[Dict[str, Any]]:
    """
    Recherche un RDV existant par nom du patient.
    
    Args:
        name: Nom du patient
        session: Session pour résoudre l'adapter tenant. Si None, fallback legacy (global ou SQLite).
        
    Returns:
        Dict avec les infos du RDV, ou None si non trouvé,
        ou PROVIDER_NONE_SENTINEL si provider=none (pas d'accès agenda).
    """
    from backend.calendar_adapter import get_calendar_adapter, PROVIDER_NONE_SENTINEL
    adapter = get_calendar_adapter(session) if session else None
    if adapter is not None:
        return adapter.find_booking_by_name(name)
    # Legacy: pas de session
    calendar = _get_calendar_service()
    if calendar:
        return _find_booking_google_calendar(calendar, name)
    return _find_booking_sqlite(name, session)


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


def _find_booking_sqlite(name: str, session: Any = None) -> Optional[Dict[str, Any]]:
    """Recherche un RDV dans PG ou SQLite (fallback)."""
    try:
        from backend.db import find_booking_by_name as db_find

        tenant_id = getattr(session, "tenant_id", None) or 1
        booking = db_find(name, tenant_id=tenant_id)
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
