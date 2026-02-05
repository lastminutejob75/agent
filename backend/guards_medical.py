"""
Détection urgence médicale — simple, déterministe, sans LLM.
Priorité absolue dans le pipeline (avant intent, booking, FAQ, etc.).
"""

MEDICAL_EMERGENCY_KEYWORDS = [
    # Cœur / poitrine
    "mal au cœur",
    "mal au coeur",
    "douleur thoracique",
    "douleur à la poitrine",
    "douleur poitrine",
    "poitrine",
    "serrement poitrine",

    # Respiration
    "mal à respirer",
    "difficulté à respirer",
    "je ne respire pas",
    "essoufflé",
    "essoufflement",

    # Malaise
    "malaise",
    "évanoui",
    "évanouissement",
    "perte de connaissance",
    "je me suis évanoui",

    # Neurologique
    "paralysé",
    "paralysie",
    "je ne sens plus",
    "trouble de la parole",
    "confusion soudaine",

    # Douleurs irradiantes
    "douleur bras gauche",
    "douleur mâchoire",
]


def is_medical_emergency(text: str) -> bool:
    """Détecte si le message évoque une urgence médicale (triage sans LLM)."""
    if not text:
        return False

    t = text.lower().strip()

    for kw in MEDICAL_EMERGENCY_KEYWORDS:
        if kw in t:
            return True

    return False
