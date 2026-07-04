"""Tests reformulation motif consultation — niveau B LLM."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from backend.services.motif_reformulation_service import (
    MotifReformulateRequest,
    build_motif_reformulate_response,
    is_motif_reformulate_llm_enabled,
    reformulate_motif_with_llm,
    sanitize_motif_suggestions,
)


def test_motif_reformulate_flag_disabled_by_default():
    with patch.dict(os.environ, {"ENABLE_CONSULTATION_MOTIF_REFORMULATE_LLM": "false"}, clear=False):
        assert is_motif_reformulate_llm_enabled() is False


def test_motif_reformulate_flag_enabled():
    with patch.dict(os.environ, {"ENABLE_CONSULTATION_MOTIF_REFORMULATE_LLM": "true"}, clear=False):
        assert is_motif_reformulate_llm_enabled() is True


def test_sanitize_motif_suggestions_limits_to_three():
    raw = ["  Douleurs abdominales à explorer  ", "", "Épigastralgies", "Trop longue " * 30, "Troisième", "Quatrième"]
    out = sanitize_motif_suggestions(raw)
    assert out == ["Douleurs abdominales à explorer", "Épigastralgies", "Troisième"]


def test_reformulate_motif_with_llm_mock():
    class FakeClient:
        provider = "openai"

        def complete(self, system, user, timeout_ms):
            assert timeout_ms == 2000
            assert "mal au ventre" in user
            return '{"suggestions":["Douleurs abdominales à explorer","Épigastralgies — évolution 3 jours"]}'

    with patch.dict(os.environ, {"ENABLE_CONSULTATION_MOTIF_REFORMULATE_LLM": "true"}, clear=False):
        with patch(
            "backend.services.motif_reformulation_service.create_chat_client",
            return_value=FakeClient(),
        ):
            out = reformulate_motif_with_llm("mal au ventre depuis 3 jours", 32)
    assert out == ["Douleurs abdominales à explorer", "Épigastralgies — évolution 3 jours"]


def test_build_motif_reformulate_response():
    class FakeClient:
        provider = "anthropic"

        def complete(self, system, user, timeout_ms):
            return '{"suggestions":["Céphalées à caractériser"]}'

    with patch.dict(os.environ, {"ENABLE_CONSULTATION_MOTIF_REFORMULATE_LLM": "true"}, clear=False):
        with patch(
            "backend.services.motif_reformulation_service.create_chat_client",
            return_value=FakeClient(),
        ):
            res = build_motif_reformulate_response("mal de tête", 45)
    assert res.suggestions == ["Céphalées à caractériser"]
    assert res.source == "llm"


def test_motif_reformulate_request_validation():
    with pytest.raises(ValueError):
        MotifReformulateRequest(raw_motif="   ")
