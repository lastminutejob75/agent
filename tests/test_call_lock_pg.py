# tests/test_call_lock_pg.py
"""
P0 Phase 2.1: Tests lock PG anti webhooks simultanés.
T1: LockTimeout → 204
T2: lock utilisé quand PG enabled
T3: lock jamais appelé quand PG disabled
"""
import os
import pytest
from unittest.mock import patch, MagicMock


def test_lock_timeout_returns_204():
    """T1: mock pg_lock_call_session pour lever LockTimeout → endpoint retourne 204."""
    from backend.session_pg import LockTimeout
    from fastapi.testclient import TestClient
    from backend.main import app

    def _raise_lock_timeout(*args, **kwargs):
        raise LockTimeout("lock timeout")

    with patch("backend.routes.voice._pg_lock_ok", return_value=True):
        with patch("backend.session_pg.pg_lock_call_session", side_effect=_raise_lock_timeout):
            client = TestClient(app)
            payload = {
                "message": {
                    "type": "transcript",
                    "role": "user",
                    "transcript": "Bonjour",
                    "transcriptType": "final",
                },
                "call": {"id": "test_lock_timeout_001"},
            }
            resp = client.post("/api/vapi/webhook", json=payload)
            assert resp.status_code == 204


def test_lock_used_when_pg_enabled():
    """T2: pg_lock_call_session appelé quand _pg_lock_ok et endpoint vocal hit."""
    from fastapi.testclient import TestClient
    from backend.main import app

    mock_lock = MagicMock()
    mock_lock.return_value.__enter__ = MagicMock(return_value=None)
    mock_lock.return_value.__exit__ = MagicMock(return_value=False)

    with patch("backend.routes.voice._pg_lock_ok", return_value=True):
        with patch("backend.session_pg.pg_lock_call_session", mock_lock):
            client = TestClient(app)
            payload = {
                "message": {
                    "type": "transcript",
                    "role": "user",
                    "transcript": "Bonjour",
                    "transcriptType": "final",
                },
                "call": {"id": "test_lock_used_001"},
            }
            client.post("/api/vapi/webhook", json=payload)
            assert mock_lock.call_count >= 1


def test_lock_not_used_when_pg_disabled():
    """T3: USE_PG_CALL_JOURNAL=false → _pg_lock_ok retourne False."""
    with patch("backend.config.USE_PG_CALL_JOURNAL", False):
        from backend.routes.voice import _pg_lock_ok

        assert _pg_lock_ok() is False
