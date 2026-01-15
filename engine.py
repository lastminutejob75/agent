# backend/engine.py
"""
Pipeline déterministe : edge-cases → session → FAQ → booking/qualif → transfer
Aucune créativité, aucune improvisation.
"""

from __future__ import annotations
from typing import List, Optional
from dataclasses import dataclass
import re

from backend import config, prompts, guards, tools_booking
from backend.session import Session, SessionStore
from backend.tools_faq import FaqStore, FaqResult


@dataclass(frozen=True)
class Event:
    """Événement à envoyer au client (SSE)"""
    type: str  # "partial" | "final" | "transfer" | "error"
    text: str
    conv_state: Optional[str] = None
    transfer_reason: Optional[str] = None
    silent: bool = False


# ========================
# DÉTECTION INTENT BOOKING
# ========================

def _detect_booking_intent(text: str) -> bool:
    """Détecte si le message exprime une intention de RDV"""
    text_lower = text.lower()
    
    # Normaliser les espaces/tirets
    text_normalized = text_lower.replace("-", " ").replace("_", " ")
    
    # Keywords avec variantes
    keywords = [
        "rdv",
        "rendez vous",  # Après normalisation, "rendez-vous" devient "rendez vous"
        "rendezvous",
        "dispo",
        "disponibilité",
        "créneau",
        "réserver",
        "réservation",
        "prendre",
    ]
    
    # Patterns plus flexibles
    booking_phrases = [
        "veux un rendez",
        "veux un rdv",
        "prendre rendez",
        "prendre un rendez",
        "besoin d'un rendez",
        "avoir un rendez",
    ]
    
    # Check keywords
    if any(kw in text_normalized for kw in keywords):
        return True
    
    # Check phrases
    if any(phrase in text_normalized for phrase in booking_phrases):
        return True
    
    return False


# ========================
# DÉTECTION "MOTIF = INTENTION RDV"
# ========================

_MOTIF_INTENT_KEYWORDS = [
    "rdv",
    "rendez-vous",
    "rendez vous",
    "rendezvous",
    "appointment",
]


def _looks_like_booking_intent(text: str) -> bool:
    """
    Détecte si un texte ressemble à une intention de booking plutôt qu'à un motif réel.
    Utilisé pour valider les motifs lors de la qualification.
    """
    t = text.strip().lower()
    if not t:
        return True
    
    # Si c'est très court + keywords => quasi sûr que c'est l'intention, pas le motif
    if len(t) <= 32 and any(k in t for k in _MOTIF_INTENT_KEYWORDS):
        return True
    
    # Si la phrase contient explicitement "je veux un rdv" / "je voudrais un rdv"
    if re.search(r"\b(je\s+veux|je\s+voudrais)\b.*\b(rdv|rendez)\b", t):
        return True
    
    return False


# ========================
# ENGINE
# ========================

class Engine:
    """
    Moteur de conversation déterministe.
    Applique strictement le PRD + SYSTEM_PROMPT.
    """
    
    def __init__(self, session_store: SessionStore, faq_store: FaqStore):
        self.session_store = session_store
        self.faq_store = faq_store
    
    def handle_message(self, conv_id: str, user_text: str) -> List[Event]:
        """
        Pipeline déterministe (ordre STRICT).
        
        Returns:
            Liste d'events à envoyer via SSE
        """
        session = self.session_store.get_or_create(conv_id)
        session.add_message("user", user_text)
        
        # ========================
        # TERMINAL GATE (mourir proprement)
        # ========================
        # Si la conversation est déjà terminée, on ne relance pas de flow.
        if session.state in ["CONFIRMED", "TRANSFERRED"]:
            # Option V1 la plus safe : message de clôture (pas de nouveau traitement)
            msg = prompts.MSG_CONVERSATION_CLOSED
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        # ========================
        # 1. EDGE-CASE GATE (HARD STOPS)
        # ========================
        
        # Message vide ou trop long
        is_valid, error_msg = guards.validate_length(user_text)
        if not is_valid:
            session.add_message("agent", error_msg)
            return [Event("final", error_msg, conv_state=session.state)]
        
        # Langue non française
        if not guards.detect_language_fr(user_text):
            msg = prompts.MSG_FRENCH_ONLY
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        # Spam/abuse → transfer silencieux
        if guards.is_spam_or_abuse(user_text):
            session.state = "TRANSFERRED"
            return [Event("transfer", "", transfer_reason="spam", silent=True)]
        
        # ========================
        # 2. SESSION GATE
        # ========================
        
        if session.is_expired():
            session.reset()
            msg = prompts.MSG_SESSION_EXPIRED
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state="START")]
        
        # ========================
        # 3. ROUTING : FAQ vs BOOKING vs EN COURS
        # ========================
        
        # Si en cours de qualification → continuer le flow
        if session.state in ["QUALIF_NAME", "QUALIF_MOTIF", "QUALIF_PREF", "QUALIF_CONTACT"]:
            return self._handle_qualification(session, user_text)
        
        # Si en aide contact → gérer guidance
        if session.state == "AIDE_CONTACT":
            return self._handle_aide_contact(session, user_text)
        
        # Si en attente de confirmation → valider
        if session.state == "WAIT_CONFIRM":
            return self._handle_booking_confirm(session, user_text)
        
        # Si START → déterminer FAQ ou Booking
        if session.state == "START":
            # 1) Booking intent détecté → démarrer qualification
            if _detect_booking_intent(user_text):
                session.state = "QUALIF_NAME"
                question = prompts.QUALIF_QUESTIONS["name"]
                session.add_message("agent", question)
                return [Event("final", question, conv_state=session.state)]
            
            # 2) Sinon → chercher FAQ (inclut low pour "bonjour" seul)
            return self._handle_faq(session, user_text, include_low=True)
        
        # Si FAQ_ANSWERED → permettre nouvelle interaction
        if session.state == "FAQ_ANSWERED":
            # Reset à START pour nouvelle interaction
            session.state = "START"
            # Relancer le routing
            if _detect_booking_intent(user_text):
                session.state = "QUALIF_NAME"
                question = prompts.QUALIF_QUESTIONS["name"]
                session.add_message("agent", question)
                return [Event("final", question, conv_state=session.state)]
            return self._handle_faq(session, user_text, include_low=True)
        
        # ========================
        # 5. FALLBACK TRANSFER
        # ========================
        
        # Si état inconnu ou non géré → transfer par sécurité
        session.state = "TRANSFERRED"
        msg = prompts.MSG_TRANSFER
        session.add_message("agent", msg)
        return [Event("final", msg, conv_state=session.state)]
    
    # ========================
    # HANDLERS
    # ========================
    
    def _handle_faq(self, session: Session, user_text: str, include_low: bool = True) -> List[Event]:
        """
        Cherche dans FAQ.
        
        Args:
            include_low: Si False, exclut les FAQs priority="low"
        """
        faq_result = self.faq_store.search(user_text, include_low=include_low)

        if faq_result.match:
            response = prompts.format_faq_response(faq_result.answer, faq_result.faq_id)
            session.state = "FAQ_ANSWERED"
            session.add_message("agent", response)
            return [Event("final", response, conv_state=session.state)]

        session.no_match_turns += 1

        if session.no_match_turns >= 2:
            session.state = "TRANSFERRED"
            msg = prompts.MSG_TRANSFER
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]

        msg = prompts.msg_no_match_faq(config.BUSINESS_NAME)
        session.add_message("agent", msg)
        return [Event("final", msg, conv_state=session.state)]
    
    def _handle_qualification(self, session: Session, user_text: str) -> List[Event]:
        """
        Gère le flow de qualification (4 questions).
        AVEC validation des réponses et clarifications.
        """
        current_step = session.state
        
        # ========================
        # QUALIF_NAME
        # ========================
        if current_step == "QUALIF_NAME":
            # Vérifier que ce n'est pas une répétition de la demande booking
            if _detect_booking_intent(user_text):
                msg = "Merci de me donner votre nom et prénom pour continuer."
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # Vérifier longueur minimale (un nom fait au moins 2 caractères)
            if len(user_text.strip()) < 2:
                session.state = "TRANSFERRED"
                msg = prompts.MSG_TRANSFER
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # Réponse valide → continuer
            session.qualif_data.name = user_text.strip()
            session.state = "QUALIF_MOTIF"
            question = prompts.QUALIF_QUESTIONS["motif"]
            session.add_message("agent", question)
            return [Event("final", question, conv_state=session.state)]
        
        # ========================
        # QUALIF_MOTIF
        # ========================
        elif current_step == "QUALIF_MOTIF":
            # Vérifier répétition booking intent
            if _detect_booking_intent(user_text):
                # Vérifier AVANT d'incrémenter pour permettre 1 retry
                if session.confirm_retry_count >= config.CONFIRM_RETRY_MAX:
                    session.state = "TRANSFERRED"
                    msg = prompts.MSG_TRANSFER
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]
                
                session.confirm_retry_count += 1
                msg = "Merci de me donner le motif de votre demande pour continuer."
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # NOUVEAU : Vérifier si motif générique
            if guards.is_generic_motif(user_text):
                # Vérifier AVANT d'incrémenter pour permettre 1 retry
                if session.confirm_retry_count >= config.CONFIRM_RETRY_MAX:
                    session.state = "TRANSFERRED"
                    msg = prompts.MSG_TRANSFER
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]
                
                # 1ère fois générique → aide
                session.confirm_retry_count += 1
                msg = prompts.MSG_MOTIF_HELP
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # Reset compteur si motif valide
            session.confirm_retry_count = 0
            
            # Validation PRD
            if not guards.validate_qualif_motif(user_text):
                session.state = "TRANSFERRED"
                msg = prompts.MSG_TRANSFER
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # Motif valide et utile → continuer
            session.qualif_data.motif = user_text.strip()
            session.state = "QUALIF_PREF"
            question = prompts.QUALIF_QUESTIONS["pref"]
            session.add_message("agent", question)
            return [Event("final", question, conv_state=session.state)]
        
        # ========================
        # QUALIF_PREF
        # ========================
        elif current_step == "QUALIF_PREF":
            # Vérifier que ce n'est pas une répétition
            if _detect_booking_intent(user_text):
                msg = "Merci de me donner votre créneau préféré pour continuer."
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # Pas de validation stricte sur le créneau (V1)
            # On accepte la réponse telle quelle
            session.qualif_data.pref = user_text.strip()
            session.state = "QUALIF_CONTACT"
            
            # ✅ Question adaptée au canal
            channel = getattr(session, "channel", "web")
            
            if channel == "vocal":
                question = prompts.MSG_CONTACT_ASK_VOCAL
            else:
                question = prompts.QUALIF_QUESTIONS["contact"]
            
            session.add_message("agent", question)
            return [Event("final", question, conv_state=session.state)]
        
        # ========================
        # QUALIF_CONTACT
        # ========================
        elif current_step == "QUALIF_CONTACT":
            channel = getattr(session, "channel", "web")
            contact_raw = user_text.strip()

            # Vérifier répétition booking intent
            if _detect_booking_intent(contact_raw):
                session.confirm_retry_count += 1
                
                if session.confirm_retry_count >= config.CONFIRM_RETRY_MAX:
                    session.state = "TRANSFERRED"
                    msg = prompts.MSG_TRANSFER
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]
                
                msg = "Merci de me donner votre email ou téléphone pour continuer."
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # ✅ Parsing email dicté (vocal)
            if channel == "vocal" and guards.looks_like_dictated_email(contact_raw):
                contact_raw = guards.parse_vocal_email_min(contact_raw)

            # Validation
            is_valid, contact_type = guards.validate_qualif_contact(contact_raw)

            if not is_valid:
                # Retry 1 fois (vocal) puis transfert
                if channel == "vocal" and session.contact_retry_count < 1:
                    session.contact_retry_count += 1
                    msg = prompts.MSG_CONTACT_RETRY_VOCAL
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]

                # Transfer
                session.state = "TRANSFERRED"
                msg = prompts.MSG_TRANSFER
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]

            # ✅ Valide
            session.qualif_data.contact = contact_raw
            session.qualif_data.contact_type = contact_type
            session.contact_retry_count = 0

            return self._propose_slots(session)
        
        # ========================
        # FALLBACK (état inconnu)
        # ========================
        # Si aucun des états précédents n'a matché, transfert
        session.state = "TRANSFERRED"
        msg = prompts.MSG_TRANSFER
        session.add_message("agent", msg)
        return [Event("final", msg, conv_state=session.state)]
    
    def _handle_aide_contact(self, session: Session, user_text: str) -> List[Event]:
        """
        État de guidance contact.
        Règle: 1 retry maximum, puis transfert (optionnel), mais jamais dès la 1ère erreur.
        """
        text = user_text.strip()
        
        is_valid, contact_type = guards.validate_qualif_contact(text)
        if is_valid:
            session.qualif_data.contact = text
            session.qualif_data.contact_type = contact_type
            session.contact_retry_count = 0
            session.state = "QUALIF_CONTACT"  # Retour à l'état normal avant de proposer slots
            return self._propose_slots(session)
        
        session.contact_retry_count += 1
        
        if session.contact_retry_count >= 2:
            # Option 1 (recommandée): transfert après 2 échecs réels
            session.state = "TRANSFERRED"
            msg = prompts.MSG_CONTACT_FAIL_TRANSFER
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        # Retry (1 fois)
        msg = prompts.MSG_CONTACT_RETRY
        session.add_message("agent", msg)
        return [Event("final", msg, conv_state=session.state)]
    
    def _propose_slots(self, session: Session) -> List[Event]:
        """
        Propose 3 créneaux disponibles.
        """
        
        # Récupérer slots
        slots = tools_booking.get_slots_for_display(limit=config.MAX_SLOTS_PROPOSED)
        
        if not slots:
            session.state = "TRANSFERRED"
            msg = "Désolé, nous n'avons plus de créneaux disponibles. Je vous mets en relation avec un humain."
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        # Stocker slots
        tools_booking.store_pending_slots(session, slots)
        session.state = "WAIT_CONFIRM"
        
        # Formatter message
        msg = prompts.format_slot_proposal(slots)
        session.add_message("agent", msg)
        
        # ✅ NOUVEAU : Instruction vocale après slots
        channel = getattr(session, "channel", "web")
        
        if channel == "vocal":
            instruction = prompts.MSG_CONFIRM_INSTRUCTION_VOCAL
            session.add_message("agent", instruction)
            return [
                Event("final", msg, conv_state=session.state),
                Event("final", instruction, conv_state=session.state),
            ]
        
        return [Event("final", msg, conv_state=session.state)]
    
    def _handle_booking_confirm(self, session: Session, user_text: str) -> List[Event]:
        """
        Gère confirmation RDV (WAIT_CONFIRM).
        """
        
        # ✅ Validation avec channel
        channel = getattr(session, "channel", "web")
        is_valid, slot_idx = guards.validate_booking_confirm(user_text, channel=channel)

        if is_valid:
            # Booker
            success = tools_booking.book_slot_from_session(session, slot_idx)

            if not success:
                session.state = "TRANSFERRED"
                msg = (
                    "Désolé, ce créneau vient d'être pris. "
                    "Je vous mets en relation avec un humain."
                )
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]

            # Confirmer
            slot_label = tools_booking.get_label_for_choice(session, slot_idx) or ""
            name = session.qualif_data.name or ""
            motif = session.qualif_data.motif or ""
            msg = prompts.format_booking_confirmed(slot_label, name=name, motif=motif)
            
            session.state = "CONFIRMED"
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]

        # ❌ Invalide → retry
        session.confirm_retry_count += 1

        if session.confirm_retry_count >= config.CONFIRM_RETRY_MAX:
            session.state = "TRANSFERRED"
            msg = prompts.MSG_TRANSFER
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        # ✅ Message retry adapté au canal
        msg = prompts.MSG_CONFIRM_RETRY_VOCAL if channel == "vocal" else prompts.MSG_CONFIRM_INSTRUCTION_WEB
        session.add_message("agent", msg)
        return [Event("final", msg, conv_state=session.state)]


# ========================
# FACTORY
# ========================

def create_engine() -> Engine:
    """Factory pour créer l'engine avec ses dépendances"""
    from backend.tools_faq import default_faq_store
    
    session_store = SessionStore()
    faq_store = default_faq_store()
    
    return Engine(session_store=session_store, faq_store=faq_store)


# Engine singleton (exporté pour vapi.py)
ENGINE = create_engine()
