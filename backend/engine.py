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
from backend.session_store_sqlite import SQLiteSessionStore
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
# DÉTECTION INTENT COMPLET
# ========================

def detect_intent(text: str) -> str:
    """
    Détecte l'intention de l'utilisateur.
    
    Returns:
        str: "YES", "NO", "BOOKING", "FAQ", "CANCEL", "MODIFY", "TRANSFER", "ABANDON", "UNCLEAR"
    """
    t = text.strip().lower()
    if not t:
        return "UNCLEAR"
    
    # 1. Réponses simples OUI/NON (prioritaire pour le first message)
    # OUI - matching ultra robuste pour gérer les variations de transcription
    for pattern in prompts.YES_PATTERNS:
        # Match avec word boundary pour éviter les faux positifs
        if re.search(r'\b' + re.escape(pattern) + r'\b', t):
            return "YES"
    
    # Fallback pour "oui" seul même si mal transcrit
    if t in ["oui", "ui", "wi", "oui.", "oui,", "ouais", "ouai"]:
        return "YES"
    
    # NON - vérifier si c'est suivi d'une demande spécifique
    is_no = any(t == p or t.startswith(p + " ") or t.startswith(p + ",") for p in prompts.NO_PATTERNS)
    
    # Si "non" mais contient des mots-clés FAQ → FAQ pas NO
    faq_keywords = ["horaire", "adresse", "tarif", "prix", "parking", "accès", "ouvert", "fermé"]
    if is_no and any(kw in t for kw in faq_keywords):
        return "FAQ"
    
    # 2. Intent CANCEL
    if any(p in t for p in prompts.CANCEL_PATTERNS):
        return "CANCEL"
    
    # 3. Intent MODIFY
    if any(p in t for p in prompts.MODIFY_PATTERNS):
        return "MODIFY"
    
    # 4. Intent TRANSFER (cas complexes)
    if any(p in t for p in prompts.TRANSFER_PATTERNS):
        return "TRANSFER"
    
    # 5. Intent ABANDON
    if any(p in t for p in prompts.ABANDON_PATTERNS):
        return "ABANDON"
    
    # 6. Si NON sans autre intent → probablement FAQ
    if is_no:
        return "NO"
    
    # 7. Intent BOOKING
    if _detect_booking_intent(t):
        return "BOOKING"
    
    # 8. Par défaut → FAQ (on laisse le FAQ handler décider)
    return "FAQ"


def detect_slot_choice(text: str, num_slots: int = 3) -> Optional[int]:
    """
    Détecte le choix de créneau de l'utilisateur.
    
    Args:
        text: Message de l'utilisateur
        num_slots: Nombre de créneaux proposés (1, 2 ou 3)
    
    Returns:
        int: Index du slot (0, 1, 2) ou None si non reconnu
    """
    t = text.strip().lower()
    
    # Check patterns pour chaque choix
    if any(p in t for p in prompts.SLOT_CHOICE_FIRST):
        return 0
    if num_slots >= 2 and any(p in t for p in prompts.SLOT_CHOICE_SECOND):
        return 1
    if num_slots >= 3 and any(p in t for p in prompts.SLOT_CHOICE_THIRD):
        return 2
    
    # Check jours (lundi, mardi, etc.) - nécessite les slots pour matcher
    # Pour l'instant, on retourne None et on laisse le code existant gérer
    
    return None


# ========================
# ENGINE
# ========================

class Engine:
    """
    Moteur de conversation déterministe.
    Applique strictement le PRD + SYSTEM_PROMPT.
    """
    
    def __init__(self, session_store, faq_store: FaqStore):
        self.session_store = session_store
        self.faq_store = faq_store
    
    def _save_session(self, session: Session) -> None:
        """Sauvegarde la session (si le store le supporte)."""
        if hasattr(self.session_store, 'save'):
            self.session_store.save(session)
    
    def handle_message(self, conv_id: str, user_text: str) -> List[Event]:
        """
        Pipeline déterministe (ordre STRICT).
        
        Returns:
            Liste d'events à envoyer via SSE
        """
        import time
        t_load_start = time.time()
        
        session = self.session_store.get_or_create(conv_id)
        t_load_end = time.time()
        print(f"⏱️ Session loaded in {(t_load_end - t_load_start) * 1000:.0f}ms")
        
        session.add_message("user", user_text)
        
        print(f"🔍 handle_message: conv_id={conv_id}, state={session.state}, name={session.qualif_data.name}, pending_slots={len(session.pending_slots or [])}, user='{user_text[:50]}'")
        
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
        # 3. ROUTING : Intent-based
        # ========================
        
        # Détecter l'intent
        intent = detect_intent(user_text)
        print(f"🎯 Intent detected: '{intent}' from '{user_text}'")
        channel = getattr(session, "channel", "web")
        print(f"📞 State: {session.state} | Intent: {intent} | User: '{user_text[:50]}...'")
        
        # --- FLOWS EN COURS ---
        
        # Si en cours de qualification → continuer le flow
        if session.state in ["QUALIF_NAME", "QUALIF_MOTIF", "QUALIF_PREF", "QUALIF_CONTACT"]:
            return self._handle_qualification(session, user_text)
        
        # Si en aide contact → gérer guidance
        if session.state == "AIDE_CONTACT":
            return self._handle_aide_contact(session, user_text)
        
        # Si en attente de confirmation → valider
        if session.state == "WAIT_CONFIRM":
            return self._handle_booking_confirm(session, user_text)
        
        # Si en flow CANCEL
        if session.state in ["CANCEL_NAME", "CANCEL_CONFIRM"]:
            return self._handle_cancel(session, user_text)
        
        # Si en flow MODIFY
        if session.state in ["MODIFY_NAME", "MODIFY_CONFIRM"]:
            return self._handle_modify(session, user_text)
        
        # Si en flow CLARIFY
        if session.state == "CLARIFY":
            return self._handle_clarify(session, user_text, intent)
        
        # Si en confirmation de contact
        if session.state == "CONTACT_CONFIRM":
            return self._handle_contact_confirm(session, user_text)
        
        # --- NOUVEAU FLOW : First Message ---
        
        # Si START → le premier message après "Vous appelez pour un RDV ?"
        if session.state == "START":
            
            # YES → Booking flow
            if intent == "YES":
                print(f"✅ Intent YES detected")
                
                # Essayer d'extraire des infos supplémentaires du message
                # Ex: "Oui je voudrais un RDV le matin" → extraire "matin"
                # Ex: "Oui pour Jean Dupont" → extraire le nom
                entities = extract_entities(user_text)
                
                if entities.has_any():
                    # L'utilisateur a donné des infos en plus du "oui" → les utiliser
                    print(f"📦 Extracted from YES message: name={entities.name}, pref={entities.pref}")
                    return self._start_booking_with_extraction(session, user_text)
                
                # Sinon, simple "oui" → demander le nom
                session.state = "QUALIF_NAME"
                msg = prompts.get_qualif_question("name", channel=channel)
                session.add_message("agent", msg)
                print(f"🤖 Returning: '{msg}'")
                return [Event("final", msg, conv_state=session.state)]
            
            # NO → Vérifier s'il y a un autre intent ou une question FAQ
            if intent == "NO":
                # Essayer FAQ d'abord (ex: "Non, c'est où ?")
                # Threshold bas pour les questions courtes
                try:
                    faq_result = self.faq_store.search(user_text, threshold=50)
                    if faq_result and faq_result.score >= 50:
                        print(f"📚 FAQ match after NO: {faq_result.faq_id} (score={faq_result.score})")
                        return self._handle_faq(session, user_text, include_low=False)
                except Exception as e:
                    print(f"⚠️ FAQ search error after NO: {e}")
                
                # Sinon, juste "non" → demander clarification
                session.state = "CLARIFY"
                msg = prompts.VOCAL_CLARIFY if channel == "vocal" else "D'accord. Vous avez une question ou un autre besoin ?"
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # CANCEL → Flow annulation
            if intent == "CANCEL":
                return self._start_cancel(session)
            
            # MODIFY → Flow modification
            if intent == "MODIFY":
                return self._start_modify(session)
            
            # TRANSFER → Transfert direct
            if intent == "TRANSFER":
                session.state = "TRANSFERRED"
                msg = prompts.VOCAL_TRANSFER_COMPLEX if channel == "vocal" else prompts.MSG_TRANSFER
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # ABANDON → Au revoir poli
            if intent == "ABANDON":
                session.state = "CONFIRMED"  # Terminal
                msg = prompts.VOCAL_USER_ABANDON if channel == "vocal" else "Pas de problème. Bonne journée !"
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # BOOKING → Démarrer qualification avec extraction
            if intent == "BOOKING":
                return self._start_booking_with_extraction(session, user_text)
            
            # FAQ ou UNCLEAR → Chercher dans FAQ
            return self._handle_faq(session, user_text, include_low=True)
        
        # Si FAQ_ANSWERED → permettre nouvelle interaction
        if session.state == "FAQ_ANSWERED":
            # Vérifier l'intent pour la suite
            
            # OUI pour un RDV → Booking
            if intent == "YES" or intent == "BOOKING":
                return self._start_booking_with_extraction(session, user_text)
            
            # NON merci → Au revoir
            if intent == "NO" or intent == "ABANDON":
                session.state = "CONFIRMED"
                msg = prompts.VOCAL_FAQ_GOODBYE if channel == "vocal" else "Parfait, bonne journée !"
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # Autre question → FAQ
            session.state = "START"
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
            
            # En vocal, ajouter la question de suivi
            if channel == "vocal":
                response = response + " " + prompts.VOCAL_FAQ_FOLLOWUP
            
            session.state = "FAQ_ANSWERED"
            session.no_match_turns = 0  # Reset le compteur
            session.add_message("agent", response)
            return [Event("final", response, conv_state=session.state)]

        session.no_match_turns += 1

        if session.no_match_turns >= 2:
            session.state = "TRANSFERRED"
            msg = prompts.get_message("transfer", channel=channel)
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]

        # Message plus doux pour le premier no-match
        if channel == "vocal":
            msg = "Je n'ai pas cette information. Souhaitez-vous prendre un rendez-vous ?"
        else:
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
        
        # Skip contact pour le moment - sera demandé après le choix de créneau
        next_field = get_next_missing_field(context, skip_contact=True)
        
        if not next_field:
            # name + pref remplis → proposer créneaux
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
        Utilise le prénom du client dans les questions si disponible.
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
        
        # Skip contact pour le moment - sera demandé après le choix de créneau
        next_field = get_next_missing_field(context, skip_contact=True)
        print(f"🔍 _next_qualif_step: next_field={next_field}")
        
        if not next_field:
            # name + pref remplis → proposer créneaux (contact viendra après)
            print(f"🔍 _next_qualif_step: name+pref FILLED → propose_slots")
            return self._propose_slots(session)
        
        # 📱 Si le prochain champ est "contact" ET qu'on a le numéro de l'appelant → l'utiliser directement
        if next_field == "contact" and channel == "vocal" and session.customer_phone:
            try:
                phone = str(session.customer_phone)
                # Nettoyer le format (+33612345678 → 0612345678)
                if phone.startswith("+33"):
                    phone = "0" + phone[3:]
                elif phone.startswith("33"):
                    phone = "0" + phone[2:]
                phone = phone.replace(" ", "").replace("-", "").replace(".", "")
                
                if len(phone) >= 10:
                    session.qualif_data.contact = phone[:10]
                    session.qualif_data.contact_type = "phone"
                    session.state = "CONTACT_CONFIRM"
                    phone_formatted = prompts.format_phone_for_voice(phone[:10])
                    msg = f"Votre numéro est bien le {phone_formatted} ?"
                    print(f"📱 Using caller ID directly: {phone[:10]}")
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]
            except Exception as e:
                print(f"⚠️ Error using caller ID: {e}")
                # Continue avec le flow normal (demander le numéro)
        
        # Mapper le champ vers l'état
        state_map = {
            "name": "QUALIF_NAME",
            "motif": "QUALIF_MOTIF",
            "pref": "QUALIF_PREF",
            "contact": "QUALIF_CONTACT",
        }
        session.state = state_map[next_field]
        
        # Question adaptée au canal AVEC prénom si disponible
        client_name = session.qualif_data.name or ""
        print(f"🔍 _next_qualif_step: client_name='{client_name}', channel={channel}")
        
        if client_name and channel == "vocal":
            question = prompts.get_qualif_question_with_name(next_field, client_name, channel=channel)
        else:
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
            
            # Nettoyer le nom (enlever "c'est", "je m'appelle", etc.)
            cleaned_name = guards.clean_name_from_vocal(user_text)
            print(f"🔍 QUALIF_NAME: raw='{user_text}' → cleaned='{cleaned_name}'")
            
            # Sécurité : si le nom commence par des mots-outils, prendre le dernier mot
            bad_starts = ["je", "j", "m", "appelle", "suis", "c", "est", "mon", "nom"]
            words = cleaned_name.split()
            if len(words) > 1 and words[0].lower() in bad_starts:
                # Prendre le dernier mot (le vrai prénom)
                cleaned_name = words[-1]
                print(f"🔧 QUALIF_NAME: corrected to last word: '{cleaned_name}'")
            
            # Vérifier longueur minimale (un nom fait au moins 2 caractères)
            if len(cleaned_name) < 2:
                # Redemander poliment
                msg = "Excusez-moi, je n'ai pas bien entendu. Pouvez-vous me redonner votre nom ?"
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # Réponse valide → stocker et continuer
            session.qualif_data.name = cleaned_name
            print(f"✅ QUALIF_NAME: stored name='{session.qualif_data.name}'")
            # Pas de save ici - on save après _next_qualif_step
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
            print(f"🔍 QUALIF_PREF handler: user_text='{user_text}'")
            
            # Vérifier que ce n'est pas une répétition
            if _detect_booking_intent(user_text):
                msg = prompts.get_qualif_retry("pref", channel=channel)
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # Pas de validation stricte sur le créneau (V1)
            # On accepte la réponse telle quelle
            session.qualif_data.pref = user_text.strip()
            print(f"🔍 QUALIF_PREF: stored pref='{session.qualif_data.pref}', calling _next_qualif_step")
            # Pas de save ici - on save après _propose_slots
            return self._next_qualif_step(session)
        
        # ========================
        # QUALIF_CONTACT
        # ========================
        elif current_step == "QUALIF_CONTACT":
            channel = getattr(session, "channel", "web")
            contact_raw = user_text.strip()
            
            print(f"📞 QUALIF_CONTACT: received '{contact_raw}'")

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
                # Pour email, pas d'accumulation
                is_valid, contact_type = guards.validate_qualif_contact(contact_raw)
                if is_valid:
                    session.qualif_data.contact = contact_raw
                    session.qualif_data.contact_type = contact_type
                    return self._propose_slots(session)

            # ✅ ACCUMULATION des chiffres du téléphone (vocal) - seulement si pas de numéro auto
            if channel == "vocal" and not session.customer_phone:
                new_digits = guards.parse_vocal_phone(contact_raw)
                print(f"📞 New digits from '{contact_raw}': '{new_digits}' ({len(new_digits)} digits)")
                
                # Ajouter aux chiffres déjà accumulés
                session.partial_phone_digits += new_digits
                total_digits = session.partial_phone_digits
                print(f"📞 Total accumulated: '{total_digits}' ({len(total_digits)} digits)")
                
                # Si on a 10 chiffres ou plus → on a le numéro complet
                if len(total_digits) >= 10:
                    contact_raw = total_digits[:10]
                    session.partial_phone_digits = ""  # Reset
                    print(f"📞 Got 10 digits! Phone: {contact_raw}")
                    
                    # Valider et continuer
                    session.qualif_data.contact = contact_raw
                    session.qualif_data.contact_type = "phone"
                    session.contact_retry_count = 0
                    
                    # Demander confirmation
                    session.state = "CONTACT_CONFIRM"
                    phone_formatted = prompts.format_phone_for_voice(contact_raw)
                    msg = prompts.VOCAL_CONTACT_CONFIRM.format(phone_formatted=phone_formatted)
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]
                
                else:
                    # Pas encore 10 chiffres → demander la suite
                    session.contact_retry_count += 1
                    
                    if session.contact_retry_count >= 6:
                        # Trop de tentatives → transfert
                        session.state = "TRANSFERRED"
                        session.partial_phone_digits = ""
                        msg = prompts.get_message("transfer", channel=channel)
                        session.add_message("agent", msg)
                        return [Event("final", msg, conv_state=session.state)]
                    
                    # Messages ultra-courts pour pas ralentir
                    if len(total_digits) == 0:
                        msg = "J'écoute."
                    elif len(total_digits) < 10:
                        msg = "Oui, continuez."
                    
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]
            
            # Web - validation directe
            is_valid, contact_type = guards.validate_qualif_contact(contact_raw)
            print(f"📞 Validation result: is_valid={is_valid}, type={contact_type}")

            if not is_valid:
                session.contact_retry_count += 1
                if session.contact_retry_count < 3:
                    msg = prompts.get_message("contact_retry", channel=channel)
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]

                # Transfer
                session.state = "TRANSFERRED"
                msg = prompts.get_message("transfer", channel=channel)
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]

            # ✅ Valide - stocker
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
        
        # 💾 Sauvegarder IMMÉDIATEMENT (crucial pour ne pas perdre les pending_slots)
        self._save_session(session)
        
        return [Event("final", msg, conv_state=session.state)]
    
    def _handle_booking_confirm(self, session: Session, user_text: str) -> List[Event]:
        """
        Gère confirmation RDV (WAIT_CONFIRM).
        Supporte: "oui 1", "1", "le premier", "lundi", etc.
        """
        channel = getattr(session, "channel", "web")
        
        print(f"🔍 _handle_booking_confirm: user_text='{user_text}', pending_slots={len(session.pending_slots or [])}, state={session.state}")
        
        # 🔄 Si pas de slots en mémoire (session perdue) → re-proposer
        if not session.pending_slots or len(session.pending_slots) == 0:
            print(f"⚠️ WAIT_CONFIRM but no pending_slots → re-proposing")
            return self._propose_slots(session)
        
        print(f"📋 Pending slots: {[(s.idx, s.label) for s in session.pending_slots]}")
        
        # Essayer la nouvelle détection de slot
        slot_idx = detect_slot_choice(user_text, num_slots=len(session.pending_slots or []))
        print(f"🔍 detect_slot_choice: '{user_text}' → slot_idx={slot_idx}")
        
        # Log fallback
        if slot_idx is None:
            print(f"⚠️ Trying fallback validation...")
        
        # Si pas trouvé avec la nouvelle méthode, fallback sur l'ancienne
        if slot_idx is None:
            is_valid, slot_idx = guards.validate_booking_confirm(user_text, channel=channel)
            if not is_valid:
                slot_idx = None
        
        if slot_idx is not None:
            print(f"✅ Slot choice validated: slot_idx={slot_idx}")
            
            # Stocker le choix de créneau
            try:
                slot_label = tools_booking.get_label_for_choice(session, slot_idx) or "votre créneau"
                print(f"📅 Slot label: '{slot_label}'")
            except Exception as e:
                print(f"⚠️ Error getting slot label: {e}")
                import traceback
                traceback.print_exc()
                slot_label = "votre créneau"
            
            name = session.qualif_data.name or ""
            
            # Stocker temporairement le slot choisi (on bookera après confirmation du contact)
            session.pending_slot_choice = slot_idx
            print(f"📌 Stored pending_slot_choice={slot_idx}")
            
            # 💾 Sauvegarder le choix immédiatement
            self._save_session(session)
            
            # 📱 Maintenant demander le contact (avec numéro auto si disponible)
            if channel == "vocal" and session.customer_phone:
                try:
                    phone = str(session.customer_phone)
                    # Nettoyer le format
                    if phone.startswith("+33"):
                        phone = "0" + phone[3:]
                    elif phone.startswith("33"):
                        phone = "0" + phone[2:]
                    phone = phone.replace(" ", "").replace("-", "").replace(".", "")
                    
                    if len(phone) >= 10:
                        session.qualif_data.contact = phone[:10]
                        session.qualif_data.contact_type = "phone"
                        session.state = "CONTACT_CONFIRM"
                        phone_formatted = prompts.format_phone_for_voice(phone[:10])
                        msg = f"Parfait, {slot_label} pour {name}. Votre numéro est bien le {phone_formatted} ?"
                        print(f"📱 Using caller ID for confirmation: {phone[:10]}")
                        session.add_message("agent", msg)
                        return [Event("final", msg, conv_state=session.state)]
                except Exception as e:
                    print(f"⚠️ Error using caller ID in booking confirm: {e}")
                    import traceback
                    traceback.print_exc()
                    # Continue avec le flow normal
            
            # Sinon demander le contact normalement
            print(f"📞 No caller ID, asking for contact normally")
            session.state = "QUALIF_CONTACT"
            first_name = name.split()[0] if name else ""
            print(f"👤 name='{name}', first_name='{first_name}'")
            
            if first_name and channel == "vocal":
                msg = f"Parfait, {slot_label} pour {first_name}. Et votre numéro de téléphone pour vous rappeler ?"
            else:
                msg = prompts.get_qualif_question("contact", channel=channel)
            
            print(f"✅ Final message: '{msg}'")
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
    # FLOW C: CANCEL
    # ========================
    
    def _start_cancel(self, session: Session) -> List[Event]:
        """Démarre le flow d'annulation."""
        channel = getattr(session, "channel", "web")
        session.state = "CANCEL_NAME"
        msg = prompts.VOCAL_CANCEL_ASK_NAME if channel == "vocal" else "Pas de problème. C'est à quel nom ?"
        session.add_message("agent", msg)
        return [Event("final", msg, conv_state=session.state)]
    
    def _handle_cancel(self, session: Session, user_text: str) -> List[Event]:
        """Gère le flow d'annulation."""
        channel = getattr(session, "channel", "web")
        
        if session.state == "CANCEL_NAME":
            # Stocker le nom et chercher le RDV
            session.qualif_data.name = user_text.strip()
            
            # TODO: Rechercher le RDV dans Google Calendar ou BDD
            # Pour V1, on simule qu'on trouve toujours un RDV
            existing_slot = tools_booking.find_booking_by_name(session.qualif_data.name)
            
            if not existing_slot:
                # Pas de RDV trouvé
                session.confirm_retry_count += 1
                if session.confirm_retry_count >= 2:
                    session.state = "TRANSFERRED"
                    msg = prompts.get_message("transfer", channel=channel)
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]
                
                msg = prompts.VOCAL_CANCEL_NOT_FOUND if channel == "vocal" else "Je n'ai pas trouvé de rendez-vous à ce nom. Pouvez-vous me redonner votre nom complet ?"
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # RDV trouvé → demander confirmation
            session.state = "CANCEL_CONFIRM"
            session.pending_cancel_slot = existing_slot
            slot_label = existing_slot.get("label", "votre rendez-vous")
            
            if channel == "vocal":
                msg = prompts.VOCAL_CANCEL_CONFIRM.format(slot_label=slot_label)
            else:
                msg = f"Vous avez un rendez-vous {slot_label}. Voulez-vous l'annuler ?"
            
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        elif session.state == "CANCEL_CONFIRM":
            intent = detect_intent(user_text)
            
            if intent == "YES":
                # Annuler le RDV
                success = tools_booking.cancel_booking(session.pending_cancel_slot)
                
                session.state = "CONFIRMED"
                msg = prompts.VOCAL_CANCEL_DONE if channel == "vocal" else "C'est fait, votre rendez-vous est annulé. Bonne journée !"
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            elif intent == "NO":
                # Garder le RDV
                session.state = "CONFIRMED"
                msg = prompts.VOCAL_CANCEL_KEPT if channel == "vocal" else "Pas de souci, votre rendez-vous est maintenu. Bonne journée !"
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            else:
                # Pas compris → retry
                msg = "Je n'ai pas compris. Voulez-vous annuler ce rendez-vous ? Répondez oui ou non."
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
        
        # Fallback
        return self._fallback_transfer(session)
    
    # ========================
    # FLOW D: MODIFY
    # ========================
    
    def _start_modify(self, session: Session) -> List[Event]:
        """Démarre le flow de modification."""
        channel = getattr(session, "channel", "web")
        session.state = "MODIFY_NAME"
        msg = prompts.VOCAL_MODIFY_ASK_NAME if channel == "vocal" else "Pas de souci. C'est à quel nom ?"
        session.add_message("agent", msg)
        return [Event("final", msg, conv_state=session.state)]
    
    def _handle_modify(self, session: Session, user_text: str) -> List[Event]:
        """Gère le flow de modification."""
        channel = getattr(session, "channel", "web")
        
        if session.state == "MODIFY_NAME":
            # Stocker le nom et chercher le RDV
            session.qualif_data.name = user_text.strip()
            
            existing_slot = tools_booking.find_booking_by_name(session.qualif_data.name)
            
            if not existing_slot:
                session.confirm_retry_count += 1
                if session.confirm_retry_count >= 2:
                    session.state = "TRANSFERRED"
                    msg = prompts.get_message("transfer", channel=channel)
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]
                
                msg = prompts.VOCAL_MODIFY_NOT_FOUND if channel == "vocal" else "Je n'ai pas trouvé de rendez-vous à ce nom. Pouvez-vous me redonner votre nom complet ?"
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # RDV trouvé → demander confirmation
            session.state = "MODIFY_CONFIRM"
            session.pending_cancel_slot = existing_slot
            slot_label = existing_slot.get("label", "votre rendez-vous")
            
            if channel == "vocal":
                msg = prompts.VOCAL_MODIFY_CONFIRM.format(slot_label=slot_label)
            else:
                msg = f"Vous avez un rendez-vous {slot_label}. Voulez-vous le déplacer ?"
            
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        elif session.state == "MODIFY_CONFIRM":
            intent = detect_intent(user_text)
            
            if intent == "YES":
                # Annuler l'ancien RDV et demander nouvelle préférence
                tools_booking.cancel_booking(session.pending_cancel_slot)
                
                # Rerouter vers QUALIF_PREF
                session.state = "QUALIF_PREF"
                msg = prompts.VOCAL_MODIFY_CANCELLED if channel == "vocal" else "OK, j'ai annulé l'ancien. Plutôt le matin ou l'après-midi pour le nouveau ?"
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            elif intent == "NO":
                # Garder le RDV
                session.state = "CONFIRMED"
                msg = prompts.VOCAL_CANCEL_KEPT if channel == "vocal" else "Pas de souci, votre rendez-vous est maintenu. Bonne journée !"
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            else:
                msg = "Je n'ai pas compris. Voulez-vous déplacer ce rendez-vous ? Répondez oui ou non."
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
        
        return self._fallback_transfer(session)
    
    # ========================
    # CONFIRMATION CONTACT
    # ========================
    
    def _handle_contact_confirm(self, session: Session, user_text: str) -> List[Event]:
        """Gère la confirmation du numéro de téléphone."""
        channel = getattr(session, "channel", "web")
        intent = detect_intent(user_text)
        
        if intent == "YES":
            # Numéro confirmé
            
            # Si on a déjà un slot choisi (nouveau flow) → booker et confirmer
            if session.pending_slot_choice is not None:
                slot_idx = session.pending_slot_choice
                
                # Booker le créneau
                success = tools_booking.book_slot_from_session(session, slot_idx)
                
                if not success:
                    session.state = "TRANSFERRED"
                    msg = prompts.MSG_SLOT_ALREADY_BOOKED
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]
                
                # Confirmer
                slot_label = tools_booking.get_label_for_choice(session, slot_idx) or ""
                name = session.qualif_data.name or ""
                motif = session.qualif_data.motif or ""
                msg = prompts.format_booking_confirmed(slot_label, name=name, motif=motif, channel=channel)
                
                session.state = "CONFIRMED"
                session.add_message("agent", msg)
                return [Event("final", msg, conv_state=session.state)]
            
            # Sinon (ancien flow) → proposer créneaux
            return self._propose_slots(session)
        
        elif intent == "NO":
            # Numéro incorrect
            # Vérifier si l'utilisateur donne une correction partielle (ex: "non c'est 8414")
            digits = guards.parse_vocal_phone(user_text)
            
            if len(digits) >= 4 and len(digits) < 10 and session.qualif_data.contact:
                # Correction partielle détectée - essayer de corriger les derniers chiffres
                current_phone = session.qualif_data.contact
                # Remplacer les derniers chiffres
                corrected_phone = current_phone[:10-len(digits)] + digits
                print(f"📞 Correction partielle: {current_phone} → {corrected_phone}")
                
                if len(corrected_phone) == 10:
                    session.qualif_data.contact = corrected_phone
                    phone_formatted = prompts.format_phone_for_voice(corrected_phone)
                    msg = f"D'accord, donc c'est bien le {phone_formatted} ?"
                    # Rester en CONTACT_CONFIRM pour re-confirmer
                    session.add_message("agent", msg)
                    return [Event("final", msg, conv_state=session.state)]
            
            # Sinon, redemander le numéro complet
            session.state = "QUALIF_CONTACT"
            session.qualif_data.contact = None
            session.qualif_data.contact_type = None
            session.partial_phone_digits = ""  # Reset accumulation
            msg = prompts.VOCAL_CONTACT_CONFIRM_RETRY
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        else:
            # Pas compris → redemander confirmation
            phone_formatted = prompts.format_phone_for_voice(session.qualif_data.contact or "")
            msg = f"Excusez-moi, j'ai noté le {phone_formatted}. Est-ce correct ?"
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
    
    # ========================
    # FLOW E: CLARIFY
    # ========================
    
    def _handle_clarify(self, session: Session, user_text: str, intent: str) -> List[Event]:
        """Gère la clarification après un 'non' au first message."""
        channel = getattr(session, "channel", "web")
        
        # Si l'utilisateur dit vouloir un RDV
        if intent == "YES" or intent == "BOOKING" or "rendez-vous" in user_text.lower() or "rdv" in user_text.lower():
            session.state = "QUALIF_NAME"
            msg = prompts.VOCAL_FAQ_TO_BOOKING if channel == "vocal" else "Pas de souci. C'est à quel nom ?"
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        # Si l'utilisateur dit avoir une question
        if "question" in user_text.lower() or intent == "FAQ":
            session.state = "START"
            return self._handle_faq(session, user_text, include_low=True)
        
        # Intent CANCEL
        if intent == "CANCEL":
            return self._start_cancel(session)
        
        # Intent MODIFY
        if intent == "MODIFY":
            return self._start_modify(session)
        
        # Intent TRANSFER
        if intent == "TRANSFER":
            session.state = "TRANSFERRED"
            msg = prompts.VOCAL_TRANSFER_COMPLEX if channel == "vocal" else prompts.MSG_TRANSFER
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        # Toujours pas clair → transfert
        session.confirm_retry_count += 1
        if session.confirm_retry_count >= 2:
            session.state = "TRANSFERRED"
            msg = prompts.VOCAL_STILL_UNCLEAR if channel == "vocal" else prompts.MSG_TRANSFER
            session.add_message("agent", msg)
            return [Event("final", msg, conv_state=session.state)]
        
        # Encore une chance
        msg = prompts.VOCAL_CLARIFY if channel == "vocal" else "D'accord. Vous avez une question ou vous souhaitez prendre rendez-vous ?"
        session.add_message("agent", msg)
        return [Event("final", msg, conv_state=session.state)]
    
    # ========================
    # FALLBACK
    # ========================
    
    def _fallback_transfer(self, session: Session) -> List[Event]:
        """Fallback vers transfert humain."""
        channel = getattr(session, "channel", "web")
        session.state = "TRANSFERRED"
        msg = prompts.get_message("transfer", channel=channel)
        session.add_message("agent", msg)
        return [Event("final", msg, conv_state=session.state)]


# ========================
# FACTORY
# ========================

def create_engine() -> Engine:
    """Factory pour créer l'engine avec ses dépendances"""
    from backend.tools_faq import default_faq_store
    
    # Utiliser SQLite pour persistance des sessions (robuste aux redémarrages)
    session_store = SQLiteSessionStore()
    faq_store = default_faq_store()
    
    return Engine(session_store=session_store, faq_store=faq_store)


# Engine singleton (exporté pour vapi.py)
ENGINE = create_engine()
