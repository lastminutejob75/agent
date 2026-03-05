# tests/test_booking_e2e.py
"""
Tests E2E du flow booking Vapi.
Simule exactement ce que Vapi envoie à POST /api/vapi/tool.
Utilise la vraie config en DB (tenant, routing, params_json) — pas de valeurs hardcodées.

Prérequis (variables d'environnement) :
- TEST_TENANT_ID : id du tenant de test (doit exister en base)
- TEST_TO_NUMBER : numéro DID du tenant (celui configuré dans tenant_routing)

Le tenant doit avoir dans params_json (Admin → Tenant → Actions) :
- calendar_provider=google
- calendar_id=<id du calendrier Google>

Option A — tenant existant (local/staging) :
  export TEST_TENANT_ID=1
  export TEST_TO_NUMBER="+33XXXXXXXXX"
  pytest tests/test_booking_e2e.py -v -s

Option B — créer un tenant de test :
  1. /admin/tenants → créer "Test E2E"
  2. Onglet Actions → calendar_provider=google + calendar_id=ton_calendar_test
  3. Vérifier que le DID est dans tenant_routing
  4. Lancer les tests avec TEST_TENANT_ID et TEST_TO_NUMBER

Pour débloquer les 2 tests Google Calendar (book + booking_rules) :
  1. Admin → Tenant → Actions → Agenda & Booking
     - Provider : google
     - Calendar ID : xxx@group.calendar.google.com
     - Sauvegarder
  2. Google Calendar (web) → Paramètres du calendrier de test
     - "Partager avec des personnes spécifiques"
     - Ajouter l'email du service account (client_email dans SERVICE_ACCOUNT_FILE)
     - Droits : "Apporter des modifications aux événements"
  3. pytest tests/test_booking_e2e.py -v -s
"""
from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any, Dict, Optional

import pytest
from httpx import AsyncClient

from backend.main import app
from backend.tenant_routing import add_route, normalize_did

# Variables d'environnement
TEST_TENANT_ID = int(os.environ.get("TEST_TENANT_ID", "0") or "0")
TEST_TO_NUMBER = (os.environ.get("TEST_TO_NUMBER") or "").strip()

SKIP_E2E = not (TEST_TENANT_ID and TEST_TO_NUMBER)


def make_vapi_payload(action: str, to_number: str, call_id: Optional[str] = None, **kwargs) -> dict:
    """
    Construit un payload réaliste Vapi pour POST /api/vapi/tool.
    D'après voice.py : _tool_extract_parameters, extract_to_number_from_vapi_payload.
    """
    cid = call_id or f"e2e_call_{uuid.uuid4().hex[:16]}"
    return {
        "message": {
            "type": "tool-calls",
            "call": {
                "id": cid,
                "phoneNumber": {"number": to_number},
            },
            "toolCallList": [
                {
                    "id": f"tool_{uuid.uuid4().hex[:12]}",
                    "function": {
                        "name": "booking_tool",
                        "arguments": {
                            "action": action,
                            **kwargs,
                        },
                    },
                }
            ],
        },
    }


def _parse_slot_labels_from_result(result_text: str) -> list[str]:
    """Extrait les labels de créneaux depuis le texte 'Créneaux disponibles : A, B et C.'"""
    if not result_text or "Créneaux disponibles" not in result_text:
        return []
    part = result_text.split("Créneaux disponibles :", 1)[-1].strip().rstrip(".")
    if not part:
        return []
    # "A, B et C" ou "A, B, C" -> ["A", "B", "C"]
    parts = re.split(r"\s+et\s+", part, flags=re.I)
    labels = []
    for p in parts:
        for sub in p.split(","):
            sub = sub.strip()
            if sub:
                labels.append(sub)
    return labels


def _parse_hour_from_label(label: str) -> Optional[int]:
    """Extrait l'heure depuis un label 'lundi 25 janvier à 14 heures' ou '...à 14 heures trente'."""
    m = re.search(r"à\s+(\d{1,2})\s+heures?", label, re.I)
    return int(m.group(1)) if m else None


def _parse_weekday_from_label(label: str) -> Optional[int]:
    """Extrait le weekday (0=lun..6=dim) depuis un label 'lundi 25 janvier...'."""
    days = {
        "lundi": 0,
        "mardi": 1,
        "mercredi": 2,
        "jeudi": 3,
        "vendredi": 4,
        "samedi": 5,
        "dimanche": 6,
    }
    label_lower = label.lower()
    for name, wd in days.items():
        if name in label_lower:
            return wd
    return None


def _get_test_calendar_id() -> Optional[str]:
    """Récupère le calendar_id du tenant de test (params_json)."""
    from backend.tenant_config import get_params
    params = get_params(TEST_TENANT_ID)
    return (params.get("calendar_id") or "").strip() or None


@pytest.fixture(scope="module")
def ensure_routing():
    """Assure que TEST_TO_NUMBER route vers TEST_TENANT_ID (SQLite + PG si dispo)."""
    if SKIP_E2E:
        yield
        return
    key = normalize_did(TEST_TO_NUMBER)
    if key:
        add_route("vocal", key, TEST_TENANT_ID)
        try:
            from backend.tenants_pg import pg_add_routing
            if pg_add_routing("vocal", key, TEST_TENANT_ID):
                pass  # PG route ajoutée
        except Exception:
            pass
    yield
    # Pas de cleanup routing (idempotent, réutilisable)


@pytest.fixture
def async_client():
    """Client HTTP async pour l'API FastAPI."""
    return AsyncClient(app=app, base_url="http://test")


# ---------------------------------------------------------------------------
# Test 1 : get_slots
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.skipif(SKIP_E2E, reason="TEST_TENANT_ID, TEST_TO_NUMBER requis")
async def test_get_slots_returns_slots(async_client: AsyncClient, ensure_routing):
    """POST /api/vapi/tool action=get_slots : status 200, créneaux non vides, respect booking rules."""
    payload = make_vapi_payload("get_slots", TEST_TO_NUMBER)
    r = await async_client.post("/api/vapi/tool", json=payload)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    data = r.json()
    results = data.get("results") or []
    assert len(results) >= 1, f"Expected results, got {data}"
    first = results[0]
    result_text = first.get("result") or ""
    error_text = first.get("error") or ""

    if error_text:
        pytest.fail(f"get_slots returned error: {error_text}")

    # Vérifier qu'on a des créneaux (pas "Aucun créneau disponible")
    has_slots = "Créneaux disponibles" in result_text and "Aucun créneau" not in result_text
    assert has_slots, f"Expected slots, got: {result_text[:200]}"

    labels = _parse_slot_labels_from_result(result_text)
    assert len(labels) >= 1, f"Could not parse slots from: {result_text[:200]}"

    # Vérifier que les créneaux respectent booking_start_hour et booking_end_hour du tenant
    from backend.tenant_config import get_booking_rules
    rules = get_booking_rules(TEST_TENANT_ID)
    start_h, end_h = rules["start_hour"], rules["end_hour"]
    booking_days = rules["booking_days"]

    for label in labels:
        hour = _parse_hour_from_label(label)
        wd = _parse_weekday_from_label(label)
        if hour is not None:
            assert start_h <= hour < end_h, f"Slot {label!r} hour {hour} outside {start_h}-{end_h}"
        if wd is not None:
            assert wd in booking_days, f"Slot {label!r} weekday {wd} not in {booking_days}"

    print(f"\n[E2E] get_slots: {len(labels)} créneaux → {labels}")


# ---------------------------------------------------------------------------
# Test 2 : book + vérification Google Calendar
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.skipif(SKIP_E2E, reason="TEST_TENANT_ID, TEST_TO_NUMBER requis")
async def test_book_creates_event_in_google_calendar(async_client: AsyncClient, ensure_routing):
    """get_slots → book → vérifier event dans Google Calendar (du tenant) → cleanup."""
    calendar_id = _get_test_calendar_id()
    if not calendar_id:
        pytest.skip("Tenant sans calendar_id configuré (params_json)")

    call_id = f"e2e_book_{uuid.uuid4().hex[:16]}"

    # 1. get_slots pour alimenter pending_slots
    payload_slots = make_vapi_payload("get_slots", TEST_TO_NUMBER, call_id=call_id)
    r1 = await async_client.post("/api/vapi/tool", json=payload_slots)
    assert r1.status_code == 200, f"get_slots failed: {r1.text}"
    data1 = r1.json()
    result1 = (data1.get("results") or [{}])[0].get("result") or ""
    if "Aucun créneau" in result1:
        pytest.skip("Aucun créneau disponible pour le test book")

    # 2. book
    payload_book = make_vapi_payload(
        "book",
        TEST_TO_NUMBER,
        call_id=call_id,
        selected_slot="1",
        patient_name="Test Patient E2E",
        motif="Consultation test",
    )
    r2 = await async_client.post("/api/vapi/tool", json=payload_book)
    assert r2.status_code == 200, f"book failed: {r2.text}"

    data2 = r2.json()
    result2 = (data2.get("results") or [{}])[0].get("result") or ""
    payload_parsed = json.loads(result2) if result2.strip().startswith("{") else {}
    status = payload_parsed.get("status")
    event_id = payload_parsed.get("event_id")

    assert status == "confirmed", f"Expected confirmed, got status={status} payload={payload_parsed}"

    # 3. Vérifier l'event dans le calendrier Google du tenant
    from backend.google_calendar import GoogleCalendarService
    svc = GoogleCalendarService(calendar_id)
    events = svc.list_upcoming_events(days=7)
    found = next((e for e in events if e.get("id") == event_id), None)
    assert found is not None, f"Event {event_id} not found in calendar"

    print(f"\n[E2E] book: event_id={event_id} créé dans Google Calendar")

    # 4. Cleanup
    try:
        ok = svc.cancel_appointment(event_id)
        assert ok, "Failed to delete test event"
        print(f"[E2E] book: event {event_id} supprimé (cleanup)")
    except Exception as e:
        print(f"[E2E] WARN: cleanup cancel_appointment failed: {e}")


# ---------------------------------------------------------------------------
# Test 3 : booking_rules respectées
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.skipif(SKIP_E2E, reason="TEST_TENANT_ID, TEST_TO_NUMBER requis")
async def test_booking_rules_respected(async_client: AsyncClient, ensure_routing):
    """Modifier params (duration=30, 10h-17h, lun/mar/mer) → get_slots → vérifier → restaurer."""
    from backend.tenant_config import get_params, set_params
    from backend.tenants_pg import pg_update_tenant_params
    from backend import config

    # Les booking_rules ne s'appliquent qu'avec Google Calendar (pas SQLite)
    original = get_params(TEST_TENANT_ID)
    if (original.get("calendar_provider") or "").lower() != "google" or not (original.get("calendar_id") or "").strip():
        pytest.skip("Tenant sans Google Calendar — booking_rules non applicables (SQLite)")

    original_backup = dict(original)

    new_params = {
        "booking_duration_minutes": "30",
        "booking_start_hour": "10",
        "booking_end_hour": "17",
        "booking_days": "[0, 1, 2]",  # lun, mar, mer
    }

    try:
        # Modifier params (SQLite + PG)
        set_params(TEST_TENANT_ID, new_params)
        if config.USE_PG_TENANTS:
            try:
                pg_update_tenant_params(TEST_TENANT_ID, new_params)
            except Exception:
                pass

        payload = make_vapi_payload("get_slots", TEST_TO_NUMBER)
        r = await async_client.post("/api/vapi/tool", json=payload)
        assert r.status_code == 200, f"get_slots failed: {r.text}"

        data = r.json()
        result_text = (data.get("results") or [{}])[0].get("result") or ""
        if "Aucun créneau" in result_text:
            # Pas de créneau lun/mar/mer dans les 7 prochains jours possible
            print("[E2E] booking_rules: aucun créneau (peut-être week-end proche)")
            return

        labels = _parse_slot_labels_from_result(result_text)
        assert len(labels) >= 1, f"Expected slots: {result_text[:200]}"

        for label in labels:
            hour = _parse_hour_from_label(label)
            wd = _parse_weekday_from_label(label)
            if hour is not None:
                assert 10 <= hour < 17, f"Slot {label!r} hour {hour} outside 10-17"
            if wd is not None:
                assert wd in (0, 1, 2), f"Slot {label!r} weekday {wd} not in [0,1,2] (lun/mar/mer)"

        print(f"\n[E2E] booking_rules: {len(labels)} créneaux 10h-17h lun/mar/mer → {labels}")
    finally:
        # Restaurer params originaux
        restore = {}
        for k in new_params:
            if k in original_backup:
                restore[k] = original_backup[k]
            else:
                if k == "booking_duration_minutes":
                    restore[k] = "15"
                elif k == "booking_start_hour":
                    restore[k] = "9"
                elif k == "booking_end_hour":
                    restore[k] = "18"
                elif k == "booking_days":
                    restore[k] = "[0,1,2,3,4]"
        if restore:
            set_params(TEST_TENANT_ID, restore)
            if config.USE_PG_TENANTS:
                try:
                    pg_update_tenant_params(TEST_TENANT_ID, restore)
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# Test 4 : fallback SQLite (provider=none)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.skipif(SKIP_E2E, reason="TEST_TENANT_ID, TEST_TO_NUMBER requis")
async def test_fallback_sqlite_provider_none(async_client: AsyncClient, ensure_routing):
    """Tenant avec calendar_provider=none → get_slots ne doit pas 500."""
    from backend.tenant_config import get_params, set_params
    from backend.tenants_pg import pg_update_tenant_params
    from backend import config

    # Créer un tenant temporaire avec provider=none
    # On utilise un tenant_id fictif qui n'existe peut-être pas — on modifie le tenant de test
    # pour éviter de créer un tenant. On fait un test plus simple : on modifie temporairement
    # le tenant de test en provider=none, puis on restore.
    original = get_params(TEST_TENANT_ID)
    try:
        set_params(TEST_TENANT_ID, {"calendar_provider": "none"})
        if config.USE_PG_TENANTS:
            try:
                pg_update_tenant_params(TEST_TENANT_ID, {"calendar_provider": "none"})
            except Exception:
                pass

        payload = make_vapi_payload("get_slots", TEST_TO_NUMBER)
        r = await async_client.post("/api/vapi/tool", json=payload)
        assert r.status_code == 200, f"Expected 200 (no 500), got {r.status_code}: {r.text}"

        data = r.json()
        results = data.get("results") or []
        assert len(results) >= 1
        # Avec provider=none, on attend "Aucun créneau disponible" ou liste vide
        result_text = results[0].get("result") or ""
        assert "Aucun créneau" in result_text or "Créneaux disponibles" in result_text

        print(f"\n[E2E] fallback provider=none: status 200, result={result_text[:80]}...")
    finally:
        # Restaurer calendar_provider + calendar_id
        restore = {"calendar_provider": original.get("calendar_provider") or "google"}
        if original.get("calendar_id"):
            restore["calendar_id"] = original["calendar_id"]
        set_params(TEST_TENANT_ID, restore)
        if config.USE_PG_TENANTS:
            try:
                pg_update_tenant_params(TEST_TENANT_ID, restore)
            except Exception:
                pass
