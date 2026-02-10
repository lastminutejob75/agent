# tests/test_start_router.py
"""Tests du routeur START (couche sémantique + heuristique + fallback parser)."""

import pytest
from backend.start_router import route_start, _heuristic_route, StartRoute
from backend.intent_parser import Intent


def test_route_start_parser_booking_keyword():
    """'rendez-vous' / 'rdv' reste routé BOOKING par le parser (fallback)."""
    r = route_start("je voudrais un rendez-vous")
    assert r.intent == Intent.BOOKING
    assert r.source in ("parser", "heuristic", "llm_assist")


def test_route_start_heuristic_voir_docteur():
    """Formulations type 'voir le docteur Dupont' passent par heuristique -> BOOKING."""
    r = route_start("je demande à voir le docteur Dupont")
    assert r.intent == Intent.BOOKING
    assert r.source == "heuristic"
    assert r.confidence >= 0.65


def test_route_start_heuristic_consulter_demain():
    """'consulter demain matin' -> heuristique BOOKING."""
    r = route_start("j'aimerais consulter demain matin")
    assert r.intent == Intent.BOOKING
    assert r.source == "heuristic"


def test_route_start_parser_unclear():
    """Phrase vague sans marqueur -> UNCLEAR (parser)."""
    r = route_start("euh")
    assert r.intent == Intent.UNCLEAR


def test_heuristic_empty_returns_unclear():
    """Texte vide -> UNCLEAR, source heuristic."""
    r = _heuristic_route("")
    assert r is not None
    assert r.intent == Intent.UNCLEAR
    assert r.source == "heuristic"


def test_heuristic_weak_no_route():
    """Une seule mention temps sans 'voir/docteur/rdv' -> pas de route heuristique (None)."""
    r = _heuristic_route("demain")
    assert r is None


def test_faq_vs_booking_ambiguity_adresse_docteur():
    """'Je veux l'adresse du cabinet du docteur Dupont' -> FAQ (pas BOOKING heuristique)."""
    r = route_start("Je veux l'adresse du cabinet du docteur Dupont")
    assert r.intent == Intent.FAQ, "adresse doit primer (strong FAQ) sur docteur/cabinet"


def test_faq_vs_booking_ambiguity_voir_docteur_adresse():
    """'Je veux voir le docteur pour l'adresse' -> FAQ (strong intent override heuristique)."""
    r = route_start("Je veux voir le docteur pour l'adresse")
    assert r.intent == Intent.FAQ
