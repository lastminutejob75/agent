from uuid import UUID

import pytest

from backend.pg_tenant_context import (
    reset_pg_connection_session_state,
    set_post_id_on_connection,
    set_tenant_id_on_connection,
)


def test_set_tenant_id_on_connection_uses_literal_assignment():
    executed = []

    class FakeCursor:
        def execute(self, sql, params=None):
            executed.append((sql, params))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def rollback(self):
            raise AssertionError("rollback should not be called")

    set_tenant_id_on_connection(FakeConn(), 2)

    assert executed == [("SET LOCAL app.current_tenant_id = '2'", None)]


def test_set_post_id_on_connection_uses_transaction_local_parameter():
    executed = []
    post_id = UUID("12345678-1234-5678-1234-567812345678")

    class FakeCursor:
        def execute(self, sql, params=None):
            executed.append((sql, params))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def rollback(self):
            raise AssertionError("rollback should not be called")

    connection = FakeConn()
    set_post_id_on_connection(connection, post_id)

    assert executed == [
        (
            "SELECT set_config('app.current_post_id', %s, true)",
            ("12345678-1234-5678-1234-567812345678",),
        )
    ]
    assert connection._uwi_current_post_id == str(post_id)


def test_set_post_id_on_connection_rejects_forged_value_before_query():
    class FakeConn:
        def cursor(self):
            raise AssertionError("invalid post id must not reach PostgreSQL")

    with pytest.raises(ValueError, match="valid UUID"):
        set_post_id_on_connection(FakeConn(), "x'; SET app.bypass_tenant_rls = 'on")


def test_reset_pg_connection_session_state_clears_post_context():
    class FakeConn:
        pass

    connection = FakeConn()
    connection._uwi_current_tenant_id = 7
    connection._uwi_current_post_id = "12345678-1234-5678-1234-567812345678"
    connection._uwi_bypass_rls = True
    reset_pg_connection_session_state(connection)

    assert not hasattr(connection, "_uwi_current_tenant_id")
    assert not hasattr(connection, "_uwi_current_post_id")
    assert not hasattr(connection, "_uwi_bypass_rls")
