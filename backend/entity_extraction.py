# backend/entity_extraction.py
"""
Extraction d'entités conservatrice pour le flow vocal.

Principe : Tente l'extraction, mais en cas de doute → ne pas pré-remplir.
Mieux vaut redemander que d'avoir une erreur.

Entités extraites :
- name : Nom et prénom du patient
- motif : Motif de la demande (consultation, douleur, etc.)
- pref : Préférence horaire (matin, après-midi)
"""

from __future__ import annotations
import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Dict, Optional, List, Any
from dataclasses import dataclass
from zoneinfo import ZoneInfo


@dataclass
class ExtractedEntities:
    """Entités extraites d'un message."""
    name: Optional[str] = None
    motif: Optional[str] = None
    motif_detail: Optional[str] = None  # ex: "dos" pour "douleur dos"
    pref: Optional[str] = None
    target_date: Optional[date] = None  # ex: 2026-06-18 pour « le 18 juin »
    confidence: float = 0.0  # 0.0 à 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "motif": self.motif,
            "motif_detail": self.motif_detail,
            "pref": self.pref,
            "target_date": self.target_date.isoformat() if self.target_date else None,
            "confidence": self.confidence,
        }
    
    def has_any(self) -> bool:
        """Retourne True si au moins une entité a été extraite."""
        return any([self.name, self.motif, self.pref, self.target_date])


# ----------------------------
# Patterns d'extraction (conservatifs)
# ----------------------------

# Patterns pour les noms (stricts)
# Caractères acceptés : lettres latines + accents français + ü, ö, etc.
_NAME_CHARS = r"a-zéèêëàâäôöùûüîïçñ"

# Note: On utilise [,\s] pour capturer jusqu'à la virgule ou un espace suivi d'autre chose
NAME_PATTERNS = [
    # "je suis jean dupont" ou "je suis jean dupont,"
    rf"je (?:suis|m'appelle) ([{_NAME_CHARS}]+[ ]+[{_NAME_CHARS}]+)",
    rf"(?:c'est|ici) ([{_NAME_CHARS}]+[ ]+[{_NAME_CHARS}]+)",
    rf"mon nom (?:c'est |est )?([{_NAME_CHARS}]+[ ]+[{_NAME_CHARS}]+)",
    rf"([{_NAME_CHARS}]+[ ]+[{_NAME_CHARS}]+) à l'appareil",
]

# Mots à exclure AVANT le nom (faux positifs)
# Ex: "je veux voir le docteur Martin" → "le docteur" est juste avant le nom
NAME_PREFIX_EXCLUSIONS = {
    "le docteur", "le médecin", "mon médecin", "le cabinet",
    "ma mère", "mon père", "mon fils", "ma fille", "mon mari", "ma femme",
}

# Motifs avec keywords
MOTIF_KEYWORDS: Dict[str, List[str]] = {
    "douleur": [
        "douleur", "mal", "souffre", "j'ai mal", "ça fait mal",
        "douleurs", "fait mal",
    ],
    "contrôle": [
        "controle", "contrôle", "check-up", "checkup",
        "visite de contrôle", "suivi",
    ],
    "consultation": [
        "consultation", "consulter", "voir le docteur",
        "voir le médecin",
    ],
    "renouvellement": [
        "renouvellement", "renouveler", "ordonnance",
        "prescription", "renouveler ordonnance",
    ],
    "vaccination": [
        "vaccin", "vaccination", "rappel vaccin", "vaccins",
    ],
    "bilan": [
        "bilan", "analyses", "prise de sang", "bilan sanguin",
        "analyse de sang", "analyses sanguines",
    ],
    "urgence": [
        "urgence", "urgent", "au plus vite", "rapidement",
        "le plus tôt possible",
    ],
    "résultats": [
        "résultats", "resultat", "résultat", "mes résultats",
        "récupérer résultats",
    ],
    "certificat": [
        "certificat", "certificat médical", "attestation",
    ],
}

# Localisations pour les douleurs
PAIN_LOCATIONS = [
    "dos", "tête", "ventre", "genou", "bras", "jambe",
    "épaule", "cou", "poitrine", "gorge", "oreille",
    "dent", "dents", "pied", "main", "hanche",
]

# Préférences horaires
PREF_PATTERNS: Dict[str, List[str]] = {
    "matin": [
        "matin", "matinée", "le matin", "plutôt le matin",
        "9h", "10h", "11h", "début de journée",
    ],
    "après-midi": [
        "après-midi", "après midi", "aprem", "l'après-midi",
        "14h", "15h", "16h", "17h", "cet après-midi",
    ],
    "soir": [
        "soir", "soirée", "fin de journée", "fin de journee", "18h", "19h",
        "fin d'après-midi", "fin d apres-midi", "fin d apres midi",
        "en fin de journée", "en fin de journee", "tard", "plus tard",
    ],
}

_FRENCH_MONTHS: Dict[str, int] = {
    "janvier": 1,
    "fevrier": 2,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
    "décembre": 12,
}

_FR_WEEKDAY_NAMES = [
    "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
]

# Jours de la semaine
DAYS_PATTERNS: Dict[str, List[str]] = {
    "lundi": ["lundi"],
    "mardi": ["mardi"],
    "mercredi": ["mercredi"],
    "jeudi": ["jeudi"],
    "vendredi": ["vendredi"],
    "samedi": ["samedi"],
}


# ----------------------------
# Fonctions d'extraction
# ----------------------------

def extract_name(message: str) -> Optional[str]:
    """
    Extrait le nom du message si pattern clair.
    Retourne None en cas de doute.
    """
    message_lower = message.lower().strip()
    
    for pattern in NAME_PATTERNS:
        match = re.search(pattern, message_lower, re.IGNORECASE)
        if match:
            raw_name = match.group(1).strip()
            
            # Vérifier les exclusions comme préfixe juste avant le nom
            # Ex: "voir le docteur Martin" → on cherche "le docteur" juste avant "Martin"
            match_start = match.start(1)
            prefix_text = message_lower[:match_start]
            
            is_excluded = False
            for exclusion in NAME_PREFIX_EXCLUSIONS:
                if prefix_text.rstrip().endswith(exclusion):
                    is_excluded = True
                    break
            
            if is_excluded:
                continue  # Essayer le prochain pattern
            
            # Validation basique
            parts = raw_name.split()
            if len(parts) >= 2:
                # Vérifier que ce ne sont pas des mots communs
                common_words = {"un", "une", "le", "la", "les", "de", "du", "des", "pour", "avec"}
                if any(p.lower() in common_words for p in parts):
                    continue  # Essayer le prochain pattern
                
                # Capitaliser proprement
                return raw_name.title()
    
    return None


def extract_motif(message: str) -> Dict[str, Optional[str]]:
    """
    Extrait le motif et éventuellement les détails.
    
    Returns:
        {"type": "douleur", "detail": "dos", "full": "douleur dos"}
        ou {} si rien trouvé
    """
    message_lower = message.lower().strip()
    result: Dict[str, Optional[str]] = {}
    
    for motif_type, keywords in MOTIF_KEYWORDS.items():
        if any(kw in message_lower for kw in keywords):
            result["type"] = motif_type
            
            # Si douleur, chercher la localisation
            if motif_type == "douleur":
                for loc in PAIN_LOCATIONS:
                    if loc in message_lower:
                        result["detail"] = loc
                        result["full"] = f"douleur {loc}"
                        break
                
                if "detail" not in result:
                    result["full"] = "douleur"
            else:
                result["full"] = motif_type
            
            break
    
    return result


def _normalize_fr_text(text: str) -> str:
    """Minuscules sans accents pour matching robuste."""
    lowered = (text or "").lower().strip()
    return "".join(
        c for c in unicodedata.normalize("NFD", lowered)
        if unicodedata.category(c) != "Mn"
    )


def _infer_year(day: int, month: int, ref: date) -> int:
    """Si la date est déjà passée cette année, prendre l'année suivante."""
    try:
        candidate = date(ref.year, month, day)
    except ValueError:
        return ref.year
    if candidate < ref:
        return ref.year + 1
    return ref.year


def extract_target_date(message: str, ref: Optional[date] = None) -> Optional[date]:
    """
    Extrait une date civile depuis le langage naturel français.

    Exemples : « le 18 juin », « pour le 18/06 », « demain », « après-demain ».
    """
    if not (message or "").strip():
        return None
    ref = ref or datetime.now(ZoneInfo("Europe/Paris")).date()
    raw = (message or "").strip().lower()
    norm = _normalize_fr_text(raw)

    if re.search(r"\bapres[- ]?demain\b", norm):
        return ref + timedelta(days=2)
    if re.search(r"\bdemain\b", norm):
        return ref + timedelta(days=1)
    if "aujourd" in norm:
        return ref

    iso_match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", raw)
    if iso_match:
        try:
            return date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
        except ValueError:
            pass

    slash_match = re.search(r"\b(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?\b", raw)
    if slash_match:
        day = int(slash_match.group(1))
        month = int(slash_match.group(2))
        year_raw = slash_match.group(3)
        if year_raw:
            year = int(year_raw)
            if year < 100:
                year += 2000
        else:
            year = _infer_year(day, month, ref)
        try:
            return date(year, month, day)
        except ValueError:
            pass

    month_match = re.search(
        r"(?:le\s+)?(\d{1,2})\s+"
        r"(janvier|fevrier|f[eé]vrier|mars|avril|mai|juin|juillet|ao[uû]t|"
        r"septembre|octobre|novembre|decembre|d[eé]cembre)",
        norm,
    )
    if month_match:
        day = int(month_match.group(1))
        month_key = (
            month_match.group(2)
            .replace("février", "fevrier")
            .replace("août", "aout")
            .replace("décembre", "decembre")
        )
        month = _FRENCH_MONTHS.get(month_key)
        if month:
            year = _infer_year(day, month, ref)
            try:
                return date(year, month, day)
            except ValueError:
                return None

    return None


def format_date_fr(value: date | str) -> str:
    """Affiche une date en français (ex. « jeudi 18 juin »)."""
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value[:10])
        except ValueError:
            return value
    weekday = _FR_WEEKDAY_NAMES[value.weekday()]
    month_names = ["janvier", "février", "mars", "avril", "mai", "juin",
                   "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    return f"{weekday} {value.day} {month_names[value.month - 1]}"


def time_pref_from_pref(pref: Optional[str]) -> Optional[str]:
    """Extrait matin / après-midi / soir d'une préférence combinée (« jeudi matin »)."""
    if not pref:
        return None
    p = _normalize_fr_text(pref)
    if "apres-midi" in p or "apres midi" in p or "aprem" in p:
        return "après-midi"
    if "matin" in p or "matinee" in p:
        return "matin"
    if "soir" in p or "soiree" in p:
        return "soir"
    return None


def weekday_from_pref(pref: Optional[str]) -> Optional[int]:
    """Retourne 0=lundi … 6=dimanche si un jour de semaine est dans pref."""
    if not pref:
        return None
    p = _normalize_fr_text(pref)
    for i, day in enumerate(_FR_WEEKDAY_NAMES):
        if day in p:
            return i
    return None


def extract_pref(message: str) -> Optional[str]:
    """
    Extrait la préférence horaire.
    
    Returns:
        "lundi matin", "mardi après-midi", "matin", etc.
        ou None si rien trouvé
    """
    message_lower = message.lower().strip()
    
    day_found: Optional[str] = None
    time_found: Optional[str] = None
    
    # Chercher le jour
    for day, patterns in DAYS_PATTERNS.items():
        if any(p in message_lower for p in patterns):
            day_found = day
            break
    
    # Reformulations (« plutôt en fin d'après-midi »)
    norm = _normalize_fr_text(message_lower)
    if any(p in norm for p in ("fin d apres-midi", "fin d apres midi", "fin apres-midi")):
        time_found = "soir"
    elif "plutot" in norm or "plutôt" in message_lower:
        for time_slot, patterns in PREF_PATTERNS.items():
            if any(_normalize_fr_text(p) in norm for p in patterns):
                time_found = time_slot
                break

    # Chercher le moment de la journée
    if not time_found:
        for time_slot, patterns in PREF_PATTERNS.items():
            if any(p in message_lower for p in patterns):
                time_found = time_slot
                break
    
    # Combiner
    if day_found and time_found:
        return f"{day_found} {time_found}"
    elif day_found:
        return day_found
    elif time_found:
        return time_found
    
    return None


def infer_preference_from_context(message: str) -> Optional[str]:
    """
    Infère la préférence temporelle depuis une phrase contextuelle (spec V3).
    
    Exemples :
    - "je travaille jusqu'à 16h" → "après-midi"
    - "je finis à 18h" → "fin d'après-midi"
    - "le matin je suis occupé" → "après-midi"
    - "après 17h" → "soir"
    - "en fin de matinée" → "matin"
    
    Returns:
        Préférence inférée ("matin", "après-midi", "soir") ou None
    """
    msg_lower = message.lower().strip()
    if not msg_lower:
        return None

    # Contraintes temporelles explicites → après le travail
    if any(p in msg_lower for p in ["jusqu'à 16h", "jusqu'à 17h", "finis à", "travaille jusqu'à", "travail jusqu'à"]):
        return "après-midi"
    if any(p in msg_lower for p in ["je travaille jusqu'à", "je finis à", "finir à"]):
        return "après-midi"

    # Soir / fin de journée / fin d'après-midi
    norm = _normalize_fr_text(msg_lower)
    if any(
        p in norm
        for p in (
            "apres 17h", "apres 18h", "en soiree", "apres le travail", "apres le boulot",
            "fin d apres-midi", "fin d apres midi", "fin apres-midi", "fin de journee",
            "fin de journee", "en fin de journee",
        )
    ):
        return "soir"
    if any(p in msg_lower for p in ["après 17h", "après 18h", "en soirée", "après le travail", "après le boulot"]):
        return "soir"

    # Matin explicite
    if any(p in msg_lower for p in ["avant midi", "en matinée", "tôt le matin", "début de matinée"]):
        return "matin"

    # Exclusions (négatif) : "matin occupé" → après-midi
    if "matin" in msg_lower and any(p in msg_lower for p in ["pas le", "jamais le", "occupé le", "occupée le"]):
        return "après-midi"
    if "après-midi" in msg_lower and any(p in msg_lower for p in ["pas l'", "jamais l'", "occupé l'", "occupée l'"]):
        return "matin"

    return None


def extract_entities(message: str) -> ExtractedEntities:
    """
    Extraction principale - conservatrice.
    
    Extrait nom, motif et préférence du message.
    En cas de doute, les champs restent None.
    
    Args:
        message: Le message de l'utilisateur (transcription vocale)
    
    Returns:
        ExtractedEntities avec les champs remplis si trouvés
    """
    entities = ExtractedEntities()
    confidence_points = 0
    
    # Extraction du nom
    name = extract_name(message)
    if name:
        entities.name = name
        confidence_points += 1
    
    # Extraction du motif
    motif_info = extract_motif(message)
    if motif_info:
        entities.motif = motif_info.get("full") or motif_info.get("type")
        entities.motif_detail = motif_info.get("detail")
        confidence_points += 1
    
    # Extraction de la préférence
    pref = extract_pref(message)
    if pref:
        entities.pref = pref
        confidence_points += 1

    target = extract_target_date(message)
    if target:
        entities.target_date = target
        confidence_points += 1
    
    # Calcul de la confiance (simple)
    if confidence_points > 0:
        entities.confidence = min(confidence_points / 4, 1.0)
    
    return entities


def merge_entities(
    existing: Dict[str, Any],
    extracted: ExtractedEntities
) -> Dict[str, Any]:
    """
    Fusionne les entités extraites avec le contexte existant.
    Les valeurs existantes ont priorité (déjà confirmées par l'utilisateur).
    
    Args:
        existing: Contexte existant (session)
        extracted: Nouvelles entités extraites
    
    Returns:
        Contexte mis à jour
    """
    result = existing.copy()
    
    # Ne remplacer que les valeurs manquantes
    if not result.get("name") and extracted.name:
        result["name"] = extracted.name
        result["name_extracted"] = True  # Flag pour confirmation implicite
    
    if not result.get("motif") and extracted.motif:
        result["motif"] = extracted.motif
        result["motif_extracted"] = True
    
    if not result.get("pref") and extracted.pref:
        result["pref"] = extracted.pref
        result["pref_extracted"] = True

    if not result.get("target_date") and extracted.target_date:
        result["target_date"] = extracted.target_date.isoformat()
        result["target_date_extracted"] = True
    
    return result


def get_missing_fields(context: Dict[str, Any], skip_motif: bool = True, skip_contact: bool = False) -> List[str]:
    """
    Retourne la liste des champs manquants pour la qualification.
    
    Args:
        context: Contexte de la session
        skip_motif: Si True, ne demande pas le motif (défaut pour médecin)
        skip_contact: Si True, ne demande pas le contact (sera demandé après le choix de créneau)
    
    Returns:
        Liste des champs manquants dans l'ordre
    """
    # NOUVEAU FLOW : name → pref → [choix créneau] → contact
    # Le contact est demandé APRÈS que le client ait choisi son créneau
    if skip_motif:
        required_fields = ["name", "pref"]
        if not skip_contact:
            required_fields.append("contact")
    else:
        required_fields = ["name", "motif", "pref"]
        if not skip_contact:
            required_fields.append("contact")
    
    missing = []
    
    for field in required_fields:
        if not context.get(field):
            missing.append(field)
    
    return missing


def get_next_missing_field(context: Dict[str, Any], skip_contact: bool = False) -> Optional[str]:
    """
    Retourne le prochain champ manquant pour la qualification.
    
    Args:
        context: Contexte de la session
        skip_contact: Si True, ne demande pas le contact (sera demandé après le choix de créneau)
    
    Returns:
        Le prochain champ à demander, ou None si tout est rempli
    """
    missing = get_missing_fields(context, skip_contact=skip_contact)
    return missing[0] if missing else None
