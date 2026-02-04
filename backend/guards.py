# backend/guards.py
"""
Validations strictes pour edge cases.
Toute modification doit être accompagnée de tests.
"""

from __future__ import annotations
import re
from typing import Optional, Tuple

from backend import config, prompts


# ----------------------------
# Nettoyage des noms (vocal)
# ----------------------------

_NAME_FILLER_PATTERNS = [
    r"^c'est\s+",
    r"^c\s+est\s+",  # "c est" sans apostrophe
    r"^je\s+m'appelle\s+",
    r"^je\s+m\s+appelle\s+",  # "je m appelle" sans apostrophe
    r"^je\s+suis\s+",
    r"^mon\s+nom\s+c'est\s+",
    r"^mon\s+nom\s+c\s+est\s+",  # sans apostrophe
    r"^mon\s+nom\s+est\s+",
    r"^moi\s+c'est\s+",
    r"^moi\s+c\s+est\s+",  # sans apostrophe
    r"^euh\s+",
    r"^ben\s+",
    r"^alors\s+",
    r"^donc\s+",
    r"^oui,?\s*c'est\s+",
    r"^oui,?\s*c\s+est\s+",  # sans apostrophe
    r"^oui\s+",
    r"^bonjour\s+",
    r"^bonjour,?\s*",
    r"\s*s'il\s+vous\s+pla[iî]t\s*$",
    r"\s*s\s+il\s+vous\s+pla[iî]t\s*$",  # sans apostrophe
    r"\s*voilà\s*$",
]

def clean_name_from_vocal(raw_name: str) -> str:
    """
    Nettoie un nom de tous les mots parasites courants en vocal.
    
    Exemples:
        "c'est Heni" → "Heni"
        "je m'appelle Jean Dupont" → "Jean Dupont"
        "euh ben c'est Marie" → "Marie"
        "oui c'est Pierre" → "Pierre"
    """
    cleaned = raw_name.strip()
    
    # Appliquer tous les patterns de nettoyage
    for pattern in _NAME_FILLER_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    
    # Nettoyer les espaces multiples
    cleaned = " ".join(cleaned.split())
    
    # Capitaliser chaque mot (pour "heni" → "Heni")
    if cleaned:
        cleaned = cleaned.title()
    
    return cleaned


# ----------------------------
# Extraction du nom (QUALIF_NAME — IVR pro : on valide l’info extraite, pas le message)
# ----------------------------

NAME_PREFIXES_FR = [
    "mon nom est",
    "je m'appelle",
    "je m appelle",
    "c'est",
    "c est",
    "moi c'est",
    "moi c est",
    "il s'appelle",
    "elle s'appelle",
    "nom",
]
# Ordre par longueur décroissante pour retirer le préfixe le plus long en premier
NAME_PREFIXES_FR_SORTED = sorted(
    (p.strip().lower() for p in NAME_PREFIXES_FR if p.strip()),
    key=len,
    reverse=True,
)

# Fillers à rejeter comme nom (contexte QUALIF_NAME)
FILLERS_FR_NAME = frozenset({
    "euh", "heu", "hum", "hmm", "mmh",
    "bah", "ben", "bah euh", "euh bah",
    "bof", "mouais",
    "voilà", "voila",
    "alors",
    "attends", "attendez",
    "oui", "non",
    "hein",
})


def extract_name_from_speech(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extrait un nom depuis la parole (QUALIF_NAME).
    Retourne (name, None) si OK, (None, reason) si rejet.
    reason = "filler_detected" | "not_plausible_name"
    """
    if not text or not text.strip():
        return None, "filler_detected"
    t = text.strip().lower()
    # 1. Retirer les préfixes (un seul, le plus long qui matche)
    for p in NAME_PREFIXES_FR_SORTED:
        if t.startswith(p):
            t = t[len(p) :].strip()
            break
    # 2. Supprimer ponctuation, garder lettres espaces tiret apostrophe
    t = re.sub(r"[^\w\s\-']", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return None, "filler_detected"
    # 2b. Retirer les fillers en début de phrase ("euh jean dupont" → "jean dupont")
    words = t.split()
    while words and words[0] in FILLERS_FR_NAME:
        words = words[1:]
    t = " ".join(words).strip() if words else ""
    if not t:
        return None, "filler_detected"
    # 3. Rejet si tout le reste est un filler
    if t in FILLERS_FR_NAME:
        return None, "filler_detected"
    # 4. Validation minimale (plausible)
    if not is_plausible_name(t):
        return None, "not_plausible_name"
    return t, None


# ----------------------------
# Validation heuristique du nom (plausibilité)
# ----------------------------

NAME_ALLOWED_CHARS_RE = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ' -]+$")  # lettres + apostrophe + espace + tiret
VOWELS_RE = re.compile(r"[aeiouyàâäéèêëîïôöùûüÿ]", re.IGNORECASE)
CONSONANTS_RE = re.compile(r"[bcdfghjklmnpqrstvwxzç]", re.IGNORECASE)


def normalize_text(s: str) -> str:
    return " ".join((s or "").strip().split())


def is_plausible_name(text: str) -> bool:
    """
    Heuristique minimale:
    - >= 2 caractères (après trim)
    - uniquement caractères autorisés (lettres, apostrophe, espace, tiret)
    - contient au moins 1 lettre
    - contient au moins 1 consonne (évite 'aaa', 'iiii', 'ouii')
    - pas uniquement voyelles ; rejette répétition 4+ même lettre (ex: "aaaaa")
    """
    if not text:
        return False

    s = normalize_text(text)

    if len(s) < 2:
        return False
    if len(s) > 40:
        return False  # Évite phrases (IVR safe)

    # Autoriser "Dupont", "Jean Dupont", "O'Neill", "Le-Brun"
    if not NAME_ALLOWED_CHARS_RE.match(s):
        return False

    # Doit contenir au moins 1 lettre
    if not re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", s):
        return False

    # Consonne obligatoire (réduit les faux positifs)
    if not CONSONANTS_RE.search(s):
        return False

    # Évite les suites absurdes (ex: "aaaaa" / "iiii")
    letters_only = re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿ]", "", s)
    if letters_only and len(set(letters_only.lower())) == 1 and len(letters_only) >= 4:
        return False

    return True


# ----------------------------
# Phone plausible (FR + ASR tolérant)
# ----------------------------

DIGITS_RE = re.compile(r"\d+")


def extract_phone_digits(text: str) -> str:
    """Extrait tous les chiffres d'un texte."""
    if not text:
        return ""
    return "".join(DIGITS_RE.findall(text))


def normalize_phone_fr(digits: str) -> Optional[str]:
    """
    Normalise en FR 10 chiffres (06xxxxxxxx).
    Accepte: 10 digits commençant par 0 ; 11/12 digits avec indicatif 33.
    """
    if not digits:
        return None
    digits = "".join(c for c in digits if c.isdigit())
    if not digits:
        return None
    # Cas +33 / 33
    if digits.startswith("33"):
        rest = digits[2:]
        if rest.startswith("0"):
            rest = rest[1:]
        if len(rest) == 9 and rest[0] in "67":
            return "0" + rest
    # Cas national 10 chiffres (0x...)
    if len(digits) == 10 and digits.startswith("0"):
        return digits
    return None


def format_phone_fr(phone10: str) -> str:
    """06XXXXXXXX -> '06 12 34 56 78'"""
    s = "".join(c for c in phone10 if c.isdigit())[:10]
    if len(s) != 10:
        return phone10
    return " ".join([s[i : i + 2] for i in range(0, 10, 2)])


def is_plausible_phone_input(text: str) -> Tuple[bool, Optional[str], str]:
    """
    Retourne: (ok, normalized_phone10, reason).
    reason utile pour logs (empty, no_digits, invalid_format, too_repetitive, ok).
    Rejette: trop court/long, pas de chiffres, format invalide, 0000000000/1111111111.
    """
    if not text or not text.strip():
        return False, None, "empty"
    digits = extract_phone_digits(text)
    if not digits:
        return False, None, "no_digits"
    normalized = normalize_phone_fr(digits)
    if not normalized:
        return False, None, "invalid_format"
    # Heuristiques anti numéro bidon
    if len(set(normalized)) <= 2:
        return False, None, "too_repetitive"
    return True, normalized, "ok"


# ----------------------------
# Préférence plausible (matin/après-midi + heuristiques heures)
# IVR pro : on infère une intention temporelle, pas une réponse exacte.
# ----------------------------

HOUR_RE = re.compile(r"\b([01]?\d|2[0-3])\s*(?:h|:)?\s*([0-5]\d)?\b", re.IGNORECASE)


def normalize_pref(text: str) -> str:
    """Normalisation avant toute logique préférence (QUALIF_PREF)."""
    if not text:
        return ""
    t = text.lower().strip()
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


# Table de mapping FR → intention simple (phrases réelles : "vers 14h", "après le déjeuner", etc.)
MORNING_KEYWORDS = frozenset({
    "matin", "ce matin", "demain matin",
    "avant midi", "avant 12h", "avant 12", "avant douze",
    "en fin de matinee", "en fin de matinée", "fin de matinee", "fin de matinée",
    "debut de matinee", "début de matinée",
    "10h", "9h", "11h", "matinee", "matinée",
})

AFTERNOON_KEYWORDS = frozenset({
    "apres midi", "après midi", "apres-midi", "après-midi", "aprem", "aprèm",
    "apres le dejeuner", "après le déjeuner", "apres le déjeuner",
    "apres manger", "après manger",
    "debut d apres midi", "début d'après-midi",
    "14h", "15h", "16h", "17h", "apres 12", "après 12",
    "en soiree", "en soirée", "soir",
})

NEUTRAL_KEYWORDS = frozenset({
    "peu importe", "comme vous voulez", "n importe quand", "n'importe quand",
    "quand vous voulez", "je sais pas", "je sais pas trop",
    "aucune preference", "aucune préférence",
    "indifferent", "indifférent", "n importe", "n'importe",
})

MORNING_WORDS = frozenset({
    "matin", "matinee", "matinée",
    "avant midi", "avant 12", "avant douze",
    "debut de matinee", "début de matinée",
    "fin de matinee", "fin de matinée",
})

AFTERNOON_WORDS = frozenset({
    "apres-midi", "après-midi", "aprem", "aprèm",
    "apres midi", "après midi",
    "apres 12", "après 12",
    "en debut d'apres-midi", "en début d'après-midi",
    "fin d'apres-midi", "fin d'après-midi",
    "soir", "en soiree", "en soirée",
})

ANY_WORDS = frozenset({
    "peu importe", "comme vous voulez", "n'importe", "n'importe",
    "quand vous voulez", "indifferent", "indifférent",
})


def infer_time_preference(text: str) -> Optional[str]:
    """
    Inférence temporelle simple (sans LLM).
    Retourne: "morning" | "afternoon" | "neutral" | None.
    Gère "vers 14h", "après le déjeuner", "en fin de matinée", "peu importe", "je sais pas trop".
    """
    if not text or not text.strip():
        return None
    t = normalize_pref(text)
    if not t:
        return None
    if any(k in t for k in MORNING_KEYWORDS):
        return "morning"
    if any(k in t for k in AFTERNOON_KEYWORDS):
        return "afternoon"
    if any(k in t for k in NEUTRAL_KEYWORDS):
        return "neutral"
    hour = extract_hour(text)
    if hour is not None:
        if hour < 12:
            return "morning"
        return "afternoon"
    if "jusqu" in t and ("h" in t or ":" in text):
        h = extract_hour(text)
        if h is not None and h >= 12:
            return "afternoon"
    return None


def extract_hour(text: str) -> Optional[int]:
    """Extrait une heure du texte (0-23)."""
    if not text:
        return None
    m = HOUR_RE.search(text.lower())
    if not m:
        return None
    return int(m.group(1))


def infer_preference_plausible(text: str) -> Optional[str]:
    """
    Retourne: "morning" | "afternoon" | "any" | None.
    Comprend: matin, après-midi, fin de matinée, vers 14h, après 17h, peu importe.
    """
    if not text:
        return None
    s = normalize_text(text).lower()
    for w in ANY_WORDS:
        if w in s:
            return "any"
    for w in MORNING_WORDS:
        if w in s:
            return "morning"
    for w in AFTERNOON_WORDS:
        if w in s:
            return "afternoon"
    hour = extract_hour(s)
    if hour is not None:
        if hour < 12:
            return "morning"
        return "afternoon"
    if "jusqu" in s and ("h" in s or ":" in s):
        h = extract_hour(s)
        if h is not None and h >= 12:
            return "afternoon"
    return None


# ----------------------------
# Fillers — rejet systématique (QUALIF_NAME, QUALIF_PREF, QUALIF_CONTACT, WAIT_CONFIRM)
# Une seule fonction is_filler_response() utilisée partout.
# ----------------------------

FILLER_WORDS_SIMPLE = frozenset({
    "euh", "heu", "hum", "hmm", "mmm", "mmh",
    "bah", "ben", "bha",
    "bof", "mouais",
    "hein",
    "quoi",
    "voilà",
    "voila",
    "bon",
})

FILLER_WORDS_COMPOSED = frozenset({
    "je sais pas",
    "je ne sais pas",
    "aucune idée",
    "je sais plus",
    "je sais pas trop",
    "ben je sais pas",
    "euh je sais pas",
    "bah je sais pas",
    "attendez",
    "attends",
    "attendez un peu",
    "une seconde",
    "un instant",
})

FILLER_WORDS_STRESS = frozenset({
    "désolé",
    "désolée",
    "pardon",
    "excusez-moi",
    "excusez moi",
    "je comprends pas",
    "j'ai pas compris",
    "je suis pas sûr",
    "je suis pas sure",
    "je sais plus trop",
})

FILLER_WORDS_NOISE = frozenset({
    "silence",
    "bruit",
    "respiration",
    "souffle",
})

FILLER_WORDS_FR = (
    FILLER_WORDS_SIMPLE
    | FILLER_WORDS_COMPOSED
    | FILLER_WORDS_STRESS
    | FILLER_WORDS_NOISE
)


def is_too_short(text: str) -> bool:
    """Règle structurelle : moins de 2 caractères = non informatif."""
    return len((text or "").strip()) < 2


def is_filler_response(text: str) -> bool:
    """
    True si la réponse doit être rejetée systématiquement (filler, hésitation, trop court).
    Utilisée dans QUALIF_NAME, QUALIF_PREF, QUALIF_CONTACT, WAIT_CONFIRM.
    """
    if not text:
        return True
    clean = text.lower().strip()
    if not clean:
        return True
    if clean in FILLER_WORDS_FR:
        return True
    if is_too_short(clean):
        return True
    return False


def is_filler_or_hesitation(text: str) -> bool:
    """Alias pour is_filler_response (rétrocompat)."""
    return is_filler_response(text)


# Fillers globaux (même liste FR)
FILLER_GLOBAL = FILLER_WORDS_FR

# Réponses courtes acceptées seulement dans certains états
YES_WORDS = frozenset({"oui", "ouais", "ok", "d'accord", "dac", "c'est ça", "exact", "c est ça"})
NO_WORDS = frozenset({"non", "nan", "pas du tout"})

# États où "oui" / "non" sont acceptables (sinon = filler contextuel)
YESNO_ALLOWED_STATES = frozenset({
    "START",
    "CONTACT_CONFIRM",
    "CANCEL_CONFIRM",
    "MODIFY_CONFIRM",
    "WAIT_CONFIRM",  # "oui" seul ne suffit pas, on redemande 1/2/3
    "FAQ_ANSWERED",
    "CLARIFY",
})


def is_contextual_filler(text: str, state: str) -> bool:
    """
    True si la réponse doit être traitée comme filler / non-valide dans ce contexte.
    Ex: en QUALIF_NAME, "oui" = filler ; en CONTACT_CONFIRM, "oui" = valide.
    """
    if not text:
        return True

    s = normalize_text(text).lower()
    if not s:
        return True

    # 1) Fillers universels
    if s in FILLER_GLOBAL:
        return True

    # 2) Oui/Non : autorisés uniquement dans certains états
    if s in YES_WORDS or s in NO_WORDS:
        if state not in YESNO_ALLOWED_STATES:
            return True  # ex: en QUALIF_NAME, "oui" = filler
        return False  # dans ces états, oui/non acceptables (pas forcément suffisants)

    # 3) Trop court = filler
    if is_too_short(s):
        return True

    return False


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
# CHOIX CRÉNEAU FLEXIBLE (IVR pro : jour / heure / numéro)
# ============================================

DAY_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

SLOT_NUM_1 = {"1", "un", "premier", "la première", "le premier"}
SLOT_NUM_2 = {"2", "deux", "deuxième", "second", "la deuxième", "le deuxième"}
SLOT_NUM_3 = {"3", "trois", "troisième", "la troisième", "le troisième"}


def detect_slot_choice_flexible(user_msg: str, proposed_slots: list) -> Optional[int]:
    """
    Détection du choix de créneau : numéro (1/2/3), jour ("mardi"), heure ("10h", "vers 14").
    Si ambigu (2+ slots même jour ou même heure proche) → retourne None (recovery "Dites 1, 2 ou 3").
    
    proposed_slots: list of dict with keys start, label_vocal, day, hour (optionnels).
    Returns: 1-based index (1, 2, 3) ou None.
    """
    if not proposed_slots:
        return None
    s = (user_msg or "").lower().strip()
    if not s:
        return None

    # 1) Numéro (prioritaire, non ambigu)
    words = set(s.split())
    for w in (s, *list(words)):
        if w in SLOT_NUM_1:
            return 1
        if w in SLOT_NUM_2 and len(proposed_slots) >= 2:
            return 2
        if w in SLOT_NUM_3 and len(proposed_slots) >= 3:
            return 3
    if any(w in s for w in SLOT_NUM_1):
        return 1
    if any(w in s for w in SLOT_NUM_2) and len(proposed_slots) >= 2:
        return 2
    if any(w in s for w in SLOT_NUM_3) and len(proposed_slots) >= 3:
        return 3

    # 2) Jour : si plusieurs slots ce jour → ambigu
    day_candidates = []
    for i, slot in enumerate(proposed_slots, 1):
        day = (slot.get("day") or "").lower().strip()
        if day and day in s:
            day_candidates.append(i)
    if len(day_candidates) == 1:
        return day_candidates[0]
    if len(day_candidates) > 1:
        return None

    # 3) Heure : slot le plus proche (≤1h), sinon ambigu si plusieurs à même distance
    hour = extract_hour(s)
    if hour is not None:
        candidates = []
        for i, slot in enumerate(proposed_slots, 1):
            sh = slot.get("hour")
            if sh is None:
                continue
            candidates.append((abs(sh - hour), i))
        if not candidates:
            return None
        candidates.sort()
        if candidates[0][0] <= 1:
            # Un seul à distance min ?
            best_dist = candidates[0][0]
            best_indices = [c[1] for c in candidates if c[0] == best_dist]
            if len(best_indices) == 1:
                return best_indices[0]
            return None
    return None


# ============================================
# CONFIRMATION VOCALE (un/deux/trois)
# ============================================

# Mapping mots → chiffre (FR)
_VOCAL_NUM_MAP = {
    "1": 1,
    "1.": 1,
    "1er": 1,
    "un": 1,
    "une": 1,
    "premier": 1,
    "premiere": 1,
    "première": 1,
    
    "2": 2,
    "2e": 2,
    "deux": 2,
    "second": 2,
    "seconde": 2,
    "deuxieme": 2,
    "deuxième": 2,
    
    "3": 3,
    "3e": 3,
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
    # Enlever ponctuation finale (ex: "1.", "deux!")
    raw = re.sub(r"[.,;:!?]+$", "", raw).strip()

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
        # Trop verbeux (ex: "premier s'il vous plaît") → refuser
        tokens = [t for t in re.split(r"[\s\-]+", core) if t]
        if not tokens or len(tokens) > 2:
            continue

        # Essaye chaque token (enlever ponctuation finale)
        for tok in tokens:
            tok_clean = re.sub(r"[.,;:!?]+$", "", tok)
            if tok_clean in _VOCAL_NUM_MAP:
                return _VOCAL_NUM_MAP[tok_clean]

        # Dernier token
        last = re.sub(r"[.,;:!?]+$", "", tokens[-1])
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
    original = text
    text = text.lower().strip()
    
    # Retirer les mots parasites courants
    filler_words = [
        "c'est le", "c'est", "le", "mon numéro", "numéro", "téléphone", "portable",
        "mobile", "alors", "euh", "ben", "donc", "oui", "voilà", "bon",
        "j'ai le", "mon", "ça fait", "virgule", "point"
    ]
    for word in filler_words:
        text = text.replace(word, " ")
    
    # Nettoyer espaces multiples
    text = " ".join(text.split())
    
    print(f"📞 parse_vocal_phone: '{original}' → cleaned: '{text}'")
    
    # D'abord extraire tous les chiffres déjà présents dans le texte
    existing_digits = ''.join(c for c in text if c.isdigit())
    if len(existing_digits) >= 10:
        # Le texte contient déjà des chiffres numériques
        print(f"📞 Found existing digits: {existing_digits}")
        return existing_digits[:10]  # Garder les 10 premiers
    
    # Sinon parser les mots en chiffres
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
    
    print(f"📞 parse_vocal_phone result: {digits}")
    
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
