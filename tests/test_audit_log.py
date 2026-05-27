"""Tests pour backend/audit_log.py — middleware audit + helpers + endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------- Helpers internes ----------


class TestRedaction:
    def test_redact_masks_password_field(self):
        from backend.audit_log import _redact
        out = _redact({"username": "alice", "password": "secret123"})
        assert out["username"] == "alice"
        assert out["password"] == "***REDACTED***"

    def test_redact_case_insensitive(self):
        from backend.audit_log import _redact
        out = _redact({"PASSWORD": "x", "Authorization": "Bearer y", "TOKEN": "z"})
        assert out["PASSWORD"] == "***REDACTED***"
        assert out["Authorization"] == "***REDACTED***"
        assert out["TOKEN"] == "***REDACTED***"

    def test_redact_nested_dict(self):
        from backend.audit_log import _redact
        out = _redact({"user": {"name": "alice", "api_key": "k"}})
        assert out["user"]["name"] == "alice"
        assert out["user"]["api_key"] == "***REDACTED***"

    def test_redact_list_of_dicts(self):
        from backend.audit_log import _redact
        out = _redact([{"password": "x"}, {"name": "alice"}])
        assert out[0]["password"] == "***REDACTED***"
        assert out[1]["name"] == "alice"

    def test_redact_truncates_long_strings(self):
        from backend.audit_log import _redact
        out = _redact({"data": "a" * 2000})
        assert "...[truncated" in out["data"]
        assert len(out["data"]) < 2000

    def test_redact_handles_depth_limit(self):
        from backend.audit_log import _redact
        nested = {"a": {"b": {"c": {"d": {"e": {"f": {"g": {"h": "deep"}}}}}}}}
        out = _redact(nested)
        # Doit etre tronque a un certain niveau (pas de stack overflow)
        assert out is not None


class TestSanitizePayload:
    def test_sanitize_empty_returns_none(self):
        from backend.audit_log import _sanitize_payload
        assert _sanitize_payload(None) is None
        assert _sanitize_payload(b"") is None

    def test_sanitize_invalid_json_returns_raw(self):
        from backend.audit_log import _sanitize_payload
        out = _sanitize_payload(b"not valid json")
        assert out is not None
        assert out["_note"] == "non-json"

    def test_sanitize_valid_json_redacts_secrets(self):
        from backend.audit_log import _sanitize_payload
        out = _sanitize_payload(b'{"email": "a@b.fr", "password": "secret"}')
        assert out["email"] == "a@b.fr"
        assert out["password"] == "***REDACTED***"

    def test_sanitize_truncates_huge_payload(self):
        import json
        from backend.audit_log import _sanitize_payload
        # Plein de petites cles : evite la troncature par-string et declenche
        # la troncature globale du JSON.
        huge = {f"k{i}": f"v{i}" * 5 for i in range(500)}
        out = _sanitize_payload(json.dumps(huge).encode("utf-8"))
        assert out.get("_truncated") is True
        assert out.get("_size_bytes", 0) > 4096


class TestExtractTenantId:
    def test_extracts_from_tenants_path(self):
        from backend.audit_log import _extract_tenant_id_from_path
        assert _extract_tenant_id_from_path("/api/admin/tenants/42") == 42
        assert _extract_tenant_id_from_path("/api/admin/tenants/42/suspend") == 42
        assert _extract_tenant_id_from_path("/api/admin/tenants/123/billing/cancel") == 123

    def test_extracts_from_clients_path(self):
        from backend.audit_log import _extract_tenant_id_from_path
        assert _extract_tenant_id_from_path("/api/admin/clients/7/anything") == 7

    def test_returns_none_when_no_match(self):
        from backend.audit_log import _extract_tenant_id_from_path
        assert _extract_tenant_id_from_path("/api/admin/leads") is None
        assert _extract_tenant_id_from_path("/api/health") is None


class TestClientIpExtraction:
    def test_xff_first_element_wins(self):
        from backend.audit_log import _client_ip_from_headers
        ip = _client_ip_from_headers(
            {"x-forwarded-for": "1.2.3.4, 10.0.0.1"}, fallback="9.9.9.9"
        )
        assert ip == "1.2.3.4"

    def test_x_real_ip_used_if_no_xff(self):
        from backend.audit_log import _client_ip_from_headers
        ip = _client_ip_from_headers({"x-real-ip": "5.6.7.8"}, fallback="9.9.9.9")
        assert ip == "5.6.7.8"

    def test_fallback_used_if_no_headers(self):
        from backend.audit_log import _client_ip_from_headers
        assert _client_ip_from_headers({}, fallback="9.9.9.9") == "9.9.9.9"


class TestIsAdminWritePath:
    def test_post_admin_tracked(self):
        from backend.audit_log import _is_admin_write_path
        assert _is_admin_write_path("POST", "/api/admin/tenants/42/suspend") is True
        assert _is_admin_write_path("PATCH", "/api/admin/tenants/42/params") is True
        assert _is_admin_write_path("DELETE", "/api/admin/tenants/42") is True

    def test_get_admin_not_tracked(self):
        from backend.audit_log import _is_admin_write_path
        assert _is_admin_write_path("GET", "/api/admin/tenants") is False

    def test_login_excluded(self):
        from backend.audit_log import _is_admin_write_path
        assert _is_admin_write_path("POST", "/api/admin/auth/login") is False
        assert _is_admin_write_path("POST", "/api/admin/auth/logout") is False

    def test_non_admin_path_not_tracked(self):
        from backend.audit_log import _is_admin_write_path
        assert _is_admin_write_path("POST", "/api/public/onboarding") is False
        assert _is_admin_write_path("POST", "/api/vapi/webhook") is False


# ---------- write_audit_entry / fetch ----------


class TestWriteAuditEntry:
    def test_write_logs_applicatively_even_when_pg_unavailable(self, caplog):
        # L'import de pg_connection est lazy dans write_audit_entry — on patche
        # le symbole sur le module backend.pg_pool d'origine.
        from backend.audit_log import write_audit_entry
        with patch("backend.pg_pool.pg_connection", side_effect=Exception("no pg")):
            ok = write_audit_entry(
                actor_email="admin@uwiapp.com",
                method="POST",
                path="/api/admin/tenants/42",
            )
        assert ok is False  # PG indispo → False, mais pas d'exception

    def test_write_succeeds_when_pg_works(self):
        from backend.audit_log import write_audit_entry
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_conn.cursor.return_value.__exit__.return_value = False

        # pg_connection est un context manager : __enter__ retourne la conn.
        cm = MagicMock()
        cm.__enter__.return_value = mock_conn
        cm.__exit__.return_value = False

        with patch("backend.pg_pool.pg_connection", return_value=cm):
            ok = write_audit_entry(
                actor_email="admin@uwiapp.com",
                actor_role="admin",
                tenant_id=42,
                method="POST",
                path="/api/admin/tenants/42/suspend",
                status_code=200,
                payload={"mode": "hard"},
                description="Suspended tenant 42",
            )
        assert ok is True
        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO admin_audit_log" in sql


class TestPurgeOldAuditEntries:
    def test_purge_returns_zero_when_pg_unavailable(self):
        from backend.audit_log import purge_old_audit_entries
        with patch("backend.pg_pool.pg_connection", side_effect=Exception("no pg")):
            assert purge_old_audit_entries(retention_days=365) == 0

    def test_purge_no_op_when_retention_invalid(self, caplog):
        from backend.audit_log import purge_old_audit_entries
        assert purge_old_audit_entries(retention_days=0) == 0
        assert purge_old_audit_entries(retention_days=-5) == 0

    def test_purge_returns_rowcount(self):
        from backend.audit_log import purge_old_audit_entries
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 42
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_conn.cursor.return_value.__exit__.return_value = False
        cm = MagicMock()
        cm.__enter__.return_value = mock_conn
        cm.__exit__.return_value = False

        with patch("backend.pg_pool.pg_connection", return_value=cm):
            n = purge_old_audit_entries(retention_days=180)
        assert n == 42
        # Verifie que la requete contient bien un DELETE et l'interval correct
        sql = mock_cursor.execute.call_args[0][0]
        assert "DELETE FROM admin_audit_log" in sql
        params = mock_cursor.execute.call_args[0][1]
        assert "180" in params


class TestFetchRecentAuditEntries:
    def test_returns_empty_when_pg_unavailable(self):
        from backend.audit_log import fetch_recent_audit_entries
        with patch("backend.pg_pool.pg_connection", side_effect=Exception("no pg")):
            assert fetch_recent_audit_entries(limit=10) == []

    def test_filters_passed_correctly(self):
        from datetime import datetime

        from backend.audit_log import fetch_recent_audit_entries
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "id": 1, "actor_email": "a@b.fr", "actor_role": "admin",
                "tenant_id": 42, "method": "POST", "path": "/api/admin/tenants/42",
                "status_code": 200, "request_id": "rid-1", "ip": "1.2.3.4",
                "user_agent": "ua", "payload": {}, "description": None,
                "created_at": datetime(2026, 5, 1, 12, 0, 0),
            }
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_conn.cursor.return_value.__exit__.return_value = False

        cm = MagicMock()
        cm.__enter__.return_value = mock_conn
        cm.__exit__.return_value = False

        with patch("backend.pg_pool.pg_connection", return_value=cm):
            items = fetch_recent_audit_entries(
                limit=10, actor_email="a@b.fr", tenant_id=42, method="post"
            )
        assert len(items) == 1
        assert items[0]["id"] == 1
        assert isinstance(items[0]["created_at"], str)
        assert "2026-05-01" in items[0]["created_at"]
        # method upperise dans les params SQL
        params = mock_cursor.execute.call_args[0][1]
        assert "POST" in params


# ---------- Middleware integration ----------


class TestAuditMiddleware:
    @pytest.fixture
    def client(self):
        from backend.main import app
        return TestClient(app)

    @pytest.fixture
    def admin_headers(self):
        import os
        token = os.environ.get("ADMIN_API_TOKEN") or "test-admin-token-pytest"
        return {"Authorization": f"Bearer {token}"}

    def test_get_request_does_not_trigger_write(self, client, admin_headers):
        # GET sur /api/admin/* ne doit PAS appeler write_audit_entry
        with patch("backend.audit_log.write_audit_entry") as mock_write:
            client.get("/api/admin/auth/status")
            mock_write.assert_not_called()

    def test_post_admin_triggers_write(self, client, admin_headers):
        with patch("backend.audit_log.write_audit_entry") as mock_write:
            mock_write.return_value = True
            # Endpoint qui existe et accepte POST. On utilise un 404 endpoint admin :
            # le middleware s'execute meme si la route n'existe pas (apres call_next).
            client.post(
                "/api/admin/tenants/99999/params",
                headers={**admin_headers, "Content-Type": "application/json"},
                json={"params": {"foo": "bar", "password": "shouldberedacted"}},
            )
            assert mock_write.called
            kwargs = mock_write.call_args.kwargs
            assert kwargs["method"] == "POST"
            assert kwargs["path"] == "/api/admin/tenants/99999/params"
            assert kwargs["tenant_id"] == 99999
            # Payload sanitise : password masque
            payload = kwargs.get("payload") or {}
            assert payload.get("params", {}).get("password") == "***REDACTED***"

    def test_login_is_not_audited(self, client):
        # /api/admin/auth/login contient un mot de passe : on l'exclut explicitement
        with patch("backend.audit_log.write_audit_entry") as mock_write:
            client.post(
                "/api/admin/auth/login",
                json={"email": "x@y.fr", "password": "wrong"},
            )
            mock_write.assert_not_called()


# ---------- Endpoint GET /api/admin/audit-log ----------


class TestAuditLogEndpoint:
    @pytest.fixture
    def client(self):
        from backend.main import app
        return TestClient(app)

    @pytest.fixture
    def admin_headers(self):
        import os
        token = os.environ.get("ADMIN_API_TOKEN") or "test-admin-token-pytest"
        return {"Authorization": f"Bearer {token}"}

    def test_audit_log_requires_auth(self, client):
        r = client.get("/api/admin/audit-log")
        assert r.status_code == 401

    def test_audit_log_returns_list(self, client, admin_headers):
        with patch("backend.audit_log.fetch_recent_audit_entries", return_value=[]):
            r = client.get("/api/admin/audit-log", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert isinstance(data["items"], list)
        assert data["count"] == 0

    def test_audit_log_passes_filters(self, client, admin_headers):
        with patch("backend.audit_log.fetch_recent_audit_entries", return_value=[]) as mock_fetch:
            r = client.get(
                "/api/admin/audit-log?limit=50&offset=10&actor_email=a@b.fr&tenant_id=42&method=POST&path_prefix=/api/admin/tenants",
                headers=admin_headers,
            )
        assert r.status_code == 200
        kwargs = mock_fetch.call_args.kwargs
        assert kwargs["limit"] == 50
        assert kwargs["offset"] == 10
        assert kwargs["actor_email"] == "a@b.fr"
        assert kwargs["tenant_id"] == 42
        assert kwargs["method"] == "POST"
        assert kwargs["path_prefix"] == "/api/admin/tenants"

    def test_audit_log_validates_limit_range(self, client, admin_headers):
        r = client.get("/api/admin/audit-log?limit=0", headers=admin_headers)
        assert r.status_code == 422
        r = client.get("/api/admin/audit-log?limit=10000", headers=admin_headers)
        assert r.status_code == 422
