from __future__ import annotations

import threading
import time
from typing import Optional

_CONTROL_URLS: dict[str, dict[str, object]] = {}
_LOCK = threading.Lock()
_TTL_SECONDS = 60 * 30


def set_control_url(call_id: str, control_url: str) -> None:
    call_id = str(call_id or "").strip()
    control_url = str(control_url or "").strip()
    if not call_id or not control_url:
        return
    now = time.time()
    with _LOCK:
        _purge_locked(now)
        _CONTROL_URLS[call_id] = {"url": control_url, "ts": now}


def get_control_url(call_id: str) -> Optional[str]:
    call_id = str(call_id or "").strip()
    if not call_id:
        return None
    now = time.time()
    with _LOCK:
        _purge_locked(now)
        entry = _CONTROL_URLS.get(call_id) or {}
        value = str(entry.get("url") or "").strip()
        return value or None


def _purge_locked(now: float) -> None:
    expired = [
        key
        for key, entry in _CONTROL_URLS.items()
        if now - float(entry.get("ts") or 0) > _TTL_SECONDS
    ]
    for key in expired:
        _CONTROL_URLS.pop(key, None)
