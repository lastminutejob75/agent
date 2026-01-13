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

def msg_no_match_faq(business_name: str) -> str:
    # Formulation EXACTE (pas de variation)
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
# Messages vocaux (V1)
# ----------------------------

VOCAL_CONTACT_ASK = (
    "Pour confirmer le rendez-vous, j'ai besoin d'un moyen de vous recontacter. "
    "Préférez-vous un email ou un téléphone ?"
)

VOCAL_CONTACT_EMAIL = (
    "Très bien. Pouvez-vous me dicter votre email ? "
    "Par exemple : jean point dupont arobase gmail point com."
)

VOCAL_CONTACT_PHONE = (
    "Très bien. Pouvez-vous me donner votre numéro de téléphone ? "
    "Par exemple : zéro six, douze, trente-quatre, cinquante-six, soixante-dix-huit."
)

VOCAL_CONTACT_RETRY = (
    "Je n'ai pas bien compris. "
    "Pouvez-vous me redonner votre email complet, ou bien votre numéro de téléphone ?"
)

VOCAL_CONFIRM_SLOTS = (
    "J'ai trois créneaux. Répondez simplement : un, deux, ou trois.\n"
    "Un : {slot1}. Deux : {slot2}. Trois : {slot3}."
)

VOCAL_BOOKING_CONFIRMED = (
    "Parfait, c'est confirmé pour {slot_label}. "
    "À bientôt."
)

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

# Terminal / clôture
MSG_CONVERSATION_CLOSED = (
    "C'est terminé pour cette demande. "
    "Si vous avez un nouveau besoin, ouvrez une nouvelle conversation ou parlez à un humain."
)


# ----------------------------
# Qualification (questions exactes, ordre strict)
# ----------------------------

QUALIF_QUESTIONS_ORDER: List[str] = ["name", "motif", "pref", "contact"]

QUALIF_QUESTIONS: Dict[str, str] = {
    "name": "Quel est votre nom et prénom ?",
    "motif": "Pour quel sujet ? (ex : renouvellement, douleur, bilan, visiteur médical)",
    "pref": "Quel créneau préférez-vous ? (ex : lundi matin, mardi après-midi)",
    "contact": "Quel est votre moyen de contact ? (email ou téléphone)",
}


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

def format_faq_response(answer: str, faq_id: str) -> str:
    """
    Formate une réponse FAQ avec traçabilité.

    Raises:
        ValueError: si answer est vide
    """
    if not answer or not answer.strip():
        raise ValueError("FAQ answer cannot be empty")
    return f"{answer}\n\nSource : {faq_id}"


# ----------------------------
# Slots display + confirmation (booking)
# ----------------------------

@dataclass(frozen=True)
class SlotDisplay:
    idx: int
    label: str  # ex: "Mardi 15/01 - 14:00"
    slot_id: int

def format_slot_proposal(slots: List[SlotDisplay]) -> str:
    lines = ["Créneaux disponibles :"]
    for s in slots:
        lines.append(f"{s.idx}. {s.label}")
    lines.append("")
    lines.append(MSG_CONFIRM_INSTRUCTION)
    return "\n".join(lines)

def format_booking_confirmed(slot_label: str, name: str = "", motif: str = "") -> str:
    """
    Formate la confirmation de RDV avec récapitulatif.
    SANS fausse promesse (pas d'email en V1).
    """
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
