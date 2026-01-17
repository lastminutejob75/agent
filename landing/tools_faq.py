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
    """V1 seed enrichi. Salutation en low priority."""
    items = [
        FaqItem(
            faq_id="FAQ_SALUTATION",
            question="bonjour salut",
            answer="Bonjour. Comment puis-je vous aider ?",
            priority="low",
        ),
        FaqItem(
            faq_id="FAQ_HORAIRES",
            question="Quels sont vos horaires ?",
            answer="Nos horaires sont de 9h à 18h du lundi au vendredi.",
        ),
        FaqItem(
            faq_id="FAQ_TARIFS",
            question="Quels sont vos tarifs ?",
            answer="La consultation coûte 80€ et dure 30 minutes.",
        ),
        FaqItem(
            faq_id="FAQ_ADRESSE",
            question="Quelle est votre adresse ?",
            answer="Nous sommes au 10 Rue de la Santé, 75014 Paris (métro Denfert-Rochereau).",
        ),
        FaqItem(
            faq_id="FAQ_PAIEMENT",
            question="Quels moyens de paiement acceptez-vous ?",
            answer="Nous acceptons la carte bancaire, les espèces et le chèque.",
        ),
        FaqItem(
            faq_id="FAQ_ANNULATION",
            question="Comment annuler un rendez-vous ?",
            answer=(
                "Pour annuler un rendez-vous, merci de nous contacter par téléphone au "
                "+33 6 00 00 00 00 au moins 24h à l'avance."
            ),
        ),
        FaqItem(
            faq_id="FAQ_DUREE",
            question="Quelle est la durée d'une consultation ?",
            answer="Une consultation dure 30 minutes.",
        ),
    ]
    return FaqStore(items=items)
