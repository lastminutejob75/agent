"""Tests KPI « aujourd'hui » (distinct du total 7j)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def tenant_detail():
    return {"params": {"timezone": "Europe/Paris"}}


def test_get_kpis_today_counts_bookings_in_local_day(tenant_detail):
    from backend.routes.admin import _get_kpis_today

    fixed = datetime(2026, 5, 30, 12, 0, 0, tzinfo=timezone.utc)

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, query, params):
            self.query = query
            self.params = params

        def fetchone(self):
            if "vapi_calls" in getattr(self, "query", ""):
                return {"calls": 0}
            return {"bookings": 2, "transfers": 0}

    fake_conn = MagicMock()
    fake_conn.cursor.return_value = FakeCursor()
    fake_conn.__enter__ = lambda s: s
    fake_conn.__exit__ = lambda s, *a: False

    with patch("backend.routes.admin.os.environ.get", side_effect=lambda k, d=None: "postgres://x" if "DATABASE" in k else d):
        with patch("backend.pg_pool.pg_connection", return_value=fake_conn):
            with patch("backend.pg_tenant_context.set_tenant_id_on_connection"):
                with patch("backend.public_bookings_pg.count_public_bookings", return_value=1):
                    with patch("backend.routes.admin.datetime") as mock_dt:
                        mock_dt.now.return_value = fixed.astimezone(
                            __import__("zoneinfo").ZoneInfo("Europe/Paris")
                        )
                        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
                        out = _get_kpis_today(2, "Europe/Paris")

    assert out["bookings"] == 3
    assert out["calls"] == 0
    assert "date" in out


def test_pg_update_tenant_params_blocks_protected_key_drop():
    from backend import tenants_pg

    captured = {}

    def _fake_connect(url):
        class Cur:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def execute(self_inner, q, params):
                captured["merged"] = params[0]

            @property
            def rowcount(self_inner):
                return 1

        class Conn:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def cursor(self_inner):
                return Cur()

            def commit(self_inner):
                pass

        return Conn()

    fake_psycopg = type("M", (), {"connect": staticmethod(_fake_connect)})()
    current = {
        "vapi_assistant_id": "abc",
        "contact_email": "demo@uwi.app",
        "hds_enabled": False,
    }

    with patch.dict("sys.modules", {"psycopg": fake_psycopg}):
        with patch("backend.tenants_pg._pg_url", return_value="postgres://test"):
            with patch("backend.tenants_pg.pg_get_tenant_params", return_value=(current, "pg")):
                with patch("backend.tenants_pg.pg_load_tenant_params_bypass", return_value=current):
                    with patch("backend.tenants_pg.set_tenant_id_on_connection"):
                        ok = tenants_pg.pg_update_tenant_params(2, {"hds_enabled": True})
                        assert ok is True
                        merged = __import__("json").loads(captured["merged"])
                        assert merged["vapi_assistant_id"] == "abc"
                        assert merged["hds_enabled"] is True

                        ok2 = tenants_pg.pg_update_tenant_params(2, {"vapi_assistant_id": ""})
                        assert ok2 is False


def test_backfill_parse_context():
    from scripts.backfill_public_bookings_from_ivr import _parse_context

    ctx = _parse_context('{"patient_name":"Alice","slot_label":"Lundi 10h","motif":"Contrôle"}')
    assert ctx["patient_name"] == "Alice"
    assert _parse_context("") == {}
