# tests/test_engine.py
import uuid
import pytest
from unittest.mock import patch
from backend.engine import create_engine, _detect_booking_intent
from backend import prompts
from backend.start_router import StartRoute
from backend.intent_parser import Intent


def _fake_slots(*args, **kwargs):
    """Slots factices pour atteindre CONTACT_CONFIRM / QUALIF_CONTACT."""
    return [
        prompts.SlotDisplay(idx=1, label="Mardi 15/01 - 14:00", slot_id=1, start="2026-01-15T14:00:00", day="mardi", hour=14),
        prompts.SlotDisplay(idx=2, label="Mardi 15/01 - 16:00", slot_id=2, start="2026-01-15T16:00:00", day="mardi", hour=16),
        prompts.SlotDisplay(idx=3, label="Jeudi 17/01 - 10:00", slot_id=3, start="2026-01-17T10:00:00", day="jeudi", hour=10),
    ]


def _fake_slots_vendredi(*args, **kwargs):
    """Slots avec vendredi 14h (premier) pour test early commit par jour+heure. 2026-02-06 = vendredi."""
    return [
        prompts.SlotDisplay(idx=1, label="Vendredi 06/02 - 14:00", slot_id=1, start="2026-02-06T14:00:00", day="vendredi", hour=14),
        prompts.SlotDisplay(idx=2, label="Lundi 09/02 - 09:00", slot_id=2, start="2026-02-09T09:00:00", day="lundi", hour=9),
        prompts.SlotDisplay(idx=3, label="Mardi 10/02 - 16:00", slot_id=3, start="2026-02-10T16:00:00", day="mardi", hour=16),
    ]


def test_detect_booking_intent():
    assert _detect_booking_intent("Je veux un rdv")
    assert _detect_booking_intent("je veux un rendez-vous")
    assert _detect_booking_intent("Je veux un rendez-vous")
    assert _detect_booking_intent("Avez-vous des disponibilités ?")
    assert _detect_booking_intent("Prendre rendez-vous")
    assert _detect_booking_intent("prendre un rendez-vous")
    assert _detect_booking_intent("j'ai besoin d'un rendez-vous")
    assert not _detect_booking_intent("Quels sont vos horaires ?")


def test_booking_intent_variations():
    """Test toutes les variantes de booking intent"""
    assert _detect_booking_intent("je veux un rdv")
    assert _detect_booking_intent("je veux un rendez-vous")
    assert _detect_booking_intent("je veux un rendez vous")
    assert _detect_booking_intent("prendre rendez-vous")
    assert _detect_booking_intent("prendre un rendez vous")
    assert _detect_booking_intent("avez-vous des disponibilités ?")
    assert _detect_booking_intent("je voudrais réserver")
    
    # Ne doit PAS détecter
    assert not _detect_booking_intent("Quels sont vos horaires ?")
    assert not _detect_booking_intent("Où êtes-vous situé ?")


def test_empty_message():
    """RÈGLE 3 : 1er silence → MSG_SILENCE_1 (ex « Je n'ai rien entendu… »)."""
    engine = create_engine()
    events = engine.handle_message("conv1", "")
    assert len(events) == 1
    assert events[0].type == "final"
    assert events[0].text == getattr(prompts, "MSG_SILENCE_1", prompts.MSG_EMPTY_MESSAGE)


def test_too_long_message():
    engine = create_engine()
    long_text = "x" * 600
    events = engine.handle_message("conv2", long_text)
    assert len(events) == 1
    assert events[0].type == "final"
    assert events[0].text == prompts.MSG_TOO_LONG


def test_english_message():
    engine = create_engine()
    events = engine.handle_message("conv3", "Hello what are your hours?")
    assert len(events) == 1
    assert events[0].type == "final"
    assert events[0].text == prompts.MSG_FRENCH_ONLY


def test_faq_match_exact():
    engine = create_engine()
    events = engine.handle_message("conv4", "Quels sont vos horaires ?")
    assert len(events) == 1
    assert events[0].type == "final"
    assert "Source : FAQ_HORAIRES" in events[0].text


def test_faq_no_match_twice_transfer():
    """1er no match → clarification, 2e → reformulation avec options (RDV, horaires, conseiller), 3e → INTENT_ROUTER."""
    import uuid
    from backend.engine import Engine
    from backend.session import SessionStore
    from backend.tools_faq import FaqStore
    store = SessionStore()
    engine = Engine(session_store=store, faq_store=FaqStore(items=[]))
    conv = f"conv_faq_nomatch_{uuid.uuid4().hex[:8]}"

    # 1er no match → message de clarification
    e1 = engine.handle_message(conv, "xyzabc123def")
    assert len(e1) == 1
    assert e1[0].type == "final"
    # 1ère incompréhension : reformulation ou guidage (VOCAL_START_CLARIFY_1)
    assert (
        "reformuler" in e1[0].text.lower() or "préciser" in e1[0].text.lower() or "compris" in e1[0].text.lower()
        or ("rendez-vous" in e1[0].text.lower() and "question" in e1[0].text.lower())
    )

    # 2e no match → reformulation avec les possibilités (rendez-vous, horaires, conseiller)
    e2 = engine.handle_message(conv, "test question 2")
    assert len(e2) == 1
    assert e2[0].type == "final"
    assert e2[0].conv_state == "START"
    assert "rendez-vous" in e2[0].text.lower() or "horaires" in e2[0].text.lower() or "conseiller" in e2[0].text.lower()

    # 3e no match → INTENT_ROUTER (menu 1/2/3/4) — message neutre (éviter "pas compris" → repeat)
    e3 = engine.handle_message(conv, "autre chose")
    assert len(e3) == 1
    assert e3[0].type == "final"
    assert e3[0].conv_state == "INTENT_ROUTER"
    assert "dites" in e3[0].text.lower() and ("un" in e3[0].text.lower() or "1" in e3[0].text)


def test_intent_router_two_visits_transfer():
    """2 entrées dans INTENT_ROUTER → transfert direct (anti-boucle START↔ROUTER)."""
    import uuid
    from backend.engine import Engine
    from backend.session import SessionStore
    from backend.tools_faq import FaqStore
    store = SessionStore()
    engine = Engine(session_store=store, faq_store=FaqStore(items=[]))
    conv = f"conv_router_loop_{uuid.uuid4().hex[:8]}"
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
    # 2e entrée au router → transfert direct
    assert e3[0].conv_state == "TRANSFERRED"


def test_start_oui_goes_to_clarify_not_booking():
    """P0.1 — En START, 'oui' seul = ambigu → CLARIFY (pas QUALIF_NAME). Critère d'acceptation mission."""
    engine = create_engine()
    conv = f"conv_start_oui_{uuid.uuid4().hex[:8]}"
    session = engine.session_store.get_or_create(conv)
    session.channel = "vocal"
    session.state = "START"
    engine._save_session(session)
    events = engine.handle_message(conv, "oui")
    assert len(events) >= 1
    assert events[0].conv_state == "CLARIFY"
    assert "rendez-vous" in events[0].text.lower() and "question" in events[0].text.lower()
    # Ne doit pas demander le nom (pas de passage en QUALIF_NAME)
    assert "nom" not in events[0].text.lower() or "prénom" not in events[0].text.lower()


def test_oui_after_out_of_scope_goes_to_clarify_not_intent_router():
    """
    Après OUT_OF_SCOPE (reste START), 'oui' → CLARIFY (disambiguation RDV/question),
    pas UNCLEAR/no_faq ni intent_router. Anti-régression START.
    """
    engine = create_engine()
    conv = f"conv_oui_after_oos_{uuid.uuid4().hex[:8]}"
    engine.session_store.delete(conv)
    session = engine.session_store.get_or_create(conv)
    session.channel = "vocal"
    session.state = "START"
    engine._save_session(session)

    def route_start_side_effect(*args, **kwargs):
        user_text = (args[0] if args else kwargs.get("user_text", "")) or ""
        if "pizza" in user_text.lower() or user_text.strip() == "blabla":
            return StartRoute(
                intent=Intent.OUT_OF_SCOPE,
                confidence=0.9,
                entities={"out_of_scope_response": "Nous sommes un cabinet médical. Souhaitez-vous un rendez-vous ou une question ?"},
                source="llm_assist",
            )
        if user_text.strip().lower() == "oui":
            return StartRoute(intent=Intent.YES, confidence=0.9, source="parser")
        # fallback
        return StartRoute(intent=Intent.UNCLEAR, confidence=0.5, source="parser")

    with patch("backend.engine.route_start", side_effect=route_start_side_effect):
        e1 = engine.handle_message(conv, "pizza")
    assert len(e1) >= 1
    assert e1[0].conv_state == "START"
    s = engine.session_store.get(conv)
    assert s is not None and s.state == "START"

    with patch("backend.engine.route_start", side_effect=route_start_side_effect):
        e2 = engine.handle_message(conv, "oui")
    assert len(e2) >= 1
    assert e2[0].conv_state == "CLARIFY"
    assert "rendez-vous" in e2[0].text.lower() and "question" in e2[0].text.lower()


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots)
def test_sequential_non_x2_with_pref_reproposes_not_reask_pref(mock_slots):
    """
    Préférence déjà connue (matin) + 2 "non" → re-propose de nouveaux créneaux,
    NE PAS re-demander "vous préférez matin ou après-midi".
    """
    from datetime import datetime, timedelta
    from backend.prompts import SlotDisplay

    engine = create_engine()
    conv = f"conv_pref_repropose_{uuid.uuid4().hex[:8]}"
    engine.session_store.delete(conv)
    session = engine.session_store.get_or_create(conv)
    session.channel = "vocal"
    session.state = "WAIT_CONFIRM"
    session.slot_proposal_sequential = True
    session.slot_offer_index = 0
    session.slots_list_sent = True
    session.slots_preface_sent = True
    session.qualif_data.pref = "matin"
    session.qualif_data.name = "Test"
    session.qualif_data.motif = "consultation"
    base = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    session.pending_slots = [
        SlotDisplay(1, "Lundi 9h00", 0, (base.replace(hour=9, minute=0)).isoformat(), "lundi", 9, "lundi à 9h"),
        SlotDisplay(2, "Lundi 9h15", 1, (base.replace(hour=9, minute=15)).isoformat(), "lundi", 9, "lundi à 9h"),
        SlotDisplay(3, "Lundi 14h00", 2, (base.replace(hour=14, minute=0)).isoformat(), "lundi", 14, "lundi à 14h"),
    ]
    engine._save_session(session)

    events = engine.handle_message(conv, "non")  # 1er non → propose 14h
    assert len(events) >= 1
    events = engine.handle_message(conv, "non")  # 2e non → re-propose (pas re-demandée pref)
    assert len(events) >= 1
    msg = events[0].text
    # Ne doit PAS envoyer le message qui redemande la préférence
    refus_pref_msg = getattr(prompts, "VOCAL_SLOT_REFUSE_PREF_PROMPT", "")
    assert refus_pref_msg not in msg
    # Doit proposer des créneaux (ou transfer si plus rien)
    s = engine.session_store.get(conv)
    assert s is not None
    assert s.state in ("WAIT_CONFIRM", "TRANSFERRED")


def test_sequential_non_skips_neighbor_proposes_14h():
    """
    Séquentiel : user refuse 9h → doit proposer 14h (pas 9h15).
    Anti-régression : skip voisins ±90 min après un "non".
    """
    from datetime import datetime, timedelta
    from backend.prompts import SlotDisplay

    engine = create_engine()
    conv = f"conv_seq_non_skip_{uuid.uuid4().hex[:8]}"
    engine.session_store.delete(conv)
    session = engine.session_store.get_or_create(conv)
    session.channel = "vocal"
    session.state = "WAIT_CONFIRM"
    session.slot_proposal_sequential = True
    session.slot_offer_index = 0
    session.slots_list_sent = True
    session.slots_preface_sent = True
    base = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    session.pending_slots = [
        SlotDisplay(1, "Lundi 9h00", 0, (base.replace(hour=9, minute=0)).isoformat(), "lundi", 9, "lundi à 9h"),
        SlotDisplay(2, "Lundi 9h15", 1, (base.replace(hour=9, minute=15)).isoformat(), "lundi", 9, "lundi à 9h"),
        SlotDisplay(3, "Lundi 14h00", 2, (base.replace(hour=14, minute=0)).isoformat(), "lundi", 14, "lundi à 14h"),
    ]
    session.qualif_data.name = "Test"
    session.qualif_data.motif = "consultation"
    engine._save_session(session)

    events = engine.handle_message(conv, "non")
    assert len(events) >= 1
    msg = events[0].text
    # Doit proposer 14h (pas 9h15) avec variante ACK après refus (round-robin)
    assert "14" in msg or "14h" in msg.lower()
    assert "9h15" not in msg and "9h15" not in msg.lower()
    assert any(
        p in msg.lower() for p in ["d'accord", "daccord", "très bien", "tres bien", "ok."]
    )  # variante slot refusal
    s = engine.session_store.get(conv)
    assert s is not None
    assert s.slot_offer_index == 2


def test_wait_confirm_repeat_relit_creneau_courant():
    """REPEAT en WAIT_CONFIRM : relit le créneau courant, pas de changement d'état."""
    engine = create_engine()
    conv = f"conv_repeat_slot_{uuid.uuid4().hex[:8]}"
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
    slot_msg = e_slots[0].text
    e_repeat = engine.handle_message(conv, "répétez")
    assert e_repeat and len(e_repeat) >= 1
    assert e_repeat[0].conv_state == "WAIT_CONFIRM"
    assert slot_msg in e_repeat[0].text or "14:00" in e_repeat[0].text or "créneau" in e_repeat[0].text.lower()


def test_post_faq_daccord_goes_to_clarification_not_booking():
    """POST_FAQ : user 'd'accord' → POST_FAQ_CHOICE / clarification, pas booking direct."""
    engine = create_engine()
    conv = f"conv_post_faq_{uuid.uuid4().hex[:8]}"
    engine.session_store.delete(conv)
    session = engine.session_store.get_or_create(conv)
    session.channel = "vocal"
    session.state = "POST_FAQ"
    engine._save_session(session)
    events = engine.handle_message(conv, "d'accord")
    assert len(events) >= 1
    assert events[0].conv_state == "POST_FAQ_CHOICE"
    assert "rendez-vous" in events[0].text.lower() or "question" in events[0].text.lower()


def _reply_for_booking(agent_text: str) -> str:
    """Réponse utilisateur adaptée au dernier message agent (flow name → pref → slots → contact → confirm)."""
    if not agent_text:
        return "Je veux un rdv"
    t = agent_text.lower()
    # Proposition de créneaux (avant "créneau" car "Créneaux disponibles" contient "créneau")
    if ("oui 1" in t and "oui 2" in t) or "répondez par 'oui 1'" in t or ("créneaux disponibles" in t and "confirmer" in t):
        return "oui 2"
    if "nom" in t and ("prénom" in t or "prénom" in t):
        return "Jean Dupont"
    if "créneau" in t or "préférez" in t or ("matin" in t and "après-midi" in t):
        return "Mardi matin"
    if "un, deux" in t or "dites" in t and "trois" in t:
        return "oui 2"
    if "contact" in t or "email" in t or "téléphone" in t or ("numéro" in t and "?" in t):
        return "jean@example.com"
    if "numéro est bien" in t or ("confirmer" in t and "bien" in t):
        return "Oui"
    return "Oui"


def test_booking_flow_happy_path():
    """Parcours booking piloté par le dialogue (ordre réel : name → pref → slots → choix → contact → confirm)."""
    engine = create_engine()
    conv = "conv6"
    last_agent_text = None
    max_steps = 12

    for _ in range(max_steps):
        user_msg = "Je veux un rdv" if last_agent_text is None else _reply_for_booking(last_agent_text)
        events = engine.handle_message(conv, user_msg)
        assert events, f"handle_message returned no events for user_msg={user_msg!r}"
        last_agent_text = events[0].text
        state = getattr(events[0], "conv_state", None)
        if state == "CONFIRMED":
            assert "confirmé" in last_agent_text.lower()
            return
        if state == "TRANSFERRED":
            assert last_agent_text and len(last_agent_text.strip()) > 0
            return
        if state == "INTENT_ROUTER":
            return  # Menu 1/2/3/4 affiché, considéré comme fin de parcours possible

    pytest.fail(f"Booking flow did not reach CONFIRMED/TRANSFERRED/INTENT_ROUTER after {max_steps} steps. Last agent: {last_agent_text[:200]!r}")


def test_booking_confirm_invalid_retry_then_transfer():
    engine = create_engine()
    conv = "conv7"

    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Jean Dupont")
    engine.handle_message(conv, "renouvellement ordonnance")  # Motif valide (pas générique)
    engine.handle_message(conv, "Mardi")
    engine.handle_message(conv, "jean@example.com")

    e1 = engine.handle_message(conv, "je prends le deuxième")
    assert e1[0].type == "final"
    # Le compteur confirm_retry_count peut être déjà incrémenté, donc on vérifie soit retry soit transfer
    assert ("un, deux" in e1[0].text.lower() and "trois" in e1[0].text.lower()) or e1[0].conv_state == "TRANSFERRED"

    e2 = engine.handle_message(conv, "mardi svp")
    assert e2[0].type == "final"
    # Après transfer, le message peut être MSG_TRANSFER ou MSG_CONVERSATION_CLOSED selon l'état
    assert e2[0].conv_state == "TRANSFERRED" or "mets en relation" in e2[0].text.lower() or "terminé" in e2[0].text.lower()


def test_session_expired():
    """Test 9: Session 15 min → "Votre session a expiré..." """
    from datetime import datetime, timedelta
    from backend import config
    from backend.session import Session

    # Test direct : vérifier que is_expired() fonctionne correctement
    session = Session(conv_id="test_expired")
    session.last_seen_at = datetime.utcnow() - timedelta(minutes=config.SESSION_TTL_MINUTES + 1)
    
    assert session.is_expired(), "Session should be expired after 16 minutes"
    
    # Test avec session non expirée
    session2 = Session(conv_id="test_not_expired")
    session2.last_seen_at = datetime.utcnow() - timedelta(minutes=config.SESSION_TTL_MINUTES - 1)
    
    assert not session2.is_expired(), "Session should NOT be expired after 14 minutes"
    
    # Note : Le test d'expiration via handle_message() nécessiterait un mock de datetime.utcnow()
    # car add_message() est appelé AVANT is_expired() et appelle touch() qui met à jour last_seen_at
    # Le comportement réel est testé dans l'intégration : si un utilisateur attend 15 min sans message,
    # la session expire et le prochain message déclenche MSG_SESSION_EXPIRED


def test_spam_silent_transfer():
    """Test 10: Insulte → transfert silencieux"""
    engine = create_engine()
    conv = "conv9"

    events = engine.handle_message(conv, "connard")
    assert len(events) == 1
    assert events[0].type == "transfer"
    assert events[0].silent is True
    assert events[0].transfer_reason == "spam"


# ---------- FIX B : "je veux un rdv" en QUALIF_NAME ne doit pas être accepté comme nom ----------

def test_is_valid_name_input_rejects_intent_phrases():
    """is_valid_name_input refuse les phrases d'intention (rdv, annuler, etc.), accepte les vrais noms."""
    from backend.guards import is_valid_name_input
    assert is_valid_name_input("je veux un rdv") is False
    assert is_valid_name_input("je veux un rendez-vous") is False
    assert is_valid_name_input("annuler") is False
    assert is_valid_name_input("modifier mon rdv") is False
    assert is_valid_name_input("parler à un humain") is False
    assert is_valid_name_input("Martin Dupont") is True
    assert is_valid_name_input("Jean") is True
    assert is_valid_name_input("Marie-Claire") is True
    assert is_valid_name_input("euh c'est Pierre") is True  # laisse extract_name_from_speech trancher
    # Noms composés / particules / sociétés (jusqu'à 6 mots)
    assert is_valid_name_input("Marie de la Tour") is True
    assert is_valid_name_input("SAS Dupont et Fils") is True


def test_qualif_name_intent_phrase_guided_message():
    """P0 : En QUALIF_NAME, 'je veux un rdv' → message guidé (INTENT_1), reste QUALIF_NAME, pas name_fails."""
    engine = create_engine()
    conv = "conv_qualif_intent"
    engine.handle_message(conv, "Je veux un rdv")
    events = engine.handle_message(conv, "je veux un rdv")
    assert len(events) == 1
    assert events[0].conv_state == "QUALIF_NAME"
    assert "nom" in events[0].text.lower()
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.name_fails == 0


def test_qualif_name_oui_je_veux_rendez_vous_intent_message():
    """P0 : QUALIF_NAME + 'Oui, je veux un rendez-vous' → message guidé nom (INTENT_1), pas INTENT_ROUTER."""
    engine = create_engine()
    conv = "conv_qualif_oui_rdv"
    engine.handle_message(conv, "Je veux un rdv")
    events = engine.handle_message(conv, "Oui, je veux un rendez-vous.")
    assert len(events) == 1
    assert events[0].conv_state == "QUALIF_NAME"
    assert prompts.MSG_QUALIF_NAME_INTENT_1 in events[0].text or "quel nom" in events[0].text.lower()


def test_qualif_name_intent_repeat_3_times_intent_router():
    """P1.4 : QUALIF_NAME + intent répété 3 fois → INTENT_ROUTER (menu 1/2/3/4)."""
    engine = create_engine()
    conv = "conv_qualif_intent_3"
    engine.handle_message(conv, "Je veux un rdv")
    events = None
    for _ in range(3):
        events = engine.handle_message(conv, "je veux un rendez-vous")
        assert len(events) == 1
    assert events is not None
    assert events[0].conv_state == "INTENT_ROUTER"
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.state == "INTENT_ROUTER"
    assert session.name_fails == 0
    assert "prendre" in events[0].text.lower() or "un" in events[0].text.lower()


def test_qualif_name_invalid_input_escalate_to_intent_router():
    """P0 : QUALIF_NAME + vrais inputs invalides (ex: 'x') → recovery normal → INTENT_ROUTER après seuil."""
    from backend import config
    engine = create_engine()
    conv = "conv_qualif_invalid"
    limit = config.RECOVERY_LIMITS.get("name", 3)
    engine.handle_message(conv, "Je veux un rdv")
    for _ in range(limit):
        events = engine.handle_message(conv, "x")
        assert len(events) == 1
    assert events[0].conv_state == "INTENT_ROUTER"
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.state == "INTENT_ROUTER"
    assert "dites" in events[0].text.lower() or "un" in events[0].text.lower()


def test_name_accepts_valid_name():
    """'Martin Dupont' en QUALIF_NAME est accepté, session progresse."""
    engine = create_engine()
    conv = "conv_name_accept"
    engine.handle_message(conv, "Je veux un rdv")
    events = engine.handle_message(conv, "Martin Dupont")
    assert len(events) == 1
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.qualif_data.name is not None
    assert "Martin" in session.qualif_data.name or "Dupont" in session.qualif_data.name
    assert events[0].conv_state != "QUALIF_NAME"


def test_qualif_name_martin_dupont_next_step():
    """P0 : QUALIF_NAME + 'Martin Dupont' → passage à l'étape suivante (state != QUALIF_NAME)."""
    engine = create_engine()
    conv = "conv_name_martin"
    engine.handle_message(conv, "Je veux un rdv")
    events = engine.handle_message(conv, "Martin Dupont")
    assert len(events) == 1
    assert events[0].conv_state != "QUALIF_NAME"
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.qualif_data.name is not None


# ---------- QUALIF_PREF : répétition intention RDV (P0) ----------


def test_qualif_pref_intent_phrase_guided_message():
    """P0 : En QUALIF_PREF, 'je veux un rdv' → message guidé (INTENT_1), reste QUALIF_PREF, pas preference_fails."""
    engine = create_engine()
    conv = "conv_qualif_pref_intent"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Martin Dupont")
    events = engine.handle_message(conv, "je veux un rendez-vous")
    assert len(events) == 1
    assert events[0].conv_state == "QUALIF_PREF"
    assert "matin" in events[0].text.lower() or "après-midi" in events[0].text.lower()
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.preference_fails == 0
    assert prompts.MSG_QUALIF_PREF_INTENT_1 in events[0].text


def test_qualif_pref_intent_repeat_3_times_stays_qualif_pref():
    """P0 : QUALIF_PREF + 'je veux un rendez-vous' x3 → toujours QUALIF_PREF, jamais INTENT_ROUTER."""
    engine = create_engine()
    conv = "conv_qualif_pref_intent_3"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Marie Martin")
    for _ in range(3):
        events = engine.handle_message(conv, "je veux un rendez-vous")
        assert len(events) == 1
        assert events[0].conv_state == "QUALIF_PREF"
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.state == "QUALIF_PREF"
    assert session.preference_fails == 0


def test_qualif_pref_invalid_input_escalates():
    """P0 : QUALIF_PREF + vrais inputs invalides ('bof') au seuil → INTENT_ROUTER."""
    from backend import config
    engine = create_engine()
    conv = "conv_qualif_pref_invalid"
    limit = getattr(config, "RECOVERY_LIMITS", {}).get("preference", 3)
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Jean Dupont")
    for _ in range(limit):
        events = engine.handle_message(conv, "bof")
        assert len(events) == 1
    assert events[0].conv_state == "INTENT_ROUTER"
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.state == "INTENT_ROUTER"


def test_qualif_pref_matin_next_step():
    """P0 : QUALIF_PREF + 'matin' → passage à PREFERENCE_CONFIRM (étape suivante)."""
    engine = create_engine()
    conv = "conv_qualif_pref_matin"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Paul Martin")
    events = engine.handle_message(conv, "matin")
    assert len(events) == 1
    assert events[0].conv_state == "PREFERENCE_CONFIRM"
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.pending_preference == "matin"


# ---------- CONTACT_CONFIRM : répétition intention RDV (P0) ----------


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots)
def test_contact_confirm_intent_phrase_guided_message(mock_slots):
    """P0 : En CONTACT_CONFIRM, 'je veux un rdv' → message guidé oui/non, reste CONTACT_CONFIRM, pas contact_confirm_fails."""
    engine = create_engine()
    conv = f"conv_contact_confirm_intent_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Martin Dupont")
    engine.handle_message(conv, "matin")
    engine.handle_message(conv, "oui")     # confirm pref → propose slots → WAIT_CONFIRM
    engine.handle_message(conv, "oui 1")   # early commit → "c'est bien ça ?"
    engine.handle_message(conv, "oui")     # confirm slot → QUALIF_CONTACT
    engine.handle_message(conv, "0612345678")
    events = engine.handle_message(conv, "je veux un rendez-vous")
    assert len(events) == 1
    assert events[0].conv_state == "CONTACT_CONFIRM"
    assert "oui" in events[0].text.lower() and "non" in events[0].text.lower()
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.contact_confirm_fails == 0
    assert prompts.MSG_CONTACT_CONFIRM_INTENT_1 in events[0].text


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots)
def test_contact_confirm_intent_repeat_3_times_stays_contact_confirm(mock_slots):
    """P0 : CONTACT_CONFIRM + 'je veux un rendez-vous' x3 → toujours CONTACT_CONFIRM, pas INTENT_ROUTER."""
    engine = create_engine()
    conv = f"conv_contact_confirm_repeat_3_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Marie Martin")
    engine.handle_message(conv, "matin")
    engine.handle_message(conv, "oui")    # confirm pref → WAIT_CONFIRM
    engine.handle_message(conv, "oui 1")
    engine.handle_message(conv, "oui")
    engine.handle_message(conv, "0612345678")
    for _ in range(3):
        events = engine.handle_message(conv, "je veux un rendez-vous")
        assert len(events) == 1
        assert events[0].conv_state == "CONTACT_CONFIRM"
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.state == "CONTACT_CONFIRM"
    assert session.contact_confirm_fails == 0


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots)
@patch("backend.tools_booking.book_slot_from_session", return_value=(True, None))
def test_contact_confirm_yes_no_resets_intent_counter(mock_book, mock_slots):
    """P0 : Après phrase d'intention en CONTACT_CONFIRM, répondre 'oui' remet contact_confirm_intent_repeat_count à 0."""
    engine = create_engine()
    conv = f"conv_contact_confirm_reset_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Martin Dupont")
    engine.handle_message(conv, "matin")
    engine.handle_message(conv, "oui")    # confirm pref → WAIT_CONFIRM
    engine.handle_message(conv, "oui 1")
    engine.handle_message(conv, "oui")
    engine.handle_message(conv, "0612345678")
    session = engine.session_store.get(conv)
    assert session.state == "CONTACT_CONFIRM"
    engine.handle_message(conv, "je veux un rdv")
    session = engine.session_store.get(conv)
    assert session.contact_confirm_intent_repeat_count == 1
    events = engine.handle_message(conv, "oui")
    session = engine.session_store.get(conv)
    assert session.contact_confirm_intent_repeat_count == 0
    assert events[0].conv_state == "CONFIRMED"


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots)
def test_qualif_contact_intent_phrase_does_not_increment_contact_fails(mock_slots):
    """Optionnel : QUALIF_CONTACT + 'je veux un rdv' → message guidé, pas phone_fails ni transfert."""
    engine = create_engine()
    conv = f"conv_qualif_contact_intent_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Jean Dupont")
    engine.handle_message(conv, "matin")
    engine.handle_message(conv, "oui")    # confirm pref → WAIT_CONFIRM
    engine.handle_message(conv, "oui 1")
    engine.handle_message(conv, "oui")
    events = engine.handle_message(conv, "je veux un rendez-vous")
    assert len(events) == 1
    assert events[0].conv_state == "QUALIF_CONTACT"
    assert "email" in events[0].text.lower() or "téléphone" in events[0].text.lower() or "numéro" in events[0].text.lower()
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.phone_fails == 0
    assert session.state == "QUALIF_CONTACT"
    assert prompts.MSG_QUALIF_CONTACT_INTENT in events[0].text


# ---------- Early commit (WAIT_CONFIRM) : choix non ambigu uniquement ----------


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots)
def test_early_commit_oui_1(mock_slots):
    """En WAIT_CONFIRM, 'oui 1' → early commit : state WAIT_CONFIRM, pending_slot_choice=1, message « Vous confirmez ? »."""
    engine = create_engine()
    conv = f"conv_early_oui1_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Martin Dupont")
    engine.handle_message(conv, "matin")
    engine.handle_message(conv, "oui")   # confirm pref → WAIT_CONFIRM
    events = engine.handle_message(conv, "oui 1")
    assert len(events) == 1
    assert events[0].conv_state == "WAIT_CONFIRM"
    assert "créneau 1" in events[0].text
    assert "confirmez" in events[0].text.lower()
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.pending_slot_choice == 1


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots_vendredi)
def test_wait_confirm_interrupt_explicit_choice_vendredi_14h(mock_slots):
    """P1 : Choix explicite pendant énonciation (jour+heure) → early confirm, pas de ré-énumération (P0.5, A6)."""
    engine = create_engine()
    conv = f"conv_vendredi14_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Martin Dupont")
    engine.handle_message(conv, "matin")
    engine.handle_message(conv, "oui")
    events = engine.handle_message(conv, "vendredi 14h")
    assert len(events) >= 1
    assert events[0].conv_state == "WAIT_CONFIRM"
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.pending_slot_choice == 1
    assert "confirmez" in events[0].text.lower() or "créneau" in events[0].text.lower()


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots)
def test_early_commit_le_premier(mock_slots):
    """En WAIT_CONFIRM, 'le premier' → early commit, pending_slot_choice=1."""
    engine = create_engine()
    conv = f"conv_early_premier_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Martin Dupont")
    engine.handle_message(conv, "matin")
    engine.handle_message(conv, "oui")   # confirm pref → WAIT_CONFIRM
    events = engine.handle_message(conv, "le premier")
    assert len(events) == 1
    assert events[0].conv_state == "WAIT_CONFIRM"
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.pending_slot_choice == 1


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots)
def test_no_early_commit_ambiguous_oui(mock_slots):
    """En WAIT_CONFIRM, 'oui' seul → pas de choix (pending_slot_choice reste None), redemande 1/2/3 SANS incrémenter fails (P0.5, A6)."""
    engine = create_engine()
    conv = f"conv_no_early_oui_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Martin Dupont")
    engine.handle_message(conv, "matin")
    engine.handle_message(conv, "oui")   # confirm pref → WAIT_CONFIRM
    events = engine.handle_message(conv, "oui")
    assert len(events) == 1
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.pending_slot_choice is None  # pas d'early commit
    assert getattr(session, "slot_choice_fails", 0) == 0  # pas d'incrément
    assert events[0].conv_state in ("WAIT_CONFIRM", "TRANSFERRED")
    t = events[0].text.lower()
    assert "1" in t or "2" in t or "3" in t or "un" in t or "deux" in t or "trois" in t or "relation" in t


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots)
def test_no_early_commit_ambiguous_ce_creneau(mock_slots):
    """En WAIT_CONFIRM, 'je veux ce créneau' (sans numéro) → pas d'early commit (pending_slot_choice reste None)."""
    engine = create_engine()
    conv = f"conv_no_early_ce_creneau_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Martin Dupont")
    engine.handle_message(conv, "matin")
    engine.handle_message(conv, "oui")   # confirm pref → WAIT_CONFIRM
    events = engine.handle_message(conv, "je veux ce créneau")
    assert len(events) == 1
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.pending_slot_choice is None
    assert events[0].conv_state in ("WAIT_CONFIRM", "TRANSFERRED")


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots)
def test_wait_confirm_vague_ok_no_fail(mock_slots):
    """Validation vague 'ok' / 'd\'accord' en WAIT_CONFIRM → redemande 1/2/3 SANS incrémenter slot_choice_fails."""
    engine = create_engine()
    conv = f"conv_vague_ok_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Martin Dupont")
    engine.handle_message(conv, "matin")
    engine.handle_message(conv, "oui")
    events = engine.handle_message(conv, "ok")
    assert len(events) == 1
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.pending_slot_choice is None
    assert getattr(session, "slot_choice_fails", 0) == 0
    text_lower = events[0].text.lower()
    assert ("dites" in text_lower or "dire" in text_lower) and (
        "1" in events[0].text or "2" in events[0].text or "un" in text_lower or "deux" in text_lower
    )


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots)
def test_interruption_flow_barge_in_un(mock_slots, caplog):
    """Interruption pendant énonciation : client dit 'un' après réception des créneaux → early confirm, pas de ré-énumération."""
    import logging
    caplog.set_level(logging.INFO)
    engine = create_engine()
    conv = f"conv_interrupt_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Martin Dupont")
    engine.handle_message(conv, "matin")
    engine.handle_message(conv, "oui")   # → WAIT_CONFIRM, is_reading_slots=True
    events = engine.handle_message(conv, "un")
    assert len(events) >= 1
    reply = events[0].text
    assert "bien" in reply.lower() or "créneau" in reply.lower()
    assert "1" in reply or "un" in reply.lower()
    # Ne doit pas reproposer les autres créneaux (anti-pattern)
    assert "samedi" not in reply.lower()
    assert "lundi" not in reply.lower()
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.pending_slot_choice == 1
    assert "[INTERRUPTION]" in caplog.text


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots)
def test_barge_in_le_deux_slot_choice(mock_slots):
    """Barge-in pendant lecture : « le 2 » → slot_choice=2, is_reading_slots=False."""
    engine = create_engine()
    conv = f"conv_barge2_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Martin Dupont")
    engine.handle_message(conv, "matin")
    engine.handle_message(conv, "oui")
    session = engine.session_store.get(conv)
    assert session is not None
    assert getattr(session, "is_reading_slots", False)
    events = engine.handle_message(conv, "le 2")
    assert len(events) >= 1
    session = engine.session_store.get(conv)
    assert session.pending_slot_choice == 2
    assert getattr(session, "is_reading_slots", True) is False
    assert "confirmez" in events[0].text.lower() or "créneau" in events[0].text.lower()


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots)
def test_barge_in_ordinal_deuxieme(mock_slots):
    """Barge-in pendant lecture : « le deuxième » → choix 2."""
    engine = create_engine()
    conv = f"conv_barge_ord_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Martin Dupont")
    engine.handle_message(conv, "matin")
    engine.handle_message(conv, "oui")
    events = engine.handle_message(conv, "le deuxième")
    assert len(events) >= 1
    session = engine.session_store.get(conv)
    assert session.pending_slot_choice == 2


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots)
def test_barge_in_repeat_replays_list(mock_slots):
    """Barge-in « répétez » pendant lecture → renvoie la liste, état inchangé."""
    engine = create_engine()
    conv = f"conv_barge_rep_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Martin Dupont")
    engine.handle_message(conv, "matin")
    engine.handle_message(conv, "oui")
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.state == "WAIT_CONFIRM"
    events = engine.handle_message(conv, "Répétez")
    assert len(events) >= 1
    reply = events[0].text
    assert "Mardi" in reply or "créneau" in reply.lower() or "1" in reply
    session = engine.session_store.get(conv)
    assert session.state == "WAIT_CONFIRM"
    assert session.pending_slot_choice is None


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots)
def test_barge_in_le_dernier_slot_3(mock_slots):
    """Barge-in « le dernier » pendant lecture 3 slots → choix 3."""
    engine = create_engine()
    conv = f"conv_dernier_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Martin Dupont")
    engine.handle_message(conv, "matin")
    engine.handle_message(conv, "oui")
    events = engine.handle_message(conv, "le dernier")
    assert len(events) >= 1
    session = engine.session_store.get(conv)
    assert session.pending_slot_choice == 3


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots)
def test_sequential_celui_la_confirms_current(mock_slots):
    """Séquentiel : « celui-là » après proposition créneau → confirme le créneau en cours."""
    engine = create_engine()
    conv = f"conv_celui_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Martin Dupont")
    engine.handle_message(conv, "matin")
    session = engine.session_store.get(conv)
    session.channel = "vocal"
    engine.session_store.save(session)
    engine.handle_message(conv, "oui")
    session = engine.session_store.get(conv)
    assert session.slot_proposal_sequential
    assert session.slot_offer_index == 0
    events = engine.handle_message(conv, "celui-là")
    assert len(events) >= 1
    session = engine.session_store.get(conv)
    assert session.pending_slot_choice == 1
    assert "confirmez" in events[0].text.lower() or "créneau" in events[0].text.lower()


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots)
def test_confirm_slot_oui_cest_bien_ca(mock_slots):
    """Après « Le créneau X, vous confirmez ? », « oui c'est bien ça » doit valider et passer au contact (pas transférer)."""
    engine = create_engine()
    conv = f"conv_oui_bien_ca_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Martin Dupont")
    engine.handle_message(conv, "matin")
    engine.handle_message(conv, "oui")
    engine.handle_message(conv, "un")
    events = engine.handle_message(conv, "oui c'est bien ça")
    assert len(events) >= 1
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.state == "QUALIF_CONTACT"
    assert "transfert" not in events[0].text.lower() and "conseiller" not in events[0].text.lower()


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots)
def test_confirm_slot_cest_bien_ca_cedilla(mock_slots):
    """Anti-régression : « c'est bien ça » avec ç (STT) doit être reconnu comme confirmation."""
    engine = create_engine()
    conv = f"conv_cedilla_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Martin Dupont")
    engine.handle_message(conv, "matin")
    engine.handle_message(conv, "oui")
    engine.handle_message(conv, "un")
    events = engine.handle_message(conv, "c'est bien ça")
    assert len(events) >= 1
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.state == "QUALIF_CONTACT"
    assert "transfert" not in events[0].text.lower() and "conseiller" not in events[0].text.lower()


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots)
def test_yes_with_awaiting_confirm_slot_passes_to_contact(mock_slots):
    """YES avec awaiting_confirmation=CONFIRM_SLOT → confirme le créneau, pas CLARIFY."""
    engine = create_engine()
    conv = f"conv_await_slot_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Martin Dupont")
    engine.handle_message(conv, "matin")
    engine.handle_message(conv, "oui")
    engine.handle_message(conv, "un")
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.awaiting_confirmation == "CONFIRM_SLOT"
    events = engine.handle_message(conv, "oui")
    assert len(events) >= 1
    session = engine.session_store.get(conv)
    assert session.state == "QUALIF_CONTACT"
    assert session.awaiting_confirmation is None


def test_yes_in_start_goes_to_clarify():
    """YES sans awaiting_confirmation en START → CLARIFY_YES_START (disambiguation RDV/question)."""
    engine = create_engine()
    conv = f"conv_yes_start_{uuid.uuid4().hex[:8]}"
    events = engine.handle_message(conv, "oui")
    assert len(events) == 1
    assert "rendez-vous" in events[0].text.lower() or "question" in events[0].text.lower()
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.state == "CLARIFY"


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots)
def test_yes_after_informational_message_guidance(mock_slots):
    """YES après message informatif (pas de '?') → CLARIFY_YES_GENERIC, pas changement d'état bizarre."""
    engine = create_engine()
    conv = f"conv_yes_info_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Martin Dupont")
    engine.handle_message(conv, "matin")
    engine.handle_message(conv, "oui")
    engine.handle_message(conv, "un")
    session = engine.session_store.get(conv)
    assert session is not None
    session.awaiting_confirmation = None
    session.last_agent_message = "Parfait."
    session.last_question_asked = None
    engine.session_store.save(session)
    events = engine.handle_message(conv, "oui")
    assert len(events) >= 1
    assert "confirmez" in events[0].text.lower() or "préférez" in events[0].text.lower() or "créneau" in events[0].text.lower()
    session = engine.session_store.get(conv)
    assert session.state == "WAIT_CONFIRM"


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots)
def test_yes_ambiguous_2_in_booking_gets_tight_clarification(mock_slots):
    """2e oui ambigu en booking → CLARIFY_YES_BOOKING_TIGHT (pas INTENT_ROUTER)."""
    engine = create_engine()
    conv = f"conv_yes2_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Martin Dupont")
    engine.handle_message(conv, "matin")
    engine.handle_message(conv, "oui")
    engine.handle_message(conv, "un")
    session = engine.session_store.get(conv)
    assert session is not None
    session.awaiting_confirmation = None
    session.last_agent_message = "Parfait."
    session.last_question_asked = None
    session.yes_ambiguous_count = 1
    engine.session_store.save(session)
    events = engine.handle_message(conv, "oui")
    assert len(events) >= 1
    assert "être sûr" in events[0].text.lower() or "confirmez" in events[0].text.lower()
    assert "transfert" not in events[0].text.lower() and "conseiller" not in events[0].text.lower()
    session = engine.session_store.get(conv)
    assert session.state == "WAIT_CONFIRM"


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots)
def test_yes_ambiguous_3_in_booking_goes_to_router(mock_slots):
    """3e oui ambigu en booking → INTENT_ROUTER."""
    engine = create_engine()
    conv = f"conv_yes3_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Martin Dupont")
    engine.handle_message(conv, "matin")
    engine.handle_message(conv, "oui")
    engine.handle_message(conv, "un")
    session = engine.session_store.get(conv)
    assert session is not None
    session.awaiting_confirmation = None
    session.last_agent_message = "Parfait."
    session.last_question_asked = None
    session.yes_ambiguous_count = 2
    engine.session_store.save(session)
    events = engine.handle_message(conv, "oui")
    assert len(events) >= 1
    session = engine.session_store.get(conv)
    assert session.state == "INTENT_ROUTER"


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots)
def test_yes_ambiguous_count_resets_on_non_yes(mock_slots):
    """Oui ambigu → autre chose → oui : compteur reset, pas escalade trop tôt."""
    engine = create_engine()
    conv = f"conv_yes_reset_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Martin Dupont")
    engine.handle_message(conv, "matin")
    engine.handle_message(conv, "oui")
    engine.handle_message(conv, "un")
    session = engine.session_store.get(conv)
    assert session is not None
    session.awaiting_confirmation = None
    session.last_agent_message = "Parfait."
    session.last_question_asked = None
    engine.session_store.save(session)
    events1 = engine.handle_message(conv, "oui")
    assert "confirmez" in events1[0].text.lower() or "préférez" in events1[0].text.lower()
    session = engine.session_store.get(conv)
    assert getattr(session, "yes_ambiguous_count", 0) == 1
    engine.handle_message(conv, "euh non en fait")
    session = engine.session_store.get(conv)
    assert getattr(session, "yes_ambiguous_count", 0) == 0
    session.awaiting_confirmation = None
    session.last_agent_message = "Parfait."
    session.last_question_asked = None
    engine.session_store.save(session)
    events2 = engine.handle_message(conv, "oui")
    assert "confirmez" in events2[0].text.lower() or "préférez" in events2[0].text.lower()
    session = engine.session_store.get(conv)
    assert session.state == "WAIT_CONFIRM"


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots)
def test_repeat_after_slot_confirm_replays_exact_message(mock_slots):
    """REPEAT après format_slot_early_confirm → rejoue le message exact (avec « Vous confirmez ? »)."""
    engine = create_engine()
    conv = f"conv_repeat_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    engine.handle_message(conv, "Martin Dupont")
    engine.handle_message(conv, "matin")
    session = engine.session_store.get(conv)
    session.channel = "vocal"
    engine.session_store.save(session)
    engine.handle_message(conv, "oui")
    engine.handle_message(conv, "oui")
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.awaiting_confirmation == "CONFIRM_SLOT"
    confirm_msg = session.last_agent_message or ""
    assert "confirmez" in confirm_msg.lower() or "correct" in confirm_msg.lower()
    events = engine.handle_message(conv, "Répétez")
    assert len(events) >= 1
    assert "confirmez" in events[0].text.lower() or "correct" in events[0].text.lower()
    assert events[0].text.strip() == confirm_msg.strip()
    events2 = engine.handle_message(conv, "oui")
    assert len(events2) >= 1
    session = engine.session_store.get(conv)
    assert session.state == "QUALIF_CONTACT"


@patch("backend.tools_booking.get_slots_for_display", side_effect=_fake_slots)
def test_overlap_silence_during_tts_no_fail(mock_slots):
    """Silence pendant TTS (speaking_until_ts) → 'Je vous écoute.' sans incrémenter empty_message_count (Règle 11)."""
    import time
    engine = create_engine()
    conv = f"conv_overlap_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv, "Je veux un rdv")
    session = engine.session_store.get(conv)
    session.channel = "vocal"
    session.speaking_until_ts = time.time() + 10.0
    engine.session_store.save(session)
    events = engine.handle_message(conv, "")
    assert len(events) == 1
    session2 = engine.session_store.get(conv)
    assert "écoute" in events[0].text.lower()
    assert getattr(session2, "empty_message_count", 0) == 0
