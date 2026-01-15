# backend/guards.py
"""
Validations strictes pour edge cases.
Toute modification doit être accompagnée de tests.
"""

from __future__ import annotations
import re
from typing import Optional

from backend import config, prompts


# ----------------------------
# Détection langue
# ----------------------------

_ENGLISH_WORDS = {
    "hello", "hi", "hey", "what", "where", "when", "how", "who",
    "the", "is", "are", "can", "you", "your", "appointment", "book",
    "schedule", "time", "opening", "hours", "available", "contact",
    "phone", "email", "address", "yes", "no", "please", "thank"
}

def detect_language_fr(text: str) -> bool:
    """
    Détecte si le message est probablement en français.
    
    Returns:
        True si français détecté, False sinon
    """
    words = text.lower().split()
    english_count = sum(1 for w in words if w in _ENGLISH_WORDS)
    
    if len(words) > 0 and english_count / len(words) > 0.3:
        return False
    
    return True


# ----------------------------
# Détection spam / abus
# ----------------------------

_SPAM_PATTERNS = [
    r"fuck",
    r"shit",
    r"connard",
    r"enculé",
    r"salope",
]

_SPAM_REGEX = re.compile("|".join(_SPAM_PATTERNS), re.IGNORECASE)

def is_spam_or_abuse(text: str) -> bool:
    """
    Détecte spam ou contenu abusif.
    
    Returns:
        True si spam/abus détecté
    """
    return bool(_SPAM_REGEX.search(text))


# ----------------------------
# Validation longueur
# ----------------------------

def validate_length(text: str, max_length: Optional[int] = None) -> tuple[bool, Optional[str]]:
    """
    Valide la longueur du message.
    
    Returns:
        (is_valid, error_message)
    """
    if max_length is None:
        max_length = config.MAX_MESSAGE_LENGTH
    
    if not text or not text.strip():
        return False, prompts.MSG_EMPTY_MESSAGE
    
    if len(text) > max_length:
        return False, prompts.MSG_TOO_LONG
    
    return True, None


# ----------------------------
# Validation confirmation RDV
# ----------------------------

# ============================================
# CONFIRMATION VOCALE (un/deux/trois)
# ============================================

# Mapping mots → chiffre (FR)
_VOCAL_NUM_MAP = {
    "1": 1,
    "un": 1,
    "une": 1,
    "premier": 1,
    "premiere": 1,
    "première": 1,
    
    "2": 2,
    "deux": 2,
    "second": 2,
    "seconde": 2,
    "deuxieme": 2,
    "deuxième": 2,
    
    "3": 3,
    "trois": 3,
    "troisieme": 3,
    "troisième": 3,
}

# Patterns vocaux courants
_VOCAL_CONFIRM_PATTERNS = [
    re.compile(r"^\s*oui\s+(.+?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:numero|numéro)\s+(.+?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:le|la)?\s*(.+?)\s*$", re.IGNORECASE),
]


def parse_vocal_choice_1_3(text: str) -> Optional[int]:
    """
    Parse un choix vocal vers 1/2/3.
    
    Accepte:
      - "un", "deux", "trois"
      - "oui un", "oui deux", "oui trois"
      - "1", "2", "3"
      - "numéro deux", "le deuxième", "second", etc.
    
    Refuse tout le reste.
    """
    if not text or not text.strip():
        return None

    raw = text.strip().lower()

    # Normalisation accents fréquents
    raw = (raw
        .replace("é", "e").replace("è", "e").replace("ê", "e")
        .replace("à", "a").replace("ù", "u")
        .replace("î", "i").replace("ï", "i")
        .replace("ô", "o")
    )

    # 1) Token exact connu ?
    if raw in _VOCAL_NUM_MAP:
        return _VOCAL_NUM_MAP[raw]

    # 2) Patterns avec extraction
    for pat in _VOCAL_CONFIRM_PATTERNS:
        m = pat.match(raw)
        if not m:
            continue
        
        core = m.group(1).strip()
        
        # Tokenize
        tokens = [t for t in re.split(r"[\s\-]+", core) if t]
        if not tokens:
            continue

        # Essaye chaque token
        for tok in tokens:
            if tok in _VOCAL_NUM_MAP:
                return _VOCAL_NUM_MAP[tok]

        # Dernier token
        last = tokens[-1]
        if last in _VOCAL_NUM_MAP:
            return _VOCAL_NUM_MAP[last]

    return None


def validate_booking_confirm(text: str, channel: str = "web") -> tuple[bool, Optional[int]]:
    """
    Validation confirmation RDV (web strict / vocal élargi).
    
    Web (strict):
      - "oui 1/2/3" ou "1/2/3"
    
    Vocal (élargi):
      - "un/deux/trois", "oui deux", "le deuxième", "numéro 2", etc.
    
    Returns:
        (is_valid, slot_index)
    """
    if not text or not text.strip():
        return False, None

    t = text.strip().lower()

    # Web strict (rétrocompatibilité)
    m = re.match(r"^oui\s*([123])$", t)
    if m:
        return True, int(m.group(1))
    
    if t in {"1", "2", "3"}:
        return True, int(t)

    # Vocal élargi
    if channel == "vocal":
        choice = parse_vocal_choice_1_3(text)
        if choice in (1, 2, 3):
            return True, choice

    return False, None


# ============================================
# CONTACT VOCAL (email dicté)
# ============================================

def parse_vocal_email_min(text: str) -> str:
    """
    Parse minimal d'un email dicté en FR.
    
    Ex: "jean point dupont arobase gmail point com" 
        → "jean.dupont@gmail.com"
    """
    if not text:
        return ""

    t = text.strip().lower()

    # Remplacements simples (espaces obligatoires)
    t = t.replace(" arobase ", "@")
    t = t.replace(" at ", "@")
    t = t.replace(" point ", ".")
    t = t.replace(" dot ", ".")
    
    # Enlever espaces restants
    t = t.replace(" ", "")

    return t


def looks_like_dictated_email(text: str) -> bool:
    """Détecte si le texte ressemble à un email dicté."""
    if not text:
        return False
    
    t = text.lower()
    return ("arobase" in t) or (" at " in t) or (" point " in t) or (" dot " in t)


# ----------------------------
# Validation formats qualification
# ----------------------------

def validate_email(email: str) -> bool:
    """Valide basiquement un email"""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email.strip()))


def validate_phone(phone: str) -> bool:
    """
    Valide basiquement un numéro français.
    """
    cleaned = re.sub(r"[\s\-\.]", "", phone)
    
    patterns = [
        r"^0[67]\d{8}$",
        r"^\+33[67]\d{8}$",
    ]
    
    return any(re.match(p, cleaned) for p in patterns)


def validate_qualif_contact(contact: str) -> tuple[bool, str]:
    """
    Valide le contact (email OU téléphone).
    
    Returns:
        (is_valid, contact_type) où contact_type = "email" | "phone" | "invalid"
    """
    contact = contact.strip()
    
    if validate_email(contact):
        return True, "email"
    
    if validate_phone(contact):
        return True, "phone"
    
    return False, "invalid"


def validate_qualif_motif(motif: str) -> bool:
    """
    Valide le motif : doit être 1 phrase courte.
    """
    motif = motif.strip()
    
    if not motif or len(motif) > 100:
        return False
    
    if motif.count(".") > 1 or motif.count("?") > 1:
        return False
    
    return True


def is_generic_motif(text: str) -> bool:
    """
    Détecte si le motif est trop générique (pas d'info utile).
    """
    from backend import prompts
    
    t = (text or "").strip().lower()
    
    # Normaliser ponctuation
    t = t.replace("-", " ").replace("'", " ")
    
    return t in prompts.GENERIC_MOTIFS


def is_contact_selector_word(text: str) -> bool:
    """
    Détecte si l'utilisateur donne le TYPE de contact au lieu de la donnée.
    """
    t = (text or "").strip().lower()
    return t in {
        "mail", "email", "e-mail", "e mail",
        "téléphone", "telephone", "tel", "phone",
        "portable", "mobile", "fixe"
    }
