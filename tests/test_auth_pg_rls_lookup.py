"""Vérifie que les lookups auth contournent RLS (rôle uwi_app en prod)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_pg_conn():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    cur.fetchone.return_value = (2, 1, "owner", "user@example.com", "sub-123")
    return conn, cur


@patch("backend.auth_pg._pg_url", return_value="postgres://uwi_app@test/db")
@patch("backend.auth_pg._pg_auth_lookup_conn")
def test_google_sub_lookup_uses_auth_bypass_context(mock_ctx, _url, mock_pg_conn):
    from backend.auth_pg import pg_get_tenant_user_by_google_sub

    conn, cur = mock_pg_conn
    mock_ctx.return_value.__enter__ = MagicMock(return_value=conn)
    mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

    row = pg_get_tenant_user_by_google_sub("sub-123")
    assert row is not None
    assert row["tenant_id"] == 2
    assert row["email"] == "user@example.com"
    cur.execute.assert_called_once()
    assert "google_sub" in cur.execute.call_args[0][0]


@patch("backend.pg_tenant_context.set_bypass_tenant_rls_on_connection")
@patch("backend.auth_pg._pg_url", return_value="postgres://uwi_app@test/db")
def test_auth_lookup_conn_sets_bypass(_url, mock_bypass):
    with patch("psycopg.connect") as mock_connect:
        mock_connect.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_connect.return_value.__exit__ = MagicMock(return_value=False)

        from backend.auth_pg import _pg_auth_lookup_conn

        with _pg_auth_lookup_conn() as conn:
            assert conn is not None
        mock_bypass.assert_called_once()
        _, kwargs = mock_bypass.call_args
        assert kwargs.get("enabled") is True
