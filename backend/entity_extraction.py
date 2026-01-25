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
from typing import Dict, Optional, List, Any
from dataclasses import dataclass


@dataclass
class ExtractedEntities:
    """Entités extraites d'un message."""
    name: Optional[str] = None
    motif: Optional[str] = None
    motif_detail: Optional[str] = None  # ex: "dos" pour "douleur dos"
    pref: Optional[str] = None
    confidence: float = 0.0  # 0.0 à 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "motif": self.motif,
            "motif_detail": self.motif_detail,
            "pref": self.pref,
            "confidence": self.confidence,
        }
    
    def has_any(self) -> bool:
        """Retourne True si au moins une entité a été extraite."""
        return any([self.name, self.motif, self.pref])


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
        "soir", "soirée", "fin de journée", "18h", "19h",
    ],
}

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
    
    # Chercher le moment de la journée
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
    
    # Calcul de la confiance (simple)
    if confidence_points > 0:
        entities.confidence = min(confidence_points / 3, 1.0)
    
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
    
    return result


def get_missing_fields(context: Dict[str, Any]) -> List[str]:
    """
    Retourne la liste des champs manquants pour la qualification.
    
    Args:
        context: Contexte de la session
    
    Returns:
        Liste des champs manquants dans l'ordre: ["name", "motif", "pref", "contact"]
    """
    required_fields = ["name", "motif", "pref", "contact"]
    missing = []
    
    for field in required_fields:
        if not context.get(field):
            missing.append(field)
    
    return missing


def get_next_missing_field(context: Dict[str, Any]) -> Optional[str]:
    """
    Retourne le prochain champ manquant pour la qualification.
    
    Returns:
        Le prochain champ à demander, ou None si tout est rempli
    """
    missing = get_missing_fields(context)
    return missing[0] if missing else None
