#!/usr/bin/env python3
"""
Test E2E du parcours chat public (prise de RDV web).
Usage: PYTHONPATH=. python3 scripts/test_public_chat_parcours.py [--tenant 2]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid

from backend.tenant_routing import current_tenant_id
from backend.web_chat import (
    STREAMS,
    _session_from_memory,
    ensure_stream,
    run_engine,
    start_web_chat,
)


STEPS = [
    ("bonjour", "salutation"),
    ("je voudrais un rdv", "QUALIF_NAME"),
    ("Martin Dupont", "QUALIF_PREF"),
    ("mercredi apres midi", "WAIT_CONFIRM|slots"),
]


async def drain_final(conv_id: str, timeout: float = 45.0) -> dict | None:
    """Attend le prochain event final ou error dans la file SSE."""
    q = STREAMS.get(conv_id)
    if not q:
        return None
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            raw = await asyncio.wait_for(q.get(), timeout=min(2.0, deadline - time.time()))
        except asyncio.TimeoutError:
            continue
        if raw is None:
            break
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if payload.get("type") in ("final", "error", "transfer"):
            return payload
    return None


async def turn(tenant_id: int, conv_id: str, message: str) -> tuple[dict, dict | None, float]:
    t0 = time.time()
    current_tenant_id.set(str(tenant_id))
    ensure_stream(conv_id, reset=True)
    post = await start_web_chat(tenant_id, message=message, conversation_id=conv_id, channel="web")
    sse = await drain_final(conv_id, timeout=90.0)
    elapsed = time.time() - t0
    return post, sse, elapsed


def check_state(conv_id: str, expected_fragment: str) -> tuple[bool, str]:
    session = _session_from_memory(conv_id)
    if session is None:
        return False, "no session"
    state = getattr(session, "state", "?")
    name = getattr(getattr(session, "qualif_data", None), "name", None)
    pref = getattr(getattr(session, "qualif_data", None), "pref", None)
    slots = len(getattr(session, "pending_slots", None) or [])
    detail = f"state={state} name={name!r} pref={pref!r} slots={slots}"
    if "QUALIF_NAME" in expected_fragment and state == "QUALIF_NAME":
        return True, detail
    if "QUALIF_PREF" in expected_fragment and state == "QUALIF_PREF":
        return True, detail
    if "WAIT_CONFIRM" in expected_fragment and state == "WAIT_CONFIRM" and slots > 0:
        return True, detail
    if "slots" in expected_fragment and slots > 0:
        return True, detail
    if expected_fragment == "salutation" and state in ("START", "QUALIF_NAME"):
        return True, detail
    return state == expected_fragment or expected_fragment in state, detail


async def main(tenant_id: int) -> int:
    conv_id = f"e2e-{uuid.uuid4()}"
    print(f"=== Parcours chat public tenant={tenant_id} conv={conv_id} ===\n")
    failures = 0

    for i, (message, expected) in enumerate(STEPS, 1):
        post, sse, elapsed = await turn(tenant_id, conv_id, message)
        ok_state, detail = check_state(conv_id, expected)
        post_reply = (post.get("reply") or "")[:80]
        sse_text = ((sse or {}).get("text") or (sse or {}).get("message") or "")[:120]
        sse_type = (sse or {}).get("type", "none")
        sse_slots = len((sse or {}).get("slots") or [])

        ok = ok_state and (post_reply or sse_text)
        if not ok:
            failures += 1
        mark = "OK" if ok else "FAIL"

        print(f"[{mark}] Étape {i}: {message!r}")
        print(f"       POST {elapsed:.2f}s reply={post_reply!r}")
        print(f"       SSE  type={sse_type} text={sse_text!r} slots={sse_slots}")
        print(f"       {detail}\n")

    print("=== Résumé ===")
    if failures:
        print(f"ÉCHEC: {failures}/{len(STEPS)} étape(s)")
        return 1
    print(f"SUCCÈS: {len(STEPS)}/{len(STEPS)} étapes")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", type=int, default=2)
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.tenant)))
