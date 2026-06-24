"""
Extraction LLM des préférences / restrictions RDV (JSON strict + garde-fous + retry).

Le LLM ne propose jamais de créneaux : uniquement une structure normalisée.
Fallback déterministe : appointment_preference_parser.parse_appointment_preferences.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Tuple

from datetime import date

from backend.appointment_preference_parser import (
    TIME_WINDOW_CATALOG,
    build_preference_ack,
    empty_preferences,
    merge_appointment_preferences,
    parse_appointment_preferences,
)
from backend.guards_medical import is_medical_emergency

logger = logging.getLogger(__name__)

# --- Config ---
LLM_PREF_EXTRACT_ENABLED = os.getenv("LLM_PREF_EXTRACT_ENABLED", "true").lower() in ("true", "1", "yes")
LLM_PREF_EXTRACT_TIMEOUT_MS = int(os.getenv("LLM_PREF_EXTRACT_TIMEOUT_MS", "2500"))
LLM_PREF_EXTRACT_MAX_RETRIES = int(os.getenv("LLM_PREF_EXTRACT_MAX_RETRIES", "2"))
LLM_PREF_MIN_CONFIDENCE = float(os.getenv("LLM_PREF_MIN_CONFIDENCE", "0.55"))
LLM_PREF_MAX_TEXT_LEN = int(os.getenv("LLM_PREF_MAX_TEXT_LEN", "600"))
# Modèle : voir backend/llm_provider.py (OpenAI gpt-4o-mini ou Anthropic Haiku 4.5)

ALLOWED_WINDOW_LABELS = frozenset(TIME_WINDOW_CATALOG.keys())
ALLOWED_DAYS = frozenset(
    ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
)
ALLOWED_STRENGTH = frozenset(("hard", "soft"))
ALLOWED_URGENCY = frozenset(("normal", "high", "soon"))
ALLOWED_FLEXIBILITY = frozenset(("low", "medium", "high"))
ALLOWED_SORTING = frozenset(("default", "earliest_available"))

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")

# Phrases d'accusé autorisées sans chiffres inventés (créneaux réels = FSM)
_ACK_FORBIDDEN = re.compile(
    r"\d|€|\b\d{1,2}\s*h\b|créneau\s+(?:le|du|à)",
    re.I,
)

SYSTEM_PROMPT = """Tu es un module d'extraction de contraintes de disponibilité pour un secrétariat médical français.
Tu ne réserves jamais de rendez-vous. Tu n'inventes aucun créneau, horaire précis du cabinet, prix ou adresse.
Tu retournes UNIQUEMENT un JSON valide sur une seule ligne (pas de markdown).

Règles métier :
- preferred_time_windows / excluded_time_windows : label parmi la liste autorisée, strength "hard" (obligation) ou "soft" (préférence).
- "Pas dispo le matin" / "je ne peux pas le matin" => excluded matin hard, PAS preferred matin.
- "Plutôt fin de journée" => preferred fin_de_journee soft.
- "Pas avant 17h" => earliest_time "17:00" (pas de créneau avant).
- "Je travaille jusqu'à 18h" => earliest_time "18:30" ou excluded matin + milieu_apres_midi + fin_apres_midi hard.
- urgency "high" ou "soon" seulement si demande explicite (urgent, au plus vite, premier disponible).
- safety_required true UNIQUEMENT si symptôme potentiellement grave (douleur thoracique, malaise, etc.).
- clarification_needed : une courte question si la phrase est ambiguë (ex. "pas trop tard" sans heure). Sinon null.
- user_ack : 1 phrase naturelle max 180 caractères, SANS chiffre ni horaire précis (pas de "14h", pas de date). Reformule ce que tu as compris.
- Ne remplis pas earliest_date/latest_date sauf si l'utilisateur mentionne un jour/semaine explicite (format YYYY-MM-DD)."""

USER_PROMPT_TEMPLATE = """Date de référence (aujourd'hui) : {ref_date}
Canal : {channel}
Message patient : "{text}"

Labels horaires autorisés : {labels}

Schéma JSON (une ligne) :
{{"confidence":0.0-1.0,"safety_required":false,"safety_message":null,"clarification_needed":null,"user_ack":"phrase sans chiffre","preferred_days":[],"excluded_days":[],"preferred_time_windows":[{{"label":"fin_de_journee","strength":"soft"}}],"excluded_time_windows":[{{"label":"matin","strength":"hard"}}],"earliest_date":null,"latest_date":null,"earliest_time":null,"latest_time":null,"urgency":"normal","flexibility":"medium","sorting":"default"}}

Retourne UNIQUEMENT le JSON."""

REPAIR_PROMPT_TEMPLATE = """Ta réponse précédente était invalide : {error}
Corrige et renvoie UNIQUEMENT le JSON sur une ligne, sans texte autour.

Message patient : "{text}"
Date de référence : {ref_date}"""


@dataclass
class ExtractionMeta:
    source: str  # llm | regex | llm+regex
    confidence: float
    attempts: int
    last_error: Optional[str] = None
    user_ack: Optional[str] = None


class PrefLLMClient(Protocol):
    def complete(self, system: str, user: str, timeout_ms: int) -> str:
        ...


class StubPrefLLMClient:
    """Tests : JSON configurable."""

    def __init__(self, response: Optional[str] = None):
        self.response = response

    def complete(self, system: str, user: str, timeout_ms: int) -> str:
        if self.response:
            return self.response
        return json.dumps(
            {
                "confidence": 0.9,
                "safety_required": False,
                "safety_message": None,
                "clarification_needed": None,
                "user_ack": "D'accord, je cherche en évitant le matin.",
                "preferred_days": [],
                "excluded_days": [],
                "preferred_time_windows": [],
                "excluded_time_windows": [{"label": "matin", "strength": "hard"}],
                "earliest_date": None,
                "latest_date": None,
                "earliest_time": None,
                "latest_time": None,
                "urgency": "normal",
                "flexibility": "medium",
                "sorting": "default",
            },
            ensure_ascii=False,
        )


def get_pref_llm_client() -> Optional[PrefLLMClient]:
    if not LLM_PREF_EXTRACT_ENABLED:
        return None
    from backend.llm_provider import create_chat_client

    return create_chat_client(purpose="pref", provider_env_key="LLM_PREF_PROVIDER")


def _looks_like_pure_json(text: str) -> bool:
    if not text or "\n" in text or "\r" in text or "```" in text:
        return False
    s = text.strip()
    return len(s) >= 2 and s[0] == "{" and s[-1] == "}"


def _parse_json(raw: str) -> Optional[Dict[str, Any]]:
    if not _looks_like_pure_json(raw):
        # Extraire premier bloc JSON si le modèle a ajouté du texte
        m = re.search(r"\{.*\}", raw.strip())
        if not m:
            return None
        raw = m.group(0)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _norm_window_list(items: Any, field_name: str) -> Tuple[List[Dict[str, str]], Optional[str]]:
    if not items:
        return [], None
    if not isinstance(items, list):
        return [], f"{field_name} must be a list"
    out: List[Dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            return [], f"{field_name} invalid item"
        label = (item.get("label") or "").strip().lower().replace("-", "_")
        strength = (item.get("strength") or "soft").strip().lower()
        if label not in ALLOWED_WINDOW_LABELS:
            return [], f"unknown label {label}"
        if strength not in ALLOWED_STRENGTH:
            return [], f"invalid strength {strength}"
        start, end = TIME_WINDOW_CATALOG[label]
        out.append({"label": label, "start": start, "end": end, "strength": strength})
    return out, None


def _validate_user_ack(text: Optional[str]) -> Optional[str]:
    if not text or not isinstance(text, str):
        return None
    s = text.strip()
    if len(s) < 8 or len(s) > 200:
        return None
    if _ACK_FORBIDDEN.search(s):
        return None
    lower = s.lower()
    for bad in ("lundi à", "mardi à", "mercredi à", "jeudi à", "vendredi à", "rdv à", "rendez-vous à"):
        if bad in lower:
            return None
    return s


def validate_llm_preference_payload(data: Dict[str, Any], raw_user_text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Valide et normalise la sortie LLM vers le format appointment_preferences."""
    try:
        conf = float(data.get("confidence", 0))
        if not (0 <= conf <= 1):
            return None, "confidence out of range"

        pref_days = [d.lower() for d in (data.get("preferred_days") or []) if isinstance(d, str)]
        excl_days = [d.lower() for d in (data.get("excluded_days") or []) if isinstance(d, str)]
        for d in pref_days + excl_days:
            if d not in ALLOWED_DAYS:
                return None, f"invalid day {d}"

        pref_w, err = _norm_window_list(data.get("preferred_time_windows"), "preferred_time_windows")
        if err:
            return None, err
        excl_w, err = _norm_window_list(data.get("excluded_time_windows"), "excluded_time_windows")
        if err:
            return None, err

        # Contradiction : preferred matin + excluded matin hard
        pref_labels = {w["label"] for w in pref_w}
        excl_hard = {w["label"] for w in excl_w if w["strength"] == "hard"}
        if "matin" in pref_labels and "matin" in excl_hard:
            pref_w = [w for w in pref_w if w["label"] != "matin"]

        urgency = (data.get("urgency") or "normal").strip().lower()
        if urgency not in ALLOWED_URGENCY:
            return None, "invalid urgency"
        flexibility = (data.get("flexibility") or "medium").strip().lower()
        if flexibility not in ALLOWED_FLEXIBILITY:
            return None, "invalid flexibility"
        sorting = (data.get("sorting") or "default").strip().lower()
        if sorting not in ALLOWED_SORTING:
            return None, "invalid sorting"

        earliest_date = data.get("earliest_date")
        latest_date = data.get("latest_date")
        for key, val in (("earliest_date", earliest_date), ("latest_date", latest_date)):
            if val is not None and val != "null":
                if not isinstance(val, str) or not _DATE_RE.match(val):
                    return None, f"invalid {key}"

        earliest_time = data.get("earliest_time")
        latest_time = data.get("latest_time")
        for key, val in (("earliest_time", earliest_time), ("latest_time", latest_time)):
            if val is not None and val != "null":
                if not isinstance(val, str) or not _TIME_RE.match(val):
                    return None, f"invalid {key}"

        safety_required = bool(data.get("safety_required"))
        safety_message = data.get("safety_message")
        if safety_required:
            if not isinstance(safety_message, str) or len(safety_message.strip()) < 20:
                safety_message = (
                    "Si vous pensez être face à une urgence médicale, "
                    "appelez immédiatement le 15 ou le 112."
                )
        else:
            safety_message = None

        clar = data.get("clarification_needed")
        if clar is not None and clar != "null":
            if not isinstance(clar, str) or len(clar.strip()) < 10 or len(clar) > 160:
                return None, "invalid clarification_needed"
            if any(c.isdigit() for c in clar):
                return None, "clarification must not contain digits"
            clar = clar.strip()
        else:
            clar = None

        user_ack = _validate_user_ack(data.get("user_ack"))

        # Garde-fou médical déterministe (prioritaire)
        if is_medical_emergency(raw_user_text):
            safety_required = True
            safety_message = (
                "Si vous pensez être face à une urgence médicale, "
                "appelez immédiatement le 15 ou le 112."
            )

        result = empty_preferences(raw_user_text)
        result.update(
            {
                "preferred_days": list(dict.fromkeys(pref_days)),
                "excluded_days": list(dict.fromkeys(excl_days)),
                "preferred_time_windows": pref_w,
                "excluded_time_windows": excl_w,
                "earliest_date": earliest_date if earliest_date not in (None, "null") else None,
                "latest_date": latest_date if latest_date not in (None, "null") else None,
                "earliest_time": earliest_time if earliest_time not in (None, "null") else None,
                "latest_time": latest_time if latest_time not in (None, "null") else None,
                "urgency": urgency,
                "flexibility": flexibility,
                "sorting": sorting,
                "safety_required": safety_required,
                "safety_message": safety_message,
                "clarification_needed": clar,
                "_llm_confidence": conf,
                "_user_ack": user_ack,
            }
        )
        return result, None
    except Exception as e:
        return None, str(e)


def _llm_extract_once(
    text: str,
    ref_date: date,
    channel: str,
    client: PrefLLMClient,
    timeout_ms: int,
    repair_error: Optional[str] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    """Un appel LLM. Retourne (payload, error, raw)."""
    labels = ", ".join(sorted(ALLOWED_WINDOW_LABELS))
    safe_text = text.replace('"', "'")[:LLM_PREF_MAX_TEXT_LEN]
    if repair_error:
        user = REPAIR_PROMPT_TEMPLATE.format(
            error=repair_error[:200],
            text=safe_text,
            ref_date=ref_date.isoformat(),
        )
    else:
        user = USER_PROMPT_TEMPLATE.format(
            ref_date=ref_date.isoformat(),
            channel=channel,
            text=safe_text,
            labels=labels,
        )
    try:
        raw = client.complete(SYSTEM_PROMPT, user, timeout_ms)
    except TimeoutError:
        return None, "timeout", None
    except Exception as e:
        return None, f"llm_error:{type(e).__name__}", None

    data = _parse_json(raw or "")
    if not data:
        return None, "invalid_json", raw
    payload, err = validate_llm_preference_payload(data, text)
    if err:
        return None, err, raw
    return payload, None, raw


def extract_preferences_with_llm(
    text: str,
    ref: Optional[date] = None,
    channel: str = "web",
    client: Optional[PrefLLMClient] = None,
) -> Tuple[Optional[Dict[str, Any]], ExtractionMeta]:
    """
    Extraction via LLM avec retries et validation stricte.
    Retourne (None, meta) si échec total (appeler le parseur regex ensuite).
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo

    ref = ref or datetime.now(ZoneInfo("Europe/Paris")).date()
    meta = ExtractionMeta(source="llm", confidence=0.0, attempts=0)

    if not text or not text.strip():
        return None, meta

    client = client or get_pref_llm_client()
    if client is None:
        meta.source = "regex"
        return None, meta

    last_error: Optional[str] = None
    max_attempts = 1 + max(0, LLM_PREF_EXTRACT_MAX_RETRIES)

    for attempt in range(max_attempts):
        meta.attempts = attempt + 1
        payload, err, _raw = _llm_extract_once(
            text,
            ref,
            channel,
            client,
            LLM_PREF_EXTRACT_TIMEOUT_MS,
            repair_error=last_error if attempt > 0 else None,
        )
        if payload is not None:
            conf = float(payload.pop("_llm_confidence", 0.0))
            user_ack = payload.pop("_user_ack", None)
            meta.confidence = conf
            meta.user_ack = user_ack
            if conf < LLM_PREF_MIN_CONFIDENCE and not (
                payload.get("preferred_time_windows")
                or payload.get("excluded_time_windows")
                or payload.get("excluded_days")
                or payload.get("earliest_time")
            ):
                last_error = "low_confidence"
                continue
            return payload, meta
        last_error = err or "unknown"
        meta.last_error = last_error
        logger.info(
            "llm_pref_extract attempt=%s/%s error=%s",
            attempt + 1,
            max_attempts,
            last_error,
        )
        # Échec de transport (timeout / réseau / SDK) : ne pas réessayer.
        # Le provider est dégradé, les tentatives suivantes ré-échoueront en
        # ajoutant ~2,5s chacune et bloqueront le tour de conversation. La regex
        # prend le relais immédiatement.
        if last_error == "timeout" or last_error.startswith("llm_error:"):
            break

    meta.source = "regex"
    return None, meta


def _regex_covers_message(regex_parsed: Dict[str, Any]) -> bool:
    """True si le parseur déterministe a déjà extrait des contraintes exploitables."""
    if regex_parsed.get("safety_required"):
        return True
    if regex_parsed.get("preferred_time_windows") or regex_parsed.get("excluded_time_windows"):
        return True
    if regex_parsed.get("preferred_days") or regex_parsed.get("excluded_days"):
        return True
    if regex_parsed.get("earliest_date") or regex_parsed.get("latest_date"):
        return True
    if regex_parsed.get("earliest_time") or regex_parsed.get("latest_time"):
        return True
    return False


def extract_preferences_hybrid(
    text: str,
    ref: Optional[date] = None,
    channel: str = "web",
    client: Optional[PrefLLMClient] = None,
) -> Tuple[Dict[str, Any], ExtractionMeta]:
    """
    Regex d'abord ; LLM seulement si le message reste ambigu (latence web).
    """
    from backend.start_router import is_booking_start_message
    from backend.appointment_preference_parser import message_has_availability_hints

    if is_booking_start_message(text) and not message_has_availability_hints(text):
        regex_parsed = parse_appointment_preferences(text, ref=ref)
        meta = ExtractionMeta(source="booking_start_skip", confidence=0.9, attempts=0)
        regex_parsed["user_ack"] = build_preference_ack(regex_parsed)
        return regex_parsed, meta

    regex_parsed = parse_appointment_preferences(text, ref=ref)
    if not LLM_PREF_EXTRACT_ENABLED or _regex_covers_message(regex_parsed):
        meta = ExtractionMeta(source="regex", confidence=0.88, attempts=0)
        regex_parsed["user_ack"] = build_preference_ack(regex_parsed)
        return regex_parsed, meta

    llm_parsed, meta = extract_preferences_with_llm(text, ref=ref, channel=channel, client=client)

    if llm_parsed is not None:
        merged = merge_appointment_preferences(regex_parsed, llm_parsed)
        # Compléter les champs vides côté LLM avec le regex (dates, etc.)
        for key in ("earliest_date", "latest_date", "earliest_time", "latest_time"):
            if not merged.get(key) and regex_parsed.get(key):
                merged[key] = regex_parsed[key]
        if not merged.get("excluded_time_windows") and regex_parsed.get("excluded_time_windows"):
            merged["excluded_time_windows"] = regex_parsed["excluded_time_windows"]
        if not merged.get("preferred_time_windows") and regex_parsed.get("preferred_time_windows"):
            merged["preferred_time_windows"] = regex_parsed["preferred_time_windows"]
        meta.source = "llm+regex" if meta.source == "llm" else meta.source
        ack = meta.user_ack or build_preference_ack(merged)
        if ack:
            merged["user_ack"] = ack
        return merged, meta

    meta.source = "regex"
    regex_parsed["user_ack"] = build_preference_ack(regex_parsed)
    return regex_parsed, meta


def resolve_preference_user_ack(prefs: Dict[str, Any]) -> str:
    """Phrase d'accusé pour l'UI (jamais de créneau inventé)."""
    custom = prefs.get("user_ack")
    if isinstance(custom, str) and custom.strip():
        validated = _validate_user_ack(custom)
        if validated:
            return validated
    return build_preference_ack(prefs) or "Très bien, je consulte les créneaux disponibles."
