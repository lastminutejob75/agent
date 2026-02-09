"""
Tests de l'envoi du rapport quotidien par email.
- Endpoint POST /api/reports/daily (secret, réponse)
- send_daily_report_email (construction HTML, appel SMTP mocké)
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from datetime import date

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.email_service import send_daily_report_email, _build_html


# ============== Endpoint ==============

def test_daily_report_403_without_secret():
    """Sans header X-Report-Secret → 403."""
    with patch.dict(os.environ, {"REPORT_SECRET": "secret123"}, clear=False):
        client = TestClient(app)
        r = client.post("/api/reports/daily")
    assert r.status_code == 403


def test_daily_report_403_wrong_secret():
    """Mauvais X-Report-Secret → 403."""
    with patch.dict(os.environ, {"REPORT_SECRET": "secret123"}, clear=False):
        client = TestClient(app)
        r = client.post("/api/reports/daily", headers={"X-Report-Secret": "wrong"})
    assert r.status_code == 403


def test_daily_report_503_no_secret_configured():
    """REPORT_SECRET absent en env → 503."""
    with patch.dict(os.environ, {}, clear=False):
        old = os.environ.pop("REPORT_SECRET", None)
        try:
            client = TestClient(app)
            r = client.post("/api/reports/daily", headers={"X-Report-Secret": "any"})
            assert r.status_code == 503
        finally:
            if old is not None:
                os.environ["REPORT_SECRET"] = old


def test_daily_report_202_accepted_and_send_email_in_background(monkeypatch):
    """Bon secret + REPORT_EMAIL → 202 Accepted, send_daily_report_email appelée en arrière-plan."""
    import time
    sent = []

    def _fake_send(to, client_name, date_str, data):
        sent.append({"to": to, "client_name": client_name, "date_str": date_str, "data_keys": list(data.keys())})
        return True, None

    monkeypatch.setenv("REPORT_SECRET", "test_secret_rapport")
    monkeypatch.setenv("REPORT_EMAIL", "admin@test.fr")
    monkeypatch.setattr(
        "backend.routes.reports.send_daily_report_email",
        _fake_send,
    )
    monkeypatch.setattr(
        "backend.routes.reports.get_daily_report_data",
        lambda cid, d: {"calls_total": 0, "booked": 0, "transfers": 0, "abandons": 0, "events_count": 0},
    )

    client = TestClient(app)
    r = client.post("/api/reports/daily", headers={"X-Report-Secret": "test_secret_rapport"})

    assert r.status_code == 202
    body = r.json()
    assert body.get("status") == "accepted"
    time.sleep(0.4)  # laisser le thread arrière-plan exécuter
    assert len(sent) >= 1
    assert sent[0]["to"] == "admin@test.fr"
    assert "calls_total" in sent[0]["data_keys"]


# ============== Service email (construction + envoi mocké) ==============

def test_send_daily_report_email_success(monkeypatch):
    """send_daily_report_email avec SMTP mocké → True, pas d'exception."""
    sendmail_calls = []

    class FakeSMTP:
        def __init__(self, host, port):
            pass
        def starttls(self):
            pass
        def login(self, user, password):
            pass
        def sendmail(self, from_addr, to_addrs, msg):
            sendmail_calls.append({"from": from_addr, "to": list(to_addrs), "msg_len": len(msg)})
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setenv("SMTP_EMAIL", "noreply@test.fr")
    monkeypatch.setenv("SMTP_PASSWORD", "fake")
    monkeypatch.setenv("SMTP_HOST", "smtp.test.fr")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setattr("backend.services.email_service.smtplib.SMTP", FakeSMTP)

    data = {"calls_total": 2, "booked": 1, "transfers": 0, "abandons": 0, "events_count": 3}
    ok, err = send_daily_report_email("dest@test.fr", "Cabinet", date.today().isoformat(), data)

    assert ok is True
    assert err is None
    assert len(sendmail_calls) == 1
    assert sendmail_calls[0]["to"] == ["dest@test.fr"]
    assert sendmail_calls[0]["msg_len"] > 100


def test_send_daily_report_email_skip_if_no_smtp(monkeypatch):
    """Sans SMTP_EMAIL/SMTP_PASSWORD → False + message, pas d'envoi."""
    monkeypatch.delenv("SMTP_EMAIL", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    ok, err = send_daily_report_email("dest@test.fr", "Cabinet", "2026-02-04", {"calls_total": 0})
    assert ok is False
    assert err is not None
    assert "SMTP" in err


def test_build_html_contains_client_and_date():
    """_build_html produit du HTML avec client_name et date."""
    html = _build_html("Mon Cabinet", "2026-02-04", {"calls_total": 1, "booked": 0, "transfers": 0, "abandons": 0})
    assert "Mon Cabinet" in html
    assert "2026" in html
    assert "Rapport" in html and "appels" in html
    assert "feedback" in html.lower() or "améliorer" in html.lower()
    assert "<html" in html.lower()
