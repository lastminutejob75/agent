# tests/test_tenant_config.py
"""Tests feature flags par tenant."""
import pytest
from backend import config
from backend.tenant_config import get_flags, set_flags, FLAG_KEYS


def test_get_flags_returns_defaults():
    f = get_flags(999)  # tenant inexistant
    assert f == config.DEFAULT_FLAGS


def test_set_flags_merge():
    set_flags(1, {"ENABLE_BARGEIN_SLOT_CHOICE": False})
    f = get_flags(1)
    assert f["ENABLE_BARGEIN_SLOT_CHOICE"] is False
    assert f["ENABLE_SEQUENTIAL_SLOTS"] is True  # inchangé
    set_flags(1, {"ENABLE_BARGEIN_SLOT_CHOICE": True})  # restore


def test_get_flags_tenant_none_uses_default():
    """get_flags(None) utilise DEFAULT_TENANT_ID (1), merge avec config.DEFAULT_FLAGS."""
    f = get_flags(None)
    assert set(f.keys()) == set(config.DEFAULT_FLAGS.keys())
    assert all(isinstance(v, bool) for v in f.values())
