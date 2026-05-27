"""Tests pour backend/log_setup.py — logs structures + buffer + middleware."""

from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient


# ---------- LogBuffer ----------


class TestLogBuffer:
    def test_buffer_appends_and_returns_recent(self):
        from backend.log_setup import LogBuffer
        buf = LogBuffer(maxlen=10)
        for i in range(5):
            buf.append({"level": "INFO", "msg": f"msg{i}", "i": i})
        recent = buf.recent(limit=10)
        assert len(recent) == 5
        # Ordre = plus recent en premier
        assert recent[0]["i"] == 4
        assert recent[-1]["i"] == 0

    def test_buffer_respects_maxlen(self):
        from backend.log_setup import LogBuffer
        buf = LogBuffer(maxlen=3)
        for i in range(10):
            buf.append({"level": "INFO", "msg": f"msg{i}", "i": i})
        assert buf.size() == 3
        recent = buf.recent(limit=10)
        # Les 3 plus recents (i=7,8,9), plus recent en premier
        assert [e["i"] for e in recent] == [9, 8, 7]

    def test_buffer_filter_by_level(self):
        from backend.log_setup import LogBuffer
        buf = LogBuffer(maxlen=10)
        buf.append({"level": "INFO", "msg": "a"})
        buf.append({"level": "WARNING", "msg": "b"})
        buf.append({"level": "ERROR", "msg": "c"})
        buf.append({"level": "INFO", "msg": "d"})
        assert len(buf.recent(level="INFO")) == 2
        assert len(buf.recent(level="WARNING")) == 1
        assert len(buf.recent(level="error")) == 1  # case insensitive

    def test_buffer_clear(self):
        from backend.log_setup import LogBuffer
        buf = LogBuffer(maxlen=10)
        buf.append({"level": "INFO", "msg": "a"})
        buf.clear()
        assert buf.size() == 0

    def test_buffer_limit_caps_results(self):
        from backend.log_setup import LogBuffer
        buf = LogBuffer(maxlen=100)
        for i in range(50):
            buf.append({"level": "INFO", "msg": f"m{i}", "i": i})
        recent = buf.recent(limit=5)
        assert len(recent) == 5


# ---------- request_id contextvar ----------


class TestRequestIdVar:
    def test_default_is_empty_string(self):
        from backend.log_setup import get_request_id
        # Hors contexte HTTP : ""
        assert get_request_id() in ("", "")  # peut etre setté par un autre test, on tolere

    def test_set_and_get(self):
        from backend.log_setup import set_request_id, get_request_id, _request_id_var
        token = set_request_id("abc-123")
        try:
            assert get_request_id() == "abc-123"
        finally:
            _request_id_var.reset(token)


# ---------- JsonFormatter ----------


class TestJsonFormatter:
    def test_format_outputs_valid_json(self):
        from backend.log_setup import JsonFormatter
        fmt = JsonFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname=__file__, lineno=1,
            msg="hello", args=None, exc_info=None,
        )
        out = fmt.format(record)
        data = json.loads(out)
        assert data["level"] == "INFO"
        assert data["logger"] == "test"
        assert data["msg"] == "hello"
        assert "ts" in data
        assert "request_id" in data

    def test_format_includes_extra_fields(self):
        from backend.log_setup import JsonFormatter
        fmt = JsonFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname=__file__, lineno=1,
            msg="action", args=None, exc_info=None,
        )
        record.user_id = 42
        record.tenant_id = "abc"
        out = fmt.format(record)
        data = json.loads(out)
        assert data["user_id"] == 42
        assert data["tenant_id"] == "abc"

    def test_format_includes_request_id_when_set(self):
        from backend.log_setup import JsonFormatter, set_request_id, _request_id_var
        token = set_request_id("rid-xyz")
        try:
            fmt = JsonFormatter()
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname=__file__, lineno=1,
                msg="m", args=None, exc_info=None,
            )
            data = json.loads(fmt.format(record))
            assert data["request_id"] == "rid-xyz"
        finally:
            _request_id_var.reset(token)

    def test_format_handles_non_serializable_extra(self):
        from backend.log_setup import JsonFormatter

        class Weird:
            def __repr__(self):
                return "<Weird>"

        fmt = JsonFormatter()
        record = logging.LogRecord(
            name="t", level=logging.INFO, pathname=__file__, lineno=1,
            msg="m", args=None, exc_info=None,
        )
        record.weird = Weird()
        out = fmt.format(record)
        data = json.loads(out)
        assert data["weird"] == "<Weird>"


# ---------- BufferHandler integration ----------


class TestBufferHandlerIntegration:
    def test_buffer_receives_log_via_logger(self):
        from backend.log_setup import LogBuffer, BufferHandler

        buf = LogBuffer(maxlen=10)
        h = BufferHandler(buf, level=logging.INFO)
        logger = logging.getLogger("test_buffer_handler_integration")
        logger.addHandler(h)
        logger.setLevel(logging.INFO)
        try:
            logger.info("hello", extra={"foo": "bar"})
            recent = buf.recent(limit=10)
            assert len(recent) >= 1
            entry = recent[0]
            assert entry["msg"] == "hello"
            assert entry["foo"] == "bar"
            assert entry["level"] == "INFO"
        finally:
            logger.removeHandler(h)


# ---------- configure_logging ----------


class TestConfigureLogging:
    def test_configure_is_idempotent(self, monkeypatch):
        from backend.log_setup import configure_logging
        configure_logging()
        n1 = len(logging.getLogger().handlers)
        configure_logging()
        n2 = len(logging.getLogger().handlers)
        # Pas de duplication des _uwi_log_handler tagges
        assert n2 == n1

    def test_log_json_env_activates_json_formatter(self, monkeypatch):
        from backend.log_setup import configure_logging, JsonFormatter
        monkeypatch.setenv("LOG_JSON", "true")
        configure_logging()
        root = logging.getLogger()
        # Au moins un handler avec JsonFormatter
        json_handlers = [
            h for h in root.handlers
            if isinstance(getattr(h, "formatter", None), JsonFormatter)
        ]
        assert len(json_handlers) >= 1


# ---------- Middleware HTTP ----------


class TestRequestLoggingMiddleware:
    @pytest.fixture
    def client(self):
        from backend.main import app
        return TestClient(app)

    def test_response_includes_x_request_id_header(self, client):
        r = client.get("/api/admin/auth/status")
        assert "x-request-id" in {k.lower() for k in r.headers.keys()}
        rid = r.headers.get("X-Request-ID") or r.headers.get("x-request-id")
        assert rid and len(rid) > 8

    def test_client_provided_request_id_is_reused(self, client):
        r = client.get(
            "/api/admin/auth/status",
            headers={"X-Request-ID": "client-rid-12345"},
        )
        rid = r.headers.get("X-Request-ID") or r.headers.get("x-request-id")
        assert rid == "client-rid-12345"

    def test_request_end_is_logged_in_buffer(self, client):
        from backend.log_setup import get_log_buffer
        buf = get_log_buffer()
        before = buf.size()
        client.get("/api/admin/auth/status")
        recent = buf.recent(limit=50)
        # Au moins un log "request_end" doit etre present
        request_ends = [e for e in recent if e.get("msg") == "request_end"]
        assert len(request_ends) >= 1
        last = request_ends[0]
        assert last["status_code"] == 200
        assert last["path"] == "/api/admin/auth/status"
        assert "duration_ms" in last
        assert last["request_id"]


# ---------- Endpoint /api/admin/logs/recent ----------


class TestLogsRecentEndpoint:
    @pytest.fixture
    def client(self):
        from backend.main import app
        return TestClient(app)

    @pytest.fixture
    def admin_headers(self):
        import os
        token = os.environ.get("ADMIN_API_TOKEN") or "test-admin-token-pytest"
        return {"Authorization": f"Bearer {token}"}

    def test_logs_recent_requires_auth(self, client):
        r = client.get("/api/admin/logs/recent")
        assert r.status_code == 401

    def test_logs_recent_with_admin_token_returns_items(self, client, admin_headers):
        client.get("/api/admin/auth/status")  # genere au moins un log
        r = client.get("/api/admin/logs/recent", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert isinstance(data["items"], list)
        assert "count" in data
        assert "buffer_size" in data

    def test_logs_recent_supports_limit(self, client, admin_headers):
        for _ in range(5):
            client.get("/api/admin/auth/status")
        r = client.get("/api/admin/logs/recent?limit=3", headers=admin_headers)
        assert r.status_code == 200
        assert len(r.json()["items"]) <= 3

    def test_logs_recent_supports_level_filter(self, client, admin_headers):
        client.get("/api/admin/auth/status")
        r = client.get("/api/admin/logs/recent?level=INFO", headers=admin_headers)
        assert r.status_code == 200
        items = r.json()["items"]
        for item in items:
            assert item["level"] == "INFO"

    def test_logs_recent_limit_validated(self, client, admin_headers):
        # limit=0 → 422
        r = client.get("/api/admin/logs/recent?limit=0", headers=admin_headers)
        assert r.status_code == 422
        # limit=10000 → 422
        r = client.get("/api/admin/logs/recent?limit=10000", headers=admin_headers)
        assert r.status_code == 422


# ---------- compute_metrics ----------


class TestComputeMetrics:
    def _make_buffer(self, entries):
        from backend.log_setup import LogBuffer
        buf = LogBuffer(maxlen=100)
        for e in entries:
            buf.append(e)
        return buf

    def test_empty_buffer_returns_zero_counts(self):
        from backend.log_setup import compute_metrics
        buf = self._make_buffer([])
        m = compute_metrics(buf)
        assert m["total_requests"] == 0
        assert m["by_status"] == {}
        assert m["latency"] == {}
        assert m["top_paths"] == []

    def test_counts_by_status_and_method(self):
        from backend.log_setup import compute_metrics
        buf = self._make_buffer([
            {"level": "INFO", "msg": "request_end", "method": "GET", "path": "/a", "status_code": 200, "duration_ms": 10},
            {"level": "INFO", "msg": "request_end", "method": "GET", "path": "/a", "status_code": 200, "duration_ms": 20},
            {"level": "INFO", "msg": "request_end", "method": "POST", "path": "/b", "status_code": 404, "duration_ms": 30},
            {"level": "INFO", "msg": "request_end", "method": "POST", "path": "/c", "status_code": 500, "duration_ms": 100},
        ])
        m = compute_metrics(buf)
        assert m["total_requests"] == 4
        assert m["by_status"]["200"] == 2
        assert m["by_status"]["404"] == 1
        assert m["by_status"]["500"] == 1
        assert m["by_method"]["GET"] == 2
        assert m["by_method"]["POST"] == 2
        assert m["errors_4xx"] == 1
        assert m["errors_5xx"] == 1

    def test_latency_percentiles(self):
        from backend.log_setup import compute_metrics
        # 100 latences de 1 a 100 ms
        entries = [
            {"level": "INFO", "msg": "request_end", "method": "GET", "path": "/x",
             "status_code": 200, "duration_ms": i + 1}
            for i in range(100)
        ]
        m = compute_metrics(self._make_buffer(entries))
        # p50 ~50, p95 ~95, p99 ~99
        assert 45 <= m["latency"]["p50_ms"] <= 55
        assert 90 <= m["latency"]["p95_ms"] <= 96
        assert 95 <= m["latency"]["p99_ms"] <= 100
        assert m["latency"]["max_ms"] == 100
        assert m["latency"]["avg_ms"] == 50

    def test_top_paths_sorted_by_count_with_errors(self):
        from backend.log_setup import compute_metrics
        buf = self._make_buffer([
            {"level": "INFO", "msg": "request_end", "method": "GET", "path": "/a", "status_code": 200, "duration_ms": 10},
            {"level": "INFO", "msg": "request_end", "method": "GET", "path": "/a", "status_code": 200, "duration_ms": 20},
            {"level": "INFO", "msg": "request_end", "method": "GET", "path": "/a", "status_code": 500, "duration_ms": 50},
            {"level": "INFO", "msg": "request_end", "method": "GET", "path": "/b", "status_code": 200, "duration_ms": 5},
        ])
        m = compute_metrics(buf)
        assert m["top_paths"][0]["path"] == "/a"
        assert m["top_paths"][0]["count"] == 3
        assert m["top_paths"][0]["errors"] == 1
        # Avg : (10+20+50)/3 ~= 26
        assert 25 <= m["top_paths"][0]["avg_ms"] <= 27
        assert m["top_paths"][1]["path"] == "/b"
        assert m["top_paths"][1]["count"] == 1

    def test_logs_by_level_counts_all_logs(self):
        from backend.log_setup import compute_metrics
        buf = self._make_buffer([
            {"level": "INFO", "msg": "x"},
            {"level": "INFO", "msg": "y"},
            {"level": "WARNING", "msg": "z"},
            {"level": "ERROR", "msg": "boom"},
        ])
        m = compute_metrics(buf)
        assert m["logs_by_level"]["INFO"] == 2
        assert m["logs_by_level"]["WARNING"] == 1
        assert m["logs_by_level"]["ERROR"] == 1

    def test_ignores_non_request_end_logs_for_http_stats(self):
        from backend.log_setup import compute_metrics
        buf = self._make_buffer([
            {"level": "INFO", "msg": "user_action", "method": "GET", "status_code": 200},
            {"level": "INFO", "msg": "request_end", "method": "GET", "path": "/x",
             "status_code": 200, "duration_ms": 10},
        ])
        m = compute_metrics(buf)
        assert m["total_requests"] == 1


# ---------- Endpoint /api/admin/logs/metrics ----------


class TestLogsMetricsEndpoint:
    @pytest.fixture
    def client(self):
        from backend.main import app
        return TestClient(app)

    @pytest.fixture
    def admin_headers(self):
        import os
        token = os.environ.get("ADMIN_API_TOKEN") or "test-admin-token-pytest"
        return {"Authorization": f"Bearer {token}"}

    def test_requires_auth(self, client):
        r = client.get("/api/admin/logs/metrics")
        assert r.status_code == 401

    def test_returns_metrics_structure(self, client, admin_headers):
        client.get("/api/admin/auth/status")  # generate at least one log
        r = client.get("/api/admin/logs/metrics", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        m = data["metrics"]
        assert "total_requests" in m
        assert "by_status" in m
        assert "by_method" in m
        assert "errors_4xx" in m
        assert "errors_5xx" in m
        assert "latency" in m
        assert "top_paths" in m
        assert "logs_by_level" in m
