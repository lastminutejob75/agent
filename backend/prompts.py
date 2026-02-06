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


# --- Silence vocal (RÈGLE 3) — ton bienveillant, phrases courtes TTS ---
MSG_SILENCE_1 = (
    "Excusez-moi. Je ne vous ai pas entendu. "
    "Pouvez-vous répéter, s'il vous plaît ?"
)
MSG_SILENCE_2 = (
    "Je vous écoute. "
    "Allez-y, je suis là."
)

# --- Bruit STT (nova-2-phonecall : confidence faible, pas de vrai silence) ---
MSG_NOISE_1 = "Excusez-moi. Je vous entends mal. Pouvez-vous répéter, s'il vous plaît ?"
MSG_NOISE_2 = "Il y a du bruit sur la ligne. Rapprochez-vous du téléphone et répétez, s'il vous plaît."

# --- Custom LLM (chat/completions) : texte incompréhensible / garbage ---
MSG_UNCLEAR_1 = "Excusez-moi. Je n'ai pas bien compris. Pouvez-vous répéter, s'il vous plaît ?"

# --- Crosstalk (barge-in) : user parle pendant TTS → no-op sans incrémenter unclear ---
MSG_VOCAL_CROSSTALK_ACK = "Je vous écoute."
# --- Overlap : UNCLEAR juste après réponse agent → pas d'incrément, demander de répéter ---
MSG_OVERLAP_REPEAT = "Je vous ai entendu en même temps. Répétez maintenant, s'il vous plaît."
# --- Semi-sourd : TEXT court pendant que l'agent parle ---
MSG_OVERLAP_REPEAT_SHORT = "Pardon. Répétez, s'il vous plaît."

# --- Contrainte horaire (RÈGLE 7) ---
MSG_TIME_CONSTRAINT_IMPOSSIBLE = (
    "D'accord. Mais nous fermons à {closing}. "
    "Je peux vous proposer un créneau plus tôt, ou je vous mets en relation avec quelqu'un. "
    "Vous préférez : un créneau plus tôt, ou parler à quelqu'un ?"
)

# ----------------------------
# Messages exacts (System Prompt)
# ----------------------------

def msg_no_match_faq(business_name: str, channel: str = "web") -> str:
    """
    Message quand aucune FAQ ne correspond.
    Ton différent selon le canal.
    """
    if channel == "vocal":
        return (
            f"Je ne suis pas certaine de pouvoir répondre à cette question. "
            f"Je peux vous mettre en relation avec {business_name}. Souhaitez-vous que je le fasse ?"
        )
    # Web - format texte standard
    return (
        "Je ne suis pas certain de pouvoir répondre précisément.\n"
        f"Je peux vous mettre en relation avec {business_name}. Souhaitez-vous que je le fasse ?"
    )

MSG_EMPTY_MESSAGE = "Je n'ai pas reçu votre message. Pouvez-vous réessayer ?"
MSG_TOO_LONG = "Votre message est trop long. Pouvez-vous résumer ?"
MSG_FRENCH_ONLY = "Je ne parle actuellement que français."
MSG_SESSION_EXPIRED = "Votre session a expiré. Puis-je vous aider ?"
MSG_TRANSFER = "Je vous transfère vers un conseiller. Ne quittez pas, s'il vous plaît."
MSG_ALREADY_TRANSFERRED = "Vous avez été transféré à un conseiller. Un instant, s'il vous plaît."

# =========================
# MÉDICAL — TRIAGE (urgence vitale + non vital + escalade douce)
# =========================
# Urgence vitale (hard stop, TTS-friendly — calme, non alarmiste, ferme)
VOCAL_MEDICAL_EMERGENCY = (
    "Je suis vraiment désolée, mais je ne peux pas gérer cette situation ici. "
    "Appelez immédiatement le 15 ou le 112, ou faites-vous aider par une personne autour de vous."
)

# Non vital : accueil + proposition RDV
MSG_MEDICAL_NON_URGENT_ACK = (
    "D'accord. Je note pour le médecin : {motif}. "
    "Si les symptômes s'aggravent ou vous inquiètent, contactez un professionnel de santé. "
    "Je vous propose un rendez-vous : plutôt le matin ou l'après-midi ?"
)

# Inquiétude / escalade douce
MSG_MEDICAL_CAUTION = (
    "Merci. Je note votre demande. "
    "Je ne peux pas évaluer la gravité à distance. "
    "Si vous avez un doute ou si ça s'aggrave, appelez le 15 ou le 112. "
    "Sinon, je vous propose un rendez-vous : matin ou après-midi ?"
)

# Booking
# Instruction confirmation (Web - legacy)
MSG_CONFIRM_INSTRUCTION = "Répondez par 'oui 1', 'oui 2' ou 'oui 3' pour confirmer."

# Instruction confirmation (Vocal) — ton invitant, phrases courtes TTS
MSG_CONFIRM_INSTRUCTION_VOCAL = (
    "Quel créneau préférez-vous ? "
    "Dites un, deux ou trois."
)

# Instruction confirmation (Web)
MSG_CONFIRM_INSTRUCTION_WEB = (
    "Répondez par 'oui 1', 'oui 2' ou 'oui 3' pour confirmer."
)

MSG_CONFIRM_RETRY_VOCAL = (
    "Excusez-moi. Dites simplement : un, deux ou trois, s'il vous plaît."
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

# Salutation d'accueil (ton chaleureux, pas sec)
VOCAL_SALUTATION = (
    "Bonjour, vous êtes bien chez {business_name}. Comment puis-je vous aider ?"
)

# Fallback si besoin
VOCAL_SALUTATION_NEUTRAL = (
    "Bonjour, bienvenue chez {business_name}. Je vous écoute."
)

VOCAL_SALUTATION_LONG = (
    "Bonjour, vous êtes bien chez {business_name}. "
    "Je suis là pour vous aider. Que souhaitez-vous faire ?"
)

VOCAL_SALUTATION_SHORT = "Bonjour, je vous écoute."

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

VOCAL_FAQ_FOLLOWUP = (
    "Souhaitez-vous autre chose ?"
)

VOCAL_FAQ_GOODBYE = "Très bien. Merci de votre appel. Bonne journée."

VOCAL_FAQ_TO_BOOKING = "Très bien. Pour le rendez-vous, à quel nom, s'il vous plaît ?"

# POST_FAQ : "oui" ambigu → une seule question de choix (A3)
VOCAL_POST_FAQ_CHOICE = (
    "Très bien. Souhaitez-vous prendre un rendez-vous, ou poser une autre question ?"
)
VOCAL_POST_FAQ_CHOICE_RETRY = "Dites : rendez-vous, ou : question."

# POST_FAQ - Disambiguation "oui" seul (vocal + web)
VOCAL_POST_FAQ_DISAMBIG = (
    "D'accord. Souhaitez-vous prendre rendez-vous, "
    "ou avez-vous une autre question ?"
)
MSG_POST_FAQ_DISAMBIG_WEB = (
    "Que puis-je faire pour vous ?\n\n"
    "• Prendre rendez-vous\n"
    "• Poser une question"
)


# ----------------------------
# FLOW C: CANCEL - Annulation de RDV
# ----------------------------

VOCAL_CANCEL_ASK_NAME = "Bien sûr. À quel nom est le rendez-vous, s'il vous plaît ?"
# Message envoyé immédiatement en vocal pendant la recherche du RDV (évite le "mmm" TTS)
VOCAL_CANCEL_LOOKUP_HOLDING = "Un instant, je cherche votre rendez-vous."

# Recovery progressive : nom pas compris (CANCEL_NAME)
VOCAL_CANCEL_NAME_RETRY_1 = "Excusez-moi. Je n'ai pas noté votre nom. Pouvez-vous répéter, s'il vous plaît ?"
VOCAL_CANCEL_NAME_RETRY_2 = "Votre nom et prénom. Par exemple : Martin Dupont."

VOCAL_CANCEL_NOT_FOUND = (
    "Je ne trouve pas de rendez-vous à ce nom. "
    "Pouvez-vous vérifier l'orthographe, s'il vous plaît ?"
)

# RDV non trouvé : proposer vérifier ou humain (pas transfert direct)
VOCAL_CANCEL_NOT_FOUND_VERIFIER_HUMAN = (
    "Je ne trouve pas de rendez-vous au nom de {name}. "
    "Souhaitez-vous vérifier l'orthographe, ou parler à un conseiller ? "
    "Dites : vérifier, ou : conseiller."
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
    "Très bien. Votre rendez-vous est maintenu. "
    "Bonne journée."
)

# --- CANCEL (robustesse prod) ---
# Si l'annulation échoue techniquement (pas d'event_id, erreur tool, etc.)
CANCEL_FAILED_TRANSFER = (
    "Je n'arrive pas à annuler automatiquement. Je vous mets en relation avec quelqu'un. Un instant."
)

# Si on détecte que le RDV vient d'une source non annulable (ex: SQLite sans event_id)
CANCEL_NOT_SUPPORTED_TRANSFER = (
    "Je peux vous aider, mais je ne peux pas annuler automatiquement dans ce système. "
    "Je vous mets en relation avec quelqu'un. Un instant."
)


# ----------------------------
# FLOW D: MODIFY - Modification de RDV
# ----------------------------

VOCAL_MODIFY_ASK_NAME = "Très bien. À quel nom est le rendez-vous, s'il vous plaît ?"

# Recovery progressive : nom pas compris (MODIFY_NAME)
VOCAL_MODIFY_NAME_RETRY_1 = "Excusez-moi. Je n'ai pas noté votre nom. Pouvez-vous répéter, s'il vous plaît ?"
VOCAL_MODIFY_NAME_RETRY_2 = "Votre nom et prénom. Par exemple : Martin Dupont."

VOCAL_MODIFY_NOT_FOUND = (
    "Je n'ai pas trouvé de rendez-vous à ce nom. "
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
    "Très bien, j'ai annulé l'ancien. Plutôt le matin ou l'après-midi pour le nouveau ?"
)


# ----------------------------
# FLOW E: UNCLEAR - Cas flou
# ----------------------------

VOCAL_CLARIFY = (
    "Pas de souci ! Je peux vous renseigner si vous avez une question, "
    "ou vous aider à prendre un rendez-vous. Qu'est-ce qui vous ferait plaisir ?"
)

VOCAL_STILL_UNCLEAR = (
    "D'accord. Je vous mets en relation avec un conseiller. Un instant, s'il vous plaît."
)

# ----------------------------
# INTENT_ROUTER (spec V3 — menu reset universel)
# ----------------------------

VOCAL_INTENT_ROUTER = (
    "Je vous écoute. "
    "Dites un pour prendre rendez-vous. "
    "Dites deux pour annuler ou modifier. "
    "Dites trois pour poser une question. "
    "Ou dites quatre pour parler à un conseiller."
)
# Échec 3 nom (test B1) : même menu avec intro stabilisante
VOCAL_NAME_FAIL_3_INTENT_ROUTER = (
    "Je vais simplifier. Dites un pour rendez-vous. Dites deux pour annuler ou modifier. Dites trois pour une question. Ou dites quatre pour un conseiller."
)

MSG_INTENT_ROUTER = (
    "Je vais simplifier. Dites : un, pour prendre un rendez-vous ; "
    "deux, pour annuler ou modifier ; trois, pour poser une question ; "
    "quatre, pour parler à quelqu'un. Dites simplement : un, deux, trois ou quatre."
)

MSG_INTENT_ROUTER_FAQ = "Quelle est votre question ?"

MSG_INTENT_ROUTER_RETRY = (
    "Vous pouvez simplement dire : un, deux, trois ou quatre, s'il vous plaît."
)

MSG_PREFERENCE_CONFIRM = "D'accord, donc plutôt {pref}, c'est bien ça ?"

# ----------------------------
# Recovery téléphone / préférence / créneau (VOCAL_* — cohérence B2/B3)
# ----------------------------

VOCAL_PHONE_FAIL_1 = "Excusez-moi. Je n'ai pas bien noté votre numéro. Pouvez-vous le redire, s'il vous plaît ?"
VOCAL_PHONE_FAIL_2 = (
    "Dites-le comme ceci : zéro six, douze, trente-quatre, cinquante-six, soixante-dix-huit."
)
VOCAL_PHONE_FAIL_3 = "Je n'arrive pas à noter votre numéro. Pouvez-vous me donner votre email, s'il vous plaît ?"

VOCAL_PHONE_CONFIRM = "Je confirme : {phone_spaced}. C'est bien ça ?"
VOCAL_PHONE_CONFIRM_NO = "D'accord. Quel est votre numéro ?"

VOCAL_PREF_ASK = (
    "Préférez-vous un rendez-vous le matin "
    "ou l'après-midi ?"
)
VOCAL_PREF_FAIL_1 = "Je vous écoute. Plutôt le matin, ou l'après-midi ?"
VOCAL_PREF_FAIL_2 = (
    "Dites simplement. "
    "Le matin. "
    "Ou l'après-midi."
)
VOCAL_PREF_ANY = "Très bien. Je propose le matin. Ça vous va ?"
VOCAL_PREF_ANY_NO = "D'accord. Plutôt l'après-midi ?"
# Confirmation après inférence ("vers 14h" → afternoon)
VOCAL_PREF_CONFIRM_MATIN = "D'accord, plutôt le matin. C'est bien ça ?"
VOCAL_PREF_CONFIRM_APRES_MIDI = "D'accord, plutôt l'après-midi. C'est bien ça ?"
# PREF_FAIL_3 → INTENT_ROUTER (dans engine)

VOCAL_SLOT_FAIL_1 = "Je n'ai pas bien saisi. Vous pouvez dire : un, deux ou trois, s'il vous plaît."
VOCAL_SLOT_FAIL_2 = "Par exemple : je prends le deux. Lequel vous convient ?"
# SLOT_FAIL_3 → INTENT_ROUTER (dans engine)

# Recovery nom (QUALIF_NAME — test B1)
VOCAL_NAME_ASK = (
    "Très bien. "
    "À quel nom, s'il vous plaît ?"
)
VOCAL_NAME_FAIL_1 = "Excusez-moi. Je n'ai pas bien saisi votre nom. Pouvez-vous répéter, s'il vous plaît ?"
VOCAL_NAME_FAIL_2 = "Votre nom et prénom. Par exemple : Martin Dupont."
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
    RESULT = "Très bien."

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
    "Je comprends. Je vous mets en relation avec un conseiller qui pourra mieux vous aider. Un instant, s'il vous plaît."
)

VOCAL_TRANSFER_CALLBACK = (
    "Vous pouvez rappeler au {phone_number} aux horaires d'ouverture. "
    "Bonne journée !"
)


# ----------------------------
# Cas EDGE
# ----------------------------

VOCAL_NO_SLOTS_MORNING = (
    "Je suis désolée. Je n'ai plus de créneaux le matin cette semaine. "
    "L'après-midi vous conviendrait-il ?"
)

VOCAL_NO_SLOTS_AFTERNOON = (
    "Je suis désolée. Je n'ai plus de créneaux l'après-midi non plus. "
    "Je peux noter votre demande. Quel est votre numéro, s'il vous plaît ?"
)

VOCAL_WAITLIST_ADDED = (
    "C'est noté. On vous rappelle dès qu'un créneau se libère. "
    "Bonne journée !"
)

VOCAL_USER_ABANDON = "Pas de souci. N'hésitez pas à nous recontacter si besoin. Bonne journée."

VOCAL_TAKE_TIME = "Prenez votre temps, je vous écoute."

VOCAL_INSULT_RESPONSE = (
    "Je comprends que vous soyez frustré. "
    "Comment puis-je vous aider ?"
)

# Motif invalide - aide
VOCAL_MOTIF_HELP = (
    "Désolé, je n'ai pas bien compris. "
    "C'est plutôt pour un contrôle, une consultation, ou autre chose ?"
)

# Contact
VOCAL_CONTACT_ASK = (
    "Parfait. Pour finaliser, préférez-vous le téléphone, ou l'email ?"
)

VOCAL_CONTACT_EMAIL = (
    "Très bien. Pouvez-vous m'épeler votre email ? "
    "Par exemple : jean point dupont arobase gmail point com."
)

VOCAL_CONTACT_PHONE = (
    "Très bien. Quel est votre numéro de téléphone ? "
    "Prenez votre temps, je note. "
    "Par exemple : zéro six, douze, trente-quatre, cinquante-six, soixante-dix-huit."
)

VOCAL_CONTACT_RETRY = (
    "Excusez-moi. Je n'ai pas bien noté. "
    "Pouvez-vous le redonner, chiffre par chiffre, s'il vous plaît ?"
)

# Créneaux
VOCAL_CONFIRM_SLOTS = (
    "Très bien. Voici trois créneaux.\n"
    "Un : {slot1}. Deux : {slot2}. Trois : {slot3}.\n"
    "Dites simplement : un, deux, ou trois."
)

VOCAL_BOOKING_CONFIRMED = (
    "C'est parfait. Votre rendez-vous est confirmé pour {slot_label}. "
    "Vous recevrez un SMS de rappel. "
    "À très bientôt."
)

# Transitions TTS-friendly (mini-bibliothèque : répondent à une action du client)
# À utiliser après validation d'étape / préférence / correction, pas en flottant.
VOCAL_ACK_POSITIVE = [
    "Très bien.",
    "D'accord.",
    "Parfait.",
]

VOCAL_ACK_UNDERSTANDING = [
    "Je comprends.",
    "Je vois.",
]

# Anciens fillers (Alors, Bon, Donc, Eh bien) remplacés par transitions explicites
# pour éviter ton sec / improvisé en TTS. Utiliser VOCAL_ACK_* ou "Pour continuer…".
VOCAL_FILLERS = [
    "Très bien.",
    "D'accord.",
]

# Erreurs et incompréhension — ton doux, pas sec
VOCAL_NOT_UNDERSTOOD = (
    "Excusez-moi, je n'ai pas bien compris. Pouvez-vous reformuler ?"
)

VOCAL_TRANSFER_HUMAN = (
    "Je vous transfère vers un conseiller qui pourra vous aider. "
    "Un instant, s'il vous plaît."
)

VOCAL_NO_SLOTS = (
    "Je suis désolée. Nous n'avons plus de créneaux disponibles. "
    "Je vous mets en relation avec un conseiller."
)

VOCAL_GOODBYE = "Merci de votre appel. Je vous souhaite une excellente journée, au revoir."

VOCAL_GOODBYE_AFTER_BOOKING = "C'est parfait, merci à vous. À très bientôt, bonne journée."

# ============================================
# CONTACT (Vocal)
# ============================================

MSG_CONTACT_ASK_VOCAL = (
    "Pour vous recontacter, j'ai besoin d'un téléphone ou d'un email. "
    "Vous pouvez me le dicter."
)

MSG_CONTACT_RETRY_VOCAL = (
    "Excusez-moi. Je n'ai pas bien noté. "
    "Pouvez-vous me redonner votre numéro de téléphone, s'il vous plaît ?"
)

# Confirmation du numéro (VOCAL_PHONE_CONFIRM / VOCAL_PHONE_CONFIRM_NO en Recovery ci-dessus)
VOCAL_CONTACT_CONFIRM = (
    "J'ai noté le {phone_formatted}. C'est bien ça ?"
)
# P1.3 Vocal : confirmation ultra courte
VOCAL_CONTACT_CONFIRM_SHORT = "Le {phone_formatted}, c'est bien ça ?"
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
MSG_QUALIF_NAME_RETRY_VOCAL = "Très bien. Quel est votre nom et prénom, s'il vous plaît ?"
# P0 : répétition d'intention RDV en QUALIF_NAME → message guidé, sans incrémenter name_fails
MSG_QUALIF_NAME_INTENT_1 = "Très bien. Pour continuer, j'ai besoin de votre nom et prénom, s'il vous plaît."
MSG_QUALIF_NAME_INTENT_2 = "Votre nom et prénom, par exemple : Martin Dupont."
MSG_QUALIF_MOTIF_RETRY_VOCAL = "Attendez, c'est pour quoi exactement ?"
MSG_QUALIF_PREF_RETRY_VOCAL = "Vous préférez plutôt quel moment de la journée ?"
# P0 : répétition d'intention RDV en QUALIF_PREF → message guidé, pas preference_fails
MSG_QUALIF_PREF_INTENT_1 = "D'accord, j'ai bien compris. Vous préférez le matin ou l'après-midi ?"
MSG_QUALIF_PREF_INTENT_2 = "Pour choisir le créneau : dites \"matin\" ou \"après-midi\"."
MSG_QUALIF_CONTACT_RETRY_VOCAL = "Pour vous rappeler, c'est quoi le mieux ? Téléphone ou email ?"
# P0 : répétition d'intention RDV en CONTACT_CONFIRM → message guidé oui/non, pas contact_confirm_fails
MSG_CONTACT_CONFIRM_INTENT_1 = "D'accord. Juste pour confirmer : oui ou non ?"
MSG_CONTACT_CONFIRM_INTENT_2 = "Dites \"oui\" pour confirmer, ou \"non\" pour corriger."
# Optionnel : QUALIF_CONTACT quand l'utilisateur répond par une intention RDV
MSG_QUALIF_CONTACT_INTENT = "D'accord. Pour finaliser, j'ai besoin de votre email ou numéro de téléphone."

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

# Retry booking : créneau pris → reproposer (jusqu'à 2 fois), puis transfert
MSG_SLOT_TAKEN_REPROPOSE = (
    "Ce créneau vient d'être pris. Je vous propose d'autres disponibilités. "
    "Le matin ou l'après-midi ?"
)
MSG_SLOT_TAKEN_TRANSFER = (
    "Je suis désolée, les créneaux changent vite. Je vous mets en relation avec un conseiller."
)
# Early commit (choix anticipé non ambigu) : confirmation avant de passer au contact
MSG_SLOT_EARLY_CONFIRM = "Très bien. Si j'ai bien compris, vous choisissez le créneau {idx} : {label}. C'est bien ça ?"
# P1.3 Vocal : une phrase courte (latence + clarté), ton bienveillant
MSG_SLOT_EARLY_CONFIRM_VOCAL = "Parfait. Le créneau {idx}, {label}. C'est bien ça ?"


def format_slot_early_confirm(idx: int, label: str, channel: str = "web") -> str:
    """Message de confirmation du slot choisi (early commit). P1.3 : version courte en vocal."""
    if channel == "vocal":
        return MSG_SLOT_EARLY_CONFIRM_VOCAL.format(idx=idx, label=label)
    return MSG_SLOT_EARLY_CONFIRM.format(idx=idx, label=label)

# P1.1 Barge-in : user parle pendant énumération créneaux → une phrase courte, pas d'incrément fails
MSG_SLOT_BARGE_IN_HELP = "Pas de souci. Vous pouvez dire : un, deux ou trois, s'il vous plaît."
# Validation vague (oui/ok/d'accord sans choix 1/2/3) en WAIT_CONFIRM → redemander sans pénalité (P0.5, A6)
MSG_WAIT_CONFIRM_NEED_NUMBER = "D'accord. Pour confirmer, dites simplement : un, deux ou trois."


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
# Relance après une réponse FAQ (web) : permettre de poser une autre question ou prendre RDV
MSG_FAQ_FOLLOWUP_WEB = "Souhaitez-vous autre chose ?"

# FAQ no match : reformulation puis menu (1er → reformulation, 2e → INTENT_ROUTER)
MSG_FAQ_NO_MATCH_FIRST = "Je n'ai pas cette information. Souhaitez-vous prendre un rendez-vous ?"
MSG_FAQ_REFORMULATE = "Je n'ai pas bien compris votre question. Pouvez-vous la reformuler ?"
MSG_FAQ_REFORMULATE_VOCAL = "Excusez-moi. Je n'ai pas bien saisi. Pouvez-vous reformuler, s'il vous plaît ?"
# Retry 2 : donner exemples (horaires, tarifs, localisation)
MSG_FAQ_RETRY_EXEMPLES = (
    "Je peux répondre à des questions sur nos horaires, tarifs, ou localisation. "
    "Posez votre question simplement."
)
MSG_FAQ_RETRY_EXEMPLES_VOCAL = (
    "Je peux vous répondre sur les horaires, les tarifs, ou l'adresse. Quelle est votre question ?"
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


# P1.2 Lecture créneaux en 2 messages vocaux (réduit interruptions)
MSG_SLOTS_PREFACE_VOCAL = (
    "Très bien. "
    "Voici les créneaux disponibles."
)


def format_slot_list_vocal_only(slots: List[SlotDisplay]) -> str:
    """Liste des 3 créneaux + instruction (sans preface). P1.2 message 2."""
    if len(slots) < 3:
        return format_slot_proposal_vocal(slots)
    return (
        f"Un : {slots[0].label}. "
        f"Deux : {slots[1].label}. "
        f"Trois : {slots[2].label}. "
        "Vous pouvez dire un, deux ou trois, s'il vous plaît."
    )


def format_slot_proposal_vocal(slots: List[SlotDisplay]) -> str:
    """
    Formate la proposition de créneaux pour le vocal.
    Ton chaleureux et invitant (pas sec), adapté au TTS.
    """
    if len(slots) == 1:
        return (
            f"Je vous propose un créneau : {slots[0].label}. "
            "Est-ce que ça vous convient ?"
        )
    elif len(slots) == 2:
        return (
            f"Je vous propose deux créneaux. "
            f"Un : {slots[0].label}. "
            f"Deux : {slots[1].label}. "
            "Vous pouvez dire un ou deux, s'il vous plaît."
        )
    else:
        # 3 créneaux (cas standard)
        return (
            f"Je vous propose trois créneaux. "
            f"Un : {slots[0].label}. "
            f"Deux : {slots[1].label}. "
            f"Trois : {slots[2].label}. "
            "Vous pouvez dire un, deux ou trois, selon ce qui vous convient."
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
        "Merci. À très bientôt !",
    ])
    
    return "\n".join(parts)


def format_booking_confirmed_vocal(slot_label: str, name: str = "") -> str:
    """
    Confirmation de RDV pour le vocal.
    Ton professionnel et rassurant. Phrases courtes pour TTS (R1).
    """
    if name:
        first_name = name.split()[0] if name else ""
        return (
            "Parfait. "
            f"Votre rendez-vous est confirmé pour {slot_label}. "
            "Vous recevrez un SMS de rappel. "
            f"À très bientôt, {first_name}."
        )
    return (
        "Parfait. "
        f"Votre rendez-vous est confirmé pour {slot_label}. "
        "Vous recevrez un SMS de rappel. "
        "À très bientôt."
    )
