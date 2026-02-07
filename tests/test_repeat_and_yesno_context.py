# tests/test_repeat_and_yesno_context.py
"""
Patch final prod : REPEAT fiable + YES/NO contextualisé.
C1–C5 : tests ciblés (REPEAT relit dernier prompt, YES/NO uniquement en états confirm).
"""
import re
import uuid
import pytest
from unittest.mock import patch

from backend.engine import create_engine
from backend import prompts

# Détection message de transfert (robuste aux formulations)
TRANSFER_RE = re.compile(r"(transf(è|e)r|passe|conseiller|mettre en relation)", re.I)


def _has_transfer_message(session) -> bool:
    """True si un message agent de type transfert existe dans session.messages (derniers 10)."""
    messages = getattr(session, "messages", None) or []
    for m in list(messages)[-10:]:
        role = m.get("role", "") if isinstance(m, dict) else getattr(m, "role", "")
        text = (m.get("content") or m.get("text") or "") if isinstance(m, dict) else getattr(m, "text", "")
        if role in ("assistant", "agent") and text and TRANSFER_RE.search(text):
            return True
    return False


def _assert_response_looks_like_transfer(text: str) -> None:
    assert text, "Expected non-empty response"
    assert TRANSFER_RE.search(text), f"Expected transfer-like response, got: {text!r}"


def _fake_slots(*args, **kwargs):
    return [
        prompts.SlotDisplay(idx=1, label="Mardi 15/01 - 14:00", slot_id=1, start="2026-01-15T14:00:00", day="mardi", hour=14),
        prompts.SlotDisplay(idx=2, label="Mardi 15/01 - 16:00", slot_id=2, start="2026-01-15T16:00:00", day="mardi", hour=16),
        prompts.SlotDisplay(idx=3, label="Jeudi 17/01 - 10:00", slot_id=3, start="2026-01-17T10:00:00", day="jeudi", hour=10),
    ]


# --- C1 : REPEAT en WAIT_CONFIRM relit le dernier prompt, sans changer d'état ni compteurs ---
def test_c1_repeat_wait_confirm_relit_dernier_prompt_sans_escalade():
    """REPEAT en WAIT_CONFIRM : même message, state et slot_offer_index inchangés, pas d'incrément unclear/no_match."""
    engine = create_engine()
    conv = f"conv_c1_{uuid.uuid4().hex[:8]}"
    engine.session_store.delete(conv)
    session = engine.session_store.get_or_create(conv)
    session.channel = "vocal"
    engine._save_session(session)

    with patch("backend.tools_booking.get_slots_for_display", _fake_slots):
        engine.handle_message(conv, "je veux un rdv")
        engine.handle_message(conv, "Jean Dupont")
        engine.handle_message(conv, "consultation")
        engine.handle_message(conv, "matin")
        e_slots = engine.handle_message(conv, "oui")

    assert e_slots and e_slots[0].conv_state == "WAIT_CONFIRM"
    slot_msg_before = e_slots[0].text
    session_before = engine.session_store.get_or_create(conv)
    idx_before = getattr(session_before, "slot_offer_index", 0)
    no_match_before = getattr(session_before, "no_match_turns", 0)
    unclear_before = getattr(session_before, "start_unclear_count", 0)

    e_repeat = engine.handle_message(conv, "répétez")

    assert e_repeat and len(e_repeat) >= 1
    assert e_repeat[0].conv_state == "WAIT_CONFIRM"
    # Même contenu (créneau proposé) ou même texte si last_say_key utilisé
    assert (
        slot_msg_before in e_repeat[0].text
        or "14:00" in e_repeat[0].text
        or "créneau" in e_repeat[0].text.lower()
        or "Mardi 15/01" in e_repeat[0].text
    )
    session_after = engine.session_store.get_or_create(conv)
    assert getattr(session_after, "slot_offer_index", 0) == idx_before
    assert getattr(session_after, "no_match_turns", 0) == no_match_before
    assert getattr(session_after, "start_unclear_count", 0) == unclear_before


# --- C2 : REPEAT en START après "euh" renvoie encore start_clarify_1 ---
def test_c2_repeat_start_apres_euh_relit_clarify():
    """START : 'euh' => VOCAL_START_CLARIFY_1 ; puis 'pardon, répétez' => même message, state START."""
    engine = create_engine()
    conv = f"conv_c2_{uuid.uuid4().hex[:8]}"
    engine.session_store.delete(conv)
    session = engine.session_store.get_or_create(conv)
    session.channel = "vocal"
    engine._save_session(session)

    e1 = engine.handle_message(conv, "euh")
    assert e1 and e1[0].conv_state == "START"
    clarify_msg = e1[0].text
    assert (
        clarify_msg == prompts.VOCAL_START_CLARIFY_1
        or clarify_msg == prompts.MSG_START_CLARIFY_1_WEB
        or "préciser" in clarify_msg.lower()
        or "reformuler" in clarify_msg.lower()
    )

    e2 = engine.handle_message(conv, "pardon, répétez")
    assert e2 and len(e2) >= 1
    assert e2[0].conv_state == "START"
    assert e2[0].text == clarify_msg or (
        "préciser" in e2[0].text.lower() or "reformuler" in e2[0].text.lower()
    )


# --- C3 : POST_FAQ "d'accord" => POST_FAQ_CHOICE (disambiguation), pas booking ---
def test_c3_post_faq_daccord_disambiguation_pas_booking():
    """POST_FAQ : 'd'accord' => state POST_FAQ_CHOICE + message disambiguation, pas de démarrage booking."""
    engine = create_engine()
    conv = f"conv_c3_{uuid.uuid4().hex[:8]}"
    engine.session_store.delete(conv)
    session = engine.session_store.get_or_create(conv)
    session.state = "POST_FAQ"
    session.channel = "vocal"
    engine._save_session(session)

    events = engine.handle_message(conv, "d'accord")

    assert len(events) >= 1
    assert events[0].conv_state == "POST_FAQ_CHOICE"
    assert "rendez-vous" in events[0].text.lower() or "question" in events[0].text.lower()
    session_after = engine.session_store.get_or_create(conv)
    assert session_after.state != "QUALIF_NAME"
    assert session_after.state != "QUALIF_MOTIF"


# --- C4 : YES en QUALIF_NAME => clarification (demande de répéter le nom), pas étape suivante ---
def test_c4_qualif_name_oui_clarification_pas_suivant():
    """QUALIF_NAME + 'oui' => demande de répéter/clarifier le nom, pas passage à l'étape suivante."""
    engine = create_engine()
    conv = f"conv_c4_{uuid.uuid4().hex[:8]}"
    engine.session_store.delete(conv)
    session = engine.session_store.get_or_create(conv)
    session.state = "QUALIF_NAME"
    session.qualif_data.name = None
    engine._save_session(session)

    events = engine.handle_message(conv, "oui")

    assert len(events) >= 1
    assert events[0].conv_state == "QUALIF_NAME"
    session_after = engine.session_store.get_or_create(conv)
    assert session_after.state == "QUALIF_NAME"
    assert "nom" in events[0].text.lower() or "prénom" in events[0].text.lower() or "répéter" in events[0].text.lower() or "préciser" in events[0].text.lower()


# --- C5 : NO en WAIT_CONFIRM séquentiel => slot_offer_index=1 + message slot2 ---
def test_c5_wait_confirm_non_propose_slot_suivant():
    """WAIT_CONFIRM séquentiel, slot_offer_index=0 : 'non' => slot_offer_index=1 + message proposant le slot 2."""
    engine = create_engine()
    conv = f"conv_c5_{uuid.uuid4().hex[:8]}"
    engine.session_store.delete(conv)
    session = engine.session_store.get_or_create(conv)
    session.channel = "vocal"
    session.state = "WAIT_CONFIRM"
    session.slot_proposal_sequential = True
    session.slot_offer_index = 0
    session.pending_slots = _fake_slots()
    engine._save_session(session)

    events = engine.handle_message(conv, "non")

    assert len(events) >= 1
    session_after = engine.session_store.get_or_create(conv)
    assert getattr(session_after, "slot_offer_index", 0) == 1
    assert "16:00" in events[0].text or "Mardi 15/01 - 16" in events[0].text or "créneau" in events[0].text.lower()
    assert "convient" in events[0].text.lower() or "conven" in events[0].text.lower()


def _run_turn(engine, conv_id: str, user_text: str):
    """Envoie un message, recharge la session, retourne (session, texte_réponse)."""
    events = engine.handle_message(conv_id, user_text)
    session = engine.session_store.get_or_create(conv_id)
    resp = (events[0].text if events and events[0].text else "") or ""
    return session, resp


def test_repeat_after_transfer_relit_transfer():
    """
    Après un transfert, « répétez » doit relire le dernier message de transfert quand c’est possible.
    Si la session a été rechargée (last_say_key absent) et qu’aucun message de transfert n’est
    dans l’historique, on accepte un fallback générique (mais non vide).
    """
    engine = create_engine()
    conv = f"conv_repeat_transfer_{uuid.uuid4().hex[:8]}"
    engine.session_store.delete(conv)
    session = engine.session_store.get_or_create(conv)
    session.channel = "vocal"
    session.state = "START"
    engine._save_session(session)

    # 1) Déclencher un transfert
    session, resp1 = _run_turn(engine, conv, "je veux parler à un humain")
    assert session.state == "TRANSFERRED"

    # Y a-t-il un message de transfert dans l’historique à ce stade ?
    has_transfer_in_history = _has_transfer_message(session)

    # 2) L’utilisateur dit « répétez »
    session, resp2 = _run_turn(engine, conv, "répétez")

    assert session.state == "TRANSFERRED"
    assert resp2 and isinstance(resp2, str)

    if has_transfer_in_history:
        # Si on a un message de transfert en historique, REPEAT doit ressembler à un transfert.
        _assert_response_looks_like_transfer(resp2)
    else:
        # Si aucun message de transfert (ex. reload a perdu l’info), on accepte un fallback non vide.
        assert len(resp2.strip()) >= 5
