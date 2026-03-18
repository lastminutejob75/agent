from backend.routes.tenant import _call_summary_from_detail, _classify_call_context, _resolve_call_status


def test_resolve_call_status_prefers_cancel_done():
    status = _resolve_call_status(
        {"result": "rdv"},
        {"events": [{"event": "booking_confirmed"}, {"event": "cancel_done"}]},
    )

    assert status == "CANCELLED"


def test_resolve_call_status_prefers_modify_done():
    status = _resolve_call_status(
        {"result": "rdv"},
        {"events": [{"event": "booking_confirmed"}, {"event": "modify_done"}]},
    )

    assert status == "RESCHEDULED"


def test_call_summary_and_context_cover_cancelled_calls():
    detail = {"events": [{"event": "cancel_done", "meta": {}}], "transcript": "Patient: je veux annuler mon rendez-vous"}

    summary = _call_summary_from_detail("CANCELLED", detail)
    context = _classify_call_context("CANCELLED", detail)

    assert "annul" in summary.lower()
    assert context["reason_category"] == "agenda"
