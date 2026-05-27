"""Tests pour backend/exports.py — generation CSV calls + bookings."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch


# ---------- Helpers internes ----------


class TestSafeFilename:
    def test_basic(self):
        from backend.exports import _safe_filename
        name = _safe_filename("appels", tenant_id=42, days=7)
        assert name.startswith("appels_")
        assert "tenant42" in name
        assert "7j" in name
        assert name.endswith(".csv")

    def test_no_tenant(self):
        from backend.exports import _safe_filename
        name = _safe_filename("rdv", tenant_id=None, days=30)
        assert "tenant" not in name
        assert "30j" in name
        assert name.endswith(".csv")

    def test_strips_dangerous_chars(self):
        from backend.exports import _safe_filename
        name = _safe_filename("evil/../path", tenant_id=1, days=1)
        assert "/" not in name
        assert ".." not in name


class TestFormatHelpers:
    def test_iso_to_local_from_str(self):
        from backend.exports import _format_iso_to_local
        assert _format_iso_to_local("2026-05-09T12:34:56Z") == "2026-05-09 12:34:56"
        assert _format_iso_to_local("2026-05-09T12:34:56.123Z") == "2026-05-09 12:34:56"
        assert _format_iso_to_local("2026-05-09 12:34:56+00:00") == "2026-05-09 12:34:56"
        assert _format_iso_to_local("") == ""
        assert _format_iso_to_local(None) == ""

    def test_iso_to_local_from_datetime(self):
        from backend.exports import _format_iso_to_local
        dt = datetime(2026, 5, 9, 12, 34, 56)
        assert _format_iso_to_local(dt) == "2026-05-09 12:34:56"

    def test_format_duration(self):
        from backend.exports import _format_duration
        assert _format_duration(0) == "0s"
        assert _format_duration(45) == "45s"
        assert _format_duration(60) == "1m 00s"
        assert _format_duration(125) == "2m 05s"
        assert _format_duration(3600) == "1h 00m"
        assert _format_duration(3725) == "1h 02m"
        assert _format_duration(None) == ""
        assert _format_duration("") == ""

    def test_result_label_fr(self):
        from backend.exports import _result_label_fr
        assert _result_label_fr("rdv") == "RDV pris"
        assert _result_label_fr("transfer") == "Transfert humain"
        assert _result_label_fr("abandoned") == "Abandon"
        assert _result_label_fr("other") == "Autre"
        assert _result_label_fr("") == ""

    def test_csv_value(self):
        from backend.exports import _csv_value
        assert _csv_value(None) == ""
        assert _csv_value(True) == "oui"
        assert _csv_value(False) == "non"
        assert _csv_value(42) == "42"
        assert _csv_value(3.14) == "3.14"
        assert _csv_value("hello") == "hello"


class TestStreamCsv:
    def test_includes_bom_and_headers(self):
        from backend.exports import stream_csv
        rows = [{"a": "1", "b": "2"}]
        chunks = list(stream_csv(rows, headers=["A", "B"], columns=["a", "b"]))
        full = b"".join(chunks).decode("utf-8")
        # BOM UTF-8 en premier
        assert full.startswith("\ufeff")
        assert "A;B" in full
        assert "1;2" in full

    def test_empty_rows_only_header(self):
        from backend.exports import stream_csv
        chunks = list(stream_csv([], headers=["A"], columns=["a"]))
        full = b"".join(chunks).decode("utf-8")
        assert full.startswith("\ufeff")
        assert "A" in full
        # Pas de ligne de donnees
        lines = [line for line in full.splitlines() if line.strip()]
        assert len(lines) == 1  # juste l'header

    def test_custom_delimiter(self):
        from backend.exports import stream_csv
        rows = [{"a": "1", "b": "2"}]
        chunks = list(stream_csv(rows, headers=["A", "B"], columns=["a", "b"], delimiter=","))
        full = b"".join(chunks).decode("utf-8")
        assert "A,B" in full
        assert "1,2" in full
        assert ";" not in full.split("\n")[1]  # pas de ; sur la ligne data

    def test_quotes_values_with_delimiter(self):
        from backend.exports import stream_csv
        rows = [{"name": "Dupont; Jean"}]  # contient le delimiter
        chunks = list(stream_csv(rows, headers=["Name"], columns=["name"]))
        full = b"".join(chunks).decode("utf-8")
        # csv.QUOTE_MINIMAL escape avec des guillemets
        assert '"Dupont; Jean"' in full

    def test_streams_in_chunks(self):
        from backend.exports import stream_csv
        rows = [{"a": str(i)} for i in range(150)]  # > chunk_size (50)
        chunks = list(stream_csv(rows, headers=["A"], columns=["a"]))
        # Au moins 3 chunks (BOM+header puis chunks de 50)
        assert len(chunks) >= 3


# ---------- Calls CSV ----------


class TestCallsCsv:
    def test_enrich_call_row(self):
        from backend.exports import _enrich_call_row
        row = {
            "started_at": "2026-05-09T08:30:00Z",
            "result": "rdv",
            "duration_sec": 65,
            "tenant_name": "Cabinet Dupont",
        }
        out = _enrich_call_row(row)
        assert out["_date"] == "2026-05-09"
        assert out["_time"] == "08:30:00"
        assert out["_result_label"] == "RDV pris"
        assert out["_duration_label"] == "1m 05s"

    def test_build_calls_csv_response_returns_streaming(self):
        from backend.exports import (
            CALLS_COLUMNS,
            CALLS_HEADERS,
            _enrich_call_row,
            build_calls_csv_response,
            stream_csv,
        )
        items = [
            {
                "call_id": "c1",
                "started_at": "2026-05-09T08:30:00Z",
                "tenant_id": 1,
                "tenant_name": "Cabinet Dupont",
                "customer_number": "+33612345678",
                "result": "rdv",
                "duration_sec": 65,
                "last_event": "booking_confirmed",
            }
        ]
        resp = build_calls_csv_response(items, tenant_id=1, days=7)
        assert resp.media_type.startswith("text/csv")
        assert "attachment" in resp.headers["content-disposition"]
        assert "tenant1" in resp.headers["content-disposition"]
        # Test contenu du flux directement (le sync generator)
        chunks = list(stream_csv(
            (_enrich_call_row(r) for r in items),
            CALLS_HEADERS, CALLS_COLUMNS,
        ))
        text = b"".join(chunks).decode("utf-8")
        assert text.startswith("\ufeff")
        assert "Date;Heure;Tenant" in text
        assert "Cabinet Dupont" in text
        assert "RDV pris" in text
        assert "1m 05s" in text
        assert "+33612345678" in text


# ---------- Bookings CSV ----------


class TestBookingsCsv:
    def test_enrich_booking_row(self):
        from backend.exports import _enrich_booking_row
        row = {
            "created_at": "2026-05-09T08:30:00Z",
            "rdv_at": "2026-05-15T14:00:00Z",
            "patient_name": "Alice",
        }
        out = _enrich_booking_row(row)
        assert out["_date_taken"] == "2026-05-09"
        assert out["_time_taken"] == "08:30:00"
        assert out["_date_rdv"] == "2026-05-15"
        assert out["_time_rdv"] == "14:00:00"

    def test_build_bookings_csv_response(self):
        from backend.exports import (
            BOOKINGS_COLUMNS,
            BOOKINGS_HEADERS,
            _enrich_booking_row,
            build_bookings_csv_response,
            stream_csv,
        )
        items = [
            {
                "tenant_id": 1,
                "tenant_name": "Cabinet Dupont",
                "call_id": "c1",
                "created_at": "2026-05-09T08:30:00Z",
                "patient_name": "Alice Martin",
                "patient_phone": "+33612345678",
                "rdv_at": "2026-05-15T14:00:00Z",
                "motif": "Consultation",
                "status": "confirme",
                "source": "appel",
            }
        ]
        resp = build_bookings_csv_response(items, tenant_id=1, days=30)
        assert resp.media_type.startswith("text/csv")
        assert "attachment" in resp.headers["content-disposition"]
        chunks = list(stream_csv(
            (_enrich_booking_row(r) for r in items),
            BOOKINGS_HEADERS, BOOKINGS_COLUMNS,
        ))
        text = b"".join(chunks).decode("utf-8")
        assert text.startswith("\ufeff")
        assert "Patient" in text
        assert "Alice Martin" in text
        assert "+33612345678" in text
        assert "Consultation" in text
        assert "confirme" in text


# ---------- fetch_bookings_from_pg ----------


class TestFetchBookings:
    def test_returns_empty_when_pg_unavailable(self):
        from backend.exports import fetch_bookings_from_pg
        with patch("backend.pg_pool.pg_connection", side_effect=Exception("no pg")):
            assert fetch_bookings_from_pg(tenant_id=1, days=7) == []

    def test_extracts_meta_json(self):
        from backend.exports import fetch_bookings_from_pg
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "tenant_id": 1,
                "call_id": "c1",
                "created_at": datetime(2026, 5, 9, 8, 30, 0),
                "event": "booking_confirmed",
                "meta_json": {
                    "patient_name": "Alice",
                    "phone": "+33612345678",
                    "rdv_at": "2026-05-15T14:00:00",
                    "motif": "Consultation",
                },
                "patient_phone": None,
            }
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_conn.cursor.return_value.__exit__.return_value = False
        cm = MagicMock()
        cm.__enter__.return_value = mock_conn
        cm.__exit__.return_value = False

        with patch("backend.pg_pool.pg_connection", return_value=cm):
            items = fetch_bookings_from_pg(tenant_id=1, days=7)
        assert len(items) == 1
        assert items[0]["patient_name"] == "Alice"
        assert items[0]["patient_phone"] == "+33612345678"
        assert items[0]["motif"] == "Consultation"
        assert items[0]["status"] == "confirme"

    def test_meta_json_as_string_is_parsed(self):
        from backend.exports import fetch_bookings_from_pg
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "tenant_id": 1,
                "call_id": "c1",
                "created_at": datetime(2026, 5, 9, 8, 30, 0),
                "event": "booking_confirmed",
                "meta_json": '{"patient_name": "Bob"}',
                "patient_phone": "+33611111111",
            }
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_conn.cursor.return_value.__exit__.return_value = False
        cm = MagicMock()
        cm.__enter__.return_value = mock_conn
        cm.__exit__.return_value = False

        with patch("backend.pg_pool.pg_connection", return_value=cm):
            items = fetch_bookings_from_pg(tenant_id=1, days=7)
        assert items[0]["patient_name"] == "Bob"
        # Le patient_phone prioritaire vient de call_sessions.customer_number
        assert items[0]["patient_phone"] == "+33611111111"
