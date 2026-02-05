# backend/guards_medical_triage.py
"""
Triage médical P1 : red flags vitaux (hard stop) + symptômes non vitaux + escalade douce.
Déterministe, sans LLM, TTS-friendly.
"""
import re
from typing import Optional

# =========================
# RED FLAGS MÉDICAUX — URGENCES
# =========================
# ⚠️ Règle : un seul match = urgence immédiate. Pas de diagnostic. Orientation uniquement.
# Volontairement large et prudent (HAS-compatible dans l'esprit).
# RED_FLAG_CATEGORIES : source de vérité pour détection + catégorie (audit, pas de symptôme stocké).

RED_FLAG_CATEGORIES = {
    "cardio_respiratoire": [
        r"douleur.*(poitrine|thorax)",
        r"mal.*(poitrine|thorax|cœur|coeur)",
        r"oppression.*(poitrine|thorax)",
        r"gêne respiratoire",
        r"difficulté.*respirer",
        r"j'?ai du mal à respirer",
        r"essouffl",
        r"respiration sifflante",
        r"lèvres.*bleu",
        r"cyanose",
    ],
    "neurologique": [
        r"perte de connaissance",
        r"évanoui",
        r"syncope",
        r"convulsion",
        r"crise.*(épilep|convulsion)",
        r"paralys",
        r"faiblesse.*(bras|jambe|côté)",
        r"difficulté.*parler",
        r"trouble.*(parole|vision)",
        r"visage.*(figé|paralys)",
        r"avc",
        r"mal de tête.*brutal",
        r"céphalée.*violente",
        r"\bmalaise\b",
    ],
    "hemorragie_trauma": [
        r"saignement.*abondant",
        r"hémorrag",
        r"vomir.*sang",
        r"sang.*(selles|urines)",
        r"traumatisme.*crâne",
        r"chute.*violente",
        r"accident",
    ],
    "infectieux_grave": [
        r"fièvre.*(très élevée|40)",
        r"raideur.*nuque",
        r"confusion",
        r"état.*confus",
        r"somnolence.*inhabituelle",
    ],
    "pediatrie": [
        r"(bébé|nourrisson|enfant).*(ne respire pas)",
        r"(bébé|nourrisson|enfant).*(très mou|inerte)",
        r"(bébé|nourrisson|enfant).*(convulsion)",
        r"(bébé|nourrisson|enfant).*(fièvre).*moins de 3 mois",
    ],
    "psychiatrique": [
        r"envie de mourir",
        r"me suicider",
        r"me faire du mal",
    ],
}

# Liste plate conservée pour usage externe (ex. tests) si besoin
RED_FLAGS = [
    p for patterns in RED_FLAG_CATEGORIES.values() for p in patterns
]

# Symptômes non vitaux fréquents
NON_URGENT_KEYWORDS = [
    "fièvre", "fievre", "douleur", "mal au", "mal de",
    "toux", "rhume", "gorge", "migraine",
    "nausée", "vomissement", "diarrhée",
    "fatigue", "vertige", "maux",
]

# Signaux d'inquiétude / escalade douce
CAUTION_KEYWORDS = [
    "je suis inquiet", "je suis inquiète",
    "j'ai peur", "ça m'inquiète",
    "ça empire", "ça s'aggrave",
    "c'est grave", "je ne sais pas",
]


def detect_medical_red_flag(text: str) -> Optional[str]:
    """
    Retourne la catégorie du premier red flag matché, ou None.
    Utilisé pour décision urgence + log d'audit (catégorie uniquement, pas de symptôme stocké).
    """
    if not text:
        return None
    normalized = text.lower()
    for category, patterns in RED_FLAG_CATEGORIES.items():
        for pattern in patterns:
            if re.search(pattern, normalized):
                return category
    return None


def detect_medical_red_flags(text: str) -> bool:
    """Détecte une urgence vitale (hard stop). Compatibilité avec code existant."""
    return detect_medical_red_flag(text) is not None


def classify_medical_symptoms(text: str) -> Optional[str]:
    """
    Retourne:
      - "CAUTION" si inquiétude
      - "NON_URGENT" si symptômes non vitaux
      - None sinon
    """
    if not text:
        return None
    t = text.lower()
    if any(k in t for k in CAUTION_KEYWORDS):
        return "CAUTION"
    if any(k in t for k in NON_URGENT_KEYWORDS):
        return "NON_URGENT"
    return None


def extract_symptom_motif_short(text: str, max_words: int = 8) -> str:
    """Motif court, sans diagnostic."""
    if not text:
        return ""
    words = re.findall(r"\w+", text.lower())
    return " ".join(words[:max_words])
