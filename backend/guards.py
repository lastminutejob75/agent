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
    # Anglais
    r"fuck",
    r"shit",
    r"asshole",
    r"bitch",
    # Français - insultes
    r"connard",
    r"connasse",
    r"enculé",
    r"salope",
    r"pute",
    r"putain",
    r"niquer",
    r"nique",
    r"ta mère",
    r"ta gueule",
    r"fdp",
    r"ntm",
    r"fils de pute",
    r"va te faire",
    r"casse.?toi",
    r"dégage",
    r"batard",
    r"bâtard",
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


# Mapping des mots vers chiffres pour transcription vocale
_WORD_TO_DIGIT = {
    # Chiffres simples
    "zéro": "0", "zero": "0", "0": "0",
    "un": "1", "une": "1", "1": "1",
    "deux": "2", "2": "2",
    "trois": "3", "3": "3",
    "quatre": "4", "4": "4",
    "cinq": "5", "5": "5",
    "six": "6", "6": "6",
    "sept": "7", "7": "7",
    "huit": "8", "8": "8",
    "neuf": "9", "9": "9",
    # Dizaines
    "dix": "10", "10": "10",
    "onze": "11", "11": "11",
    "douze": "12", "12": "12",
    "treize": "13", "13": "13",
    "quatorze": "14", "14": "14",
    "quinze": "15", "15": "15",
    "seize": "16", "16": "16",
    "dix-sept": "17", "dix sept": "17", "17": "17",
    "dix-huit": "18", "dix huit": "18", "18": "18",
    "dix-neuf": "19", "dix neuf": "19", "19": "19",
    "vingt": "20", "20": "20",
    "vingt-et-un": "21", "vingt et un": "21", "21": "21",
    "vingt-deux": "22", "vingt deux": "22", "22": "22",
    "vingt-trois": "23", "vingt trois": "23", "23": "23",
    "vingt-quatre": "24", "vingt quatre": "24", "24": "24",
    "vingt-cinq": "25", "vingt cinq": "25", "25": "25",
    "vingt-six": "26", "vingt six": "26", "26": "26",
    "vingt-sept": "27", "vingt sept": "27", "27": "27",
    "vingt-huit": "28", "vingt huit": "28", "28": "28",
    "vingt-neuf": "29", "vingt neuf": "29", "29": "29",
    "trente": "30", "30": "30",
    "trente-et-un": "31", "trente et un": "31", "31": "31",
    "trente-deux": "32", "trente deux": "32", "32": "32",
    "trente-trois": "33", "trente trois": "33", "33": "33",
    "trente-quatre": "34", "trente quatre": "34", "34": "34",
    "trente-cinq": "35", "trente cinq": "35", "35": "35",
    "trente-six": "36", "trente six": "36", "36": "36",
    "trente-sept": "37", "trente sept": "37", "37": "37",
    "trente-huit": "38", "trente huit": "38", "38": "38",
    "trente-neuf": "39", "trente neuf": "39", "39": "39",
    "quarante": "40", "40": "40",
    "quarante-et-un": "41", "quarante et un": "41", "41": "41",
    "quarante-deux": "42", "quarante deux": "42", "42": "42",
    "quarante-trois": "43", "quarante trois": "43", "43": "43",
    "quarante-quatre": "44", "quarante quatre": "44", "44": "44",
    "quarante-cinq": "45", "quarante cinq": "45", "45": "45",
    "quarante-six": "46", "quarante six": "46", "46": "46",
    "quarante-sept": "47", "quarante sept": "47", "47": "47",
    "quarante-huit": "48", "quarante huit": "48", "48": "48",
    "quarante-neuf": "49", "quarante neuf": "49", "49": "49",
    "cinquante": "50", "50": "50",
    "cinquante-et-un": "51", "cinquante et un": "51", "51": "51",
    "cinquante-deux": "52", "cinquante deux": "52", "52": "52",
    "cinquante-trois": "53", "cinquante trois": "53", "53": "53",
    "cinquante-quatre": "54", "cinquante quatre": "54", "54": "54",
    "cinquante-cinq": "55", "cinquante cinq": "55", "55": "55",
    "cinquante-six": "56", "cinquante six": "56", "56": "56",
    "cinquante-sept": "57", "cinquante sept": "57", "57": "57",
    "cinquante-huit": "58", "cinquante huit": "58", "58": "58",
    "cinquante-neuf": "59", "cinquante neuf": "59", "59": "59",
    "soixante": "60", "60": "60",
    "soixante-et-un": "61", "soixante et un": "61", "61": "61",
    "soixante-deux": "62", "soixante deux": "62", "62": "62",
    "soixante-trois": "63", "soixante trois": "63", "63": "63",
    "soixante-quatre": "64", "soixante quatre": "64", "64": "64",
    "soixante-cinq": "65", "soixante cinq": "65", "65": "65",
    "soixante-six": "66", "soixante six": "66", "66": "66",
    "soixante-sept": "67", "soixante sept": "67", "67": "67",
    "soixante-huit": "68", "soixante huit": "68", "68": "68",
    "soixante-neuf": "69", "soixante neuf": "69", "69": "69",
    "soixante-dix": "70", "soixante dix": "70", "70": "70",
    "soixante-et-onze": "71", "soixante et onze": "71", "soixante onze": "71", "71": "71",
    "soixante-douze": "72", "soixante douze": "72", "72": "72",
    "soixante-treize": "73", "soixante treize": "73", "73": "73",
    "soixante-quatorze": "74", "soixante quatorze": "74", "74": "74",
    "soixante-quinze": "75", "soixante quinze": "75", "75": "75",
    "soixante-seize": "76", "soixante seize": "76", "76": "76",
    "soixante-dix-sept": "77", "soixante dix sept": "77", "77": "77",
    "soixante-dix-huit": "78", "soixante dix huit": "78", "78": "78",
    "soixante-dix-neuf": "79", "soixante dix neuf": "79", "79": "79",
    "quatre-vingt": "80", "quatre vingt": "80", "80": "80",
    "quatre-vingt-un": "81", "quatre vingt un": "81", "81": "81",
    "quatre-vingt-deux": "82", "quatre vingt deux": "82", "82": "82",
    "quatre-vingt-trois": "83", "quatre vingt trois": "83", "83": "83",
    "quatre-vingt-quatre": "84", "quatre vingt quatre": "84", "84": "84",
    "quatre-vingt-cinq": "85", "quatre vingt cinq": "85", "85": "85",
    "quatre-vingt-six": "86", "quatre vingt six": "86", "86": "86",
    "quatre-vingt-sept": "87", "quatre vingt sept": "87", "87": "87",
    "quatre-vingt-huit": "88", "quatre vingt huit": "88", "88": "88",
    "quatre-vingt-neuf": "89", "quatre vingt neuf": "89", "89": "89",
    "quatre-vingt-dix": "90", "quatre vingt dix": "90", "90": "90",
    "quatre-vingt-onze": "91", "quatre vingt onze": "91", "91": "91",
    "quatre-vingt-douze": "92", "quatre vingt douze": "92", "92": "92",
    "quatre-vingt-treize": "93", "quatre vingt treize": "93", "93": "93",
    "quatre-vingt-quatorze": "94", "quatre vingt quatorze": "94", "94": "94",
    "quatre-vingt-quinze": "95", "quatre vingt quinze": "95", "95": "95",
    "quatre-vingt-seize": "96", "quatre vingt seize": "96", "96": "96",
    "quatre-vingt-dix-sept": "97", "quatre vingt dix sept": "97", "97": "97",
    "quatre-vingt-dix-huit": "98", "quatre vingt dix huit": "98", "98": "98",
    "quatre-vingt-dix-neuf": "99", "quatre vingt dix neuf": "99", "99": "99",
}


def parse_vocal_phone(text: str) -> str:
    """
    Parse un numéro de téléphone dicté vocalement.
    
    Exemples:
        "zéro six douze trente quatre" → "0612304"
        "06 12 34 56 78" → "0612345678"
        "zero six un deux trois quatre cinq six sept huit" → "0612345678"
    """
    text = text.lower().strip()
    
    # Retirer les mots parasites
    for word in ["c'est le", "c'est", "le", "mon numéro", "numéro", "téléphone", "portable"]:
        text = text.replace(word, " ")
    
    # Nettoyer espaces multiples
    text = " ".join(text.split())
    
    # Essayer d'abord de trouver des patterns de 2 chiffres (ex: "douze", "trente-quatre")
    result = ""
    
    # Remplacer les patterns composés d'abord (ordre décroissant de longueur)
    sorted_patterns = sorted(_WORD_TO_DIGIT.keys(), key=len, reverse=True)
    
    remaining = text
    while remaining:
        remaining = remaining.strip()
        if not remaining:
            break
            
        found = False
        for pattern in sorted_patterns:
            if remaining.startswith(pattern):
                result += _WORD_TO_DIGIT[pattern]
                remaining = remaining[len(pattern):]
                found = True
                break
        
        if not found:
            # Passer au caractère suivant
            if remaining[0].isdigit():
                result += remaining[0]
            remaining = remaining[1:]
    
    # Nettoyer le résultat - garder seulement les chiffres
    digits = ''.join(c for c in result if c.isdigit())
    
    return digits


def validate_phone(phone: str) -> bool:
    """
    Valide basiquement un numéro français.
    Accepte les formats:
    - 0612345678 (10 chiffres commençant par 06 ou 07)
    - +33612345678
    """
    # D'abord essayer de parser si c'est du texte vocal
    if any(c.isalpha() for c in phone):
        phone = parse_vocal_phone(phone)
    
    cleaned = re.sub(r"[\s\-\.\(\)]", "", phone)
    
    # Accepter aussi +33 au début
    if cleaned.startswith("+33"):
        cleaned = "0" + cleaned[3:]
    elif cleaned.startswith("33"):
        cleaned = "0" + cleaned[2:]
    
    patterns = [
        r"^0[1-9]\d{8}$",  # Tous les numéros français (01-09)
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
    
    # Essayer de parser comme numéro vocal
    parsed_phone = parse_vocal_phone(contact) if any(c.isalpha() for c in contact) else contact
    cleaned_phone = re.sub(r"[\s\-\.\(\)]", "", parsed_phone)
    
    # Normaliser +33
    if cleaned_phone.startswith("+33"):
        cleaned_phone = "0" + cleaned_phone[3:]
    elif cleaned_phone.startswith("33"):
        cleaned_phone = "0" + cleaned_phone[2:]
    
    if validate_phone(cleaned_phone):
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
