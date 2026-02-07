"""
Tests triage médical — priorité absolue, sans LLM.
- Red flags → EMERGENCY (session bloquée).
- NON_URGENT / CAUTION → message + QUALIF_PREF (escalade douce).
"""
import uuid
import pytest
from backend.engine import create_engine
from backend.guards_medical import is_medical_emergency, MEDICAL_EMERGENCY_KEYWORDS
from backend.guards_medical_triage import (
    detect_medical_red_flag,
    detect_medical_red_flags,
    classify_medical_symptoms,
    extract_symptom_motif_short,
    RED_FLAG_CATEGORIES,
)


def test_medical_emergency_preempts_booking():
    """Détection 'mal au cœur' → message urgence + state EMERGENCY."""
    engine = create_engine()
    conv_id = f"test_emergency_{uuid.uuid4().hex[:8]}"
    events = engine.handle_message(conv_id, "j'ai mal au cœur")
    assert len(events) >= 1
    text = events[0].text.lower()
    assert "15" in text or "112" in text or "urgence" in text or "quinze" in text
    session = engine.session_store.get(conv_id)
    assert session is not None
    assert session.state == "EMERGENCY"


def test_medical_emergency_douleur_poitrine():
    """Détection 'douleur poitrine' → EMERGENCY."""
    engine = create_engine()
    conv_id = f"test_emergency_poitrine_{uuid.uuid4().hex[:8]}"
    events = engine.handle_message(conv_id, "douleur poitrine")
    assert len(events) >= 1
    text = events[0].text.lower()
    assert "15" in text or "112" in text or "urgence" in text or "quinze" in text
    session = engine.session_store.get(conv_id)
    assert session.state == "EMERGENCY"


def test_medical_emergency_mal_respirer():
    """Détection 'difficulté à respirer' → EMERGENCY."""
    engine = create_engine()
    conv_id = f"test_emergency_resp_{uuid.uuid4().hex[:8]}"
    events = engine.handle_message(conv_id, "j'ai du mal à respirer")
    assert len(events) >= 1
    text = events[0].text.lower()
    assert "15" in text or "112" in text or "urgence" in text or "quinze" in text
    session = engine.session_store.get(conv_id)
    assert session.state == "EMERGENCY"


def test_medical_emergency_malaise():
    """Détection 'malaise' → EMERGENCY."""
    engine = create_engine()
    conv_id = f"test_emergency_malaise_{uuid.uuid4().hex[:8]}"
    events = engine.handle_message(conv_id, "malaise")
    assert len(events) >= 1
    text = events[0].text.lower()
    assert "15" in text or "112" in text or "urgence" in text or "quinze" in text
    session = engine.session_store.get(conv_id)
    assert session.state == "EMERGENCY"


def test_emergency_session_blocked_repeats_message():
    """Une fois en EMERGENCY, tout message (oui, rdv, silence) → répète le message urgence."""
    engine = create_engine()
    conv_id = f"test_emergency_repeat_{uuid.uuid4().hex[:8]}"
    engine.handle_message(conv_id, "j'ai mal au cœur")
    events_oui = engine.handle_message(conv_id, "oui")
    assert len(events_oui) >= 1
    t = events_oui[0].text.lower()
    assert "15" in events_oui[0].text or "112" in events_oui[0].text or "urgence" in t or "quinze" in t
    session = engine.session_store.get(conv_id)
    assert session.state == "EMERGENCY"

    events_rdv = engine.handle_message(conv_id, "je veux un rdv")
    assert len(events_rdv) >= 1
    t2 = events_rdv[0].text.lower()
    assert "15" in events_rdv[0].text or "112" in events_rdv[0].text or "urgence" in t2 or "quinze" in t2
    assert engine.session_store.get(conv_id).state == "EMERGENCY"


def test_guard_is_medical_emergency_keywords():
    """is_medical_emergency détecte les mots-clés de la liste."""
    assert is_medical_emergency("j'ai mal au cœur") is True
    assert is_medical_emergency("douleur thoracique") is True
    assert is_medical_emergency("essoufflé") is True
    assert is_medical_emergency("perte de connaissance") is True
    assert is_medical_emergency("je me suis évanoui") is True
    assert is_medical_emergency("") is False
    assert is_medical_emergency("je veux un rendez-vous") is False
    assert is_medical_emergency("quels sont vos horaires") is False


def test_triage_non_urgent_fievre():
    """Symptôme non vital (fièvre) → message ack + QUALIF_PREF, pas EMERGENCY."""
    engine = create_engine()
    conv_id = f"test_fievre_{uuid.uuid4().hex[:8]}"
    events = engine.handle_message(conv_id, "j'ai de la fièvre depuis hier")
    assert len(events) >= 1
    text = events[0].text.lower()
    assert "médecin" in text or "rendez-vous" in text
    assert "matin" in text or "après-midi" in text
    session = engine.session_store.get(conv_id)
    assert session.state == "QUALIF_PREF"
    assert session.qualif_data.motif is not None


def test_triage_caution_inquiete():
    """Inquiétude (ça m'inquiète) → MSG_MEDICAL_CAUTION + QUALIF_PREF."""
    engine = create_engine()
    conv_id = f"test_caution_{uuid.uuid4().hex[:8]}"
    events = engine.handle_message(conv_id, "j'ai mal au ventre et ça m'inquiète")
    assert len(events) >= 1
    text = events[0].text.lower()
    assert "15" in events[0].text or "112" in events[0].text
    assert "matin" in text or "après-midi" in text
    session = engine.session_store.get(conv_id)
    assert session.state == "QUALIF_PREF"


def test_triage_red_flags_vs_non_urgent():
    """Red flag (douleur poitrine) → EMERGENCY ; douleur genou → non urgent si pas red flag."""
    assert detect_medical_red_flags("douleur à la poitrine") is True
    assert detect_medical_red_flags("j'ai mal au genou") is False
    assert classify_medical_symptoms("j'ai mal au genou") == "NON_URGENT"
    motif = extract_symptom_motif_short("j'ai mal au genou depuis une semaine", max_words=8)
    assert "mal" in motif and "genou" in motif


def test_je_ne_sais_pas_seul_pas_caution():
    """« Je ne sais pas » seul (ex. à l'accueil) → pas CAUTION, évite message gravité."""
    assert classify_medical_symptoms("je ne sais pas") is None
    assert classify_medical_symptoms("ben j'en sais pas") is None
    assert classify_medical_symptoms("euh je sais pas") is None


def test_je_ne_sais_pas_avec_symptome_caution():
    """« Je ne sais pas » + symptôme → CAUTION (contexte médical)."""
    assert classify_medical_symptoms("je ne sais pas si c'est grave, j'ai mal de tête") == "CAUTION"
    assert classify_medical_symptoms("j'ai de la fièvre et ça m'inquiète") == "CAUTION"


def test_red_flag_category_audit():
    """Catégories d'audit : on log la catégorie, pas le symptôme (traçable, non médical)."""
    assert detect_medical_red_flag("douleur à la poitrine") == "cardio_respiratoire"
    assert detect_medical_red_flag("j'ai mal au cœur") == "cardio_respiratoire"
    assert detect_medical_red_flag("perte de connaissance") == "neurologique"
    assert detect_medical_red_flag("difficulté à parler") == "neurologique"
    assert detect_medical_red_flag("saignement abondant") == "hemorragie_trauma"
    assert detect_medical_red_flag("mon bébé ne respire pas") == "pediatrie"
    assert detect_medical_red_flag("envie de mourir") == "psychiatrique"
    assert detect_medical_red_flag("j'ai mal au genou") is None
    assert "cardio_respiratoire" in RED_FLAG_CATEGORIES
    assert "psychiatrique" in RED_FLAG_CATEGORIES
