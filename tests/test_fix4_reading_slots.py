# tests/test_fix4_reading_slots.py
"""
Fix #4: tests reset centralisé is_reading_slots — helpers, invariant, transition.
"""
import pytest
from backend.session import Session, set_reading_slots, reset_slots_reading


def test_set_and_reset_reading_slots():
    """set_reading_slots(True) puis reset_slots_reading() → False."""
    s = Session(conv_id="c1")
    assert s.is_reading_slots is False
    set_reading_slots(s, True, "propose")
    assert s.is_reading_slots is True
    reset_slots_reading(s)
    assert s.is_reading_slots is False


def test_reset_slots_reading_idempotent():
    """reset_slots_reading quand déjà False ne change rien."""
    s = Session(conv_id="c2")
    reset_slots_reading(s)
    assert s.is_reading_slots is False


def test_invariant_after_handle_message_non_wait_confirm():
    """Session state=QUALIF_NAME, is_reading_slots=True → au premier handle_message, correction à False."""
    from backend.engine import Engine
    from backend.session_store_sqlite import SQLiteSessionStore
    from backend.tools_faq import FaqStore
    import tempfile
    import os
    db_path = os.path.join(tempfile.gettempdir(), "test_fix4_sessions.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    store = SQLiteSessionStore(db_path=db_path)
    engine = Engine(session_store=store, faq_store=FaqStore(items=[]))
    conv_id = "fix4-invariant"
    session = store.get_or_create(conv_id)
    session.state = "QUALIF_NAME"
    session.is_reading_slots = True  # incohérent (checkpoint legacy)
    store.save(session)
    # Clear cache pour forcer rechargement depuis DB
    if conv_id in store._memory_cache:
        del store._memory_cache[conv_id]
    # handle_message recharge la session et doit appliquer l'invariant
    events = engine.handle_message(conv_id, "Je veux un rendez-vous")
    session_after = store.get(conv_id)
    assert session_after is not None
    assert session_after.state != "WAIT_CONFIRM"
    assert session_after.is_reading_slots is False
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass


def test_trigger_transfer_resets_reading_slots():
    """_trigger_transfer remet is_reading_slots à False."""
    from backend.engine import Engine
    from backend.session_store_sqlite import SQLiteSessionStore
    from backend.tools_faq import FaqStore
    import tempfile
    import os
    db_path = os.path.join(tempfile.gettempdir(), "test_fix4_transfer_sessions.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    store = SQLiteSessionStore(db_path=db_path)
    engine = Engine(session_store=store, faq_store=FaqStore(items=[]))
    session = store.get_or_create("fix4-transfer")
    session.state = "WAIT_CONFIRM"
    session.is_reading_slots = True
    store.save(session)
    evts = engine._trigger_transfer(session, "web", "test_reason", user_text="")
    session_after = store.get("fix4-transfer")
    assert session_after is not None
    assert session_after.state == "TRANSFERRED"
    assert session_after.is_reading_slots is False
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass
