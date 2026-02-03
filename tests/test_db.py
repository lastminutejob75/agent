# tests/test_db.py
"""
Tests pour backend/db.py
"""

import pytest
from datetime import datetime, timedelta
import os

from backend.db import (
    init_db,
    cleanup_old_slots,
    list_free_slots,
    count_free_slots,
    get_conn,
    book_slot_atomic,
    find_booking_by_name,
    cancel_booking_sqlite,
    TARGET_MIN_SLOTS,
)


@pytest.fixture
def clean_db():
    """Fixture pour nettoyer la DB avant chaque test"""
    db_path = "agent.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    init_db(days=7)
    yield
    # Cleanup après test (optionnel, car tests peuvent partager la DB)


def test_cleanup_creates_weekday_slots_only(clean_db):
    """Vérifie que cleanup ne crée que des slots en semaine (lundi-vendredi)"""
    cleanup_old_slots()
    slots = list_free_slots(limit=30)

    for slot in slots:
        date = datetime.strptime(slot["date"], "%Y-%m-%d")
        assert date.weekday() < 5, f"Slot on weekend: {slot['date']}"


def test_cleanup_ensures_minimum_slots(clean_db):
    """Vérifie que cleanup garantit au moins TARGET_MIN_SLOTS slots futurs"""
    cleanup_old_slots()
    count = count_free_slots()

    assert count >= TARGET_MIN_SLOTS, f"Expected >= {TARGET_MIN_SLOTS} slots, got {count}"


def test_cleanup_deletes_old_slots(clean_db):
    """Vérifie que cleanup supprime les slots passés"""
    # Créer un slot hier
    conn = get_conn()
    try:
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        conn.execute(
            "INSERT INTO slots (date, time) VALUES (?, ?)", (yesterday, "10:00")
        )
        conn.commit()
    finally:
        conn.close()

    # Cleanup
    cleanup_old_slots()

    # Vérifier suppression
    conn = get_conn()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        cur = conn.execute(
            "SELECT COUNT(*) as c FROM slots WHERE date < ?", (today,)
        )
        count = cur.fetchone()["c"]
        assert count == 0, "Old slots should be deleted"
    finally:
        conn.close()


def test_list_free_slots_returns_future_only(clean_db):
    """Vérifie que list_free_slots ne retourne que des slots futurs"""
    cleanup_old_slots()
    slots = list_free_slots(limit=30)

    today = datetime.now().strftime("%Y-%m-%d")
    for slot in slots:
        assert slot["date"] >= today, f"Slot in past: {slot['date']}"


def test_cleanup_idempotent(clean_db):
    """Vérifie que plusieurs appels à cleanup donnent le même résultat"""
    cleanup_old_slots()
    count1 = count_free_slots()

    cleanup_old_slots()
    count2 = count_free_slots()

    # Devrait être stable (ou proche, car dates changent)
    assert abs(count1 - count2) <= 1, "Cleanup should be roughly idempotent"


def test_find_booking_by_name_and_cancel_sqlite(clean_db):
    """find_booking_by_name trouve un RDV réservé ; cancel_booking_sqlite libère le slot."""
    cleanup_old_slots()
    slots = list_free_slots(limit=1)
    assert slots, "need at least one free slot"
    slot_id = slots[0]["id"]

    ok = book_slot_atomic(
        slot_id=slot_id,
        name="Jean Dupont",
        contact="jean@test.fr",
        contact_type="email",
        motif="Consultation",
    )
    assert ok is True

    booking = find_booking_by_name("Jean Dupont")
    assert booking is not None
    assert booking["slot_id"] == slot_id
    assert booking["name"] == "Jean Dupont"

    ok_cancel = cancel_booking_sqlite(booking)
    assert ok_cancel is True

    # Après annulation, plus de RDV pour ce nom
    assert find_booking_by_name("Jean Dupont") is None
    # Le slot redevient libre
    free = list_free_slots(limit=100)
    free_ids = [s["id"] for s in free]
    assert slot_id in free_ids

