"""Tests pour backend/system_info.py."""

from __future__ import annotations

from unittest.mock import patch


class TestIsSecretKey:
    def test_obvious_secrets(self):
        from backend.system_info import _is_secret_key
        assert _is_secret_key("PASSWORD") is True
        assert _is_secret_key("password") is True
        assert _is_secret_key("API_KEY") is True
        assert _is_secret_key("STRIPE_SECRET_KEY") is True
        assert _is_secret_key("VAPI_API_KEY") is True
        assert _is_secret_key("JWT_SECRET") is True

    def test_not_secrets(self):
        from backend.system_info import _is_secret_key
        assert _is_secret_key("LOG_LEVEL") is False
        assert _is_secret_key("ENV") is False
        assert _is_secret_key("PORT") is False


class TestFilteredEnv:
    def test_returns_only_whitelisted_vars(self, monkeypatch):
        from backend.system_info import _filtered_env
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("EVIL_SECRET_KEY", "ne-doit-pas-apparaitre")
        out = _filtered_env()
        assert "LOG_LEVEL" in out["vars"]
        assert out["vars"]["LOG_LEVEL"] == "DEBUG"
        # La variable arbitraire ne doit pas etre dans vars (whitelist)
        assert "EVIL_SECRET_KEY" not in out["vars"]

    def test_presence_only_secrets_no_value(self, monkeypatch):
        from backend.system_info import _filtered_env
        monkeypatch.setenv("VAPI_API_KEY", "mon-vrai-secret-123")
        out = _filtered_env()
        assert out["configured"]["VAPI_API_KEY"] is True
        # La valeur ne doit pas apparaitre dans la sortie
        assert "mon-vrai-secret-123" not in str(out)

    def test_presence_only_unset_returns_false(self, monkeypatch):
        from backend.system_info import _filtered_env
        monkeypatch.delenv("VAPI_API_KEY", raising=False)
        out = _filtered_env()
        assert out["configured"]["VAPI_API_KEY"] is False


class TestFormatUptime:
    def test_seconds(self):
        from backend.system_info import _format_uptime
        assert _format_uptime(45) == "45s"

    def test_minutes_seconds(self):
        from backend.system_info import _format_uptime
        assert _format_uptime(125) == "2m 05s"

    def test_hours_minutes(self):
        from backend.system_info import _format_uptime
        assert _format_uptime(3725) == "1h 02m"

    def test_days(self):
        from backend.system_info import _format_uptime
        assert _format_uptime(86400 + 3 * 3600 + 30 * 60) == "1j 3h 30m"


class TestGitSha:
    def test_uses_railway_env_first(self, monkeypatch):
        from backend.system_info import _git_sha_short
        monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "abcdef1234567890")
        sha = _git_sha_short()
        assert sha == "abcdef12"  # tronque a 8

    def test_returns_none_when_unavailable(self, monkeypatch):
        from backend.system_info import _git_sha_short
        monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
        monkeypatch.delenv("GIT_COMMIT_SHA", raising=False)
        monkeypatch.delenv("SOURCE_COMMIT", raising=False)
        monkeypatch.delenv("VERCEL_GIT_COMMIT_SHA", raising=False)
        # On ne peut pas tester le fallback .git en isolation sans mock plus invasif.
        # On verifie au moins que ca ne crash pas et retourne soit un sha (si .git
        # existe sur le checkout de test) soit None.
        sha = _git_sha_short()
        assert sha is None or isinstance(sha, str)


class TestGetSystemInfo:
    def test_structure(self):
        from backend.system_info import get_system_info
        info = get_system_info()
        # Sections requises
        assert "build" in info
        assert "runtime" in info
        assert "process" in info
        assert "env" in info
        assert "now" in info

    def test_runtime_contains_python_version(self):
        import sys

        from backend.system_info import get_system_info
        info = get_system_info()
        assert info["runtime"]["python_version"] == sys.version.split()[0]
        assert info["runtime"]["python_implementation"]

    def test_process_uptime_increases(self):
        import time

        from backend.system_info import get_system_info, reset_start_time_for_tests
        reset_start_time_for_tests(time.time() - 5.0)
        info = get_system_info()
        assert info["process"]["uptime_seconds"] >= 4
        assert "s" in info["process"]["uptime_label"]

    def test_env_no_secrets_in_output(self, monkeypatch):
        from backend.system_info import get_system_info
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_extremely_secret_value_42")
        info = get_system_info()
        # Ne doit jamais apparaitre dans la sortie complete
        assert "sk_live_extremely_secret_value_42" not in str(info)
        # Mais flag de presence oui
        assert info["env"]["configured"]["STRIPE_SECRET_KEY"] is True
