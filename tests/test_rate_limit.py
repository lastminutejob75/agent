"""Tests pour backend/rate_limit.py."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _reset_buckets(monkeypatch):
    """Vide les compteurs entre tests + reactive le rate-limit (test conftest le force "")."""
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    from backend.rate_limit import reset_all
    reset_all()
    yield
    reset_all()


# ---------- Helper unitaire ----------


class TestCheckRateLimit:
    def test_allows_under_limit(self):
        from backend.rate_limit import check_rate_limit, RateLimitExceeded
        req = _fake_request("1.2.3.4")
        # 5 tentatives sur fenetre 10s : ok
        for _ in range(5):
            check_rate_limit("test", req, max_attempts=5, window_seconds=10)

    def test_raises_when_over_limit(self):
        from backend.rate_limit import check_rate_limit, RateLimitExceeded
        req = _fake_request("1.2.3.4")
        for _ in range(5):
            check_rate_limit("test", req, max_attempts=5, window_seconds=10)
        with pytest.raises(RateLimitExceeded) as exc_info:
            check_rate_limit("test", req, max_attempts=5, window_seconds=10)
        assert exc_info.value.retry_after >= 1

    def test_isolation_between_keys(self):
        from backend.rate_limit import check_rate_limit
        req = _fake_request("1.2.3.4")
        for _ in range(5):
            check_rate_limit("login", req, max_attempts=5, window_seconds=10)
        # autre key → bucket different, pas de blocage
        for _ in range(5):
            check_rate_limit("onboarding", req, max_attempts=5, window_seconds=10)

    def test_isolation_between_clients(self):
        from backend.rate_limit import check_rate_limit
        for _ in range(5):
            check_rate_limit("test", _fake_request("1.1.1.1"), max_attempts=5, window_seconds=10)
        # autre IP → bucket different
        check_rate_limit("test", _fake_request("2.2.2.2"), max_attempts=5, window_seconds=10)

    def test_disabled_via_env(self, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
        from backend.rate_limit import check_rate_limit
        req = _fake_request("1.2.3.4")
        # 100 tentatives : ok car desactive
        for _ in range(100):
            check_rate_limit("test", req, max_attempts=5, window_seconds=10)

    def test_x_forwarded_for_takes_priority(self):
        from backend.rate_limit import check_rate_limit, get_attempts
        req = _fake_request("1.2.3.4", xff="9.9.9.9, 10.0.0.1")
        check_rate_limit("test", req, max_attempts=5, window_seconds=10)
        # Le compteur doit etre attribue a 9.9.9.9 (premier de la chaine XFF)
        assert get_attempts("test", "9.9.9.9") == 1
        assert get_attempts("test", "1.2.3.4") == 0

    def test_window_slides(self, monkeypatch):
        """Apres expiration de la fenetre, les anciennes tentatives sont oubliees."""
        from backend.rate_limit import check_rate_limit, RateLimitExceeded
        import backend.rate_limit as rl

        # Simule le passage du temps : on remplace time.monotonic
        current = [1000.0]
        monkeypatch.setattr(rl.time, "monotonic", lambda: current[0])

        req = _fake_request("1.2.3.4")
        for _ in range(5):
            check_rate_limit("test", req, max_attempts=5, window_seconds=10)
        with pytest.raises(RateLimitExceeded):
            check_rate_limit("test", req, max_attempts=5, window_seconds=10)

        # Fenetre passe (+11s)
        current[0] += 11
        # Ne doit plus lever
        check_rate_limit("test", req, max_attempts=5, window_seconds=10)


# ---------- Integration /api/admin/auth/login ----------


class TestLoginRateLimit:
    @pytest.fixture
    def client(self):
        from backend.main import app
        return TestClient(app)

    def test_login_rate_limit_blocks_after_max_attempts(self, client, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_LOGIN_MAX", "3")
        monkeypatch.setenv("RATE_LIMIT_LOGIN_WINDOW_S", "60")

        # 3 tentatives invalides : 401
        for _ in range(3):
            r = client.post(
                "/api/admin/auth/login",
                json={"email": "wrong@example.com", "password": "wrong"},
            )
            assert r.status_code == 401

        # 4eme : 429
        r = client.post(
            "/api/admin/auth/login",
            json={"email": "wrong@example.com", "password": "wrong"},
        )
        assert r.status_code == 429
        assert "Retry-After" in r.headers

    def test_login_rate_limit_disabled_allows_many(self, client, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
        for _ in range(10):
            r = client.post(
                "/api/admin/auth/login",
                json={"email": "wrong@example.com", "password": "wrong"},
            )
            # 401 ou 503, jamais 429
            assert r.status_code != 429


# ---------- Integration /api/public/onboarding ----------


class TestOnboardingRateLimit:
    @pytest.fixture
    def client(self):
        from backend.main import app
        return TestClient(app)

    def test_onboarding_rate_limit_blocks_after_max(self, client, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_ONBOARDING_MAX", "2")
        monkeypatch.setenv("RATE_LIMIT_ONBOARDING_WINDOW_S", "60")
        body = {
            "email": "test@example.com",
            "company_name": "Cabinet Test",
            "calendar_provider": "google",
            "calendar_id": "test@group.calendar.google.com",
        }
        # 2 requetes : possiblement OK ou erreur metier (peu importe le code <500 hors 429)
        for _ in range(2):
            r = client.post("/api/public/onboarding", json=body)
            assert r.status_code != 429
        # 3eme : 429
        r = client.post("/api/public/onboarding", json=body)
        assert r.status_code == 429
        assert "Retry-After" in r.headers


# ---------- Helpers ----------


def _fake_request(ip: str, xff: str = ""):
    """Construit un objet ressemblant a un Request pour les tests unitaires."""

    class FakeClient:
        def __init__(self, host):
            self.host = host

    class FakeRequest:
        def __init__(self, ip, xff):
            self.client = FakeClient(ip)
            self.headers = {"x-forwarded-for": xff} if xff else {}

    return FakeRequest(ip, xff)
