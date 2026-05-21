"""
Chat web (widget /frontend + fiche publique praticien).
POST message → run_engine → SSE stream.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from backend.engine import ENGINE, Event
from backend.routes.voice import _get_engine
from backend.tenant_routing import current_tenant_id

logger = logging.getLogger(__name__)

STREAMS: Dict[str, asyncio.Queue[Optional[str]]] = {}


def _slots_ui_payload(session: Any) -> list:
    """Créneaux proposés pour boutons cliquables (web)."""
    if getattr(session, "state", None) != "WAIT_CONFIRM":
        return []
    pending = getattr(session, "pending_slots", None) or []
    if not pending:
        return []
    out: list = []
    for i, slot in enumerate(pending[:3]):
        if isinstance(slot, dict):
            label = (slot.get("label") or slot.get("label_vocal") or "").strip()
        else:
            label = (
                getattr(slot, "label", None) or getattr(slot, "label_vocal", None) or ""
            ).strip()
        if not label:
            continue
        out.append({"index": i + 1, "label": label})
    return out


def _attach_slots(payload: Dict[str, Any], session: Any) -> None:
    slots = _slots_ui_payload(session)
    if slots:
        payload["slots"] = slots


def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


async def push_event(conv_id: str, payload: dict) -> None:
    q = STREAMS.get(conv_id)
    if not q:
        return
    await q.put(json.dumps(payload, ensure_ascii=False))


async def close_stream(conv_id: str) -> None:
    q = STREAMS.get(conv_id)
    if q:
        await q.put(None)


def ensure_stream(conv_id: str) -> None:
    if conv_id not in STREAMS:
        STREAMS[conv_id] = asyncio.Queue()


async def emit_event(conv_id: str, ev: Event, session: Any = None) -> None:
    payload: Dict[str, Any] = {
        "type": ev.type,
        "timestamp": now_iso(),
    }

    if ev.type == "transfer":
        payload["reason"] = ev.transfer_reason or "unknown"
        payload["silent"] = bool(ev.silent)
        payload["text"] = ev.text or ""
        payload["conv_state"] = ev.conv_state
        if session is not None:
            _attach_slots(payload, session)
        await push_event(conv_id, payload)
        if payload.get("conv_state") in ["CONFIRMED", "TRANSFERRED"]:
            await close_stream(conv_id)
        return

    if ev.type in ("partial", "final"):
        payload["text"] = ev.text
        payload["conv_state"] = ev.conv_state
        if session is not None and ev.type == "final":
            _attach_slots(payload, session)
        await push_event(conv_id, payload)
        if payload.get("conv_state") in ["CONFIRMED", "TRANSFERRED"]:
            await close_stream(conv_id)
        return

    if ev.type == "error":
        payload["message"] = ev.text
        await push_event(conv_id, payload)
        return

    payload["text"] = ev.text
    await push_event(conv_id, payload)


async def run_engine(conv_id: str, message: str, channel: str = "web") -> None:
    """Exécute engine.handle_message et push SSE events."""
    try:
        session = ENGINE.session_store.get_or_create(conv_id)
        session.channel = channel
        try:
            ctx_tid = current_tenant_id.get()
            if ctx_tid and not getattr(session, "tenant_id", None):
                session.tenant_id = int(ctx_tid)
        except Exception:
            pass
        tenant_id = getattr(session, "tenant_id", None)
        if tenant_id is not None:
            from backend.billing_pg import get_tenant_suspension
            from backend import prompts

            is_suspended, _, suspension_mode = get_tenant_suspension(int(tenant_id))
            if is_suspended:
                msg = (
                    getattr(prompts, "MSG_VOCAL_SUSPENDED_SOFT", None)
                    if (suspension_mode or "hard").strip().lower() == "soft"
                    else getattr(prompts, "MSG_VOCAL_SUSPENDED", prompts.MSG_VOCAL_SUSPENDED)
                ) or getattr(prompts, "MSG_VOCAL_SUSPENDED", "Votre service est temporairement suspendu.")
                await push_event(
                    conv_id,
                    {"type": "final", "text": msg, "conv_state": "START", "timestamp": now_iso()},
                )
                return

        # Pas de partial « … » sur le web : évite « Je réfléchis » pendant les requêtes PG
        if channel != "web":
            await push_event(conv_id, {"type": "partial", "text": "…", "timestamp": now_iso()})

        engine = _get_engine(conv_id)
        events = engine.handle_message(conv_id, message)

        session = ENGINE.session_store.get(conv_id)
        for ev in events:
            await emit_event(conv_id, ev, session)

        if not events or not any(
            getattr(ev, "type", None) == "final" and (getattr(ev, "text", None) or "").strip() for ev in events
        ):
            from backend.engine import Event as Evt
            from backend import prompts

            fallback = getattr(prompts, "MSG_UNCLEAR_1", "Je n'ai pas bien compris. Pouvez-vous répéter ?")
            await emit_event(conv_id, Evt("final", fallback, conv_state="START"), session)

    except Exception:
        logger.exception("run_engine failed conv_id=%s", conv_id)
        await push_event(
            conv_id,
            {"type": "error", "message": "Erreur serveur, veuillez réessayer", "timestamp": now_iso()},
        )


def _register_web_conv_tenant(tenant_id: int, conv_id: str) -> None:
    try:
        from backend.session_pg import _WEB_CONV_TENANT_CACHE, _WEB_CACHE_MAX

        _WEB_CONV_TENANT_CACHE[conv_id] = int(tenant_id)
        if len(_WEB_CONV_TENANT_CACHE) > _WEB_CACHE_MAX:
            for k in list(_WEB_CONV_TENANT_CACHE.keys())[: _WEB_CACHE_MAX // 2]:
                _WEB_CONV_TENANT_CACHE.pop(k, None)
    except Exception:
        pass


def _is_greeting_only(message: str) -> bool:
    from backend.start_router import _GREETING_ONLY

    return bool(_GREETING_ONLY.match((message or "").strip()))


def _greeting_reply(channel: str) -> str:
    from backend import prompts

    return prompts.get_message("salutation", channel=channel) or "Bonjour ! Comment puis-je vous aider ?"


def _session_from_memory(conv_id: str):
    """Session en cache mémoire uniquement (évite un aller-retour PG sur le POST)."""
    store = ENGINE.session_store
    if hasattr(store, "_cache_get"):
        return store._cache_get(conv_id)
    return store.get(conv_id)


def _touch_web_session(conv_id: str, tenant_id: int, *, state: Optional[str] = None) -> None:
    """Met à jour la session web en mémoire (sans sauvegarde PG synchrone)."""
    from backend.session import Session

    store = ENGINE.session_store
    session = _session_from_memory(conv_id)
    if session is None:
        session = Session(conv_id=conv_id)
        if hasattr(store, "_cache_put"):
            store._cache_put(session)
        else:
            session = store.get_or_create(conv_id)
    session.tenant_id = int(tenant_id)
    session.channel = "web"
    if state:
        session.state = state


def _instant_reply(message: str, channel: str, conv_id: Optional[str] = None) -> Optional[str]:
    """Réponses synchrones (sans PG) : salutation, début RDV, nom reçu en QUALIF_NAME."""
    msg = (message or "").strip()
    if not msg:
        return None
    if _is_greeting_only(msg):
        return _greeting_reply(channel)
    from backend.start_router import is_booking_start_message
    from backend import guards, prompts

    if is_booking_start_message(msg):
        return prompts.get_qualif_question("name", channel=channel) or "Quel est votre nom et prénom ?"

    if conv_id:
        session = _session_from_memory(conv_id)
        if session and getattr(session, "state", None) == "QUALIF_NAME":
            extracted, reject = guards.extract_name_from_speech(msg)
            if extracted is not None and not reject:
                return (
                    prompts.get_qualif_question("pref", channel=channel)
                    or "Quel créneau préférez-vous ? (ex : lundi matin, mardi après-midi)"
                )
    return None


async def start_web_chat(
    tenant_id: int,
    *,
    message: str,
    conversation_id: Optional[str] = None,
    channel: str = "web",
) -> dict:
    """Démarre ou continue une conversation web pour un tenant donné."""
    conv_id = (conversation_id or "").strip() or str(uuid.uuid4())
    tid = int(tenant_id)
    current_tenant_id.set(str(tid))
    _register_web_conv_tenant(tid, conv_id)
    ensure_stream(conv_id)

    msg = (message or "").strip()
    out: Dict[str, Any] = {"conversation_id": conv_id}

    instant = _instant_reply(msg, channel, conv_id)
    if instant:
        out["reply"] = instant
        from backend.start_router import is_booking_start_message
        from backend import guards

        if is_booking_start_message(msg):
            _touch_web_session(conv_id, tid, state="QUALIF_NAME")
        else:
            mem = _session_from_memory(conv_id)
            if mem and getattr(mem, "state", None) == "QUALIF_NAME":
                extracted, reject = guards.extract_name_from_speech(msg)
                if extracted is not None and not reject:
                    _touch_web_session(conv_id, tid, state="QUALIF_PREF")

    asyncio.create_task(run_engine(conv_id, msg, channel))
    return out


def _resolve_session_tenant(conv_id: str, expected_tenant_id: Optional[int] = None):
    from backend import config
    from backend.security import is_production

    session = ENGINE.session_store.get(conv_id) if is_production() else ENGINE.session_store.get_or_create(conv_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Conversation introuvable")

    tid = getattr(session, "tenant_id", None)
    if tid is None and not is_production():
        tid = config.DEFAULT_TENANT_ID
    if tid is None:
        raise HTTPException(status_code=404, detail="Conversation introuvable")

    if expected_tenant_id is not None and int(tid) != int(expected_tenant_id):
        raise HTTPException(status_code=404, detail="Conversation introuvable")

    current_tenant_id.set(str(tid))
    return session


async def web_chat_stream(conv_id: str, *, expected_tenant_id: Optional[int] = None) -> StreamingResponse:
    _resolve_session_tenant(conv_id, expected_tenant_id)
    ensure_stream(conv_id)

    async def gen():
        q = STREAMS[conv_id]
        while True:
            item = await q.get()
            if item is None:
                break
            yield f"data: {item}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
