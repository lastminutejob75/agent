# tests/test_tenant_resolution_whatsapp.py
"""Tests résolution tenant depuis numéro WhatsApp (To)."""
from __future__ import annotations

import pytest
from fastapi import HTTPException


def test_resolve_tenant_from_whatsapp_unknown_raises_404(monkeypatch):
    """Numéro inconnu → 404."""
    import backend.tenant_routing as tr
    monkeypatch.setattr(tr.config, "USE_PG_TENANTS", False)
    # SQLite sans route pour ce numéro → 404
    with pytest.raises(HTTPException) as exc:
        tr.resolve_tenant_from_whatsapp("+33999999999")
    assert exc.value.status_code == 404
    assert "No tenant" in (exc.value.detail or "")


def test_resolve_tenant_from_whatsapp_invalid_number_raises_400(monkeypatch):
    """Format invalide (pas de +) → 400."""
    import backend.tenant_routing as tr
    with pytest.raises(HTTPException) as exc:
        tr.resolve_tenant_from_whatsapp("0612345678")
    assert exc.value.status_code == 400
    assert "Invalid" in (exc.value.detail or "")


def test_resolve_tenant_from_whatsapp_sqlite_route(monkeypatch, tmp_path):
    """Avec une route SQLite channel=whatsapp → tenant_id correct."""
    import backend.tenant_routing as tr
    import backend.db as db
    monkeypatch.setattr(tr.config, "USE_PG_TENANTS", False)
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "agent.db"))
    db.init_db(days=0)
    db.ensure_tenant_config()
    conn = db.get_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO tenant_routing (channel, did_key, tenant_id) VALUES (?, ?, ?)",
            ("whatsapp", "+33600000000", 42),
        )
        conn.commit()
    finally:
        conn.close()

    tenant_id = tr.resolve_tenant_from_whatsapp("+33600000000")
    assert tenant_id == 42

    tenant_id_spaces = tr.resolve_tenant_from_whatsapp("+33 6 00 00 00 00")
    assert tenant_id_spaces == 42

    tenant_id_prefix = tr.resolve_tenant_from_whatsapp("whatsapp:+33600000000")
    assert tenant_id_prefix == 42


def test_current_tenant_id_context_var():
    """current_tenant_id ContextVar peut être set/get."""
    from backend.tenant_routing import current_tenant_id
    token = current_tenant_id.set("123")
    try:
        assert current_tenant_id.get() == "123"
    finally:
        current_tenant_id.reset(token)
    assert current_tenant_id.get() is None
