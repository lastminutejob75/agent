"""Tests pour backend/health_checks.py + endpoint /api/health."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _reset_health_cache():
    """Vide le cache health entre tests pour eviter les fuites."""
    from backend.health_checks import reset_cache
    reset_cache()
    yield
    reset_cache()


# ---------- Checks individuels ----------


class TestCheckPostgres:
    def test_not_configured_when_no_url(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("PG_EVENTS_URL", raising=False)
        from backend.health_checks import check_postgres, STATUS_NOT_CONFIGURED
        result = check_postgres()
        assert result["status"] == STATUS_NOT_CONFIGURED

    def test_ok_when_query_succeeds(self, monkeypatch):
        from contextlib import contextmanager

        from backend.health_checks import check_postgres, STATUS_OK

        cur = MagicMock()
        cur.fetchone.return_value = (1,)
        cur.__enter__ = MagicMock(return_value=cur)
        cur.__exit__ = MagicMock(return_value=False)

        conn = MagicMock()
        conn.cursor.return_value = cur

        @contextmanager
        def _fake_pg_connection():
            yield conn

        monkeypatch.setenv("DATABASE_URL", "postgres://fake")
        monkeypatch.setattr("backend.pg_pool.pg_connection", _fake_pg_connection)

        result = check_postgres()
        assert result["status"] == STATUS_OK
        assert "latency_ms" in result

    def test_down_when_connection_fails(self, monkeypatch):
        from backend.health_checks import check_postgres, STATUS_DOWN
        monkeypatch.setenv("DATABASE_URL", "postgres://fake")

        def _raise(*a, **kw):
            raise RuntimeError("connection refused")

        monkeypatch.setattr("backend.pg_pool.pg_connection", _raise)
        result = check_postgres()
        assert result["status"] == STATUS_DOWN
        assert "connection refused" in result["detail"]


class TestCheckVapi:
    def test_not_configured_without_api_key(self, monkeypatch):
        monkeypatch.delenv("VAPI_API_KEY", raising=False)
        from backend.health_checks import check_vapi, STATUS_NOT_CONFIGURED
        result = check_vapi()
        assert result["status"] == STATUS_NOT_CONFIGURED

    def test_ok_on_200(self, monkeypatch):
        from backend.health_checks import check_vapi, STATUS_OK
        monkeypatch.setenv("VAPI_API_KEY", "fake-key")

        mock_resp = MagicMock(status_code=200)
        with patch("backend.health_checks.httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.get.return_value = mock_resp
            result = check_vapi()
        assert result["status"] == STATUS_OK

    def test_degraded_on_auth_failure(self, monkeypatch):
        from backend.health_checks import check_vapi, STATUS_DEGRADED
        monkeypatch.setenv("VAPI_API_KEY", "bad-key")

        mock_resp = MagicMock(status_code=401)
        with patch("backend.health_checks.httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.get.return_value = mock_resp
            result = check_vapi()
        assert result["status"] == STATUS_DEGRADED
        assert "auth failed" in result["detail"]

    def test_down_on_network_error(self, monkeypatch):
        from backend.health_checks import check_vapi, STATUS_DOWN
        monkeypatch.setenv("VAPI_API_KEY", "fake-key")

        with patch("backend.health_checks.httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.get.side_effect = RuntimeError("timeout")
            result = check_vapi()
        assert result["status"] == STATUS_DOWN


class TestCheckCalendar:
    def test_not_configured_when_disabled(self, monkeypatch):
        from backend.health_checks import check_calendar, STATUS_NOT_CONFIGURED
        import backend.config as config
        monkeypatch.setattr(config, "GOOGLE_CALENDAR_ENABLED", False)
        monkeypatch.setattr(config, "GOOGLE_CALENDAR_DISABLE_REASON", "no creds", raising=False)
        result = check_calendar()
        assert result["status"] == STATUS_NOT_CONFIGURED


class TestCheckEmail:
    def test_postmark_ok(self, monkeypatch):
        from backend.health_checks import check_email, STATUS_OK
        monkeypatch.setenv("EMAIL_PROVIDER", "postmark")
        monkeypatch.setenv("POSTMARK_SERVER_TOKEN", "tok-123")
        result = check_email()
        assert result["status"] == STATUS_OK

    def test_postmark_degraded_without_token(self, monkeypatch):
        from backend.health_checks import check_email, STATUS_DEGRADED
        monkeypatch.setenv("EMAIL_PROVIDER", "postmark")
        monkeypatch.delenv("POSTMARK_SERVER_TOKEN", raising=False)
        result = check_email()
        assert result["status"] == STATUS_DEGRADED

    def test_smtp_ok(self, monkeypatch):
        from backend.health_checks import check_email, STATUS_OK
        monkeypatch.delenv("EMAIL_PROVIDER", raising=False)
        monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
        monkeypatch.setenv("SMTP_EMAIL", "x@x.com")
        monkeypatch.setenv("SMTP_PASSWORD", "pass")
        result = check_email()
        assert result["status"] == STATUS_OK

    def test_not_configured(self, monkeypatch):
        from backend.health_checks import check_email, STATUS_NOT_CONFIGURED
        for var in ("EMAIL_PROVIDER", "POSTMARK_SERVER_TOKEN", "SMTP_HOST", "SMTP_EMAIL", "SMTP_PASSWORD"):
            monkeypatch.delenv(var, raising=False)
        result = check_email()
        assert result["status"] == STATUS_NOT_CONFIGURED


# ---------- Cache ----------


class TestCache:
    def test_check_is_cached(self, monkeypatch):
        from backend.health_checks import check_email
        monkeypatch.setenv("EMAIL_PROVIDER", "postmark")
        monkeypatch.setenv("POSTMARK_SERVER_TOKEN", "tok-123")

        r1 = check_email()
        # Modifie l'env entre les 2 appels : le cache doit retourner le 1er resultat
        monkeypatch.delenv("POSTMARK_SERVER_TOKEN", raising=False)
        r2 = check_email()
        assert r1 == r2  # cache hit

    def test_reset_cache_invalidates(self, monkeypatch):
        from backend.health_checks import check_email, reset_cache, STATUS_OK, STATUS_DEGRADED
        monkeypatch.setenv("EMAIL_PROVIDER", "postmark")
        monkeypatch.setenv("POSTMARK_SERVER_TOKEN", "tok")
        r1 = check_email()
        assert r1["status"] == STATUS_OK
        reset_cache()
        monkeypatch.delenv("POSTMARK_SERVER_TOKEN", raising=False)
        r2 = check_email()
        assert r2["status"] == STATUS_DEGRADED


# ---------- Aggregate ----------


class TestRunAllChecks:
    def test_run_all_returns_all_services(self):
        from backend.health_checks import run_all_checks
        result = run_all_checks()
        assert "status" in result
        assert "checked_at" in result
        assert "services" in result
        assert set(result["services"].keys()) == {
            "postgres", "vapi", "twilio", "stripe", "calendar", "email",
        }

    def test_aggregate_down_when_critical_service_down(self):
        from backend.health_checks import _aggregate_status, STATUS_DOWN
        services = {
            "postgres": {"status": STATUS_DOWN},
            "vapi": {"status": "ok"},
            "twilio": {"status": "ok"},
            "stripe": {"status": "ok"},
            "calendar": {"status": "ok"},
            "email": {"status": "ok"},
        }
        assert _aggregate_status(services) == STATUS_DOWN

    def test_aggregate_degraded_when_email_degraded(self):
        from backend.health_checks import _aggregate_status, STATUS_DEGRADED
        services = {
            "postgres": {"status": "ok"},
            "vapi": {"status": "ok"},
            "twilio": {"status": "ok"},
            "stripe": {"status": "ok"},
            "calendar": {"status": "ok"},
            "email": {"status": STATUS_DEGRADED},
        }
        assert _aggregate_status(services) == STATUS_DEGRADED

    def test_aggregate_ok_when_all_ok(self):
        from backend.health_checks import _aggregate_status, STATUS_OK
        services = {k: {"status": STATUS_OK} for k in ("postgres", "vapi", "twilio", "stripe", "calendar", "email")}
        assert _aggregate_status(services) == STATUS_OK


# ---------- Endpoint /api/health ----------


class TestApiHealthEndpoint:
    @pytest.fixture
    def client(self):
        from backend.main import app
        return TestClient(app)

    def test_endpoint_returns_200_when_ok(self, client, monkeypatch):
        from backend.health_checks import STATUS_OK
        with patch("backend.health_checks.run_all_checks") as mock_run:
            mock_run.return_value = {
                "status": STATUS_OK,
                "checked_at": "2026-05-09T12:00:00",
                "services": {},
            }
            r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_endpoint_returns_503_when_down(self, client):
        from backend.health_checks import STATUS_DOWN
        with patch("backend.health_checks.run_all_checks") as mock_run:
            mock_run.return_value = {
                "status": STATUS_DOWN,
                "checked_at": "2026-05-09T12:00:00",
                "services": {"postgres": {"status": STATUS_DOWN}},
            }
            r = client.get("/api/health")
        assert r.status_code == 503
        body = r.json()
        assert body["status"] == "down"

    def test_endpoint_returns_200_when_degraded(self, client):
        from backend.health_checks import STATUS_DEGRADED
        with patch("backend.health_checks.run_all_checks") as mock_run:
            mock_run.return_value = {
                "status": STATUS_DEGRADED,
                "checked_at": "2026-05-09T12:00:00",
                "services": {},
            }
            r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "degraded"

    def test_endpoint_is_public(self, client):
        """Pas d'auth requise (utile pour Railway/uptime monitoring)."""
        with patch("backend.health_checks.run_all_checks") as mock_run:
            mock_run.return_value = {
                "status": "ok",
                "checked_at": "2026-05-09T12:00:00",
                "services": {},
            }
            r = client.get("/api/health")
        assert r.status_code == 200
