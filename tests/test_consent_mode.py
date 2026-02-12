# tests/test_consent_mode.py
"""
Tests P0.5 consent_mode (implicit | explicit).
- implicit : persist au 1er message (comportement actuel)
- explicit : demander oui/non avant de traiter
"""
import pytest
from unittest.mock import patch

from backend.engine import Engine
from backend.session_store_sqlite import SQLiteSessionStore
from backend.tools_faq import FaqStore


@pytest.fixture
def session_store():
    """SessionStore SQLite in-memory."""
    import tempfile
    import os
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    try:
        store = SQLiteSessionStore(path)
        yield store
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


@pytest.fixture
def engine(session_store):
    return Engine(session_store=session_store, faq_store=FaqStore(items=[]))


def test_consent_mode_implicit_first_message(engine, session_store):
    """Mode implicit : premier message → traitement normal, pas de prompt consentement."""
    with patch("backend.engine.get_consent_mode", return_value="implicit"):
        conv_id = "test-implicit-1"
        session = session_store.get_or_create(conv_id)
        session.channel = "vocal"
        session.tenant_id = 1
        session_store.save(session)

        events = engine.handle_message(conv_id, "Je voudrais un rendez-vous")
        assert len(events) >= 1
        # Pas de VOCAL_CONSENT_PROMPT
        texts = [e.text for e in events if e.text]
        assert not any("enregistre ce que vous dites" in (t or "") for t in texts)


def test_consent_mode_explicit_yes(engine, session_store):
    """Mode explicit : 1) prompt → 2) oui → continue."""
    with patch("backend.engine.get_consent_mode", return_value="explicit"):
        conv_id = "test-explicit-yes"
        session = session_store.get_or_create(conv_id)
        session.channel = "vocal"
        session.tenant_id = 1
        session_store.save(session)

        # 1er message : prompt consentement
        events1 = engine.handle_message(conv_id, "Bonjour")
        assert len(events1) >= 1
        t1 = events1[0].text or ""
        assert "enregistre ce que vous dites" in t1 or "d'accord" in t1.lower()

        # 2e message : oui → continue (clarification START : "oui" ambigu)
        events2 = engine.handle_message(conv_id, "oui")
        assert len(events2) >= 1
        t2 = events2[0].text or ""
        # Après oui, on continue → clarification (rendez-vous ou question)
        assert "rendez-vous" in t2.lower() or "question" in t2.lower() or "créneau" in t2.lower()


def test_consent_mode_explicit_no(engine, session_store):
    """Mode explicit : 1) prompt → 2) non → transfert."""
    with patch("backend.engine.get_consent_mode", return_value="explicit"):
        conv_id = "test-explicit-no"
        session = session_store.get_or_create(conv_id)
        session.channel = "vocal"
        session.tenant_id = 1
        session_store.save(session)

        # 1er message : prompt
        engine.handle_message(conv_id, "Bonjour")

        # 2e message : non → transfert
        events = engine.handle_message(conv_id, "non")
        assert len(events) >= 1
        t = events[0].text or ""
        assert "relation avec un humain" in t or "conseiller" in t.lower()
        session2 = session_store.get_or_create(conv_id)
        assert session2.state == "TRANSFERRED"
