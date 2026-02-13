# tests/test_transfer_budget.py
"""
Tests P0 transfer budget : réduction des transferts techniques.
- Budget 2 : 1er échec technique → menu safe default, 2e → menu court, 3e → transfert
- user_requested, consent_denied, emergency, no_slots_final → transfert immédiat (pas de budget)
"""
from __future__ import annotations

import uuid

from backend.engine import Engine, create_engine
from backend.session import SessionStore
from backend.tools_faq import FaqStore
from backend import prompts


def _fake_slots(*args, **kwargs):
    return [
        prompts.SlotDisplay(idx=1, label="Mardi 15/01 - 14:00", slot_id=1, start="2026-01-15T14:00:00", day="mardi", hour=14),
        prompts.SlotDisplay(idx=2, label="Mardi 15/01 - 16:00", slot_id=2, start="2026-01-15T16:00:00", day="mardi", hour=16),
        prompts.SlotDisplay(idx=3, label="Jeudi 17/01 - 10:00", slot_id=3, start="2026-01-17T10:00:00", day="jeudi", hour=10),
    ]


def test_transfer_budget_prevents_intent_router_loop_once():
    """2e visite au router → budget prévient, envoie menu safe default (pas de transfert)."""
    store = SessionStore()
    engine = Engine(session_store=store, faq_store=FaqStore(items=[]))
    conv = f"conv_budget_{uuid.uuid4().hex[:8]}"

    # 1) Première entrée au router (3 no-match FAQ)
    engine.handle_message(conv, "xyzabc1")
    engine.handle_message(conv, "xyzabc2")
    e1 = engine.handle_message(conv, "xyzabc3")
    assert e1[0].conv_state == "INTENT_ROUTER"

    # 2) Choisir "3" (question) → retour START
    e2 = engine.handle_message(conv, "trois")
    assert e2[0].conv_state == "START"

    # 3) Re-déclencher le router (3 no-match)
    engine.handle_message(conv, "abcfoo1")
    engine.handle_message(conv, "abcfoo2")
    e3 = engine.handle_message(conv, "abcfoo3")
    # P0 : 2e entrée → budget prévient, menu safe default (pas TRANSFERRED)
    assert e3[0].conv_state == "INTENT_ROUTER"
    assert "rendez-vous" in e3[0].text.lower() or "question" in e3[0].text.lower()
    session = store.get(conv)
    assert session.transfer_budget_remaining == 1


def test_transfer_budget_exhausted_then_transfer():
    """Budget épuisé (2 préventions) → 3e échec technique → transfert."""
    store = SessionStore()
    engine = Engine(session_store=store, faq_store=FaqStore(items=[]))
    conv = f"conv_exhaust_{uuid.uuid4().hex[:8]}"

    # 1) Router 1
    engine.handle_message(conv, "x1")
    engine.handle_message(conv, "x2")
    engine.handle_message(conv, "x3")
    engine.handle_message(conv, "trois")  # question → START

    # 2) Router 2 → budget prévient (remaining=1)
    engine.handle_message(conv, "y1")
    engine.handle_message(conv, "y2")
    e2 = engine.handle_message(conv, "y3")
    assert e2[0].conv_state == "INTENT_ROUTER"

    # 3) À INTENT_ROUTER, dire "hein" 2x → unclear_count=2, budget prévient (remaining=0), reset unclear_count
    engine.handle_message(conv, "hein")
    e3 = engine.handle_message(conv, "hein")
    assert e3[0].conv_state == "INTENT_ROUTER"

    # 4) Encore "hein" 2x (unclear_count repasse à 2 après reset) → budget=0 → transfert
    engine.handle_message(conv, "hein")
    e4 = engine.handle_message(conv, "hein")
    assert e4[0].conv_state == "TRANSFERRED"
    assert e4[0].transfer_reason == "intent_router_unclear"


def test_transfer_budget_does_not_apply_user_requested():
    """User dit 'conseiller' → transfert immédiat (user_requested, pas de budget)."""
    engine = create_engine()
    conv = f"conv_user_req_{uuid.uuid4().hex[:8]}"
    session = engine.session_store.get_or_create(conv)
    session.channel = "vocal"
    session.state = "START"
    engine._save_session(session)

    events = engine.handle_message(conv, "je veux parler a un conseiller")
    assert len(events) >= 1
    assert events[0].conv_state == "TRANSFERRED"
    assert events[0].transfer_reason == "user_requested"
    session = engine.session_store.get(conv)
    assert session.transfer_budget_remaining == 2  # pas consommé


def test_abandon_strict_does_not_trigger_on_cest_bon():
    """P0.4 — 'c'est bon' seul ne doit pas être détecté comme ABANDON (confirmation)."""
    from backend.intent_parser import detect_strong_intent, Intent

    assert detect_strong_intent("c'est bon") is None
    assert detect_strong_intent("cest bon") is None
    assert detect_strong_intent("ok") is None
    assert detect_strong_intent("bon") is None
    # Vrais abandons
    assert detect_strong_intent("au revoir") == Intent.ABANDON
    assert detect_strong_intent("laisse tomber") == Intent.ABANDON


def test_contextual_menu_in_wait_confirm():
    """P0.6 — En WAIT_CONFIRM, _maybe_prevent_transfer renvoie menu contextuel (1/2/3), pas menu global."""
    store = SessionStore()
    engine = Engine(session_store=store, faq_store=FaqStore(items=[]))
    conv = f"conv_ctx_{uuid.uuid4().hex[:8]}"
    session = store.get_or_create(conv)
    session.channel = "vocal"
    session.state = "WAIT_CONFIRM"
    session.slot_proposal_sequential = False  # mode 1/2/3
    session.transfer_budget_remaining = 1
    engine._save_session(session)

    prev = engine._maybe_prevent_transfer(session, "vocal", "slot_choice_fails", "nimportequoi")
    assert prev is not None
    assert prev[0].conv_state == "WAIT_CONFIRM"
    assert "un" in prev[0].text.lower() and "deux" in prev[0].text.lower() and "trois" in prev[0].text.lower()
    assert "rendez-vous" not in prev[0].text.lower()


def test_contextual_menu_in_qualif_contact():
    """P0.6 — En QUALIF_CONTACT, menu contextuel téléphone/email."""
    store = SessionStore()
    engine = Engine(session_store=store, faq_store=FaqStore(items=[]))
    conv = f"conv_ctx2_{uuid.uuid4().hex[:8]}"
    session = store.get_or_create(conv)
    session.channel = "vocal"
    session.state = "QUALIF_CONTACT"
    session.transfer_budget_remaining = 1
    engine._save_session(session)

    prev = engine._maybe_prevent_transfer(session, "vocal", "contact_failed", "xxx")
    assert prev is not None
    assert prev[0].conv_state == "QUALIF_CONTACT"
    assert "téléphone" in prev[0].text.lower() or "telephone" in prev[0].text.lower()
    assert "email" in prev[0].text.lower()
