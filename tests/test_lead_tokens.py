"""Tests pour backend/lead_tokens.py (audit securite 2026-05).

Couvre les helpers HMAC : signature, verification, edge cases.
"""

from __future__ import annotations

import os
import time

import pytest

# Le secret est defini via conftest.py (JWT_SECRET) qui sert de fallback


@pytest.fixture(autouse=True)
def _ensure_secret(monkeypatch):
    """Assure qu'un secret est present (fallback JWT_SECRET du conftest)."""
    monkeypatch.setenv("LEAD_TOKEN_SECRET", "test-lead-token-secret-32-bytes-min-ok")


def test_make_token_returns_versioned_4parts():
    """Format `v1.{lead}.{exp}.{sig}` (4 parties separees par `.`)."""
    from backend.lead_tokens import make_lead_token

    t = make_lead_token("lead-abc-123")
    parts = t.split(".")
    assert len(parts) == 4
    assert parts[0] == "v1"


def test_make_token_with_empty_lead_raises():
    """make_lead_token() refuse un lead_id vide."""
    from backend.lead_tokens import make_lead_token

    with pytest.raises(ValueError):
        make_lead_token("")
    with pytest.raises(ValueError):
        make_lead_token("   ")


def test_verify_token_valid_round_trip():
    """Un token genere doit etre verifiable avec le bon lead_id."""
    from backend.lead_tokens import make_lead_token, verify_lead_token

    t = make_lead_token("lead-xyz-999")
    ok, lead_id, reason = verify_lead_token(t, expected_lead_id="lead-xyz-999")
    assert ok is True
    assert lead_id == "lead-xyz-999"
    assert reason is None


def test_verify_token_without_expected_lead_works():
    """Si expected_lead_id n'est pas fourni, on accepte n'importe quel lead_id."""
    from backend.lead_tokens import make_lead_token, verify_lead_token

    t = make_lead_token("any-lead")
    ok, lead_id, reason = verify_lead_token(t)
    assert ok is True
    assert lead_id == "any-lead"


def test_verify_token_lead_mismatch():
    """Token genere pour lead A, verifie pour lead B → lead_mismatch."""
    from backend.lead_tokens import make_lead_token, verify_lead_token

    t = make_lead_token("lead-A")
    ok, lead_id, reason = verify_lead_token(t, expected_lead_id="lead-B")
    assert ok is False
    assert reason == "lead_mismatch"


def test_verify_token_missing():
    """Token vide ou None → missing."""
    from backend.lead_tokens import verify_lead_token

    ok, _, reason = verify_lead_token("", expected_lead_id="x")
    assert ok is False
    assert reason == "missing"

    ok, _, reason = verify_lead_token(None, expected_lead_id="x")
    assert ok is False
    assert reason == "missing"


def test_verify_token_malformed():
    """Token avec format invalide → malformed."""
    from backend.lead_tokens import verify_lead_token

    cases = [
        "garbage",
        "v1.only-two-parts",
        "v1.x.y",  # 3 parties au lieu de 4
        "v1.x.y.z.extra",  # 5 parties
        "v1.!!!.???.@@@",  # base64url invalide
    ]
    for tok in cases:
        ok, _, reason = verify_lead_token(tok, expected_lead_id="x")
        assert ok is False, f"token '{tok}' should be invalid"
        assert reason in ("malformed", "version", "bad_signature"), f"unexpected reason for '{tok}': {reason}"


def test_verify_token_wrong_version():
    """Token avec version inconnue → version."""
    from backend.lead_tokens import verify_lead_token

    # Token bien forme mais version 'v2' (inexistante)
    fake = "v2.bGVhZA.MTcwMA.c2ln"
    ok, _, reason = verify_lead_token(fake, expected_lead_id="lead")
    assert ok is False
    assert reason == "version"


def test_verify_token_expired():
    """TTL negatif → expired."""
    from backend.lead_tokens import make_lead_token, verify_lead_token

    t = make_lead_token("lead-expire", ttl_seconds=-1)
    ok, _, reason = verify_lead_token(t, expected_lead_id="lead-expire")
    assert ok is False
    assert reason == "expired"


def test_verify_token_tampered_signature():
    """Token dont la signature a ete modifiee → bad_signature.

    NB : on modifie le 1er caractere et pas le dernier. En base64url sans
    padding, le dernier char d'une signature SHA-256 (43 chars) n'encode que
    4 bits utiles (les 2 derniers bits sont du padding), donc plusieurs chars
    differents peuvent decoder vers les memes octets et produire un faux
    negatif (~6% du temps). En modifiant un char interne, on garantit le
    changement.
    """
    from backend.lead_tokens import make_lead_token, verify_lead_token

    t = make_lead_token("lead-tamper")
    parts = t.split(".")
    sig = parts[3]
    # Inverser le 1er caractere de la signature (deterministe)
    tampered_sig = ("A" if sig[0] != "A" else "B") + sig[1:]
    tampered = ".".join(parts[:3] + [tampered_sig])

    ok, _, reason = verify_lead_token(tampered, expected_lead_id="lead-tamper")
    assert ok is False
    assert reason == "bad_signature"


def test_verify_token_tampered_lead_part():
    """Token dont le lead_id a ete modifie → bad_signature (la sig ne match plus)."""
    from backend.lead_tokens import _b64url_encode, make_lead_token, verify_lead_token

    t = make_lead_token("lead-original")
    parts = t.split(".")
    # Remplacer le lead_id encode mais garder la sig (qui n'est plus valide)
    fake_lead = _b64url_encode(b"lead-pirate")
    tampered = ".".join([parts[0], fake_lead, parts[2], parts[3]])

    ok, _, reason = verify_lead_token(tampered)
    assert ok is False
    assert reason == "bad_signature"


def test_verify_token_no_secret(monkeypatch):
    """Pas de secret configure → no_secret."""
    from backend.lead_tokens import make_lead_token, verify_lead_token

    t = make_lead_token("lead-x")
    # Effacer tous les secrets
    monkeypatch.delenv("LEAD_TOKEN_SECRET", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("ADMIN_SESSION_SECRET", raising=False)

    ok, _, reason = verify_lead_token(t, expected_lead_id="lead-x")
    assert ok is False
    assert reason == "no_secret"


def test_extract_token_from_query_string():
    """extract_token_from_request() recupere le token depuis ?token=..."""
    from backend.lead_tokens import extract_token_from_request

    class FakeReq:
        class _Q:
            def __init__(self, d):
                self._d = d

            def get(self, k):
                return self._d.get(k)

        def __init__(self, qs=None, headers=None):
            self.query_params = self._Q(qs or {})
            self.headers = headers or {}

    req = FakeReq(qs={"token": "abc.def.ghi.jkl"})
    assert extract_token_from_request(req) == "abc.def.ghi.jkl"


def test_extract_token_from_header():
    """extract_token_from_request() recupere le token depuis le header X-Lead-Token."""
    from backend.lead_tokens import extract_token_from_request

    class FakeReq:
        class _Q:
            def get(self, k):
                return None

        def __init__(self, h=None):
            self.query_params = self._Q()
            self.headers = h or {}

    # Header lowercase (FastAPI normalise)
    req = FakeReq(h={"x-lead-token": "header-token"})
    assert extract_token_from_request(req) == "header-token"


def test_extract_token_query_takes_priority_over_header():
    """Si les deux sont presents, la query string prime."""
    from backend.lead_tokens import extract_token_from_request

    class FakeReq:
        class _Q:
            def __init__(self, d):
                self._d = d

            def get(self, k):
                return self._d.get(k)

        def __init__(self, qs, h):
            self.query_params = self._Q(qs)
            self.headers = h

    req = FakeReq(qs={"token": "from-query"}, h={"x-lead-token": "from-header"})
    assert extract_token_from_request(req) == "from-query"


def test_extract_token_absent_returns_empty():
    """Aucune source → string vide (pas d'exception)."""
    from backend.lead_tokens import extract_token_from_request

    class FakeReq:
        class _Q:
            def get(self, k):
                return None

        def __init__(self):
            self.query_params = self._Q()
            self.headers = {}

    assert extract_token_from_request(FakeReq()) == ""


def test_secret_priority_chain(monkeypatch):
    """LEAD_TOKEN_SECRET prime sur JWT_SECRET prime sur ADMIN_SESSION_SECRET."""
    from backend.lead_tokens import _get_secret

    monkeypatch.setenv("LEAD_TOKEN_SECRET", "lead-sec")
    monkeypatch.setenv("JWT_SECRET", "jwt-sec")
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "admin-sec")
    assert _get_secret() == "lead-sec"

    monkeypatch.delenv("LEAD_TOKEN_SECRET")
    assert _get_secret() == "jwt-sec"

    monkeypatch.delenv("JWT_SECRET")
    assert _get_secret() == "admin-sec"

    monkeypatch.delenv("ADMIN_SESSION_SECRET")
    assert _get_secret() == ""


def test_token_is_url_safe():
    """Le token doit etre safe en query string (pas de caracteres a urlencode)."""
    from backend.lead_tokens import make_lead_token

    t = make_lead_token("lead-safe")
    # Caracteres autorises base64url + `.` + ASCII alphanum
    for c in t:
        assert c.isalnum() or c in "-._~"
