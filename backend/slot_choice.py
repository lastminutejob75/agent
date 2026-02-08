# backend/slot_choice.py
"""
Détection du choix de créneau en phase proposition (early commit).

Règles anti-faux-positifs (P0.5) :
- Chiffre seul : accepté UNIQUEMENT si le message normalisé est exactement "1", "2" ou "3".
  Refusé : "j'ai 2 questions", "je veux 3 rendez-vous" (chiffre dans une phrase).
- En phrase : on n'accepte un chiffre que s'il est précédé d'un marqueur de choix :
  oui 1/2/3, choix/option/créneau/numéro/n° + 1/2/3, le 1/2/3, premier/deuxième/troisième.
  Refusé : "mon numero c'est 06 12 34 56 78" (numéro = téléphone, pas marqueur de slot).
- Jour seul ou heure seule : refusé. "vendredi" -> None, "14h" -> None.
- Jour+heure : accepté UNIQUEMENT si ça matche exactement 1 des slots proposés (pending_slots).
  Si 0 ou >1 match -> None (flow normal "dites oui 1/2/3").
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, List, Optional

# Jours FR -> weekday (lundi=0, mardi=1, ... dimanche=6)
_DAY_TO_WEEKDAY = {
    "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3,
    "vendredi": 4, "samedi": 5, "dimanche": 6,
}


def _normalize(t: str) -> str:
    if not t:
        return ""
    s = t.strip().lower()
    s = re.sub(r"[\s']+", " ", s)
    s = re.sub(r"[.,;!?°]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# Mots qui, seuls, ne constituent PAS un choix (ambigu)
_YES_ONLY = frozenset({
    "oui", "ouais", "ouaip", "daccord", "d'accord", "ok", "okay", "parfait", "c'est ça", "c est ça",
})


def _parse_day_time(text: str) -> Optional[tuple]:
    """
    Parse jour + heure dans le texte.
    Returns (weekday, hour, minute) ou None.
    """
    t = _normalize(text)
    day_match = re.search(
        r"\b(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\b",
        t,
        re.IGNORECASE,
    )
    if not day_match:
        return None
    day_str = day_match.group(1).lower()
    weekday = _DAY_TO_WEEKDAY.get(day_str)
    if weekday is None:
        return None

    # Heure : 14h, 14 h, 14:00, 14h30, 14:30
    time_match = re.search(r"\b(\d{1,2})\s*[h:]\s*(\d{0,2})\b", t)
    if time_match:
        hour = int(time_match.group(1))
        raw_m = time_match.group(2)
        minute = int(raw_m) if (raw_m and raw_m.strip()) else 0
    else:
        time_match = re.search(r"\b(\d{1,2})\s*h\b", t)
        if time_match:
            hour = int(time_match.group(1))
            minute = 0
        else:
            return None

    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return (weekday, hour, minute)
    return None


def _slot_to_day_hour_min(slot: Any) -> Optional[tuple]:
    """Extrait (weekday, hour, minute) d'un slot (SlotDisplay ou dict)."""
    start = getattr(slot, "start", None) or (slot.get("start") if isinstance(slot, dict) else None)
    if start:
        try:
            if isinstance(start, str):
                dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            else:
                dt = start
            return (dt.weekday(), dt.hour, dt.minute)
        except Exception:
            pass
    day_str = getattr(slot, "day", None) or (slot.get("day") if isinstance(slot, dict) else "")
    hour = getattr(slot, "hour", 0) or (slot.get("hour", 0) if isinstance(slot, dict) else 0)
    if day_str:
        weekday = _DAY_TO_WEEKDAY.get(day_str.lower())
        if weekday is not None:
            minute = getattr(slot, "minute", 0) or (slot.get("minute", 0) if isinstance(slot, dict) else 0)
            return (weekday, int(hour), int(minute))
    return None


def detect_slot_choice_by_datetime(text: str, slots: list) -> Optional[int]:
    """
    Match jour+heure dans text contre les slots proposés.
    - Si EXACTEMENT 1 slot correspond -> retourne idx (1-based).
    - Si 0 ou >1 correspondance -> None.
    """
    if not text or not slots or len(slots) == 0:
        return None
    parsed = _parse_day_time(text)
    if parsed is None:
        return None
    target_wd, target_h, target_m = parsed
    matches: List[int] = []
    for i, slot in enumerate(slots):
        key = _slot_to_day_hour_min(slot)
        if key is None:
            continue
        wd, h, m = key
        if wd == target_wd and h == target_h and m == target_m:
            idx_1based = getattr(slot, "idx", i + 1) or (slot.get("idx", i + 1) if isinstance(slot, dict) else i + 1)
            matches.append(idx_1based)
    if len(matches) == 1:
        return matches[0]
    return None


def detect_slot_choice_early(text: str, pending_slots: Optional[list] = None) -> Optional[int]:
    """
    Détection choix de créneau non ambigu (early commit).

    Ordre :
    1) Message exact "1" / "2" / "3" -> OK
    2) "oui" seul -> None (ambigu)
    3) Ordinaux : premier, deuxième, troisième (avec ou sans "le")
    4) Marqueur + chiffre : oui 1, choix 2, option 3, créneau 1, numéro 2, n° 3, le 1
    5) Si pending_slots fourni : match jour+heure (vendredi 14h) -> 1 seul match

    Refus : "j'ai 2 questions", "je veux 3 rdv", "mon numero c'est 06..." (chiffre sans marqueur de choix).
    """
    if not text or not text.strip():
        return None

    t = _normalize(text)

    # 1) Chiffre seul : UNIQUEMENT message exact "1", "2" ou "3"
    if t in ("1", "2", "3"):
        return int(t)

    # 2) "oui" / "ok" seuls = ambigu
    if t in _YES_ONLY:
        return None

    # 3) Ordinaux (premier, deuxième, troisième) avec ou sans "le"
    if re.match(r"^(le\s+)?(premier|un)\s*$", t):
        return 1
    if re.match(r"^(le\s+)?(deuxième|deuxieme|deux|second)\s*$", t):
        return 2
    if re.match(r"^(le\s+)?(troisième|troisieme|trois)\s*$", t):
        return 3

    # 4) Marqueur explicite + chiffre (pas de chiffre seul en phrase)
    if re.match(r"^oui\s+(1|un|premier)\s*$", t):
        return 1
    if re.match(r"^oui\s+(2|deux|deuxième|deuxieme|second)\s*$", t):
        return 2
    if re.match(r"^oui\s+(3|trois|troisième|troisieme)\s*$", t):
        return 3
    if re.match(r"^le\s*[123]\s*$", t):
        return int(re.search(r"[123]", t).group(0))
    for prefix in ("choix", "option", "creneau", "créneau", "numero", "numéro", "n"):
        m = re.match(r"^" + re.escape(prefix) + r"\s*([123])\s*$", t)
        if m:
            return int(m.group(1))
    if re.match(r"^(choix|option|creneau|créneau|numero|numéro)\s+(1|un|premier)\s*$", t):
        return 1
    if re.match(r"^(choix|option|creneau|créneau|numero|numéro)\s+(2|deux|deuxième|deuxieme|second)\s*$", t):
        return 2
    if re.match(r"^(choix|option|creneau|créneau|numero|numéro)\s+(3|trois|troisième|troisieme)\s*$", t):
        return 3

    # 5) Jour + heure (match unique sur pending_slots)
    if pending_slots:
        return detect_slot_choice_by_datetime(text, pending_slots)

    return None
