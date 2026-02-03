# backend/prompts.py
"""
Single source of truth pour TOUTES les formulations exactes.
Aucune string "user-facing" ne doit être hardcodée ailleurs.

⚠️ RÈGLE ABSOLUE :
Toute modification de ce fichier doit être accompagnée d'une mise à jour
de tests/test_prompt_compliance.py ET d'une validation PRD.

Ce fichier est la SOURCE DE VÉRITÉ pour le comportement de l'agent.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict
import re


# ----------------------------
# Messages exacts (System Prompt)
# ----------------------------

def msg_no_match_faq(business_name: str, channel: str = "web") -> str:
    """
    Message quand aucune FAQ ne correspond.
    Ton différent selon le canal.
    """
    if channel == "vocal":
        # Ton parisien naturel
        return (
            f"Hmm, là je suis pas sûr de pouvoir vous répondre. "
            f"Je vous passe quelqu'un de chez {business_name}, d'accord ?"
        )
    # Web - format texte standard
    return (
        "Je ne suis pas certain de pouvoir répondre précisément.\n"
        f"Puis-je vous mettre en relation avec {business_name} ?"
    )

MSG_EMPTY_MESSAGE = "Je n'ai pas reçu votre message. Pouvez-vous réessayer ?"
MSG_TOO_LONG = "Votre message est trop long. Pouvez-vous résumer ?"
MSG_FRENCH_ONLY = "Je ne parle actuellement que français."
MSG_SESSION_EXPIRED = "Votre session a expiré. Puis-je vous aider ?"
MSG_TRANSFER = "Je vous mets en relation avec un humain pour vous aider."
MSG_ALREADY_TRANSFERRED = "Vous avez été transféré à un humain. Quelqu'un va vous répondre sous peu."

# Booking
# Instruction confirmation (Web - legacy)
MSG_CONFIRM_INSTRUCTION = "Répondez par 'oui 1', 'oui 2' ou 'oui 3' pour confirmer."

# Instruction confirmation (Vocal)
MSG_CONFIRM_INSTRUCTION_VOCAL = (
    "Pour confirmer, dites : un, deux ou trois. "
    "Vous pouvez aussi dire : oui un, oui deux, oui trois."
)

# Instruction confirmation (Web)
MSG_CONFIRM_INSTRUCTION_WEB = (
    "Répondez par 'oui 1', 'oui 2' ou 'oui 3' pour confirmer."
)

MSG_CONFIRM_RETRY_VOCAL = (
    "Je n'ai pas compris. Dites seulement : un, deux ou trois."
)


def get_confirm_instruction(channel: str = "web") -> str:
    """
    Retourne le message de confirmation adapté au canal.
    """
    return MSG_CONFIRM_INSTRUCTION_VOCAL if channel == "vocal" else MSG_CONFIRM_INSTRUCTION_WEB

# Qualification - Contact
MSG_CONTACT_INVALID = "Le format du contact est invalide. Merci de fournir un email ou un numéro de téléphone valide."
MSG_CONTACT_INVALID_TRANSFER = "Le format du contact est invalide. Je vous mets en relation avec un humain pour vous aider."

# Qualification - Motif (aide)
MSG_AIDE_MOTIF = (
    "Pour continuer, indiquez le motif du rendez-vous "
    "(ex : consultation, contrôle, douleur, devis). Répondez en 1 courte phrase."
)
MSG_INVALID_MOTIF = (
    "Merci d'indiquer le motif en une courte phrase "
    "(par exemple : consultation, suivi, information)."
)

# Qualification - Contact (aide)
MSG_CONTACT_HINT = (
    "Pour continuer, j'ai besoin d'un contact.\n"
    "👉 Répondez avec un email (ex : nom@email.com)\n"
    "ou un numéro de téléphone (ex : 06 12 34 56 78)."
)

MSG_CONTACT_CHOICE_ACK_EMAIL = "Très bien. Quelle adresse email puis-je utiliser ?"
MSG_CONTACT_CHOICE_ACK_PHONE = "Très bien. Quel numéro de téléphone puis-je utiliser ?"

# Utilisé après 1 erreur (et seulement 1)
MSG_CONTACT_RETRY = (
    "Je n'ai pas pu valider ce contact.\n"
    "Merci de répondre avec un email complet (ex : nom@email.com) "
    "ou un numéro de téléphone (ex : 06 12 34 56 78)."
)

# Si 2e échec -> transfert
MSG_CONTACT_FAIL_TRANSFER = (
    "Je n'arrive pas à valider votre contact. "
    "Je vous mets en relation avec un humain pour vous aider."
)

# ----------------------------
# Messages vocaux (V1) - Ton Parisien naturel
# ----------------------------

# Salutation d'accueil (voix chaleureuse)
# Question directe mais accueillante
VOCAL_SALUTATION = (
    "Bonjour et bienvenue chez {business_name} ! Vous appelez pour prendre un rendez-vous ?"
)

# Fallback si besoin
VOCAL_SALUTATION_NEUTRAL = (
    "Bonjour ! Bienvenue chez {business_name}, je vous écoute."
)

VOCAL_SALUTATION_LONG = (
    "Bonjour ! Bienvenue chez {business_name}. "
    "Je suis là pour vous aider. Qu'est-ce que je peux faire pour vous ?"
)

VOCAL_SALUTATION_SHORT = "Oui, je vous écoute ?"

# Message d'accueil pour le First Message Vapi
def get_vocal_greeting(business_name: str) -> str:
    """
    Retourne le message d'accueil pour Vapi.
    Format: "Bonjour Cabinet Dupont, vous appelez pour un rendez-vous ?"
    """
    return VOCAL_SALUTATION.format(business_name=business_name)


# ----------------------------
# FLOW B: FAQ - Réponses et relances
# ----------------------------

VOCAL_FAQ_FOLLOWUP = "Est-ce que je peux vous aider pour autre chose ?"

VOCAL_FAQ_GOODBYE = "Avec plaisir ! Bonne journée et à bientôt !"

VOCAL_FAQ_TO_BOOKING = "Bien sûr ! C'est à quel nom ?"


# ----------------------------
# FLOW C: CANCEL - Annulation de RDV
# ----------------------------

VOCAL_CANCEL_ASK_NAME = "Bien sûr, pas de problème ! C'est à quel nom ?"
# Message envoyé immédiatement en vocal pendant la recherche du RDV (évite le "mmm" TTS)
VOCAL_CANCEL_LOOKUP_HOLDING = "Un instant, je cherche votre rendez-vous."

# Recovery progressive : nom pas compris (CANCEL_NAME)
VOCAL_CANCEL_NAME_RETRY_1 = "Je n'ai pas noté votre nom. Vous pouvez répéter ?"
VOCAL_CANCEL_NAME_RETRY_2 = "Votre nom et prénom. Par exemple : Martin Dupont."

VOCAL_CANCEL_NOT_FOUND = (
    "Hmm, je ne trouve pas de rendez-vous à ce nom. "
    "Vous pouvez me redonner votre nom complet s'il vous plaît ?"
)

# RDV non trouvé : proposer vérifier ou humain (pas transfert direct)
VOCAL_CANCEL_NOT_FOUND_VERIFIER_HUMAN = (
    "Je ne trouve pas de rendez-vous au nom de {name}. "
    "Voulez-vous vérifier l'orthographe ou parler à quelqu'un ? "
    "Dites : vérifier, ou : humain."
)

VOCAL_CANCEL_CONFIRM = (
    "J'ai trouvé ! Vous avez un rendez-vous {slot_label}. "
    "Vous souhaitez l'annuler ?"
)

VOCAL_CANCEL_DONE = (
    "C'est fait, votre rendez-vous est bien annulé. "
    "N'hésitez pas à nous rappeler si besoin. Bonne journée !"
)

VOCAL_CANCEL_KEPT = (
    "Pas de souci, votre rendez-vous est bien maintenu. "
    "On vous attend ! Bonne journée !"
)


# ----------------------------
# FLOW D: MODIFY - Modification de RDV
# ----------------------------

VOCAL_MODIFY_ASK_NAME = "Pas de souci. C'est à quel nom ?"

# Recovery progressive : nom pas compris (MODIFY_NAME)
VOCAL_MODIFY_NAME_RETRY_1 = "Je n'ai pas noté votre nom. Vous pouvez répéter ?"
VOCAL_MODIFY_NAME_RETRY_2 = "Votre nom et prénom. Par exemple : Martin Dupont."

VOCAL_MODIFY_NOT_FOUND = (
    "Hmm, j'ai pas trouvé de rendez-vous à ce nom. "
    "Vous pouvez me redonner votre nom complet ?"
)

# RDV non trouvé : proposer vérifier ou humain (pas transfert direct)
VOCAL_MODIFY_NOT_FOUND_VERIFIER_HUMAN = (
    "Je ne trouve pas de rendez-vous au nom de {name}. "
    "Voulez-vous vérifier l'orthographe ou parler à quelqu'un ? "
    "Dites : vérifier, ou : humain."
)

VOCAL_MODIFY_CONFIRM = (
    "Vous avez un rendez-vous {slot_label}. Vous voulez le déplacer ?"
)

VOCAL_MODIFY_CANCELLED = (
    "OK, j'ai annulé l'ancien. Plutôt le matin ou l'après-midi pour le nouveau ?"
)


# ----------------------------
# FLOW E: UNCLEAR - Cas flou
# ----------------------------

VOCAL_CLARIFY = (
    "Pas de souci ! Je peux vous renseigner si vous avez une question, "
    "ou vous aider à prendre un rendez-vous. Qu'est-ce qui vous ferait plaisir ?"
)

VOCAL_STILL_UNCLEAR = (
    "Pas de problème, je vais vous passer quelqu'un qui pourra mieux vous aider. Un instant."
)

# ----------------------------
# INTENT_ROUTER (spec V3 — menu reset universel)
# ----------------------------

VOCAL_INTENT_ROUTER = (
    "Dites : Un pour rendez-vous. Deux pour annuler. Trois pour une question. Quatre pour parler à quelqu'un."
)
# Échec 3 nom (test B1) : même menu avec intro stabilisante
VOCAL_NAME_FAIL_3_INTENT_ROUTER = (
    "Je vais simplifier. Dites : Un pour rendez-vous. Deux pour annuler. Trois pour une question. Quatre pour parler à quelqu'un."
)

MSG_INTENT_ROUTER = (
    "Je vais simplifier. Dites : un, pour prendre un rendez-vous ; "
    "deux, pour annuler ou modifier ; trois, pour poser une question ; "
    "quatre, pour parler à quelqu'un. Dites simplement : un, deux, trois ou quatre."
)

MSG_INTENT_ROUTER_FAQ = "Quelle est votre question ?"

MSG_INTENT_ROUTER_RETRY = (
    "Dites juste le numéro. Par exemple : un pour rendez-vous."
)

MSG_PREFERENCE_CONFIRM = "D'accord, donc plutôt {pref}, c'est bien ça ?"

# ----------------------------
# Recovery téléphone / préférence / créneau (VOCAL_* — cohérence B2/B3)
# ----------------------------

VOCAL_PHONE_FAIL_1 = "Je n'ai pas bien compris votre numéro. Pouvez-vous le redire ?"
VOCAL_PHONE_FAIL_2 = (
    "Dites-le comme ceci : zéro six, douze, trente-quatre, cinquante-six, soixante-dix-huit."
)
VOCAL_PHONE_FAIL_3 = "Je n'arrive pas à noter votre numéro. Pouvez-vous me donner un email ?"

VOCAL_PHONE_CONFIRM = "Votre numéro est bien le {phone_spaced} ?"
VOCAL_PHONE_CONFIRM_NO = "D'accord. Quel est votre numéro ?"

VOCAL_PREF_ASK = "Vous préférez le matin ou l'après-midi ?"
VOCAL_PREF_FAIL_1 = "Préférez-vous avant midi ou plutôt après midi ?"
VOCAL_PREF_FAIL_2 = "Répondez simplement : matin ou après-midi."
VOCAL_PREF_ANY = "Très bien. Je propose le matin. Ça vous va ?"
VOCAL_PREF_ANY_NO = "D'accord. Alors plutôt l'après-midi ?"
# Confirmation après inférence ("vers 14h" → afternoon)
VOCAL_PREF_CONFIRM_MATIN = "D'accord, plutôt le matin. C'est bien ça ?"
VOCAL_PREF_CONFIRM_APRES_MIDI = "D'accord, plutôt l'après-midi. C'est bien ça ?"
# PREF_FAIL_3 → INTENT_ROUTER (dans engine)

VOCAL_SLOT_FAIL_1 = "Je n'ai pas compris. Dites seulement : un, deux ou trois."
VOCAL_SLOT_FAIL_2 = "Par exemple : 'je prends le deux'. Alors ?"
# SLOT_FAIL_3 → INTENT_ROUTER (dans engine)

# Recovery nom (QUALIF_NAME — test B1)
VOCAL_NAME_ASK = "Très bien. C'est à quel nom ?"
VOCAL_NAME_FAIL_1 = "Je n'ai pas bien noté votre nom. Pouvez-vous répéter ?"
VOCAL_NAME_FAIL_2 = "Votre nom et prénom, par exemple : Martin Dupont."
# NAME_FAIL_3 → INTENT_ROUTER (réutiliser VOCAL_INTENT_ROUTER)

# ----------------------------
# IVR Principe 2 — Clarifications guidées (jamais bloquer sec)
# ----------------------------

class ClarificationMessages:
    """
    Messages de clarification guidée (jamais "Je n'ai pas compris" seul).
    fail_count 1 = premier essai, 2 = deuxième, 3 = transfert si None.
    """
    SLOT_CHOICE_UNCLEAR = {
        1: VOCAL_SLOT_FAIL_1,
        2: VOCAL_SLOT_FAIL_2,
    }
    PREFERENCE_UNCLEAR = {
        1: VOCAL_PREF_FAIL_1,
        2: VOCAL_PREF_FAIL_2,
    }
    # Recovery nom (test B1) : 2 reformulations, puis NAME_FAIL_3 → INTENT_ROUTER dans engine
    NAME_UNCLEAR = {
        1: VOCAL_NAME_FAIL_1,
        2: VOCAL_NAME_FAIL_2,
    }
    PHONE_UNCLEAR = {
        1: VOCAL_PHONE_FAIL_1,
        2: VOCAL_PHONE_FAIL_2,
        3: VOCAL_PHONE_FAIL_3,
    }
    CANCEL_CONFIRM_UNCLEAR = {
        1: "Voulez-vous annuler ce rendez-vous ? Répondez oui ou non.",
        2: "Pour annuler, dites oui. Pour garder le rendez-vous, dites non.",
    }
    MODIFY_CONFIRM_UNCLEAR = {
        1: "Voulez-vous déplacer ce rendez-vous ? Répondez oui ou non.",
        2: "Pour déplacer, dites oui. Pour garder la date, dites non.",
    }


def get_clarification_message(
    context: str,
    fail_count: int,
    user_input: str = "",
    channel: str = "vocal",
) -> str:
    """
    Retourne une clarification guidée (jamais un blocage sec).
    
    Args:
        context: 'slot_choice' | 'preference' | 'name' | 'phone' | 'cancel_confirm' | 'modify_confirm'
        fail_count: Nombre d'échecs (1, 2, 3...)
        user_input: Message utilisateur (pour personnaliser)
        channel: 'vocal' | 'web'
    
    Returns:
        Message de clarification guidée
    """
    messages_map = {
        "slot_choice": ClarificationMessages.SLOT_CHOICE_UNCLEAR,
        "preference": ClarificationMessages.PREFERENCE_UNCLEAR,
        "name": ClarificationMessages.NAME_UNCLEAR,
        "phone": ClarificationMessages.PHONE_UNCLEAR,
        "cancel_confirm": ClarificationMessages.CANCEL_CONFIRM_UNCLEAR,
        "modify_confirm": ClarificationMessages.MODIFY_CONFIRM_UNCLEAR,
    }
    messages = messages_map.get(context, {})
    user_input_safe = (user_input or "").strip()[:50]
    if not user_input_safe:
        user_input_safe = "ça"
    template = messages.get(min(fail_count, len(messages)))
    if not template:
        return "Je vais vous mettre en relation. Un instant."
    if "{user_input}" in template:
        return template.format(user_input=user_input_safe)
    return template


# V3.1 — Confidence hint empathique après inférence
INFERENCE_CONFIRM_TEMPLATES = {
    "après-midi": "D'après ce que vous me dites, je comprends plutôt l'après-midi. C'est bien ça ?",
    "matin": "Si je comprends bien, vous préférez le matin. C'est correct ?",
    "soir": "Vous préférez donc en soirée, si je comprends bien ?",
}


def format_inference_confirmation(inferred_value: str) -> str:
    """
    Formulation empathique avec confidence hint (addendum V3.1).
    """
    return INFERENCE_CONFIRM_TEMPLATES.get(
        inferred_value,
        f"D'accord, donc plutôt {inferred_value}, c'est bien ça ?",
    )


# V3.1 — Mots-signaux de transition (structure mentale vocale)
class TransitionSignals:
    """Mots-signaux pour structurer la conversation vocale."""
    VALIDATION = "Parfait."
    PROGRESSION = "Très bien."
    AGREEMENT = "D'accord."
    PROCESSING = "Je regarde."
    RESULT = "Voilà."

    @staticmethod
    def wrap_with_signal(message: str, signal_type: str = "PROGRESSION") -> str:
        """Ajoute un mot-signal en début de message (un seul par message)."""
        signal = getattr(TransitionSignals, signal_type, "")
        if not signal or not message:
            return message
        if message.startswith(signal):
            return message
        # Éviter doublon "Très bien." + "Très bien X." (ex: après confirmation du nom)
        if signal == TransitionSignals.PROGRESSION and message.strip().lower().startswith("très bien"):
            return message
        return f"{signal} {message}"


# ----------------------------
# FLOW F: TRANSFER - Transfert humain
# ----------------------------

VOCAL_TRANSFER_COMPLEX = (
    "Je comprends. Je vais vous mettre en relation avec quelqu'un "
    "qui pourra mieux vous aider. Un instant."
)

VOCAL_TRANSFER_CALLBACK = (
    "Vous pouvez rappeler au {phone_number} aux horaires d'ouverture. "
    "Bonne journée !"
)


# ----------------------------
# Cas EDGE
# ----------------------------

VOCAL_NO_SLOTS_MORNING = (
    "Désolé, rien de disponible le matin cette semaine. "
    "L'après-midi ça vous va ?"
)

VOCAL_NO_SLOTS_AFTERNOON = (
    "Désolé, rien de disponible l'après-midi non plus. "
    "Je note votre demande. Votre numéro ?"
)

VOCAL_WAITLIST_ADDED = (
    "C'est noté. On vous rappelle dès qu'un créneau se libère. "
    "Bonne journée !"
)

VOCAL_USER_ABANDON = "Pas de problème ! N'hésitez pas à rappeler. Bonne journée !"

VOCAL_TAKE_TIME = "Prenez votre temps, je vous écoute."

VOCAL_INSULT_RESPONSE = (
    "Je comprends que vous soyez frustré. "
    "Comment puis-je vous aider ?"
)

# Motif invalide - aide
VOCAL_MOTIF_HELP = (
    "Désolé, j'ai pas bien compris. "
    "C'est plutôt pour un contrôle, une consultation, ou autre chose ?"
)

# Contact
VOCAL_CONTACT_ASK = (
    "Pour confirmer tout ça, vous préférez qu'on vous rappelle "
    "ou qu'on vous envoie un email ?"
)

VOCAL_CONTACT_EMAIL = (
    "D'accord. Dictez-moi votre email, tranquillement. "
    "Genre : jean point dupont arobase gmail point com."
)

VOCAL_CONTACT_PHONE = (
    "Parfait. C'est quoi votre numéro ? "
    "Allez-y doucement, je note."
)

VOCAL_CONTACT_RETRY = (
    "Excusez-moi, je n'ai pas bien noté. "
    "Pouvez-vous me donner votre numéro complet, chiffre par chiffre ?"
)

# Créneaux
VOCAL_CONFIRM_SLOTS = (
    "Alors, j'ai trois créneaux pour vous. "
    "Dites-moi juste : un, deux ou trois. "
    "Le un, c'est {slot1}. Le deux, {slot2}. Et le trois, {slot3}."
)

VOCAL_BOOKING_CONFIRMED = (
    "C'est noté pour {slot_label}. "
    "On vous attend, à bientôt !"
)

# Transitions naturelles
VOCAL_ACK_POSITIVE = [
    "D'accord.",
    "Très bien.",
    "Parfait.",
    "OK.",
    "Entendu.",
]

VOCAL_ACK_UNDERSTANDING = [
    "Je comprends.",
    "Je vois.",
    "Ah oui, d'accord.",
]

# Fillers naturels (utilisés avant les réponses longues)
VOCAL_FILLERS = [
    "Alors,",
    "Bon,",
    "Donc,",
    "Eh bien,",
]

# Erreurs et incompréhension - ton décontracté
VOCAL_NOT_UNDERSTOOD = (
    "Pardon, j'ai pas bien compris. Vous pouvez répéter ?"
)

VOCAL_TRANSFER_HUMAN = (
    "Bon, je vais vous passer quelqu'un qui pourra mieux vous aider. "
    "Un instant."
)

VOCAL_NO_SLOTS = (
    "Ah mince, on n'a plus de créneaux disponibles là. "
    "Je vous passe quelqu'un pour trouver une solution."
)

VOCAL_GOODBYE = "Au revoir, bonne journée !"

VOCAL_GOODBYE_AFTER_BOOKING = "Merci et à très bientôt !"

# ============================================
# CONTACT (Vocal)
# ============================================

MSG_CONTACT_ASK_VOCAL = (
    "Pour vous recontacter, quel est votre téléphone ou votre email ? "
    "Vous pouvez le dicter."
)

MSG_CONTACT_RETRY_VOCAL = (
    "Excusez-moi, je n'ai pas bien noté. "
    "Pouvez-vous me redonner votre numéro de téléphone ?"
)

# Confirmation du numéro (VOCAL_PHONE_CONFIRM / VOCAL_PHONE_CONFIRM_NO en Recovery ci-dessus)
VOCAL_CONTACT_CONFIRM = (
    "J'ai noté le {phone_formatted}. C'est bien ça ?"
)
VOCAL_CONTACT_CONFIRM_OK = "Parfait, c'est noté."
VOCAL_CONTACT_CONFIRM_RETRY = "D'accord, pouvez-vous me redonner votre numéro ?"


def format_phone_for_voice(phone: str) -> str:
    """
    Formate un numéro de téléphone pour lecture vocale.
    Ex: "0612345678" → "06, 12, 34, 56, 78"
    """
    # Nettoyer le numéro
    digits = ''.join(c for c in phone if c.isdigit())
    
    # Si numéro français (10 chiffres)
    if len(digits) == 10:
        # Format: 06 12 34 56 78
        return f"{digits[0:2]}, {digits[2:4]}, {digits[4:6]}, {digits[6:8]}, {digits[8:10]}"
    
    # Format international ou autre
    if len(digits) > 10:
        # +33 6 12 34 56 78 → grouper par 2
        formatted = []
        for i in range(0, len(digits), 2):
            formatted.append(digits[i:i+2])
        return ", ".join(formatted)
    
    # Fallback: lire chiffre par chiffre
    return ", ".join(list(digits))

# ----------------------------
# VALIDATION MOTIFS
# ----------------------------

# Motifs VALIDES avec leurs variantes
VALID_MOTIFS = {
    "consultation": ["consultation", "consulter", "voir le docteur", "rendez-vous"],
    "contrôle": ["controle", "contrôle", "check-up", "bilan", "suivi"],
    "renouvellement": ["renouvellement", "renouveler", "ordonnance", "prescription"],
    "douleur": ["douleur", "mal", "souffre", "j'ai mal", "dos", "tête", "ventre", "genou"],
    "vaccination": ["vaccin", "vaccination", "rappel"],
    "bilan": ["bilan", "analyses", "prise de sang", "bilan sanguin"],
    "urgence": ["urgence", "urgent", "vite", "rapide"],
    "résultats": ["résultats", "resultat", "analyses"],
}

# Motifs trop génériques (pas d'info utile)
# Note: "consultation", "contrôle", etc. sont des motifs VALIDES, ne pas les mettre ici
GENERIC_MOTIFS = {
    "rdv", "rendez-vous", "rendez vous", "rendezvous",
    "prendre un rdv", "rendez-vous médical",
    "voir le médecin", "un rendez vous",
    "je veux un rdv", "prendre rendez-vous",
}


# ----------------------------
# INTENT DETECTION KEYWORDS
# ----------------------------

# Réponses OUI
YES_PATTERNS = [
    "oui", "ouais", "yes", "yep", "ok", "d'accord",
    "exactement", "tout à fait", "absolument", "bien sûr",
    "s'il vous plaît", "oui s'il vous plaît", "oui svp",
    "c'est ça", "voilà", "affirmatif",
]

# Réponses NON
NO_PATTERNS = [
    "non", "nan", "no", "pas du tout", "pas vraiment",
    "non merci", "non non",
]

# Intent CANCEL
CANCEL_PATTERNS = [
    "annuler", "annulation", "supprimer",
    "je veux annuler", "annuler mon rendez-vous",
    "annuler mon rdv", "annule mon rdv",
]

# Intent MODIFY
MODIFY_PATTERNS = [
    "modifier", "changer", "déplacer", "reporter",
    "changer mon rendez-vous", "déplacer mon rdv",
    "reporter mon rdv", "modifier mon rdv",
]

# Intent TRANSFER (cas complexes)
TRANSFER_PATTERNS = [
    "parler à quelqu'un", "un humain", "un conseiller",
    "quelqu'un", "standard", "secrétariat",
    "mes résultats", "résultats d'analyses",
    "c'est urgent", "c'est grave",
    "je veux parler", "passez-moi quelqu'un",
]

# Intent ORDONNANCE (conversation naturelle : RDV ou message)
ORDONNANCE_PATTERNS = [
    "ordonnance", "ordonnances",
    "renouvellement", "renouveler",
    "prescription", "prescrip",
    "médicament", "médicaments",
    "traitement",
]

# Intent ABANDON (override → END_POLITE)
ABANDON_PATTERNS = [
    "je rappelle", "laissez tomber", "tant pis",
    "oubliez", "je vais rappeler", "plus tard",
    "j'abandonne", "je rappellerai", "je vais raccrocher",
]
# Message de clôture poli (spec END_POLITE)
MSG_END_POLITE_ABANDON = "Pas de souci. N'hésitez pas à nous rappeler. Au revoir."

# Slot choice patterns (pour WAIT_CONFIRM)
SLOT_CHOICE_FIRST = ["premier", "un", "1", "le premier", "le un"]
SLOT_CHOICE_SECOND = ["deuxième", "deux", "2", "le deuxième", "le deux", "second"]
SLOT_CHOICE_THIRD = ["troisième", "trois", "3", "le troisième", "le trois"]

# Jour patterns
DAY_PATTERNS = {
    "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3,
    "vendredi": 4, "samedi": 5, "dimanche": 6,
}

MSG_MOTIF_HELP = (
    "Merci. Pouvez-vous préciser en 1 phrase ?\n"
    "Ex : renouvellement ordonnance, douleur, bilan, visiteur médical."
)

# Messages de redirection lors de qualification (si booking intent répété)
# Web
MSG_QUALIF_NAME_RETRY = "Merci de me donner votre nom et prénom pour continuer."
MSG_QUALIF_MOTIF_RETRY = "Merci de me donner le motif de votre demande pour continuer."
MSG_QUALIF_PREF_RETRY = "Merci de me donner votre créneau préféré pour continuer."
MSG_QUALIF_CONTACT_RETRY = "Merci de me donner votre email ou téléphone pour continuer."

# Vocal - ton naturel
MSG_QUALIF_NAME_RETRY_VOCAL = "Juste avant, c'est à quel nom ?"
MSG_QUALIF_MOTIF_RETRY_VOCAL = "Attendez, c'est pour quoi exactement ?"
MSG_QUALIF_PREF_RETRY_VOCAL = "Vous préférez plutôt quel moment de la journée ?"
MSG_QUALIF_CONTACT_RETRY_VOCAL = "Pour vous rappeler, c'est quoi le mieux ? Téléphone ou email ?"

def get_qualif_retry(field: str, channel: str = "web") -> str:
    """
    Retourne le message de retry de qualification adapté au canal.
    """
    vocal_retries = {
        "name": MSG_QUALIF_NAME_RETRY_VOCAL,
        "motif": MSG_QUALIF_MOTIF_RETRY_VOCAL,
        "pref": MSG_QUALIF_PREF_RETRY_VOCAL,
        "contact": MSG_QUALIF_CONTACT_RETRY_VOCAL,
    }
    web_retries = {
        "name": MSG_QUALIF_NAME_RETRY,
        "motif": MSG_QUALIF_MOTIF_RETRY,
        "pref": MSG_QUALIF_PREF_RETRY,
        "contact": MSG_QUALIF_CONTACT_RETRY,
    }
    retries = vocal_retries if channel == "vocal" else web_retries
    return retries.get(field, "")

# Booking
MSG_NO_SLOTS_AVAILABLE = "Désolé, nous n'avons plus de créneaux disponibles. Je vous mets en relation avec un humain."
MSG_SLOT_ALREADY_BOOKED = "Désolé, ce créneau vient d'être pris. Je vous mets en relation avec un humain."

# Vapi fallbacks
MSG_VAPI_NO_UNDERSTANDING = "Je n'ai pas bien compris. Pouvez-vous répéter ?"
MSG_VAPI_ERROR = "Désolé, une erreur s'est produite. Je vous transfère."

# Terminal / clôture
MSG_CONVERSATION_CLOSED = (
    "C'est terminé pour cette demande. "
    "Si vous avez un nouveau besoin, ouvrez une nouvelle conversation ou parlez à un humain."
)

# Clarification (web) — doc SCRIPT_CONVERSATION_AGENT
MSG_CLARIFY_WEB = "D'accord. Vous avez une question ou vous souhaitez prendre rendez-vous ?"
MSG_CLARIFY_WEB_START = "D'accord. Vous avez une question ou un autre besoin ?"

# Abandon / FAQ goodbye (web)
MSG_ABANDON_WEB = "Pas de problème. Bonne journée !"
MSG_FAQ_GOODBYE_WEB = "Parfait, bonne journée !"

# FAQ no match : reformulation puis menu (1er → reformulation, 2e → INTENT_ROUTER)
MSG_FAQ_NO_MATCH_FIRST = "Je n'ai pas cette information. Souhaitez-vous prendre un rendez-vous ?"
MSG_FAQ_REFORMULATE = "Je n'ai pas bien compris votre question. Pouvez-vous la reformuler ?"
MSG_FAQ_REFORMULATE_VOCAL = "J'ai pas bien saisi. Vous pouvez reformuler votre question ?"
# Retry 2 : donner exemples (horaires, tarifs, localisation)
MSG_FAQ_RETRY_EXEMPLES = (
    "Je peux répondre à des questions sur nos horaires, tarifs, ou localisation. "
    "Posez votre question simplement."
)
MSG_FAQ_RETRY_EXEMPLES_VOCAL = (
    "Je peux répondre sur les horaires, les tarifs, ou où on se trouve. "
    "Posez votre question simplement."
)

# Cancel / Modify (web fallbacks)
MSG_CANCEL_ASK_NAME_WEB = "Pas de problème. C'est à quel nom ?"
MSG_CANCEL_NAME_RETRY_1_WEB = "Je n'ai pas noté votre nom. Répétez ?"

# Flow ORDONNANCE (conversation naturelle : RDV ou message, pas menu 1/2)
VOCAL_ORDONNANCE_ASK_CHOICE = (
    "Pour une ordonnance, vous voulez un rendez-vous ou que l'on transmette un message ?"
)
MSG_ORDONNANCE_ASK_CHOICE_WEB = (
    "Pour une ordonnance, souhaitez-vous un rendez-vous ou que l'on transmette un message ?"
)
VOCAL_ORDONNANCE_CHOICE_RETRY_1 = "Je n'ai pas compris. Vous préférez un rendez-vous ou un message ?"
VOCAL_ORDONNANCE_CHOICE_RETRY_2 = "Dites simplement : rendez-vous ou message."
VOCAL_ORDONNANCE_ASK_NAME = "D'accord. C'est à quel nom ?"
MSG_ORDONNANCE_ASK_NAME_WEB = "D'accord. C'est à quel nom ?"
VOCAL_ORDONNANCE_NAME_RETRY_1 = "Je n'ai pas noté votre nom. Répétez ?"
VOCAL_ORDONNANCE_NAME_RETRY_2 = "Votre nom et prénom, s'il vous plaît."
VOCAL_ORDONNANCE_PHONE_ASK = "Quel est votre numéro de téléphone ?"
VOCAL_ORDONNANCE_DONE = (
    "Parfait. Votre demande d'ordonnance est enregistrée. On vous rappelle rapidement. Au revoir !"
)
MSG_ORDONNANCE_DONE_WEB = (
    "Votre demande d'ordonnance est enregistrée. Nous vous rappellerons rapidement. Au revoir."
)
MSG_CANCEL_NAME_RETRY_2_WEB = "Votre nom et prénom. Par exemple : Martin Dupont."
MSG_MODIFY_ASK_NAME_WEB = "Pas de souci. C'est à quel nom ?"
MSG_MODIFY_NAME_RETRY_1_WEB = "Je n'ai pas noté votre nom. Répétez ?"
MSG_MODIFY_NAME_RETRY_2_WEB = "Votre nom et prénom. Par exemple : Martin Dupont."
MSG_CANCEL_NOT_FOUND_WEB = "Je n'ai pas trouvé de rendez-vous à ce nom. Pouvez-vous me redonner votre nom complet ?"
MSG_MODIFY_NOT_FOUND_VERIFIER_HUMAN_WEB = (
    "Je ne trouve pas de rendez-vous au nom de {name}. "
    "Voulez-vous vérifier l'orthographe ou parler à quelqu'un ? Dites : vérifier ou humain."
)
MSG_CANCEL_NOT_FOUND_VERIFIER_HUMAN_WEB = (
    "Je ne trouve pas de rendez-vous au nom de {name}. "
    "Voulez-vous vérifier l'orthographe ou parler à quelqu'un ? Dites : vérifier ou humain."
)
MSG_CANCEL_DONE_WEB = "C'est fait, votre rendez-vous est annulé. Bonne journée !"
MSG_CANCEL_KEPT_WEB = "Pas de souci, votre rendez-vous est maintenu. Bonne journée !"
MSG_MODIFY_NOT_FOUND_WEB = "Je n'ai pas trouvé de rendez-vous à ce nom. Pouvez-vous me redonner votre nom complet ?"
MSG_MODIFY_CONFIRM_WEB = "Vous avez un rendez-vous {slot_label}. Voulez-vous le déplacer ?"
MSG_CANCEL_CONFIRM_WEB = "Vous avez un rendez-vous {slot_label}. Voulez-vous l'annuler ?"
MSG_FAQ_TO_BOOKING_WEB = "Pas de souci. C'est à quel nom ?"
MSG_MODIFY_CANCELLED_WEB = "J'ai annulé l'ancien. Plutôt le matin ou l'après-midi pour le nouveau ?"


# ----------------------------
# Fonctions d'adaptation canal
# ----------------------------

def get_message(msg_key: str, channel: str = "web", **kwargs) -> str:
    """
    Retourne le message adapté au canal (web ou vocal).
    
    Usage:
        get_message("transfer", channel="vocal")
        get_message("no_slots", channel="vocal")
        get_message("salutation", channel="vocal", business_name="Cabinet Durand")
    """
    # Mapping des messages vocaux (ton parisien naturel)
    vocal_messages = {
        "transfer": VOCAL_TRANSFER_HUMAN,
        "no_slots": VOCAL_NO_SLOTS,
        "not_understood": VOCAL_NOT_UNDERSTOOD,
        "goodbye": VOCAL_GOODBYE,
        "goodbye_booking": VOCAL_GOODBYE_AFTER_BOOKING,
        "contact_ask": VOCAL_CONTACT_ASK,
        "contact_email": VOCAL_CONTACT_EMAIL,
        "contact_phone": VOCAL_CONTACT_PHONE,
        "contact_retry": VOCAL_CONTACT_RETRY,
        "booking_confirmed": VOCAL_BOOKING_CONFIRMED,
        "salutation": VOCAL_SALUTATION,
    }
    
    # Mapping des messages web (format texte standard)
    web_messages = {
        "transfer": MSG_TRANSFER,
        "no_slots": MSG_NO_SLOTS_AVAILABLE,
        "not_understood": MSG_VAPI_NO_UNDERSTANDING,
        "goodbye": MSG_CONVERSATION_CLOSED,
        "goodbye_booking": MSG_CONVERSATION_CLOSED,
        "contact_ask": MSG_CONTACT_HINT,
        "contact_email": MSG_CONTACT_CHOICE_ACK_EMAIL,
        "contact_phone": MSG_CONTACT_CHOICE_ACK_PHONE,
        "contact_retry": MSG_CONTACT_RETRY,
        "booking_confirmed": "Votre rendez-vous est confirmé pour {slot_label}.",
        "salutation": "Bonjour ! Comment puis-je vous aider ?",
    }
    
    messages = vocal_messages if channel == "vocal" else web_messages
    msg = messages.get(msg_key, "")
    
    # Format avec les kwargs si fournis
    if kwargs and msg:
        try:
            msg = msg.format(**kwargs)
        except KeyError:
            pass  # Ignore missing keys
    
    return msg


# ----------------------------
# Qualification (questions exactes, ordre strict)
# ----------------------------

QUALIF_QUESTIONS_ORDER: List[str] = ["name", "motif", "pref", "contact"]

# Questions Web (format texte)
QUALIF_QUESTIONS: Dict[str, str] = {
    "name": "Quel est votre nom et prénom ?",
    "motif": "Pour quel sujet ? (ex : renouvellement, douleur, bilan, visiteur médical)",
    "pref": "Quel créneau préférez-vous ? (ex : lundi matin, mardi après-midi)",
    "contact": "Quel est votre moyen de contact ? (email ou téléphone)",
}

# Questions Vocal - ton chaleureux et naturel, phrases courtes pour TTS
# SANS question motif (supprimée - inutile pour médecin)
QUALIF_QUESTIONS_VOCAL: Dict[str, str] = {
    "name": VOCAL_NAME_ASK,
    "motif": "",  # DÉSACTIVÉ - on ne demande plus le motif
    "pref": "Super. Vous préférez plutôt le matin ou l'après-midi ?",
    "contact": "Parfait ! Et votre numéro de téléphone pour vous rappeler ?",
}

# Questions avec nom inclus (après avoir reçu le nom)
def get_qualif_question_with_name(field: str, name: str, channel: str = "web") -> str:
    """
    Retourne la question de qualification avec le nom du client (ton chaleureux).
    Ex: "Super Jean ! Plutôt le matin ou l'après-midi ?"
    """
    if channel != "vocal" or not name:
        return get_qualif_question(field, channel)
    
    # Extraire le prénom
    first_name = name.split()[0] if name else ""
    
    vocal_questions_with_name = {
        "motif": "",  # DÉSACTIVÉ
        "pref": f"Très bien {first_name}. Vous préférez plutôt le matin ou l'après-midi ?",
        "contact": f"Parfait. Et votre numéro de téléphone pour vous rappeler ?",
    }
    
    return vocal_questions_with_name.get(field, get_qualif_question(field, channel))

def get_qualif_question(field: str, channel: str = "web") -> str:
    """
    Retourne la question de qualification adaptée au canal.
    """
    if channel == "vocal":
        return QUALIF_QUESTIONS_VOCAL.get(field, QUALIF_QUESTIONS.get(field, ""))
    return QUALIF_QUESTIONS.get(field, "")


# ----------------------------
# Patterns de confirmation booking
# ----------------------------

BOOKING_CONFIRM_ACCEPTED_PATTERNS = [
    r"^oui\s*[123]$",
    r"^[123]$",
]

BOOKING_CONFIRM_PATTERNS_COMPILED = [
    re.compile(r"^oui\s*[123]$", re.IGNORECASE),
    re.compile(r"^[123]$"),
]

def is_valid_booking_confirm(text: str) -> bool:
    text = text.strip()
    return any(p.match(text) for p in BOOKING_CONFIRM_PATTERNS_COMPILED)


# ----------------------------
# Format FAQ (traçabilité)
# ----------------------------

def format_faq_response(answer: str, faq_id: str, channel: str = "web") -> str:
    """
    Formate une réponse FAQ avec traçabilité.
    
    En mode vocal, on n'ajoute PAS la source (pas naturel à l'oral).

    Raises:
        ValueError: si answer est vide
    """
    if not answer or not answer.strip():
        raise ValueError("FAQ answer cannot be empty")
    
    # Vocal : pas de "Source: XXX" (pas naturel à dire)
    if channel == "vocal":
        return answer
    
    return f"{answer}\n\nSource : {faq_id}"


# ----------------------------
# Slots display + confirmation (booking)
# ----------------------------

@dataclass(frozen=True)
class SlotDisplay:
    idx: int
    label: str  # ex: "Mardi 15/01 - 14:00"
    slot_id: int
    # IVR pro : choix flexible par jour/heure ("celui de mardi", "vers 10h")
    start: str = ""       # ISO datetime
    day: str = ""         # "lundi", "mardi", ...
    hour: int = 0         # 0-23
    label_vocal: str = "" # ex: "lundi à 10h"

def format_slot_proposal(slots: List[SlotDisplay], include_instruction: bool = True, channel: str = "web") -> str:
    """
    Formate la proposition de créneaux.
    
    Args:
        slots: Liste des créneaux à proposer
        include_instruction: Si True, ajoute l'instruction de confirmation
        channel: "web" ou "vocal" - utilisé pour choisir le bon message d'instruction
    """
    if channel == "vocal":
        # Format vocal - naturel pour TTS
        return format_slot_proposal_vocal(slots)
    
    # Format web - liste structurée
    lines = ["Créneaux disponibles :"]
    for s in slots:
        lines.append(f"{s.idx}. {s.label}")
    
    if include_instruction:
        lines.append("")
        lines.append(MSG_CONFIRM_INSTRUCTION_WEB)
    
    return "\n".join(lines)


def format_slot_proposal_vocal(slots: List[SlotDisplay]) -> str:
    """
    Formate la proposition de créneaux pour le vocal.
    Ton chaleureux et clair, avec pauses pour le TTS.
    """
    if len(slots) == 1:
        return (
            f"J'ai un créneau disponible : {slots[0].label}. "
            "Est-ce que ça vous convient ?"
        )
    elif len(slots) == 2:
        return (
            f"J'ai deux créneaux. "
            f"Un : {slots[0].label}. "
            f"Deux : {slots[1].label}. "
            "Dites un ou deux."
        )
    else:
        # 3 créneaux (cas standard)
        return (
            f"J'ai trois créneaux. "
            f"Un : {slots[0].label}. "
            f"Deux : {slots[1].label}. "
            f"Trois : {slots[2].label}. "
            "Dites un, deux ou trois."
        )

def format_booking_confirmed(slot_label: str, name: str = "", motif: str = "", channel: str = "web") -> str:
    """
    Formate la confirmation de RDV avec récapitulatif.
    SANS fausse promesse (pas d'email en V1).
    """
    if channel == "vocal":
        # Format vocal - court et naturel
        return format_booking_confirmed_vocal(slot_label, name)
    
    # Format web - structuré avec emojis
    parts = [
        "Parfait ! Votre rendez-vous est confirmé.",
        "",
        f"📅 Date et heure : {slot_label}",
    ]
    
    if name:
        parts.append(f"👤 Nom : {name}")
    
    if motif:
        parts.append(f"📋 Motif : {motif}")
    
    parts.extend([
        "",
        "À bientôt !",
    ])
    
    return "\n".join(parts)


def format_booking_confirmed_vocal(slot_label: str, name: str = "") -> str:
    """
    Confirmation de RDV pour le vocal.
    Ton professionnel et rassurant.
    """
    if name:
        # Extraire le prénom
        first_name = name.split()[0] if name else ""
        return (
            f"Parfait. Votre rendez-vous est confirmé pour {slot_label}. "
            "Vous recevrez un SMS de rappel. "
            f"À bientôt {first_name} !"
        )
    return (
        f"Parfait. Votre rendez-vous est confirmé pour {slot_label}. "
        "Vous recevrez un SMS de rappel. "
        "À bientôt !"
    )
