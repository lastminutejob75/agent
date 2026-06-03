"""
Parseur de préférences / restrictions de disponibilité pour la prise de RDV (web + vocal).

Transforme le langage naturel en structure exploitable par tools_booking.get_slots_for_display.
"""

from __future__ import annotations

import re
import unicodedata
from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from zoneinfo import ZoneInfo

from backend.entity_extraction import extract_target_date, detect_time_slot
from backend.guards_medical import is_medical_emergency
from backend.time_constraints import extract_time_constraint

# Catalogue horaire (spec produit)
TIME_WINDOW_CATALOG: Dict[str, Tuple[str, str]] = {
    "matin": ("08:00", "12:00"),
    "debut_matin": ("08:00", "10:00"),
    "milieu_matin": ("10:00", "11:00"),
    "fin_matin": ("10:30", "12:00"),
    "pause_dejeuner": ("12:00", "14:00"),
    "entre_midi_et_deux": ("12:00", "14:00"),
    "debut_apres_midi": ("13:30", "15:00"),
    "milieu_apres_midi": ("15:00", "16:30"),
    "fin_apres_midi": ("16:30", "18:00"),
    "fin_de_journee": ("17:00", "19:30"),
    "soiree": ("18:00", "19:30"),
    "avant_travail": ("08:00", "09:30"),
    "apres_travail": ("17:30", "19:30"),
    "apres_depot_enfants": ("09:00", "12:00"),
    "avant_sortie_ecole": ("08:00", "16:00"),
    "recuperation_enfants": ("16:00", "17:30"),
}

_DAYS_FR = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")

# Phrases → (label catalogue, strength) — les plus longues d'abord à l'exécution
_POSITIVE_PHRASES: List[Tuple[str, str, str]] = [
    ("plutot en fin de journee", "fin_de_journee", "soft"),
    ("en fin de journee", "fin_de_journee", "soft"),
    ("fin de journee", "fin_de_journee", "soft"),
    ("plutot en fin d apres-midi", "fin_apres_midi", "soft"),
    ("fin d apres-midi", "fin_apres_midi", "soft"),
    ("fin d apres midi", "fin_apres_midi", "soft"),
    ("plutot l apres-midi", "milieu_apres_midi", "soft"),
    ("plutot apres-midi", "milieu_apres_midi", "soft"),
    ("en debut d apres-midi", "debut_apres_midi", "soft"),
    ("debut d apres-midi", "debut_apres_midi", "soft"),
    ("milieu d apres-midi", "milieu_apres_midi", "soft"),
    ("apres le travail", "apres_travail", "soft"),
    ("avant le travail", "avant_travail", "soft"),
    ("pause dejeuner", "pause_dejeuner", "soft"),
    ("pendant ma pause dejeuner", "pause_dejeuner", "soft"),
    ("pendant la pause dejeuner", "pause_dejeuner", "soft"),
    ("entre midi et deux", "entre_midi_et_deux", "soft"),
    ("entre midi et 2", "entre_midi_et_deux", "soft"),
    ("apres avoir depose les enfants", "apres_depot_enfants", "soft"),
    ("apres le depot des enfants", "apres_depot_enfants", "soft"),
    ("avant la sortie d ecole", "avant_sortie_ecole", "soft"),
    ("debut de matinee", "debut_matin", "soft"),
    ("en debut de matinee", "debut_matin", "soft"),
    ("milieu de matinee", "milieu_matin", "soft"),
    ("fin de matinee", "fin_matin", "soft"),
    ("en fin de matinee", "fin_matin", "soft"),
    ("debut de journee", "debut_matin", "soft"),
    ("en debut de journee", "debut_matin", "soft"),
    ("plutot le matin", "matin", "soft"),
    ("plutot matinee", "matin", "soft"),
    ("plutot matin", "matin", "soft"),
    ("le matin", "matin", "soft"),
    ("en matinee", "matin", "soft"),
    ("en soiree", "soiree", "soft"),
    ("apres-midi", "milieu_apres_midi", "soft"),
    ("apres midi", "milieu_apres_midi", "soft"),
]

_NEGATIVE_PHRASES: List[Tuple[str, str, str]] = [
    ("je ne suis pas disponible le matin", "matin", "hard"),
    ("je ne suis pas dispo le matin", "matin", "hard"),
    ("je ne peux pas le matin", "matin", "hard"),
    ("pas disponible le matin", "matin", "hard"),
    ("pas dispo le matin", "matin", "hard"),
    ("evitez le matin", "matin", "hard"),
    ("eviter le matin", "matin", "hard"),
    ("pas le matin", "matin", "hard"),
    ("je ne suis pas disponible l apres-midi", "milieu_apres_midi", "hard"),
    ("pas l apres-midi", "milieu_apres_midi", "hard"),
    ("pas l apres midi", "milieu_apres_midi", "hard"),
    ("pas l apres-midi", "milieu_apres_midi", "hard"),
    ("pas l'apres-midi", "milieu_apres_midi", "hard"),
    ("pas apres-midi", "milieu_apres_midi", "hard"),
    ("pas pendant la pause dejeuner", "pause_dejeuner", "hard"),
    ("pas entre midi et deux", "entre_midi_et_deux", "hard"),
    ("pas entre 12h et 14h", "entre_midi_et_deux", "hard"),
    ("pas trop tot", "matin", "hard"),
    ("pas trop tard", "fin_de_journee", "soft"),
    ("je travaille le matin", "matin", "hard"),
    ("je travaille l apres-midi", "milieu_apres_midi", "hard"),
    ("je travaille l'apres-midi", "milieu_apres_midi", "hard"),
]

_FLEXIBILITY_HIGH = (
    "je suis flexible", "n importe quand", "n'importe quand", "peu importe",
    "comme vous voulez", "quand vous voulez", "aucune preference",
)
_URGENCY_HIGH = (
    "c est urgent", "c'est urgent", "urgent", "au plus vite", "le plus tot possible",
    "le plus tôt possible", "des que possible", "dès que possible", "je ne peux pas attendre",
    "creneau en urgence", "créneau en urgence", "rapidement", "j ai besoin rapidement",
)
_EARLIEST_AVAILABLE = (
    "premier creneau", "premier créneau", "premiers creneaux", "premier disponible",
    "le premier disponible", "je prends le premier", "creneau le plus proche",
)
_SAFETY_EXTRA = (
    "urgence vitale", "idees suicidaires", "idées suicidaires", "saignement important",
)

_HOUR_RANGE_RE = re.compile(
    r"pas\s+entre\s+(\d{1,2})\s*h(?:\s*et\s*(\d{1,2})\s*h)?",
    re.I,
)
_PAS_JOUR_RE = re.compile(
    r"(?:pas|eviter|éviter|jamais)\s+(?:le\s+)?(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)",
    re.I,
)
_PLUTOT_JOUR_RE = re.compile(
    r"(?:plutot|plutôt|de preference|de préférence|si possible|idealement|idéalement)\s+(?:le\s+)?"
    r"(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)",
    re.I,
)
_IDEALEMENT_FALLBACK_RE = re.compile(
    r"idealement\s+(\w+)\s+(\w+).*sinon\s+(\w+)",
    re.I,
)


def _normalize(text: str) -> str:
    lowered = (text or "").lower().strip()
    return "".join(
        c for c in unicodedata.normalize("NFD", lowered)
        if unicodedata.category(c) != "Mn"
    )


def empty_preferences(raw: str = "") -> Dict[str, Any]:
    return {
        "intent": "book_appointment",
        "preferred_days": [],
        "excluded_days": [],
        "preferred_time_windows": [],
        "excluded_time_windows": [],
        "earliest_date": None,
        "latest_date": None,
        "earliest_time": None,
        "latest_time": None,
        "urgency": "normal",
        "flexibility": "medium",
        "sorting": "default",
        "safety_required": False,
        "safety_message": None,
        "clarification_needed": None,
        "raw_user_text": raw or "",
    }


def _window_dict(label: str, strength: str) -> Dict[str, Any]:
    start, end = TIME_WINDOW_CATALOG[label]
    return {"label": label, "start": start, "end": end, "strength": strength}


def _append_window(target: List[Dict], label: str, strength: str) -> None:
    w = _window_dict(label, strength)
    if not any(x["label"] == w["label"] and x["strength"] == w["strength"] for x in target):
        target.append(w)


def _parse_positive_windows(norm: str, preferred: List[Dict]) -> None:
    sorted_phrases = sorted(_POSITIVE_PHRASES, key=lambda x: len(x[0]), reverse=True)
    for phrase, label, strength in sorted_phrases:
        if phrase in norm:
            _append_window(preferred, label, strength)


def _parse_negative_windows(norm: str, excluded: List[Dict]) -> None:
    sorted_phrases = sorted(_NEGATIVE_PHRASES, key=lambda x: len(x[0]), reverse=True)
    for phrase, label, strength in sorted_phrases:
        if phrase in norm:
            _append_window(excluded, label, strength)

    if "je travaille toute la journee" in norm:
        _append_window(excluded, "matin", "hard")
        _append_window(excluded, "milieu_apres_midi", "hard")
        _append_window(excluded, "fin_apres_midi", "hard")
    if "je travaille jusqu a 17h" in norm or "travaille jusqu a 17h" in norm:
        _append_window(excluded, "matin", "hard")
        _append_window(excluded, "milieu_apres_midi", "hard")
    if "je travaille jusqu a 18h" in norm or "finis a 18h" in norm or "finir a 18h" in norm:
        _append_window(excluded, "matin", "hard")
        _append_window(excluded, "milieu_apres_midi", "hard")
        _append_window(excluded, "fin_apres_midi", "hard")

    if "je dois recuperer les enfants" in norm or "recuperer les enfants" in norm:
        _append_window(excluded, "recuperation_enfants", "hard")


def _parse_hour_limits(norm: str, raw: str, result: Dict[str, Any]) -> None:
    m = re.search(r"pas\s+(?:avant|apres|après)\s+(\d{1,2})\s*h", norm)
    if m:
        hour = int(m.group(1))
        if "avant" in m.group(0):
            result["earliest_time"] = f"{hour:02d}:00"
        else:
            result["latest_time"] = f"{hour:02d}:00"
        return

    m2 = re.search(r"je ne peux pas (?:avant|apres|après)\s+(\d{1,2})\s*h", norm)
    if m2:
        hour = int(m2.group(1))
        if "avant" in m2.group(0):
            result["earliest_time"] = f"{hour:02d}:00"
        else:
            result["latest_time"] = f"{hour:02d}:00"

    m3 = _HOUR_RANGE_RE.search(norm)
    if m3:
        h1, h2 = int(m3.group(1)), int(m3.group(2) or m3.group(1))
        if h2 < h1:
            h1, h2 = h2, h1
        result["excluded_time_windows"].append({
            "label": f"entre_{h1}h_et_{h2}h",
            "start": f"{h1:02d}:00",
            "end": f"{h2:02d}:00",
            "strength": "hard",
        })

    tc = extract_time_constraint(raw)
    if tc:
        work_until = any(
            x in norm for x in ("travaille", "finis", "termine", "finir")
        ) and "jusqu" in norm
        if work_until:
            h, m = tc.minute_of_day // 60, tc.minute_of_day % 60
            if m == 0 and h < 23:
                m = 30
                if h == 23:
                    m = 0
            result["earliest_time"] = f"{h:02d}:{m:02d}"
            _append_window(result["preferred_time_windows"], "fin_de_journee", "soft")
        elif tc.type == "after":
            result["earliest_time"] = f"{tc.minute_of_day // 60:02d}:{tc.minute_of_day % 60:02d}"
        else:
            result["latest_time"] = f"{tc.minute_of_day // 60:02d}:{tc.minute_of_day % 60:02d}"


def _week_bounds(ref: date) -> Tuple[date, date]:
    """Lundi–dimanche de la semaine de ref."""
    monday = ref - timedelta(days=ref.weekday())
    return monday, monday + timedelta(days=6)


def _parse_week_phrases(norm: str, ref: date, result: Dict[str, Any]) -> None:
    mon, sun = _week_bounds(ref)
    if "semaine prochaine" in norm or "la semaine prochaine" in norm:
        result["earliest_date"] = (mon + timedelta(days=7)).isoformat()
        result["latest_date"] = (sun + timedelta(days=7)).isoformat()
        return
    if "cette semaine" in norm:
        result["earliest_date"] = ref.isoformat()
        result["latest_date"] = sun.isoformat()
        return
    if "debut de semaine" in norm or "en debut de semaine" in norm:
        for d in ("lundi", "mardi"):
            if d not in result["preferred_days"]:
                result["preferred_days"].append(d)
    if "milieu de semaine" in norm:
        for d in ("mercredi", "jeudi"):
            if d not in result["preferred_days"]:
                result["preferred_days"].append(d)
    if "fin de semaine" in norm:
        for d in ("jeudi", "vendredi", "samedi"):
            if d not in result["preferred_days"]:
                result["preferred_days"].append(d)
    if "pas avant la semaine prochaine" in norm:
        result["earliest_date"] = (mon + timedelta(days=7)).isoformat()


def _parse_days(norm: str, raw: str, result: Dict[str, Any]) -> None:
    for m in _PAS_JOUR_RE.finditer(raw):
        day = m.group(1).lower()
        if day not in result["excluded_days"]:
            result["excluded_days"].append(day)
    for m in _PLUTOT_JOUR_RE.finditer(raw):
        day = m.group(1).lower()
        if day not in result["preferred_days"]:
            result["preferred_days"].append(day)
    for day in _DAYS_FR:
        if re.search(rf"\b{day}\s+matin\b", norm):
            if day not in result["preferred_days"]:
                result["preferred_days"].append(day)
            _append_window(result["preferred_time_windows"], "matin", "soft")
        elif re.search(rf"\b{day}\s+apres", norm):
            if day not in result["preferred_days"]:
                result["preferred_days"].append(day)
            _append_window(result["preferred_time_windows"], "milieu_apres_midi", "soft")

    m = _IDEALEMENT_FALLBACK_RE.search(raw)
    if m:
        d1, t1, d2 = m.group(1).lower(), m.group(2).lower(), m.group(3).lower()
        if d1 in _DAYS_FR and d1 not in result["preferred_days"]:
            result["preferred_days"].insert(0, d1)
        if d2 in _DAYS_FR and d2 not in result["preferred_days"]:
            result["preferred_days"].append(d2)
        if "matin" in t1:
            _append_window(result["preferred_time_windows"], "matin", "soft")


def _parse_flexibility_urgency(norm: str, result: Dict[str, Any]) -> None:
    if any(p in norm for p in _FLEXIBILITY_HIGH):
        result["flexibility"] = "high"
    if any(p in norm for p in _URGENCY_HIGH):
        result["urgency"] = "high"
    if any(p in norm for p in _EARLIEST_AVAILABLE):
        result["urgency"] = "soon"
        result["sorting"] = "earliest_available"
        result["flexibility"] = "high"


def _check_safety(raw: str, norm: str) -> Tuple[bool, Optional[str]]:
    if is_medical_emergency(raw) or any(k in norm for k in _SAFETY_EXTRA):
        return True, (
            "Si vous pensez être face à une urgence médicale, appelez immédiatement le 15 ou le 112."
        )
    return False, None


def _detect_clarification(norm: str, result: Dict[str, Any]) -> Optional[str]:
    if "pas trop tard" in norm and not result.get("latest_time"):
        return "D'accord. Vous préférez plutôt avant 17h ou avant 18h ?"
    if re.search(r"\bapres\b", norm) and not re.search(r"\d{1,2}\s*h", norm):
        if "apres le travail" not in norm and "apres avoir" not in norm:
            return "Après quelle heure environ ?"
    return None


def parse_appointment_preferences(
    text: str,
    ref: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Analyse le texte utilisateur et retourne les contraintes structurées.
    """
    raw = (text or "").strip()
    ref = ref or datetime.now(ZoneInfo("Europe/Paris")).date()
    result = empty_preferences(raw)
    if not raw:
        return result

    norm = _normalize(raw)
    safety, msg = _check_safety(raw, norm)
    result["safety_required"] = safety
    result["safety_message"] = msg

    _parse_positive_windows(norm, result["preferred_time_windows"])
    _parse_negative_windows(norm, result["excluded_time_windows"])
    _parse_hour_limits(norm, raw, result)
    _parse_days(norm, raw, result)
    _parse_week_phrases(norm, ref, result)

    td = extract_target_date(raw, ref=ref)
    if td and not result["earliest_date"]:
        result["earliest_date"] = td.isoformat()
        result["latest_date"] = td.isoformat()

    slot = detect_time_slot(raw)
    if slot:
        label = {
            "matin": "matin",
            "après-midi": "milieu_apres_midi",
            "soir": "fin_de_journee",
        }.get(slot, "matin")
        _append_window(result["preferred_time_windows"], label, "soft")

    _parse_flexibility_urgency(norm, result)
    result["clarification_needed"] = _detect_clarification(norm, result)
    return result


def merge_appointment_preferences(
    base: Optional[Dict[str, Any]],
    new: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Fusionne deux analyses (messages successifs)."""
    if not base:
        return deepcopy(new) if new else empty_preferences()
    if not new:
        return deepcopy(base)
    out = deepcopy(base)
    for key in ("preferred_days", "excluded_days"):
        for item in new.get(key) or []:
            if item not in out[key]:
                out[key].append(item)
    for key in ("preferred_time_windows", "excluded_time_windows"):
        for w in new.get(key) or []:
            if not any(x["label"] == w["label"] and x["strength"] == w["strength"] for x in out[key]):
                out[key].append(deepcopy(w))
    for key in ("earliest_date", "latest_date", "earliest_time", "latest_time"):
        if new.get(key):
            out[key] = new[key]
    if new.get("urgency") not in (None, "normal"):
        out["urgency"] = new["urgency"]
    if new.get("flexibility") == "high":
        out["flexibility"] = "high"
    if new.get("sorting") == "earliest_available":
        out["sorting"] = "earliest_available"
    if new.get("safety_required"):
        out["safety_required"] = True
        out["safety_message"] = new.get("safety_message")
    if new.get("clarification_needed"):
        out["clarification_needed"] = new["clarification_needed"]
    out["raw_user_text"] = new.get("raw_user_text") or out.get("raw_user_text") or ""
    return out


def preferences_to_legacy_pref(prefs: Dict[str, Any]) -> Optional[str]:
    """Résumé texte pour qualif_data.pref (compat moteur existant)."""
    if not prefs:
        return None
    days = prefs.get("preferred_days") or []
    windows = prefs.get("preferred_time_windows") or []
    label = windows[0]["label"] if windows else None
    slot_word = None
    if label in ("matin", "debut_matin", "fin_matin", "milieu_matin"):
        slot_word = "matin"
    elif label in ("fin_de_journee", "soiree", "apres_travail"):
        slot_word = "soir"
    elif label:
        slot_word = "après-midi"
    if days and slot_word:
        return f"{days[0]} {slot_word}"
    if days:
        return days[0]
    if slot_word:
        return slot_word
    if prefs.get("earliest_date") and not days:
        try:
            d = date.fromisoformat(str(prefs["earliest_date"])[:10])
            return _DAYS_FR[d.weekday()]
        except ValueError:
            pass
    return None


def apply_preferences_to_session(session: Any, prefs: Dict[str, Any]) -> None:
    """Applique les préférences structurées sur la session (champs existants + nouveau blob)."""
    session.appointment_preferences = prefs
    qualif = getattr(session, "qualif_data", None)
    if not qualif:
        return

    legacy = preferences_to_legacy_pref(prefs)
    if legacy:
        qualif.pref = legacy

    if prefs.get("earliest_date") and not getattr(qualif, "target_date", None):
        qualif.target_date = str(prefs["earliest_date"])[:10]
    if prefs.get("earliest_date") and prefs.get("latest_date") == prefs.get("earliest_date"):
        qualif.target_date = str(prefs["earliest_date"])[:10]

    earliest_time = prefs.get("earliest_time")
    latest_time = prefs.get("latest_time")
    if earliest_time:
        try:
            h, m = map(int, earliest_time.split(":"))
            session.time_constraint_type = "after"
            session.time_constraint_minute = h * 60 + m
        except ValueError:
            pass
    elif latest_time:
        try:
            h, m = map(int, latest_time.split(":"))
            session.time_constraint_type = "before"
            session.time_constraint_minute = h * 60 + m
        except ValueError:
            pass


def build_preference_ack(prefs: Dict[str, Any]) -> str:
    """Reformulation humaine courte avant la liste de créneaux."""
    if not prefs or prefs.get("flexibility") == "high" and not (
        prefs.get("preferred_time_windows") or prefs.get("excluded_time_windows")
    ):
        return "Très bien, je vous propose les prochains créneaux disponibles."

    parts: List[str] = []
    excluded = prefs.get("excluded_time_windows") or []
    preferred = prefs.get("preferred_time_windows") or []

    hard_matin = any(w.get("label") == "matin" and w.get("strength") == "hard" for w in excluded)
    soft_fin = any(w.get("label") == "fin_de_journee" for w in preferred)

    if hard_matin and soft_fin:
        return (
            "Très bien, je vais éviter les créneaux du matin et vous proposer "
            "en priorité des rendez-vous en fin de journée."
        )
    if prefs.get("earliest_time"):
        return f"D'accord, je cherche plutôt après {prefs['earliest_time']}."
    if hard_matin:
        return "D'accord, je cherche des créneaux en évitant le matin."
    if soft_fin:
        return "Très bien, je privilégie des créneaux en fin de journée."
    if preferred:
        label = preferred[0].get("label", "").replace("_", " ")
        return f"D'accord, je privilégie des créneaux en {label}."
    if prefs.get("excluded_days"):
        days = ", ".join(prefs["excluded_days"])
        return f"Compris, j'évite le {days}."
    if prefs.get("preferred_days"):
        days = ", ".join(prefs["preferred_days"][:2])
        return f"Très bien, je regarde plutôt {days}."
    return "Très bien, je consulte l'agenda avec vos préférences."


def _hm_to_minutes(hm: str) -> int:
    h, m = hm.split(":")
    return int(h) * 60 + int(m)


def _slot_weekday_name(slot: Any) -> Optional[str]:
    day = getattr(slot, "day", None) or (slot.get("day") if isinstance(slot, dict) else None)
    if day:
        return str(day).lower()
    start = getattr(slot, "start", None) or (slot.get("start_iso") if isinstance(slot, dict) else None)
    if not start:
        return None
    try:
        dt = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)
        return _DAYS_FR[dt.weekday()]
    except Exception:
        return None


def _slot_minutes(slot: Any) -> int:
    from backend.tools_booking import _slot_minute_of_day
    return _slot_minute_of_day(slot)


def _slot_date(slot: Any) -> Optional[date]:
    start = getattr(slot, "start", None) or (slot.get("start_iso") if isinstance(slot, dict) else None)
    if not start:
        return None
    try:
        dt = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)
        return dt.date()
    except Exception:
        return None


def _slot_overlaps_window(slot_min: int, window: Dict[str, Any]) -> bool:
    start_m = _hm_to_minutes(window["start"])
    end_m = _hm_to_minutes(window["end"])
    return start_m <= slot_min < end_m


def _slot_violates_hard(slot: Any, prefs: Dict[str, Any]) -> bool:
    if not prefs:
        return False
    day_name = _slot_weekday_name(slot)
    if day_name and day_name in (prefs.get("excluded_days") or []):
        return True

    slot_min = _slot_minutes(slot)
    slot_d = _slot_date(slot)

    earliest_time = prefs.get("earliest_time")
    if earliest_time and slot_min < _hm_to_minutes(earliest_time):
        return True
    latest_time = prefs.get("latest_time")
    if latest_time and slot_min > _hm_to_minutes(latest_time):
        return True

    if slot_d and prefs.get("earliest_date"):
        try:
            if slot_d < date.fromisoformat(str(prefs["earliest_date"])[:10]):
                return True
        except ValueError:
            pass
    if slot_d and prefs.get("latest_date"):
        try:
            if slot_d > date.fromisoformat(str(prefs["latest_date"])[:10]):
                return True
        except ValueError:
            pass

    for w in prefs.get("excluded_time_windows") or []:
        if w.get("strength") != "hard":
            continue
        if _slot_overlaps_window(slot_min, w):
            return True
    return False


def _slot_soft_score(slot: Any, prefs: Dict[str, Any]) -> int:
    if not prefs:
        return 0
    score = 0
    slot_min = _slot_minutes(slot)
    day_name = _slot_weekday_name(slot)

    preferred_days = prefs.get("preferred_days") or []
    if preferred_days and day_name:
        if day_name == preferred_days[0]:
            score += 30
        elif day_name in preferred_days:
            score += 15

    for w in prefs.get("preferred_time_windows") or []:
        if w.get("strength") != "soft":
            continue
        if _slot_overlaps_window(slot_min, w):
            score += 20

    if prefs.get("sorting") == "earliest_available" or prefs.get("urgency") in ("high", "soon"):
        slot_d = _slot_date(slot)
        if slot_d:
            score += max(0, 40 - (slot_d - date.today()).days * 5)
        score += max(0, 12 - slot_min // 60)

    return score


def filter_slots_by_appointment_preferences(
    slots: List[Any],
    prefs: Optional[Dict[str, Any]],
) -> List[Any]:
    """Supprime les créneaux incompatibles avec les restrictions hard."""
    if not prefs or not slots:
        return list(slots or [])
    if prefs.get("flexibility") == "high" and not (
        prefs.get("excluded_time_windows") or prefs.get("excluded_days")
        or prefs.get("earliest_time") or prefs.get("latest_time")
    ):
        return list(slots)
    return [s for s in slots if not _slot_violates_hard(s, prefs)]


def rank_slots_by_appointment_preferences(
    slots: List[Any],
    prefs: Optional[Dict[str, Any]],
) -> List[Any]:
    """Classe les créneaux selon les préférences souples."""
    if not prefs or not slots:
        return list(slots or [])
    return sorted(slots, key=lambda s: (-_slot_soft_score(s, prefs), _slot_minutes(s)))


def process_user_availability_message(
    session: Any,
    text: str,
    ref: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Parse, fusionne avec les préférences session existantes, applique sur la session.
    Retourne le dict fusionné.
    """
    existing = getattr(session, "appointment_preferences", None)
    parsed = parse_appointment_preferences(text, ref=ref)
    merged = merge_appointment_preferences(existing, parsed)
    apply_preferences_to_session(session, merged)
    return merged
