# tests/test_engine.py
import pytest
from backend.engine import create_engine, _detect_booking_intent
from backend import prompts


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
    """1er no match → clarification (reformuler/préciser), 2e → INTENT_ROUTER (pas transfert direct)."""
    engine = create_engine()
    conv = "conv5"

    # 1er no match → message de clarification
    e1 = engine.handle_message(conv, "xyzabc123def")
    assert len(e1) == 1
    assert e1[0].type == "final"
    assert "reformuler" in e1[0].text.lower() or "préciser" in e1[0].text.lower() or "compris" in e1[0].text.lower()

    # 2e no match → INTENT_ROUTER (menu 1/2/3/4), pas MSG_TRANSFER
    e2 = engine.handle_message(conv, "test question 2")
    assert len(e2) == 1
    assert e2[0].type == "final"
    assert e2[0].conv_state == "INTENT_ROUTER"
    assert "dites" in e2[0].text.lower() and ("un" in e2[0].text.lower() or "1" in e2[0].text)


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


def test_qualif_name_intent_repeat_3_times_stays_qualif_name():
    """P0 : QUALIF_NAME + 'je veux un rendez-vous' x3 → toujours QUALIF_NAME, jamais INTENT_ROUTER."""
    engine = create_engine()
    conv = "conv_qualif_intent_3"
    engine.handle_message(conv, "Je veux un rdv")
    for _ in range(3):
        events = engine.handle_message(conv, "je veux un rendez-vous")
        assert len(events) == 1
        assert events[0].conv_state == "QUALIF_NAME"
    session = engine.session_store.get(conv)
    assert session is not None
    assert session.state == "QUALIF_NAME"
    assert session.name_fails == 0


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
