from unittest.mock import patch


def test_upsert_vapi_call_accepts_customer_number_only(monkeypatch):
    import psycopg

    from backend import vapi_calls_pg

    class FakeCursor:
        def execute(self, sql, params):
            self.params = params

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeConn:
        def __init__(self):
            self.cursor_obj = FakeCursor()
            self.committed = False

        def cursor(self):
            return self.cursor_obj

        def commit(self):
            self.committed = True

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    fake_conn = FakeConn()
    monkeypatch.setenv("DATABASE_URL", "postgres://fake")
    with patch("backend.vapi_calls_pg.ensure_tables", return_value=True):
        monkeypatch.setattr(psycopg, "connect", lambda *args, **kwargs: fake_conn)
        ok = vapi_calls_pg.upsert_vapi_call(tenant_id=2, call_id="call-123", customer_number="+33612345678")

    assert ok is True
    assert fake_conn.committed is True


def test_insert_call_transcript_uses_shared_pg_connection(monkeypatch):
    from backend import vapi_calls_pg

    class FakeCursor:
        def execute(self, sql, params):
            self.params = params

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeConn:
        def __init__(self):
            self.cursor_obj = FakeCursor()
            self.committed = False

        def cursor(self):
            return self.cursor_obj

        def commit(self):
            self.committed = True

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    fake_conn = FakeConn()
    monkeypatch.setenv("DATABASE_URL", "postgres://fake")
    with patch("backend.vapi_calls_pg.ensure_tables", return_value=True):
        with patch("backend.vapi_calls_pg.pg_connection", return_value=fake_conn):
            ok = vapi_calls_pg.insert_call_transcript(
                tenant_id=2,
                call_id="call-456",
                role="assistant",
                transcript="Bonjour",
                is_final=True,
            )

    assert ok is True
    assert fake_conn.committed is True
