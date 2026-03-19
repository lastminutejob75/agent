from unittest.mock import patch


def test_ingest_end_of_call_report_uses_full_tenant_resolution():
    from backend import vapi_usage_pg

    payload = {
        "message": {
            "type": "end-of-call-report",
            "call": {
                "id": "call-usage-1",
                "assistantId": "asst_live_123",
                "startedAt": "2026-03-19T09:00:00Z",
                "endedAt": "2026-03-19T09:02:30Z",
                "durationSeconds": 150,
            },
        },
    }

    with patch("backend.tenant_routing.resolve_tenant_id_from_vapi_payload", return_value=(2, "assistant")) as mock_resolve:
        with patch("backend.vapi_usage_pg.upsert_vapi_call_usage", return_value=True) as mock_upsert:
            ok = vapi_usage_pg.ingest_end_of_call_report(payload)

    assert ok is True
    mock_resolve.assert_called_once_with(payload, channel="vocal")
    mock_upsert.assert_called_once()
    kwargs = mock_upsert.call_args.kwargs
    assert kwargs["tenant_id"] == 2
    assert kwargs["vapi_call_id"] == "call-usage-1"
    assert kwargs["duration_sec"] == 150.0
