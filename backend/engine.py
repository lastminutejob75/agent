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
from backend.entity_extraction import extract_entities, get_next_missing_field


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
                return self._start_booking_with_extraction(session, user_text)
            
            # 2) Sinon → chercher FAQ (inclut low pour "bonjour" seul)
            return self._handle_faq(session, user_text, include_low=True)
        
        # Si FAQ_ANSWERED → permettre nouvelle interaction
        if session.state == "FAQ_ANSWERED":
            # Reset à START pour nouvelle interaction
            session.state = "START"
            # Relancer le routing
            if _detect_booking_intent(user_text):
                return self._start_booking_with_extraction(session, user_text)
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
        channel = getattr(session, "channel", "web")
        faq_result = self.faq_store.search(user_text, include_low=include_low)

        if faq_result.match:
            response = prompts.format_faq_response(faq_result.answer, faq_result.faq_id, channel=channel)
            session.state = "FAQ_ANSWERED"
            session.add_message("agent", response)
            return [Event("final", response, conv_state=session.state)]

        session.no_match_turns += 1

        if session.no_match_turns >= 2:
            session.state = "TRANSFERRED"
            msg = prompts.get_message("transfer", channel=channel)
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]

        msg = prompts.msg_no_match_faq(config.BUSINESS_NAME, channel=channel)
        session.add_message("agent", msg)
        return [Event("final", msg, conv_state=session.state)]
    
    def _start_booking_with_extraction(self, session: Session, user_text: str) -> List[Event]:
        """
        Démarre le flow de booking avec extraction d'entités.
        
        Extrait nom, motif, préférence du premier message si présents,
        puis pose seulement les questions manquantes.
        """
        channel = getattr(session, "channel", "web")
        
        # Extraction conservatrice
        entities = extract_entities(user_text)
        
        # Pré-remplir les champs extraits
        if entities.name:
            session.qualif_data.name = entities.name
            session.extracted_name = True  # Flag pour confirmation implicite
        
        if entities.motif:
            session.qualif_data.motif = entities.motif
            session.extracted_motif = True
        
        if entities.pref:
            session.qualif_data.pref = entities.pref
            session.extracted_pref = True
        
        # Construire le contexte pour trouver le prochain champ manquant
        context = {
            "name": session.qualif_data.name,
            "motif": session.qualif_data.motif,
            "pref": session.qualif_data.pref,
            "contact": session.qualif_data.contact,
        }
        
        next_field = get_next_missing_field(context)
        
        if not next_field:
            # Tout est rempli (rare mais possible) → proposer créneaux
            return self._propose_slots(session)
        
        # Mapper le champ vers l'état
        state_map = {
            "name": "QUALIF_NAME",
            "motif": "QUALIF_MOTIF",
            "pref": "QUALIF_PREF",
            "contact": "QUALIF_CONTACT",
        }
        session.state = state_map[next_field]
        
        # Construire la réponse avec confirmation implicite si extraction
        response_parts = []
        
        # Confirmation implicite des entités extraites
        if entities.has_any():
            if entities.name and entities.motif:
                response_parts.append(f"Parfait {entities.name}, pour {entities.motif}.")
            elif entities.name:
                response_parts.append(f"Très bien {entities.name}.")
            elif entities.motif:
                response_parts.append(f"D'accord, pour {entities.motif}.")
            else:
                response_parts.append("Très bien.")
        
        # Question suivante
        question = prompts.get_qualif_question(next_field, channel=channel)
        response_parts.append(question)
        
        response = " ".join(response_parts)
        session.add_message("agent", response)
        
        return [Event("final", response, conv_state=session.state)]
    
    def _next_qualif_step(self, session: Session) -> List[Event]:
        """
        Détermine et pose la prochaine question de qualification.
        Skip automatiquement les champs déjà remplis (par extraction ou réponse précédente).
        """
        channel = getattr(session, "channel", "web")
        
        # Construire le contexte actuel
        context = {
            "name": session.qualif_data.name,
            "motif": session.qualif_data.motif,
            "pref": session.qualif_data.pref,
            "contact": session.qualif_data.contact,
        }
        
        # DEBUG: Log context
        print(f"🔍 _next_qualif_step: context={context}")
        
        next_field = get_next_missing_field(context)
        print(f"🔍 _next_qualif_step: next_field={next_field}")
        
        if not next_field:
            # Tout est rempli → proposer créneaux
            print(f"🔍 _next_qualif_step: ALL FILLED → propose_slots")
            return self._propose_slots(session)
        
        # Mapper le champ vers l'état
        state_map = {
            "name": "QUALIF_NAME",
            "motif": "QUALIF_MOTIF",
            "pref": "QUALIF_PREF",
            "contact": "QUALIF_CONTACT",
        }
        session.state = state_map[next_field]
        
        # Question adaptée au canal
        question = prompts.get_qualif_question(next_field, channel=channel)
        print(f"🔍 _next_qualif_step: asking for {next_field} → '{question}'")
        session.add_message("agent", question)
        
        return [Event("final", question, conv_state=session.state)]
    
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
            channel = getattr(session, "channel", "web")
            
            # Vérifier que ce n'est pas une répétition de la demande booking
            if _detect_booking_intent(user_text):
                msg = prompts.get_qualif_retry("name", channel=channel)
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # Vérifier longueur minimale (un nom fait au moins 2 caractères)
            if len(user_text.strip()) < 2:
                session.state = "TRANSFERRED"
                msg = prompts.get_message("transfer", channel=channel)
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # Réponse valide → trouver le prochain champ manquant
            session.qualif_data.name = user_text.strip()
            return self._next_qualif_step(session)
        
        # ========================
        # QUALIF_MOTIF
        # ========================
        elif current_step == "QUALIF_MOTIF":
            channel = getattr(session, "channel", "web")
            
            # Vérifier répétition booking intent
            if _detect_booking_intent(user_text):
                # Vérifier AVANT d'incrémenter pour permettre 1 retry
                if session.confirm_retry_count >= config.CONFIRM_RETRY_MAX:
                    session.state = "TRANSFERRED"
                    msg = prompts.get_message("transfer", channel=channel)
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]
                
                session.confirm_retry_count += 1
                msg = prompts.get_qualif_retry("motif", channel=channel)
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # NOUVEAU : Vérifier si motif générique
            if guards.is_generic_motif(user_text):
                # Vérifier AVANT d'incrémenter pour permettre 1 retry
                if session.confirm_retry_count >= config.CONFIRM_RETRY_MAX:
                    session.state = "TRANSFERRED"
                    msg = prompts.get_message("transfer", channel=channel)
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
                msg = prompts.get_message("transfer", channel=channel)
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # Motif valide et utile → trouver le prochain champ manquant
            session.qualif_data.motif = user_text.strip()
            return self._next_qualif_step(session)
        
        # ========================
        # QUALIF_PREF
        # ========================
        elif current_step == "QUALIF_PREF":
            channel = getattr(session, "channel", "web")
            
            # Vérifier que ce n'est pas une répétition
            if _detect_booking_intent(user_text):
                msg = prompts.get_qualif_retry("pref", channel=channel)
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # Pas de validation stricte sur le créneau (V1)
            # On accepte la réponse telle quelle
            session.qualif_data.pref = user_text.strip()
            return self._next_qualif_step(session)
        
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
                    msg = prompts.get_message("transfer", channel=channel)
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]
                
                msg = prompts.get_qualif_retry("contact", channel=channel)
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
                    msg = prompts.get_message("contact_retry", channel=channel)
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]

                # Transfer
                session.state = "TRANSFERRED"
                msg = prompts.get_message("transfer", channel=channel)
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
        channel = getattr(session, "channel", "web")
        session.state = "TRANSFERRED"
        msg = prompts.get_message("transfer", channel=channel)
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
        import time
        t_start = time.time()
        
        channel = getattr(session, "channel", "web")
        print(f"🔍 _propose_slots: fetching slots...")
        
        try:
            # Récupérer slots
            slots = tools_booking.get_slots_for_display(limit=config.MAX_SLOTS_PROPOSED)
            print(f"🔍 _propose_slots: got {len(slots) if slots else 0} slots in {(time.time() - t_start) * 1000:.0f}ms")
        except Exception as e:
            print(f"❌ _propose_slots ERROR: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: transfert
            session.state = "TRANSFERRED"
            msg = prompts.get_message("transfer", channel=channel)
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        if not slots:
            print(f"⚠️ _propose_slots: NO SLOTS AVAILABLE")
            session.state = "TRANSFERRED"
            msg = prompts.get_message("no_slots", channel=channel)
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        # Stocker slots
        tools_booking.store_pending_slots(session, slots)
        session.state = "WAIT_CONFIRM"
        
        # Formatter message avec instruction adaptée au channel
        msg = prompts.format_slot_proposal(slots, include_instruction=True, channel=channel)
        print(f"✅ _propose_slots: proposing {len(slots)} slots")
        session.add_message("agent", msg)
        
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
                msg = prompts.MSG_SLOT_ALREADY_BOOKED
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]

            # Confirmer avec message adapté au canal
            slot_label = tools_booking.get_label_for_choice(session, slot_idx) or ""
            name = session.qualif_data.name or ""
            motif = session.qualif_data.motif or ""
            msg = prompts.format_booking_confirmed(slot_label, name=name, motif=motif, channel=channel)
            
            session.state = "CONFIRMED"
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]

        # ❌ Invalide → retry
        session.confirm_retry_count += 1

        if session.confirm_retry_count >= config.CONFIRM_RETRY_MAX:
            session.state = "TRANSFERRED"
            msg = prompts.get_message("transfer", channel=channel)
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
