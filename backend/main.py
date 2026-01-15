# backend/main.py
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, Optional, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.engine import ENGINE, Event
from backend import config
from backend.db import init_db, list_free_slots, count_free_slots
from backend import vapi

app = FastAPI()

# Routers (avant les mounts pour éviter les conflits)
app.include_router(vapi.router)

# Static frontend (optionnel - peut ne pas exister)
try:
    import os
    if os.path.exists("frontend"):
        app.mount("/frontend", StaticFiles(directory="frontend", html=True), name="frontend")
except Exception:
    pass  # Frontend optionnel pour Railway

# Init DB (V1) - au démarrage, mais ne pas faire échouer l'app si ça échoue
try:
    init_db()
except Exception as e:
    import logging
    logging.warning(f"DB init failed (non-critical): {e}")
    pass

# SSE Streams
STREAMS: Dict[str, asyncio.Queue[Optional[str]]] = {}


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


@app.on_event("startup")
async def startup():
    """Démarre le background task de cleanup"""
    asyncio.create_task(cleanup_old_conversations())


async def cleanup_old_conversations():
    """
    Purge les conversations/streams expirés toutes les 60s.
    """
    while True:
        await asyncio.sleep(60)

        to_remove = []
        for conv_id in list(STREAMS.keys()):
            session = ENGINE.session_store.get(conv_id)
            if session is None or session.is_expired():
                to_remove.append(conv_id)

        for conv_id in to_remove:
            try:
                await close_stream(conv_id)
            except Exception:
                pass
            STREAMS.pop(conv_id, None)
            ENGINE.session_store.delete(conv_id)


@app.get("/health")
async def health() -> dict:
    """Health check - doit toujours répondre même en cas d'erreur DB"""
    try:
        free_slots = count_free_slots()
    except Exception:
        free_slots = -1  # Indique que la DB n'est pas accessible
    
    return {
        "status": "ok",
        "streams": len(STREAMS),
        "free_slots": free_slots,
    }


@app.get("/")
async def root():
    """Redirige vers le frontend"""
    return RedirectResponse(url="/frontend/")


@app.get("/debug/slots")
async def debug_slots() -> dict:
    slots = list_free_slots(limit=30)
    return {"free": count_free_slots(), "slots": slots}


@app.post("/chat")
async def chat(payload: dict, request: Request) -> dict:
    message = (payload.get("message") or "")
    conv_id = payload.get("conversation_id") or str(uuid.uuid4())
    channel = payload.get("channel", "web")  # ← NOUVEAU

    ensure_stream(conv_id)

    asyncio.create_task(run_engine(conv_id, message, channel))  # ← PASSER channel
    return {"conversation_id": conv_id}


@app.get("/stream/{conv_id}")
async def stream(conv_id: str):
    ensure_stream(conv_id)

    async def gen():
        q = STREAMS[conv_id]
        while True:
            item = await q.get()
            if item is None:
                break
            yield f"data: {item}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


async def run_engine(conv_id: str, message: str, channel: str = "web") -> None:
    """
    Exécute engine.handle_message et push SSE events.
    """
    try:
        # Stocker channel dans session
        session = ENGINE.session_store.get_or_create(conv_id)
        session.channel = channel
        
        await push_event(conv_id, {
            "type": "partial",
            "text": "…",
            "timestamp": now_iso(),
        })

        events = ENGINE.handle_message(conv_id, message)

        for ev in events:
            await emit_event(conv_id, ev)

    except Exception:
        await push_event(conv_id, {
            "type": "error",
            "message": "Erreur serveur, veuillez réessayer",
            "timestamp": now_iso(),
        })


async def emit_event(conv_id: str, ev: Event) -> None:
    payload: Dict[str, Any] = {
        "type": ev.type,
        "timestamp": now_iso(),
    }

    if ev.type == "transfer":
        payload["reason"] = ev.transfer_reason or "unknown"
        payload["silent"] = bool(ev.silent)
        payload["text"] = ev.text or ""
        payload["conv_state"] = ev.conv_state
        await push_event(conv_id, payload)
        # Si c'est un état terminal, on ferme immédiatement le stream
        if payload.get("conv_state") in ["CONFIRMED", "TRANSFERRED"]:
            await close_stream(conv_id)
        return

    if ev.type in ("partial", "final"):
        payload["text"] = ev.text
        payload["conv_state"] = ev.conv_state
        await push_event(conv_id, payload)
        # Si c'est un état terminal, on ferme immédiatement le stream
        if payload.get("conv_state") in ["CONFIRMED", "TRANSFERRED"]:
            await close_stream(conv_id)
        return

    if ev.type == "error":
        payload["message"] = ev.text
        await push_event(conv_id, payload)
        return

    payload["text"] = ev.text
    await push_event(conv_id, payload)
