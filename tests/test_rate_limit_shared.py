"""Tests rate_limit.py (mémoire)."""
import pytest

from backend.rate_limit import check_sliding_window


def test_sliding_window_memory():
    key = "test-key-unique"
    for _ in range(3):
        check_sliding_window(key, limit=3, window_sec=60)
    with pytest.raises(RuntimeError):
        check_sliding_window(key, limit=3, window_sec=60)
