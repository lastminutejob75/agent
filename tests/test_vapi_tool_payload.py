# tests/test_vapi_tool_payload.py
"""Test extraction des paramètres du tool Vapi (message.toolCallList / toolCalls)."""
import pytest
from backend.routes.voice import _tool_extract_parameters, _tool_extract_tool_call_id


def test_extract_parameters_from_tool_call_list():
    """Payload réel Vapi : message.toolCallList[0].function.arguments (objet)."""
    payload = {
        "message": {
            "toolCallList": [
                {
                    "id": "call_pNe6A43EFEjnBnqunHwHiC67",
                    "function": {
                        "name": "function_tool",
                        "arguments": {
                            "action": "get_slots",
                            "patient_name": "Henri",
                            "motif": "ordonnance",
                            "preference": "après-midi",
                        },
                    },
                }
            ],
        },
    }
    params = _tool_extract_parameters(payload)
    assert params.get("action") == "get_slots"
    assert params.get("patient_name") == "Henri"
    assert params.get("motif") == "ordonnance"
    assert params.get("preference") == "après-midi"


def test_extract_parameters_from_tool_call_list_string_args():
    """Arguments en JSON string (certains clients Vapi)."""
    payload = {
        "message": {
            "toolCallList": [
                {
                    "id": "call_abc123",
                    "function": {
                        "arguments": '{"action":"get_slots","patient_name":"Henri","motif":"ordonnance","preference":"après-midi"}',
                    },
                }
            ],
        },
    }
    params = _tool_extract_parameters(payload)
    assert params.get("action") == "get_slots"
    assert params.get("patient_name") == "Henri"
    assert params.get("preference") == "après-midi"


def test_extract_tool_call_id_from_tool_call_list():
    payload = {
        "message": {
            "toolCallList": [{"id": "call_pNe6A43EFEjnBnqunHwHiC67", "function": {"arguments": {"action": "get_slots"}}}],
        },
    }
    assert _tool_extract_tool_call_id(payload) == "call_pNe6A43EFEjnBnqunHwHiC67"


def test_extract_parameters_legacy_top_level_parameters():
    """Ancien format : payload.parameters."""
    payload = {"parameters": {"action": "book", "selected_slot": "2", "patient_name": "Marie"}}
    params = _tool_extract_parameters(payload)
    assert params.get("action") == "book"
    assert params.get("patient_name") == "Marie"
    assert params.get("selected_slot") == "2"
