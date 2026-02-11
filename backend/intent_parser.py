# backend/intent_parser.py
"""
Parsing STT + routing déterministe : fonctions pures, testables.
- Lexiques dédiés ici (pas de matching basé sur prompts.py : wording ≠ source de matching).
- Règle anti résolution silencieuse : si le parseur hésite entre 2 routes → retourner None ; le caller clarifie.
  Ex. hein ≠ un, de ≠ deux (ROUTER_AMBIGUOUS).
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Optional, List

# ---------------------------------------------------------------------------
# 0) Types / Enums
# ---------------------------------------------------------------------------

class Intent(str, Enum):
    YES = "YES"
    NO = "NO"
    BOOKING = "BOOKING"
    CANCEL = "CANCEL"
    MODIFY = "MODIFY"
    TRANSFER = "TRANSFER"
    ABANDON = "ABANDON"
    FAQ = "FAQ"
    REPEAT = "REPEAT"
    UNCLEAR = "UNCLEAR"
    ORDONNANCE = "ORDONNANCE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"  # hors-sujet (ex. LLM Assist)


class RouterChoice(str, Enum):
    ROUTER_1 = "1"
    ROUTER_2 = "2"
    ROUTER_3 = "3"
    ROUTER_4 = "4"


class SlotChoice(str, Enum):
    SLOT_1 = "1"
    SLOT_2 = "2"
    SLOT_3 = "3"


class ContactChoice(str, Enum):
    CONTACT_PHONE = "phone"
    CONTACT_EMAIL = "email"


# ---------------------------------------------------------------------------
# Lexiques dédiés (matching intent) — ne pas dépendre de prompts.py
# ---------------------------------------------------------------------------

# Strong intents (ordre de priorité : TRANSFER > CANCEL > MODIFY > ABANDON > ORDONNANCE > FAQ)
_TRANSFER_LEXICON = [
    "conseiller", "quelqu un", "quelqu'un", "humain", "une personne", "parler a quelqu un",
    "agent", "standard", "secretariat", "secretaire",
    "je veux parler", "mettez moi quelqu un", "passez moi quelqu un",
    "un humain", "un conseiller", "mes resultats", "resultats d analyses",
    "c est urgent", "c est grave",
]
_CANCEL_LEXICON = [
    "annuler", "annulation", "supprimer",
    "je veux annuler", "annuler mon rendez vous", "annuler mon rdv", "supprimer mon rendez vous",
]
_MODIFY_LEXICON = [
    "modifier", "changer", "deplacer", "reporter", "reprogrammer", "decaler", "avancer",
    "changer mon rendez vous", "deplacer mon rdv", "reporter mon rdv", "modifier mon rdv",
]
_ABANDON_LEXICON = [
    "au revoir", "bye", "merci au revoir", "c est tout", "c est tout merci",
    "ca sera tout", "ca sera tout merci", "ce sera tout", "ce sera tout merci",
    "non merci au revoir", "bonne journee", "stop",
    "laisse tomber", "laissez tomber", "tant pis",
    "annule tout", "j abandonne", "oubliez", "je rappelle", "je vais rappeler", "plus tard",
]
_ORDONNANCE_LEXICON = [
    "ordonnance", "ordonnances", "renouvellement", "renouveler",
    "prescription", "prescrip", "medicament", "medicaments", "traitement",
]
# FAQ fort : vrais signaux (horaires, adresse, tarif…). Exclure mots métier/motif (consultation, service, pédiatre).
_FAQ_STRONG_LEXICON = [
    "adresse", "ou etes vous", "ou est", "c est ou",
    "horaires", "horaire", "heures d ouverture", "ouvert", "ferme",
    "tarif", "tarifs", "prix", "combien coute",
    "parking", "acces", "telephone du cabinet",
]

_YES_LEXICON = [
    "oui", "ouais", "ouai", "ok", "okay", "d accord", "daccord",
    "exactement", "tout a fait", "absolument", "bien sur",
    "c est bon", "ca marche", "exact", "parfait", "c est ca", "voila", "affirmatif",
    "c est bien ca", "cest bien ca", "oui c est bien ca", "oui cest bien ca",
    "c est correct", "cest correct", "oui c est correct", "oui cest correct",
]
_NO_LEXICON = [
    "non", "nan", "pas du tout", "pas vraiment",
    "non merci", "nom merci", "pas maintenant", "ca ne va pas", "pas possible",
]
_REPEAT_LEXICON = [
    "repete", "repeter", "vous pouvez repeter", "encore", "redis", "redire",
    "vous pouvez redire", "j ai pas compris", "jai pas compris", "pas compris",
    "pardon", "comment", "quoi", "attendez", "reprenez", "recommencez",
]
# Mots entiers uniquement (éviter "quoi" dans "nimportequoi", "encore" dans "encorebizarre")
_REPEAT_SINGLE_WORDS = frozenset({
    "repete", "repeter", "repetes", "repetez", "encore", "redis", "redire", "pardon",
    "comment", "quoi", "reprendre", "reécoute", "reecoute", "attendez", "reprenez",
})

# Filler / silence / bruit : UNCLEAR mais ne pas envoyer en _handle_faq (clarify/guidance à la place).
UNCLEAR_FILLER_TOKENS = frozenset({"euh", "hein", "hum", "euhh", "mmh"})
# « Je ne sais pas » à l'accueil = filler (pas une vraie demande) → clarification, pas FAQ paiement/espèces.
FILLER_JE_SAIS_PAS = frozenset({
    "je ne sais pas", "je sais pas", "j en sais pas", "j'en sais pas",
    "ben je sais pas", "ben j en sais pas", "euh je sais pas", "bien je sais pas",
})

# États où YES/NO sont interprétés comme choix (confirmations). Ailleurs (START, POST_FAQ, CLARIFY…)
# "oui"/"d'accord" → UNCLEAR pour éviter de déclencher un choix par erreur.
# États où "oui"/"d'accord" est interprété comme YES (confirmations explicites + POST_FAQ disambiguation).
ALLOWED_YESNO_STATES = frozenset({
    "CONTACT_CONFIRM", "CANCEL_CONFIRM", "MODIFY_CONFIRM", "WAIT_CONFIRM",
    "PREFERENCE_CONFIRM", "POST_FAQ", "POST_FAQ_CHOICE",
})


def is_unclear_filler(text: str) -> bool:
    """
    True si le texte est uniquement filler/silence/bruit (euh, hein, hum) ou « je ne sais pas ».
    À utiliser en START : si UNCLEAR + is_unclear_filler → clarify/guidance, pas _handle_faq.
    Évite le faux match FAQ « paiement en espèces » pour « je sais pas ».
    """
    if not text or not text.strip():
        return True
    t = normalize_stt_text(text)
    if not t or len(t) < 2:
        return True
    tokens = t.split()
    if len(tokens) <= 1 and t in UNCLEAR_FILLER_TOKENS:
        return True
    if t in UNCLEAR_FILLER_TOKENS:
        return True
    if t in FILLER_JE_SAIS_PAS:
        return True
    # Variantes courtes « … sais pas » (évite FAQ paiement/espèces)
    if len(tokens) <= 5 and "sais pas" in t:
        return True
    return False


# ---------------------------------------------------------------------------
# 1) Normalisation STT (pure)
# ---------------------------------------------------------------------------
# Règle : la normalisation ne doit jamais supprimer les mots porteurs de négation/accord :
# pas, non, plus, jamais. (Apostrophe → espace : "d'accord" → "d accord", le "d" reste.)
_ACCENT_MAP = str.maketrans(
    "àâäéèêëïîôùûüçœæ",
    "aaaeeeeiioouucea"
)


def normalize_stt_text(raw: str) -> str:
    """
    Normalise le texte STT pour parsing déterministe.
    - lower, trim, ponctuation → espace, apostrophes/tirets → espace, accents → ascii, espaces multiples.
    - Ne jamais supprimer : pas, non, plus, jamais (on ne supprime aucun mot, seulement caractères).
    """
    if not raw or not isinstance(raw, str):
        return ""
    t = raw.strip().lower()
    if not t:
        return ""
    # Uniformiser apostrophes
    t = t.replace("'", " ").replace("'", " ").replace("'", " ")
    # Ponctuation → espace
    t = re.sub(r"[.,;:!?\[\]()\"…]", " ", t)
    # Tirets internes (après-midi → apres midi)
    t = t.replace("-", " ")
    # Accents → ascii pour matching STT
    t = t.translate(_ACCENT_MAP)
    # Espaces multiples
    t = " ".join(t.split())
    return t.strip()


def tokenize(text: str) -> List[str]:
    """Split simple, garde les mots (après normalize_stt_text)."""
    t = normalize_stt_text(text)
    return t.split() if t else []


# ---------------------------------------------------------------------------
# 2) Détection intents forts (override global) — pure
# ---------------------------------------------------------------------------

def _pattern_in_text(text_normalized: str, patterns: List[str]) -> bool:
    """Match lexique sur texte déjà normalisé (patterns en forme normalisée)."""
    for p in patterns:
        if p and (p in text_normalized or text_normalized == p):
            return True
    return False


def detect_strong_intent(text: str, state: str = "") -> Optional[Intent]:
    """
    Priorité: TRANSFER > CANCEL > MODIFY > ABANDON > ORDONNANCE > FAQ
    Lexiques dédiés (pas prompts.py). Retourne None si aucun. Pure.
    """
    if not text or not text.strip():
        return None
    t = normalize_stt_text(text)
    if not t:
        return None
    if _pattern_in_text(t, _TRANSFER_LEXICON):
        return Intent.TRANSFER
    if _pattern_in_text(t, _CANCEL_LEXICON):
        return Intent.CANCEL
    if _pattern_in_text(t, _MODIFY_LEXICON):
        return Intent.MODIFY
    if _pattern_in_text(t, _ABANDON_LEXICON):
        return Intent.ABANDON
    if _pattern_in_text(t, _ORDONNANCE_LEXICON):
        return Intent.ORDONNANCE
    if _pattern_in_text(t, _FAQ_STRONG_LEXICON):
        return Intent.FAQ
    return None


# ---------------------------------------------------------------------------
# 3) Détection intents "soft" (YES/NO/REPEAT/BOOKING/UNCLEAR) — pure
# ---------------------------------------------------------------------------

def _is_yes(text: str) -> bool:
    t = normalize_stt_text(text)
    if not t:
        return False
    for p in _YES_LEXICON:
        if p in t or t == p or t.startswith(p + " ") or t.startswith(p + ","):
            return True
    if t in ("oui", "ui", "wi", "ouais", "ouai", "ok", "okay", "d accord", "daccord"):
        return True
    return False


def _is_no(text: str) -> bool:
    t = normalize_stt_text(text)
    if not t:
        return False
    for p in _NO_LEXICON:
        if t == p or t.startswith(p + " ") or t.startswith(p + ","):
            return True
    return False


def extract_slot_choice(text: str, num_slots: int = 3) -> Optional[int]:
    """
    Extrait un choix de créneau 1/2/3 depuis une phrase courte (barge-in pendant lecture).
    Utilise normalize_stt_text pour robustesse STT.
    Retourne 1, 2 ou 3 uniquement ; None sinon.
    num_slots : utilisé pour "dernier"/"le dernier" → 3 si num_slots >= 3.
    """
    if not text or not text.strip():
        return None
    t = normalize_stt_text(text)
    if not t or len(t) > 50:
        return None
    # Chiffre seul
    if t in ("1", "2", "3"):
        return int(t)
    # Ordinaux
    if re.match(r"^(le\s+)?(premier|un)\s*$", t):
        return 1
    if re.match(r"^(le\s+)?(deuxième|deuxieme|deux|second)\s*$", t):
        return 2
    if re.match(r"^(le\s+)?(troisième|troisieme|trois)\s*$", t):
        return 3
    # "dernier" / "le dernier" → 3 si on a 3 slots
    if re.match(r"^(le\s+)?dernier\s*$", t) and num_slots >= 3:
        return 3
    # Marqueur + chiffre : le 1, numero 2, choix 3, prends le 1
    m = re.search(r"^(?:le|numero|choix|option|creneau|prends?\s+le)\s*([123])\s*$", t)
    if m:
        return int(m.group(1))
    if re.match(r"^le\s*[123]\s*$", t):
        return int(re.search(r"[123]", t).group(0))
    return None


def _is_repeat(text: str) -> bool:
    t = normalize_stt_text(text)
    if not t:
        return False
    tokens = t.split()
    if any(w in _REPEAT_SINGLE_WORDS for w in tokens):
        return True
    for p in _REPEAT_LEXICON:
        if " " in p and (p in t or t == p):
            return True
        if t == p:
            return True
    return False


# Liste noire start intent : annulation / déplacement / négation / RDV existant → pas BOOKING
# Priorité : strong intent (CANCEL/MODIFY) est déjà évalué avant _is_booking ; ceci est un garde-fou.
_BOOKING_START_BLACKLIST = [
    "annuler", "deplacer", "reporter", "changer mon rendez",
    "pas de rendez", "pas de rdv", "pas un rendez", "pas un rdv",
    " pas ", " plus ", " aucun ", " non ", "non ", " non",  # négation (avec espaces pour éviter faux positifs)
    "deja un rendez", "deja un rdv", "j ai deja",
    " mon rendez yous", "mon rendez yous ",  # "mon rendez-vous" / RDV existant ambigu
]


def _is_booking_blacklist(text: str) -> bool:
    """True si on ne doit pas traiter comme INTENT_BOOKING (annulation, négation, déplacement, RDV existant)."""
    t = normalize_stt_text(text)
    if not t:
        return False
    if t == "non" or t.startswith("non "):
        return True
    return any(bl in t for bl in _BOOKING_START_BLACKLIST)


def _is_booking(text: str) -> bool:
    t = normalize_stt_text(text)
    if not t:
        return False
    if _is_booking_blacklist(text):
        return False
    # Mots-clés courts (start intent "rendez-vous" — liste blanche produit)
    if t in ("rdv", "rendez vous", "rendezvous") or t.strip() in ("rdv", "rendez vous", "rendezvous"):
        return True
    booking_markers = [
        "rendez-vous", "rendez vous", "rdv",
        "prendre rendez-vous", "prendre rendez vous", "prendre rdv",
        "prise de rendez vous", "rendez vous svp", "un rendez vous", "un rdv",
        "réserver", "reserver", "booker", "je veux venir", "je veux un rendez", "je voudrais un rendez",
        "je voudrais un créneau", "je voudrais un creneau",
    ]
    return any(m in t for m in booking_markers)


def _is_faq_keywords(text: str) -> bool:
    t = normalize_stt_text(text)
    kw = ["horaire", "horaires", "adresse", "tarif", "prix", "parking", "accès", "ouvert", "fermé", "où", "ou "]
    return any(k in t for k in kw)


def detect_intent(text: str, state: str = "") -> Intent:
    """
    Intent "soft". YES/NO ne sont actifs que dans les états de confirmation
    (CONTACT_CONFIRM, CANCEL_CONFIRM, MODIFY_CONFIRM, WAIT_CONFIRM, …).
    Ailleurs (START, POST_FAQ, CLARIFY) : "oui"/"d'accord" → UNCLEAR (pas de choix direct).
    """
    if not text or not text.strip():
        return Intent.UNCLEAR
    t = normalize_stt_text(text)
    if len(t) < 2 and t not in ("oui", "non", "ok"):
        return Intent.UNCLEAR
    # REPEAT avant filler (ex: "pardon" = REPEAT, pas UNCLEAR)
    if _is_repeat(text):
        return Intent.REPEAT
    # Filler seul (euh, hein, hum) => UNCLEAR (ne pas router vers _handle_faq en START)
    if t in UNCLEAR_FILLER_TOKENS or (len(t.split()) <= 1 and t in UNCLEAR_FILLER_TOKENS):
        return Intent.UNCLEAR
    try:
        from backend.guards import FILLER_GLOBAL
        if t in FILLER_GLOBAL:
            return Intent.UNCLEAR
    except Exception:
        pass
    # YES / NO : actifs seulement dans les états de confirmation (éviter "d'accord" → choix partout)
    if _is_yes(text):
        if state in ALLOWED_YESNO_STATES:
            return Intent.YES
        return Intent.UNCLEAR
    if _is_no(text):
        return Intent.NO
    # Strong intents (réutiliser pour cohérence)
    strong = detect_strong_intent(text, state)
    if strong is not None:
        return strong
    # BOOKING (explicite)
    if _is_booking(text):
        return Intent.BOOKING
    # FAQ par défaut si mots-clés
    if _is_faq_keywords(text):
        return Intent.FAQ
    return Intent.UNCLEAR


# ---------------------------------------------------------------------------
# 4) Parsing menu INTENT_ROUTER — pure
# ---------------------------------------------------------------------------

ROUTER_AMBIGUOUS = frozenset({"hein", "de"})

ROUTER_1_TOKENS = ["un", "1", "premier", "le premier", "première option", "rendez-vous", "rdv", "prendre rendez-vous", "réserver", "booker", "je veux venir", "je voudrais un créneau"]
ROUTER_2_TOKENS = ["deux", "2", "deuxième", "le deuxième", "seconde option", "annuler", "annulation", "modifier", "changer", "déplacer"]
ROUTER_3_TOKENS = ["trois", "3", "troisième", "le troisième", "question", "une question", "renseignement", "info", "informations"]
ROUTER_4_TOKENS = ["quatre", "4", "quatrième", "le quatrième", "conseiller", "humain", "quelqu'un", "quelqu un", "une personne"]
ROUTER_4_STT_TOLERANCE = ["cat", "catre", "quattre", "katr", "quatres"]


def parse_router_choice(text: str) -> Optional[RouterChoice]:
    """
    Parse le choix menu 1/2/3/4. hein seul / de seul => None (ambiguïté).
    """
    if not text or not text.strip():
        return None
    t = normalize_stt_text(text)
    if not t:
        return None
    if t in ROUTER_AMBIGUOUS:
        return None
    if any(p in t for p in ROUTER_4_TOKENS + ROUTER_4_STT_TOLERANCE):
        return RouterChoice.ROUTER_4
    if any(p in t for p in ROUTER_1_TOKENS):
        return RouterChoice.ROUTER_1
    if any(p in t for p in ROUTER_2_TOKENS):
        return RouterChoice.ROUTER_2
    if any(p in t for p in ROUTER_3_TOKENS):
        return RouterChoice.ROUTER_3
    return None


# ---------------------------------------------------------------------------
# 5) Parsing choix de créneau (mode non-séquentiel)
# ---------------------------------------------------------------------------

SLOT_1_TOKENS = ["premier", "le premier", "1", "un", "option 1"]
SLOT_2_TOKENS = ["deuxième", "le deuxième", "2", "deux", "option 2", "second"]
SLOT_3_TOKENS = ["troisième", "le troisième", "3", "trois", "option 3"]


def parse_slot_choice(text: str) -> Optional[SlotChoice]:
    """
    "oui deux" transcrit "oui de" => None (clarification).
    """
    if not text or not text.strip():
        return None
    t = normalize_stt_text(text)
    if not t:
        return None
    # Ambiguïté "oui de" (oui deux ?) => ne pas résoudre
    if t.startswith("oui de") or t == "oui de" or (t.startswith("oui") and " de " in t and len(t) < 20):
        return None
    if any(p in t for p in SLOT_1_TOKENS) or (t.startswith("oui") and ("1" in t or "un" in t or "premier" in t)):
        return SlotChoice.SLOT_1
    if any(p in t for p in SLOT_2_TOKENS) or (t.startswith("oui") and ("2" in t or "deux" in t or "deuxième" in t)):
        return SlotChoice.SLOT_2
    if any(p in t for p in SLOT_3_TOKENS) or (t.startswith("oui") and ("3" in t or "trois" in t or "troisième" in t)):
        return SlotChoice.SLOT_3
    return None


# ---------------------------------------------------------------------------
# 6) Parsing contact choice
# ---------------------------------------------------------------------------

def parse_contact_choice(text: str) -> Optional[ContactChoice]:
    if not text or not text.strip():
        return None
    t = normalize_stt_text(text)
    if not t:
        return None
    phone = ["téléphone", "telephone", "numéro", "numero", "portable", "mobile", "appel", "appelez-moi", "appelez moi"]
    email = ["email", "mail", "adresse mail", "courriel", "écrire", "par mail", "mel", "mèl", "mél"]
    if any(p in t for p in phone):
        return ContactChoice.CONTACT_PHONE
    if any(p in t for p in email):
        return ContactChoice.CONTACT_EMAIL
    return None


# ---------------------------------------------------------------------------
# 7) Normalisation téléphone (pure)
# ---------------------------------------------------------------------------

def words_to_digits(text: str) -> str:
    """
    Convertit mots (zéro..neuf, dix, etc.) en chiffres. Pure, sans effet de bord.
    Approche robuste : 0–9 en mots, dizaines (dix…seize), dictée "deux par deux".
    Ne pas sur-interpréter les composés ambigus ; fallback email après 2–3 fails (côté engine).
    """
    if not text or not text.strip():
        return ""
    try:
        from backend.guards import _WORD_TO_DIGIT
    except AttributeError:
        return "".join(c for c in text if c.isdigit())
    remaining = normalize_stt_text(text)
    if not remaining:
        return "".join(c for c in text if c.isdigit())
    result = []
    sorted_keys = sorted(_WORD_TO_DIGIT.keys(), key=lambda k: len(normalize_stt_text(k)), reverse=True)
    while remaining:
        remaining = remaining.strip()
        if not remaining:
            break
        found = False
        for pattern in sorted_keys:
            pnorm = normalize_stt_text(pattern)
            if not pnorm:
                continue
            if remaining == pnorm or remaining.startswith(pnorm + " ") or remaining.startswith(pnorm):
                result.append(_WORD_TO_DIGIT[pattern])
                remaining = remaining[len(pnorm):].strip()
                found = True
                break
        if not found:
            if remaining and remaining[0].isdigit():
                result.append(remaining[0])
                remaining = remaining[1:].strip()
            else:
                remaining = remaining[1:].strip() if len(remaining) > 1 else ""
    digits = "".join(c for c in "".join(result) if c.isdigit())
    return digits


def normalize_phone(raw_text: str) -> Optional[str]:
    """
    Normalise numéro FR : 10 chiffres 0X... ; +33/33 => 0 ; 9 chiffres 6/7 => 0 prefix.
    Retourne None si invalide. Pure.
    """
    if not raw_text or not raw_text.strip():
        return None
    raw = raw_text.strip()
    if any(c.isalpha() for c in raw):
        digits = words_to_digits(raw)
    else:
        digits = "".join(c for c in raw if c.isdigit())
    if not digits:
        return None
    try:
        from backend.guards import normalize_phone_fr
        return normalize_phone_fr(digits)
    except Exception:
        pass
    if digits.startswith("33"):
        rest = digits[2:].lstrip("0")
        if len(rest) == 9 and rest[0] in "67":
            return "0" + rest
        if len(rest) == 9:
            return "0" + rest
    if len(digits) == 10 and digits[0] == "0":
        return digits
    if len(digits) == 9 and digits[0] in "67":
        return "0" + digits
    return None
