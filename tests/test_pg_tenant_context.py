from backend.pg_tenant_context import set_tenant_id_on_connection


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
