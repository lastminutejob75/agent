# backend/start_router.py
"""
Router START : heuristique + parser + LLM Assist (un seul endroit). Plus de double-router en engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, Callable
import re
import logging

import backend.intent_parser as intent_parser
from backend.intent_parser import detect_intent, detect_strong_intent, Intent

logger = logging.getLogger(__name__)

# ---- Heuristique minimal (filet pour formulations type "voir le docteur Dupont") ----
_BOOKING_HINTS = re.compile(
    r"\b(rdv|rendez[- ]?vous|prendre\s+un\s+rendez[- ]?vous|"
    r"voir|consulter|rencontrer|passer\s+voir)\b",
    re.IGNORECASE,
)
_PROVIDER_HINTS = re.compile(r"\b(dr|docteur|médecin)\b", re.IGNORECASE)
_TIME_HINTS = re.compile(
    r"\b(demain|aujourd'hui|lundi|mardi|mercredi|jeudi|vendredi|samedi|"
    r"matin|après[- ]?midi|\d{1,2}\s?h(\d{2})?)\b",
    re.IGNORECASE,
)


@dataclass
class StartRoute:
    intent: Intent  # Intent enum (OUT_OF_SCOPE inclus)
    confidence: float = 0.0
    entities: Optional[Dict[str, Any]] = None
    source: str = "router"  # "llm_assist" | "heuristic" | "parser"


# Strong intents : ne jamais les écraser par l'heuristique BOOKING ("voir tarifs" -> FAQ)
_STRONG_OVERRIDE_HEURISTIC = frozenset({
    Intent.FAQ, Intent.TRANSFER, Intent.CANCEL, Intent.MODIFY, Intent.ABANDON, Intent.ORDONNANCE,
})

# Whitelist buckets FAQ (évite fausses FAQ)
FAQ_BUCKET_WHITELIST = frozenset({"HORAIRES", "ADRESSE", "TARIFS", "ACCES", "CONTACT", "AUTRE"})


def _heuristic_route(text: str) -> Optional[StartRoute]:
    t = (text or "").strip()
    if not t:
        return StartRoute(intent=Intent.UNCLEAR, confidence=0.0, source="heuristic")

    score = 0
    if _BOOKING_HINTS.search(t):
        score += 2
    if _PROVIDER_HINTS.search(t):
        score += 2
    if _TIME_HINTS.search(t):
        score += 1

    if score >= 3:
        return StartRoute(
            intent=Intent.BOOKING,
            confidence=min(0.85, 0.55 + 0.1 * score),
            entities={"heuristic_score": score},
            source="heuristic",
        )
    return None


def _try_llm_assist(
    text: str,
    *,
    state: str,
    channel: str,
    client: Any,
    should_try: Callable[[str, str, Optional[str]], bool],
    intent_current: str,
    strong_intent: Optional[str],
    min_confidence: float,
) -> Optional[StartRoute]:
    """
    Logique ex-"Zone grise" : llm_assist_classify → StartRoute.
    Ne s'applique que si intent_current == "UNCLEAR", pas sur filler.
    """
    if intent_current != "UNCLEAR":
        return None
    if not text or not text.strip():
        return None
    if intent_parser.is_unclear_filler(text):
        return None
    if not should_try(text, intent_current, strong_intent):
        return None

    from backend.llm_assist import llm_assist_classify

    assist = llm_assist_classify(
        text=text,
        state=state,
        channel=channel,
        client=client,
    )
    if not assist or float(getattr(assist, "confidence", 0.0)) < float(min_confidence):
        return None

    a_intent = getattr(assist, "intent", None)
    a_conf = float(getattr(assist, "confidence", 0.0))
    a_bucket = getattr(assist, "faq_bucket", None)

    entities: Dict[str, Any] = {
        "llm_used": True,
        "llm_intent": a_intent,
        "llm_confidence": a_conf,
        "llm_bucket": a_bucket,
    }

    if a_intent == "OUT_OF_SCOPE":
        entities["out_of_scope_response"] = getattr(assist, "out_of_scope_response", None)
        return StartRoute(intent=Intent.OUT_OF_SCOPE, confidence=a_conf, entities=entities, source="llm_assist")
    if a_intent in ("CANCEL", "MODIFY", "TRANSFER", "ABANDON", "ORDONNANCE"):
        return StartRoute(
            intent=Intent(a_intent),
            confidence=a_conf,
            entities=entities,
            source="llm_assist",
        )
    if a_intent == "BOOKING":
        return StartRoute(intent=Intent.BOOKING, confidence=a_conf, entities=entities, source="llm_assist")
    if a_intent == "FAQ":
        bucket_ok = a_bucket and str(a_bucket).strip().upper() in FAQ_BUCKET_WHITELIST
        if bucket_ok:
            entities["faq_bucket"] = str(a_bucket).strip().upper()
        entities["llm_bucket"] = a_bucket  # pour log (même si non retenu)
        return StartRoute(intent=Intent.FAQ, confidence=a_conf, entities=entities, source="llm_assist")
    if a_intent == "UNCLEAR":
        entities["no_faq"] = True
        return StartRoute(intent=Intent.UNCLEAR, confidence=a_conf, entities=entities, source="llm_assist")
    return None


def route_start(
    text: str,
    *,
    state: str = "START",
    channel: str = "vocal",
    llm_client: Any = None,
    should_try_llm_assist: Optional[Callable[[str, str, Optional[str]], bool]] = None,
    strong_intent: Optional[str] = None,
    llm_assist_min_confidence: float = 0.70,
) -> StartRoute:
    """
    Un seul router START : heuristique → parser → LLM Assist (si UNCLEAR + activé).
    Ne jamais préférer heuristique BOOKING à une intention forte (FAQ, TRANSFER, …).
    """
    # 0) Heuristique booking (filet), sauf si strong intent prioritaire
    hr = _heuristic_route(text)
    if hr is not None:
        strong = strong_intent if strong_intent is not None else detect_strong_intent(text)
        if strong is not None and strong in _STRONG_OVERRIDE_HEURISTIC:
            pass  # ignorer heuristique, continuer vers parser
        else:
            return hr

    # 1) Parser existant
    i = detect_intent(text, state=state)
    r = StartRoute(intent=i, confidence=0.0, entities=None, source="parser")

    # 2) LLM Assist uniquement si UNCLEAR + activé + non filler
    if r.intent == Intent.UNCLEAR and llm_client is not None and should_try_llm_assist is not None:
        ar = _try_llm_assist(
            text,
            state=state,
            channel=channel,
            client=llm_client,
            should_try=should_try_llm_assist,
            intent_current=r.intent,
            strong_intent=strong_intent,
            min_confidence=llm_assist_min_confidence,
        )
        if ar is not None:
            return ar

    return r
