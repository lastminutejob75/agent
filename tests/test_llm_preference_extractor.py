# tests/test_llm_preference_extractor.py
import json

import pytest

from backend.llm_preference_extractor import (
    StubPrefLLMClient,
    extract_preferences_hybrid,
    extract_preferences_with_llm,
    validate_llm_preference_payload,
    resolve_preference_user_ack,
    _validate_user_ack,
)
from backend.appointment_preference_parser import preferences_to_legacy_pref


class TestValidatePayload:
    def test_valid_exclusion_matin(self):
        data = {
            "confidence": 0.88,
            "safety_required": False,
            "preferred_days": [],
            "excluded_days": [],
            "preferred_time_windows": [],
            "excluded_time_windows": [{"label": "matin", "strength": "hard"}],
            "user_ack": "D'accord, je cherche en évitant le matin.",
            "urgency": "normal",
            "flexibility": "medium",
            "sorting": "default",
        }
        payload, err = validate_llm_preference_payload(data, "pas dispo le matin")
        assert err is None
        assert payload["excluded_time_windows"][0]["start"] == "08:00"

    def test_reject_contradiction_preferred_matin_with_excluded(self):
        data = {
            "confidence": 0.9,
            "preferred_time_windows": [{"label": "matin", "strength": "soft"}],
            "excluded_time_windows": [{"label": "matin", "strength": "hard"}],
            "urgency": "normal",
            "flexibility": "medium",
            "sorting": "default",
        }
        payload, err = validate_llm_preference_payload(data, "test")
        assert err is None
        assert not any(w["label"] == "matin" for w in payload["preferred_time_windows"])

    def test_reject_ack_with_digits(self):
        assert _validate_user_ack("Je propose mardi à 14h") is None
        assert _validate_user_ack("D'accord, j'évite le matin.") is not None


class TestLlmExtractStub:
    def test_stub_excludes_matin(self):
        client = StubPrefLLMClient()
        payload, meta = extract_preferences_with_llm(
            "je veux un rdv mais je ne suis pas dispo le matin",
            client=client,
        )
        assert payload is not None
        assert meta.attempts >= 1
        assert any(w["label"] == "matin" for w in payload["excluded_time_windows"])

    def test_hybrid_fallback_regex_when_llm_disabled(self, monkeypatch):
        import backend.llm_preference_extractor as lpe

        monkeypatch.setattr(lpe, "LLM_PREF_EXTRACT_ENABLED", False)
        monkeypatch.setattr(lpe, "get_pref_llm_client", lambda: None)
        merged, meta = extract_preferences_hybrid("je ne suis pas dispo le matin")
        assert meta.source == "regex"
        assert preferences_to_legacy_pref(merged) == "après-midi"

    def test_hybrid_llm_plus_regex(self):
        client = StubPrefLLMClient()
        merged, meta = extract_preferences_hybrid(
            "je veux un rdv mais je ne suis pas dispo le matin",
            client=client,
        )
        assert meta.source in ("llm+regex", "llm")
        assert preferences_to_legacy_pref(merged) == "après-midi"
        ack = resolve_preference_user_ack(merged)
        assert "matin" in ack.lower()

    def test_retry_on_invalid_json(self):
        bad = StubPrefLLMClient(response="not json")
        payload, meta = extract_preferences_with_llm("plutôt le matin", client=bad)
        assert payload is None
        assert meta.attempts >= 2

    def test_repair_on_invalid_label(self):
        bad_json = json.dumps(
            {
                "confidence": 0.9,
                "preferred_time_windows": [{"label": "invalid_label", "strength": "soft"}],
                "excluded_time_windows": [],
                "urgency": "normal",
                "flexibility": "medium",
                "sorting": "default",
            }
        )
        good_json = json.dumps(
            {
                "confidence": 0.9,
                "preferred_time_windows": [],
                "excluded_time_windows": [{"label": "matin", "strength": "hard"}],
                "user_ack": "Compris, sans le matin.",
                "urgency": "normal",
                "flexibility": "medium",
                "sorting": "default",
            }
        )
        calls = []

        class FlakyClient(StubPrefLLMClient):
            def complete(self, system, user, timeout_ms):
                calls.append(user)
                if len(calls) == 1:
                    return bad_json
                return good_json

        client = FlakyClient()
        payload, meta = extract_preferences_with_llm("pas le matin", client=client)
        assert payload is not None
        assert meta.attempts == 2
