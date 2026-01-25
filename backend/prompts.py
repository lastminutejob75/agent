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

# Salutation d'accueil (voix Jérémie - accent parisien)
VOCAL_SALUTATION = (
    "Bonjour ! Bienvenue chez {business_name}. "
    "Je suis là pour vous aider. Qu'est-ce que je peux faire pour vous ?"
)

VOCAL_SALUTATION_SHORT = "Oui, je vous écoute ?"

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
    "Pardon, j'ai pas bien capté. "
    "Vous pouvez me redonner votre email ou votre numéro ?"
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
    "Je n'ai pas réussi à noter. "
    "Pouvez-vous redire votre téléphone ou votre email, plus lentement ?"
)

# Motifs trop génériques (pas d'info utile)
GENERIC_MOTIFS = {
    "rdv", "rendez-vous", "rendez vous", "rendezvous",
    "consultation", "prendre un rdv", "rendez-vous médical",
    "voir le médecin", "un rendez vous"
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

# Questions Vocal - ton parisien naturel, phrases courtes pour TTS
QUALIF_QUESTIONS_VOCAL: Dict[str, str] = {
    "name": "C'est à quel nom ?",
    "motif": "Et c'est pour quoi exactement ?",
    "pref": "Vous préférez plutôt le matin ou l'après-midi ?",
    "contact": "Pour vous rappeler, vous préférez qu'on vous envoie un SMS ou un email ?",
}

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
    Ton parisien naturel, phrases courtes pour TTS.
    """
    if len(slots) == 1:
        return (
            f"J'ai un créneau pour vous : {slots[0].label}. "
            "Ça vous convient ?"
        )
    elif len(slots) == 2:
        return (
            f"Alors, j'ai deux créneaux. "
            f"Le premier, c'est {slots[0].label}. "
            f"Le deuxième, {slots[1].label}. "
            "Lequel vous préférez, le un ou le deux ?"
        )
    else:
        # 3 créneaux (cas standard)
        return (
            f"OK, j'ai trois créneaux pour vous. "
            f"Le un, c'est {slots[0].label}. "
            f"Le deux, {slots[1].label}. "
            f"Et le trois, {slots[2].label}. "
            "Dites-moi juste : un, deux ou trois."
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
    Court, naturel, sans emojis.
    """
    if name:
        return (
            f"C'est tout bon {name} ! "
            f"Rendez-vous confirmé pour {slot_label}. "
            "On vous attend, à très bientôt !"
        )
    return (
        f"Parfait, c'est noté ! "
        f"Rendez-vous confirmé pour {slot_label}. "
        "À très bientôt !"
    )
