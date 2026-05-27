"""Tests pour backend/sentry_setup.py — initialisation conditionnelle."""

from __future__ import annotations

from unittest.mock import patch

import pytest

# Skip toute la suite si sentry-sdk n'est pas installe (cas local sans
# pip install -r requirements.txt). La CI installe tout.
sentry_sdk = pytest.importorskip("sentry_sdk")


class TestDetectEnvironment:
    def test_explicit_sentry_env_wins(self, monkeypatch):
        from backend.sentry_setup import _detect_environment
        monkeypatch.setenv("SENTRY_ENVIRONMENT", "PROD")
        monkeypatch.setenv("RAILWAY_ENVIRONMENT", "staging")
        assert _detect_environment() == "prod"

    def test_railway_env_used_if_no_sentry_env(self, monkeypatch):
        from backend.sentry_setup import _detect_environment
        monkeypatch.delenv("SENTRY_ENVIRONMENT", raising=False)
        monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
        assert _detect_environment() == "production"

    def test_default_is_development(self, monkeypatch):
        from backend.sentry_setup import _detect_environment
        monkeypatch.delenv("SENTRY_ENVIRONMENT", raising=False)
        monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
        monkeypatch.delenv("ENV", raising=False)
        assert _detect_environment() == "development"


class TestInitSentry:
    def setup_method(self):
        # Reset l'etat avant chaque test
        from backend.sentry_setup import reset_for_tests
        reset_for_tests()

    def test_init_returns_false_when_no_dsn(self, monkeypatch):
        from backend.sentry_setup import init_sentry, is_initialized
        monkeypatch.delenv("SENTRY_DSN", raising=False)
        assert init_sentry() is False
        assert is_initialized() is False

    def test_init_returns_false_when_empty_dsn(self, monkeypatch):
        from backend.sentry_setup import init_sentry
        monkeypatch.setenv("SENTRY_DSN", "")
        assert init_sentry() is False

    def test_init_calls_sentry_sdk_when_dsn_present(self, monkeypatch):
        from backend.sentry_setup import init_sentry, is_initialized
        monkeypatch.setenv("SENTRY_DSN", "https://fake@sentry.io/123")
        with patch("sentry_sdk.init") as mock_init:
            ok = init_sentry()
        assert ok is True
        assert is_initialized() is True
        mock_init.assert_called_once()
        kwargs = mock_init.call_args.kwargs
        assert kwargs["dsn"] == "https://fake@sentry.io/123"
        assert kwargs["send_default_pii"] is False

    def test_init_idempotent(self, monkeypatch):
        from backend.sentry_setup import init_sentry
        monkeypatch.setenv("SENTRY_DSN", "https://fake@sentry.io/123")
        with patch("sentry_sdk.init") as mock_init:
            assert init_sentry() is True
            assert init_sentry() is True
        # init() doit etre appele 1 seule fois
        assert mock_init.call_count == 1

    def test_init_uses_traces_sample_rate(self, monkeypatch):
        from backend.sentry_setup import init_sentry
        monkeypatch.setenv("SENTRY_DSN", "https://fake@sentry.io/123")
        monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "0.25")
        with patch("sentry_sdk.init") as mock_init:
            init_sentry()
        kwargs = mock_init.call_args.kwargs
        assert kwargs["traces_sample_rate"] == 0.25

    def test_init_invalid_traces_rate_falls_back_to_zero(self, monkeypatch):
        from backend.sentry_setup import init_sentry
        monkeypatch.setenv("SENTRY_DSN", "https://fake@sentry.io/123")
        monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "not-a-number")
        with patch("sentry_sdk.init") as mock_init:
            init_sentry()
        kwargs = mock_init.call_args.kwargs
        assert kwargs["traces_sample_rate"] == 0.0


class TestBeforeSend:
    def test_4xx_http_exception_filtered_out(self):
        from fastapi import HTTPException

        from backend.sentry_setup import _before_send
        exc = HTTPException(status_code=404, detail="Not Found")
        event = {"foo": "bar"}
        out = _before_send(event, {"exc_info": (HTTPException, exc, None)})
        assert out is None  # filtre

    def test_5xx_http_exception_passes_through(self):
        from fastapi import HTTPException

        from backend.sentry_setup import _before_send
        exc = HTTPException(status_code=500, detail="Server Error")
        event = {"foo": "bar"}
        out = _before_send(event, {"exc_info": (HTTPException, exc, None)})
        assert out == event  # pas filtre

    def test_other_exceptions_pass_through(self):
        from backend.sentry_setup import _before_send
        exc = ValueError("oops")
        event = {"foo": "bar"}
        out = _before_send(event, {"exc_info": (ValueError, exc, None)})
        assert out == event


class TestCaptureHelpers:
    def test_capture_exception_no_op_when_not_initialized(self):
        from backend.sentry_setup import capture_exception, reset_for_tests
        reset_for_tests()
        # Ne doit pas crash
        capture_exception(ValueError("test"))

    def test_capture_message_no_op_when_not_initialized(self):
        from backend.sentry_setup import capture_message, reset_for_tests
        reset_for_tests()
        capture_message("hello")
