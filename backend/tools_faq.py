# backend/tools_faq.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple

from rapidfuzz import fuzz, process
from backend import config


def _norm(s: str) -> str:
    """Normalisation simple V1 (déterministe)."""
    return (s or "").strip().lower()


@dataclass(frozen=True)
class FaqItem:
    faq_id: str
    question: str
    answer: str
    priority: str = "normal"  # "normal" | "low"


@dataclass(frozen=True)
class FaqResult:
    match: bool
    score: float
    faq_id: Optional[str] = None
    answer: Optional[str] = None


class FaqStore:
    """V1: store en mémoire, matching lexical strict + priority."""

    def __init__(self, items: List[FaqItem]) -> None:
        self.items = items
        # Pré-index normalisé pour stabilité + perfs
        self._items_norm: List[Tuple[str, FaqItem]] = [(_norm(i.question), i) for i in items]

    def search(self, query: str, include_low: bool = True) -> FaqResult:
        """
        Recherche FAQ avec gestion priority.

        include_low=False exclut les FAQs priority="low"
        """
        q = _norm(query)
        if not q:
            return FaqResult(match=False, score=0.0)

        candidates: List[Tuple[str, FaqItem]]
        if include_low:
            candidates = self._items_norm
        else:
            candidates = [(qn, it) for (qn, it) in self._items_norm if it.priority == "normal"]

        if not candidates:
            return FaqResult(match=False, score=0.0)

        questions_norm = [qn for (qn, _) in candidates]

        result = process.extractOne(q, questions_norm, scorer=fuzz.WRatio)
        if result is None:
            return FaqResult(match=False, score=0.0)

        _choice, score, idx = result
        score_norm = float(score) / 100.0

        if score_norm >= config.FAQ_THRESHOLD:
            item = candidates[idx][1]
            return FaqResult(match=True, score=score_norm, faq_id=item.faq_id, answer=item.answer)

        return FaqResult(match=False, score=score_norm)


def default_faq_store() -> FaqStore:
    """
    FAQ avec plusieurs variations pour chaque question.
    Le matching utilise fuzzy search, donc plus de variations = meilleure reconnaissance.
    """
    # Réponses communes
    REPONSE_HORAIRES = "Nous sommes ouverts du lundi au vendredi, de 9 heures à 18 heures."
    REPONSE_TARIFS = "La consultation coûte 80 euros et dure 30 minutes."
    REPONSE_ADRESSE = "Nous sommes au 10 Rue de la Santé, dans le 14ème arrondissement de Paris, métro Denfert-Rochereau."
    REPONSE_PAIEMENT = "Nous acceptons la carte bancaire, les espèces et le chèque."
    REPONSE_ANNULATION = "Pour annuler un rendez-vous, merci de nous contacter par téléphone au moins 24 heures à l'avance."
    REPONSE_DUREE = "Une consultation dure 30 minutes."
    
    items = [
        # Salutation (low priority)
        FaqItem(faq_id="FAQ_SALUTATION", question="bonjour salut", answer="Bonjour. Comment puis-je vous aider ?", priority="low"),
        
        # HORAIRES - plusieurs variations
        FaqItem(faq_id="FAQ_HORAIRES", question="quels sont vos horaires", answer=REPONSE_HORAIRES),
        FaqItem(faq_id="FAQ_HORAIRES", question="horaires ouverture", answer=REPONSE_HORAIRES),
        FaqItem(faq_id="FAQ_HORAIRES", question="vous êtes ouvert quand", answer=REPONSE_HORAIRES),
        FaqItem(faq_id="FAQ_HORAIRES", question="c'est ouvert à quelle heure", answer=REPONSE_HORAIRES),
        FaqItem(faq_id="FAQ_HORAIRES", question="ouvert le samedi", answer=REPONSE_HORAIRES),
        FaqItem(faq_id="FAQ_HORAIRES", question="fermé le dimanche", answer=REPONSE_HORAIRES),
        FaqItem(faq_id="FAQ_HORAIRES", question="heures ouverture", answer=REPONSE_HORAIRES),
        FaqItem(faq_id="FAQ_HORAIRES", question="à quelle heure vous ouvrez", answer=REPONSE_HORAIRES),
        FaqItem(faq_id="FAQ_HORAIRES", question="à quelle heure vous fermez", answer=REPONSE_HORAIRES),
        FaqItem(faq_id="FAQ_HORAIRES", question="vous fermez à quelle heure", answer=REPONSE_HORAIRES),
        
        # TARIFS - plusieurs variations
        FaqItem(faq_id="FAQ_TARIFS", question="quels sont vos tarifs", answer=REPONSE_TARIFS),
        FaqItem(faq_id="FAQ_TARIFS", question="combien coûte une consultation", answer=REPONSE_TARIFS),
        FaqItem(faq_id="FAQ_TARIFS", question="c'est combien", answer=REPONSE_TARIFS),
        FaqItem(faq_id="FAQ_TARIFS", question="quel est le prix", answer=REPONSE_TARIFS),
        FaqItem(faq_id="FAQ_TARIFS", question="tarif consultation", answer=REPONSE_TARIFS),
        FaqItem(faq_id="FAQ_TARIFS", question="prix de la consultation", answer=REPONSE_TARIFS),
        
        # ADRESSE - plusieurs variations
        FaqItem(faq_id="FAQ_ADRESSE", question="quelle est votre adresse", answer=REPONSE_ADRESSE),
        FaqItem(faq_id="FAQ_ADRESSE", question="où êtes-vous situé", answer=REPONSE_ADRESSE),
        FaqItem(faq_id="FAQ_ADRESSE", question="c'est où", answer=REPONSE_ADRESSE),
        FaqItem(faq_id="FAQ_ADRESSE", question="vous êtes où", answer=REPONSE_ADRESSE),
        FaqItem(faq_id="FAQ_ADRESSE", question="adresse du cabinet", answer=REPONSE_ADRESSE),
        FaqItem(faq_id="FAQ_ADRESSE", question="comment venir", answer=REPONSE_ADRESSE),
        FaqItem(faq_id="FAQ_ADRESSE", question="quel métro", answer=REPONSE_ADRESSE),
        
        # PAIEMENT - plusieurs variations
        FaqItem(faq_id="FAQ_PAIEMENT", question="quels moyens de paiement", answer=REPONSE_PAIEMENT),
        FaqItem(faq_id="FAQ_PAIEMENT", question="vous prenez la carte", answer=REPONSE_PAIEMENT),
        FaqItem(faq_id="FAQ_PAIEMENT", question="carte bancaire acceptée", answer=REPONSE_PAIEMENT),
        FaqItem(faq_id="FAQ_PAIEMENT", question="je peux payer par carte", answer=REPONSE_PAIEMENT),
        FaqItem(faq_id="FAQ_PAIEMENT", question="paiement en espèces", answer=REPONSE_PAIEMENT),
        FaqItem(faq_id="FAQ_PAIEMENT", question="comment payer", answer=REPONSE_PAIEMENT),
        
        # ANNULATION - plusieurs variations
        FaqItem(faq_id="FAQ_ANNULATION", question="comment annuler un rendez-vous", answer=REPONSE_ANNULATION),
        FaqItem(faq_id="FAQ_ANNULATION", question="annuler mon rdv", answer=REPONSE_ANNULATION),
        FaqItem(faq_id="FAQ_ANNULATION", question="je veux annuler", answer=REPONSE_ANNULATION),
        FaqItem(faq_id="FAQ_ANNULATION", question="annulation rendez-vous", answer=REPONSE_ANNULATION),
        
        # DURÉE - plusieurs variations
        FaqItem(faq_id="FAQ_DUREE", question="durée consultation", answer=REPONSE_DUREE),
        FaqItem(faq_id="FAQ_DUREE", question="ça dure combien de temps", answer=REPONSE_DUREE),
        FaqItem(faq_id="FAQ_DUREE", question="combien de temps dure la consultation", answer=REPONSE_DUREE),
        FaqItem(faq_id="FAQ_DUREE", question="c'est long", answer=REPONSE_DUREE),
    ]
    return FaqStore(items=items)
