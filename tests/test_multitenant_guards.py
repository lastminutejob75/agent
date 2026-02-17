# tests/test_multitenant_guards.py
"""
Tests que les chemins SQLite sont bloqués quand MULTI_TENANT_MODE=True.

Setup : monkeypatch config.is_multi_tenant_mode → True.
Pour chaque fonction SQLite : appeler la branche SQLite → RuntimeError avec
[MULTI_TENANT] dans le message et log CRITICAL.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def enable_multi_tenant_mode(monkeypatch):
    """Force MULTI_TENANT_MODE=True pour tous les tests de ce module."""
    import backend.config as config
    monkeypatch.setattr(config, "is_multi_tenant_mode", lambda: True)


@pytest.fixture
def disable_pg_slots(monkeypatch):
    """Force USE_PG_SLOTS=False pour que db.py prenne la branche SQLite."""
    import backend.config as config
    monkeypatch.setattr(config, "USE_PG_SLOTS", False)


def test_db_count_free_slots_sqlite_blocked(disable_pg_slots, caplog):
    """db.count_free_slots en branche SQLite → RuntimeError + CRITICAL."""
    import backend.db as db
    with pytest.raises(RuntimeError) as exc:
        db.count_free_slots(tenant_id=1)
    assert "[MULTI_TENANT]" in str(exc.value)
    assert "count_free_slots" in str(exc.value)
    critical = [r for r in caplog.records if getattr(r, "levelname", "") == "CRITICAL"]
    assert critical, "Expected at least one CRITICAL log"
    assert "[MULTI_TENANT]" in (critical[0].getMessage() if hasattr(critical[0], "getMessage") else str(critical[0]))


def test_db_list_free_slots_sqlite_blocked(disable_pg_slots, caplog):
    """db.list_free_slots en branche SQLite → RuntimeError."""
    import backend.db as db
    with pytest.raises(RuntimeError) as exc:
        db.list_free_slots(tenant_id=1)
    assert "[MULTI_TENANT]" in str(exc.value)
    assert "list_free_slots" in str(exc.value)


def test_db_find_slot_id_by_datetime_blocked(caplog):
    """db.find_slot_id_by_datetime (SQLite pur) → RuntimeError."""
    import backend.db as db
    with pytest.raises(RuntimeError) as exc:
        db.find_slot_id_by_datetime("2026-02-20", "10:00")
    assert "[MULTI_TENANT]" in str(exc.value)
    assert "find_slot_id_by_datetime" in str(exc.value)


def test_db_book_slot_atomic_sqlite_blocked(disable_pg_slots, caplog):
    """db.book_slot_atomic en branche SQLite → RuntimeError."""
    import backend.db as db
    with pytest.raises(RuntimeError) as exc:
        db.book_slot_atomic(1, "Test", "", "", "", tenant_id=1)
    assert "[MULTI_TENANT]" in str(exc.value)
    assert "book_slot_atomic" in str(exc.value)


def test_db_find_booking_by_name_sqlite_blocked(disable_pg_slots):
    """db.find_booking_by_name en branche SQLite → RuntimeError."""
    import backend.db as db
    with pytest.raises(RuntimeError) as exc:
        db.find_booking_by_name("Dupont", tenant_id=1)
    assert "[MULTI_TENANT]" in str(exc.value)
    assert "find_booking_by_name" in str(exc.value)


def test_db_cancel_booking_sqlite_blocked(disable_pg_slots):
    """db.cancel_booking_sqlite en branche SQLite → RuntimeError."""
    import backend.db as db
    with pytest.raises(RuntimeError) as exc:
        db.cancel_booking_sqlite({"id": 1}, tenant_id=1)
    assert "[MULTI_TENANT]" in str(exc.value)
    assert "cancel_booking_sqlite" in str(exc.value)


def test_db_cleanup_old_slots_blocked(caplog):
    """db.cleanup_old_slots (SQLite pur) → RuntimeError."""
    import backend.db as db
    with pytest.raises(RuntimeError) as exc:
        db.cleanup_old_slots()
    assert "[MULTI_TENANT]" in str(exc.value)
    assert "cleanup_old_slots" in str(exc.value)


def test_session_store_sqlite_get_blocked(caplog):
    """session_store_sqlite.get → RuntimeError."""
    from backend.session_store_sqlite import SQLiteSessionStore
    store = SQLiteSessionStore(":memory:")
    store._init_db()
    with pytest.raises(RuntimeError) as exc:
        store.get("conv-123")
    assert "[MULTI_TENANT]" in str(exc.value)
    assert "get" in str(exc.value)


def test_session_store_sqlite_get_or_create_blocked(caplog):
    """session_store_sqlite.get_or_create → RuntimeError."""
    from backend.session_store_sqlite import SQLiteSessionStore
    store = SQLiteSessionStore(":memory:")
    store._init_db()
    with pytest.raises(RuntimeError) as exc:
        store.get_or_create("conv-456")
    assert "[MULTI_TENANT]" in str(exc.value)


def test_session_store_sqlite_save_blocked(caplog):
    """session_store_sqlite.save → RuntimeError."""
    from backend.session_store_sqlite import SQLiteSessionStore
    from backend.session import Session
    store = SQLiteSessionStore(":memory:")
    store._init_db()
    session = Session(conv_id="conv-save")
    with pytest.raises(RuntimeError) as exc:
        store.save(session)
    assert "[MULTI_TENANT]" in str(exc.value)
    assert "save" in str(exc.value)


def test_session_store_sqlite_delete_blocked(caplog):
    """session_store_sqlite.delete → RuntimeError."""
    from backend.session_store_sqlite import SQLiteSessionStore
    store = SQLiteSessionStore(":memory:")
    store._init_db()
    with pytest.raises(RuntimeError) as exc:
        store.delete("conv-del")
    assert "[MULTI_TENANT]" in str(exc.value)


def test_session_store_sqlite_cleanup_old_sessions_blocked(caplog):
    """session_store_sqlite.cleanup_old_sessions → RuntimeError."""
    from backend.session_store_sqlite import SQLiteSessionStore
    store = SQLiteSessionStore(":memory:")
    store._init_db()
    with pytest.raises(RuntimeError) as exc:
        store.cleanup_old_sessions(hours=24)
    assert "[MULTI_TENANT]" in str(exc.value)


def test_client_memory_get_by_phone_blocked(caplog):
    """client_memory.get_by_phone → RuntimeError."""
    from backend.client_memory import ClientMemory
    import tempfile
    import os
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        memory = ClientMemory(db_path=path)
        memory._ensure_db()
        with pytest.raises(RuntimeError) as exc:
            memory.get_by_phone("0612345678")
        assert "[MULTI_TENANT]" in str(exc.value)
        assert "get_by_phone" in str(exc.value)
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_client_memory_get_clients_with_email_blocked(caplog):
    """client_memory.get_clients_with_email → RuntimeError."""
    from backend.client_memory import ClientMemory
    import tempfile
    import os
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        memory = ClientMemory(db_path=path)
        memory._ensure_db()
        with pytest.raises(RuntimeError) as exc:
            memory.get_clients_with_email()
        assert "[MULTI_TENANT]" in str(exc.value)
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_validate_multi_tenant_config_raises_when_pg_slots_off(monkeypatch):
    """validate_multi_tenant_config() lève si MULTI_TENANT_MODE et pas USE_PG_SLOTS."""
    import backend.config as config
    monkeypatch.setattr(config, "is_multi_tenant_mode", lambda: True)
    monkeypatch.setattr(config, "USE_PG_SLOTS", False)
    with pytest.raises(RuntimeError) as exc:
        config.validate_multi_tenant_config()
    assert "[MULTI_TENANT]" in str(exc.value)
    assert "USE_PG_SLOTS" in str(exc.value)


def test_validate_multi_tenant_config_ok_when_not_multi_tenant(monkeypatch):
    """validate_multi_tenant_config() ne lève pas si MULTI_TENANT_MODE=false."""
    import backend.config as config
    monkeypatch.setattr(config, "is_multi_tenant_mode", lambda: False)
    monkeypatch.setattr(config, "USE_PG_SLOTS", False)
    config.validate_multi_tenant_config()


def test_validate_multi_tenant_config_ok_when_pg_slots_on(monkeypatch):
    """validate_multi_tenant_config() ne lève pas si MULTI_TENANT_MODE et USE_PG_SLOTS."""
    import backend.config as config
    monkeypatch.setattr(config, "is_multi_tenant_mode", lambda: True)
    monkeypatch.setattr(config, "USE_PG_SLOTS", True)
    config.validate_multi_tenant_config()
