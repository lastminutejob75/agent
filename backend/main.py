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
import backend.config as config  # Import du MODULE (pas from import)
from backend.db import init_db, list_free_slots, count_free_slots
# Nouvelle architecture multi-canal
from backend.routes import voice, whatsapp, bland

app = FastAPI()

# Routers (avant les mounts pour éviter les conflits)
# Utilise la nouvelle architecture multi-canal
app.include_router(voice.router)      # /api/vapi/*
app.include_router(whatsapp.router)   # /api/whatsapp/*
app.include_router(bland.router)      # /api/bland/*

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
    """Initialisation au RUNTIME (pas au build Docker)"""
    import os
    
    # Debug: Vérifie l'environnement runtime
    print("\n" + "="*60)
    print("🚀 RUNTIME STARTUP")
    print("="*60)
    print(f"Environment vars count: {len(os.environ)}")
    print(f"PORT present: {bool(os.getenv('PORT'))}")
    print(f"RAILWAY_ENVIRONMENT present: {bool(os.getenv('RAILWAY_ENVIRONMENT'))}")
    print(f"GOOGLE_SERVICE_ACCOUNT_BASE64 present: {bool(os.getenv('GOOGLE_SERVICE_ACCOUNT_BASE64'))}")
    print(f"GOOGLE_CALENDAR_ID present: {bool(os.getenv('GOOGLE_CALENDAR_ID'))}")
    print("="*60 + "\n")
    
    # Charge les credentials
    try:
        config.load_google_credentials()
        print(f"✅ Startup complete - Service Account ready")
    except Exception as e:
        print(f"⚠️ Warning: Cannot load credentials: {e}")
        print(f"⚠️ Using SQLite fallback for slots")
    
    # Background tasks
    asyncio.create_task(cleanup_old_conversations())
    asyncio.create_task(keep_alive())
    print("🚀 Application started with keep-alive enabled")


async def keep_alive():
    """
    Keep-alive: ping toutes les 30 secondes pour empêcher Railway de stopper le container.
    """
    import httpx
    import os
    
    # URL de l'app (Railway ou local)
    base_url = os.getenv("RAILWAY_PUBLIC_DOMAIN")
    if base_url:
        health_url = f"https://{base_url}/health"
    else:
        health_url = "http://localhost:8080/health"
    
    print(f"🔄 Keep-alive started, pinging: {health_url}")
    
    while True:
        await asyncio.sleep(30)  # Ping toutes les 30 secondes
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(health_url, timeout=10)
                print(f"💓 Keep-alive ping: {response.status_code}")
        except Exception as e:
            print(f"⚠️ Keep-alive ping failed: {e}")


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


@app.get("/debug/env-vars")
async def debug_env_vars():
    """
    Debug endpoint - À SUPPRIMER après vérification
    Vérifie que les variables d'environnement Railway sont accessibles
    """
    import os
    
    all_keys = sorted(list(os.environ.keys()))
    google_keys = sorted([k for k in all_keys if "GOOGLE" in k])
    
    return {
        "env_count": len(all_keys),
        "sample_keys": all_keys[:25],  # Premiers 25 pour diagnostic
        "google_keys": google_keys,
        "google_values_present": {k: bool(os.environ.get(k)) for k in google_keys},
        "port_present": bool(os.getenv("PORT")),
        "railway_env_present": bool(os.getenv("RAILWAY_ENVIRONMENT")),
    }


@app.get("/health")
async def health() -> dict:
    """Health check avec vérification du fichier credentials"""
    import os
    
    try:
        free_slots = count_free_slots()
    except Exception:
        free_slots = -1
    
    return {
        "status": "ok",
        "streams": len(STREAMS),
        "free_slots": free_slots,
        "service_account_file": config.SERVICE_ACCOUNT_FILE,
        "file_exists": bool(config.SERVICE_ACCOUNT_FILE and os.path.exists(config.SERVICE_ACCOUNT_FILE)),
        "calendar_id_set": bool(config.GOOGLE_CALENDAR_ID),
        "runtime_env_count": len(os.environ)
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
