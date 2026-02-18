# backend/main.py
from __future__ import annotations

import os
from pathlib import Path

# Charger .env à la racine du projet (pour ANTHROPIC_API_KEY, LLM_ASSIST_ENABLED, etc.)
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path)

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import sqlite3

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.engine import ENGINE, Event
from backend.routes.voice import _get_engine
import backend.config as config  # Import du MODULE (pas from import)
from backend.db import init_db, list_free_slots, count_free_slots
from backend.tenant_routing import current_tenant_id
from backend.deps import require_tenant_web, TenantIdWeb
# Nouvelle architecture multi-canal
from backend.routes import voice, whatsapp, bland, reports, admin, auth, tenant

app = FastAPI()
_logger = logging.getLogger(__name__)

# CORS pour front uwiapp.com (JWT localStorage)
_cors_origins = (os.environ.get("CORS_ORIGINS") or "https://uwiapp.com,https://www.uwiapp.com,http://localhost:5173").split(",")
_cors_origins_list = [o.strip() for o in _cors_origins if o.strip()]
# Admin : mêmes origines par défaut ; optionnel ADMIN_CORS_ORIGINS pour liste plus stricte
_admin_cors_origins = (os.environ.get("ADMIN_CORS_ORIGINS") or "").strip()
_admin_origins_list = [o.strip() for o in _admin_cors_origins.split(",") if o.strip()] if _admin_cors_origins else _cors_origins_list

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-Key"],
)


@app.middleware("http")
async def admin_cors_guard(request: Request, call_next):
    """Refuse /api/admin/* si Origin présente et non autorisée (réduit la surface d'attaque)."""
    if not request.url.path.startswith("/api/admin/"):
        return await call_next(request)
    origin = (request.headers.get("origin") or "").strip()
    if not origin:
        return await call_next(request)
    if origin in _admin_origins_list:
        return await call_next(request)
    _logger.warning("admin_cors_reject path=%s origin=%s", request.url.path, origin[:80])
    return JSONResponse(status_code=403, content={"detail": "Origin not allowed for admin API"})


@app.middleware("http")
async def log_vapi_requests(request: Request, call_next):
    """Log path + status_code pour toute requête /api/vapi/* (sans body)."""
    if not request.url.path.startswith("/api/vapi/"):
        return await call_next(request)
    response = await call_next(request)
    _logger.info(
        "vapi_request",
        extra={"path": request.url.path, "method": request.method, "status_code": response.status_code},
    )
    return response


# Routers (avant les mounts pour éviter les conflits)
# Utilise la nouvelle architecture multi-canal
app.include_router(voice.router)      # /api/vapi/*
app.include_router(whatsapp.router)   # /api/whatsapp/*
app.include_router(bland.router)      # /api/bland/*
app.include_router(reports.router)    # /api/reports/*
app.include_router(admin.router)      # /api/public/onboarding, /api/admin/*
app.include_router(auth.router)       # /api/auth/*
app.include_router(tenant.router)     # /api/tenant/*

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
    """
    Initialisation au RUNTIME.
    L'init lourde (validation multi-tenant, credentials, PG) tourne en arrière-plan
    pour que /health réponde immédiatement (healthcheck Railway).
    """
    # Ne pas bloquer le démarrage : validation multi-tenant déplacée en arrière-plan
    # (évite crash au boot si MULTI_TENANT_MODE=true sans USE_PG_SLOTS → healthcheck fail)
    asyncio.create_task(cleanup_old_conversations())
    asyncio.create_task(keep_alive())
    asyncio.create_task(_init_heavy())
    print("🚀 Server ready (heavy init in background)")


async def _init_heavy():
    """Init lourde en arrière-plan (credentials, PG) — ne bloque pas le healthcheck."""
    await asyncio.to_thread(_init_heavy_sync)


def _init_heavy_sync():
    """Partie synchrone de l'init (validation multi-tenant, credentials, PG)."""
    import os
    print("🔄 Heavy init started...")
    # 1. Credentials Google en premier (aucune condition) pour que /health affiche credentials_loaded true dès que possible
    try:
        config.load_google_credentials()
        print("✅ Google credentials loaded")
        from backend import tools_booking
        tools_booking._calendar_service = None
    except Exception as e:
        config.GOOGLE_CALENDAR_ENABLED = False
        config.GOOGLE_CALENDAR_DISABLE_REASON = str(e)
        print(f"⚠️ Google Calendar disabled: {e}")
    # 2. En prod sans TEST_TENANT_ID : fallback DEFAULT_TENANT_ID pour ensure_test_number_route
    _env = (os.environ.get("ENV") or os.environ.get("RAILWAY_ENVIRONMENT") or "").lower()
    if _env == "production" and os.environ.get("TEST_TENANT_ID") is None:
        _logger.warning(
            "TEST_TENANT_ID not set in production; using DEFAULT_TENANT_ID=%s. Set TEST_TENANT_ID for correct routing.",
            config.DEFAULT_TENANT_ID,
        )
        os.environ["TEST_TENANT_ID"] = str(config.DEFAULT_TENANT_ID)
        config.TEST_TENANT_ID = config.DEFAULT_TENANT_ID
    # 3. Validation multi-tenant (ne bloque plus le startup → healthcheck OK)
    try:
        config.validate_multi_tenant_config()
        print("✅ Multi-tenant config OK")
    except RuntimeError as e:
        _logger.critical("MULTI_TENANT config invalid: %s", e)
        print(f"⚠️ MULTI_TENANT: {e}")
    # PG healthcheck
    try:
        from backend.tenants_pg import check_pg_health
        if check_pg_health(force=True):
            print("✅ PG_HEALTH ok")
        else:
            _logger.warning("PG_HEALTH down -> sqlite fallback")
            print("⚠️ PG_HEALTH down -> sqlite fallback")
    except Exception as e:
        _logger.warning("PG healthcheck failed: %s", e)
    # Route démo test → TEST_TENANT_ID (idempotent), juste après PG check pour éviter pool/transaction divergent.
    try:
        from backend.tenant_routing import ensure_test_number_route
        if ensure_test_number_route():
            print("✅ ensure_test_number_route OK")
        else:
            print("⚠️ ensure_test_number_route skipped (no TEST_VOCAL_NUMBER)")
    except Exception as e:
        _logger.warning("ensure_test_number_route failed: %s", e)
        print("⚠️ ensure_test_number_route: %s", e)
    print("✅ Heavy init done")


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


@app.get("/debug/force-load-credentials")
async def force_load_credentials():
    """Force le chargement des credentials et affiche toutes les erreurs"""
    import os
    import traceback
    
    result = {
        "google_service_account_base64_present": bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_BASE64")),
        "google_calendar_id_present": bool(os.getenv("GOOGLE_CALENDAR_ID")),
        "google_service_account_base64_length": len(os.getenv("GOOGLE_SERVICE_ACCOUNT_BASE64", "")),
        "google_calendar_id_value": os.getenv("GOOGLE_CALENDAR_ID"),
        "error": None,
        "traceback": None,
        "success": False
    }
    
    try:
        # Forcer le chargement
        config.load_google_credentials()
        result["success"] = True
        result["service_account_file"] = config.SERVICE_ACCOUNT_FILE
        result["calendar_id"] = config.GOOGLE_CALENDAR_ID
    except Exception as e:
        result["error"] = str(e)
        result["traceback"] = traceback.format_exc()
    
    return result


@app.get("/debug/config")
async def debug_config():
    """
    Diagnostic prod : expose si Google Calendar est actif (sans secrets).
    Permet de trancher A/B/C/D rapidement.
    """
    return {
        "google_calendar_enabled": getattr(config, "GOOGLE_CALENDAR_ENABLED", False),
        "reason": getattr(config, "GOOGLE_CALENDAR_DISABLE_REASON", None),
    }


@app.get("/debug/env-vars")
async def debug_env_vars():
    """
    Debug endpoint - À SUPPRIMER après vérification
    Vérifie que les variables d'environnement Railway sont accessibles
    """
    import os
    
    all_keys = sorted(list(os.environ.keys()))
    google_keys = sorted([k for k in all_keys if "GOOGLE" in k])
    
    llm_enabled = (os.getenv("LLM_ASSIST_ENABLED") or "").lower() == "true"
    anthropic_key_set = bool(os.getenv("ANTHROPIC_API_KEY"))
    return {
        "env_count": len(all_keys),
        "sample_keys": all_keys[:25],
        "google_keys": google_keys,
        "google_values_present": {k: bool(os.environ.get(k)) for k in google_keys},
        "port_present": bool(os.getenv("PORT")),
        "railway_env_present": bool(os.getenv("RAILWAY_ENVIRONMENT")),
        "llm_assist_enabled": llm_enabled,
        "anthropic_api_key_set": anthropic_key_set,
        "llm_ready": llm_enabled and anthropic_key_set,
    }


@app.get("/api/stats/bookings")
async def get_booking_stats() -> dict:
    """Stats des RDV des dernières 24h (sessions par état final)."""
    try:
        db_path = getattr(
            getattr(ENGINE, "session_store", None), "db_path", "sessions.db"
        )
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_sessions,
                SUM(CASE WHEN state = 'CONFIRMED' THEN 1 ELSE 0 END) AS confirmed,
                SUM(CASE WHEN state = 'TRANSFERRED' THEN 1 ELSE 0 END) AS transferred,
                SUM(CASE WHEN state = 'INTENT_ROUTER' THEN 1 ELSE 0 END) AS router
            FROM sessions
            WHERE last_seen_at >= ?
            """,
            (yesterday,),
        )
        row = cursor.fetchone()
        conn.close()
        total = row[0] or 0
        confirmed = row[1] or 0
        transferred = row[2] or 0
        router = row[3] or 0
        return {
            "period": "24h",
            "total_sessions": total,
            "confirmed_bookings": confirmed,
            "transferred": transferred,
            "intent_router": router,
            "conversion_rate": round(confirmed / total * 100, 1) if total > 0 else 0,
            "abandon_rate": round(
                (total - confirmed - transferred) / total * 100, 1
            )
            if total > 0
            else 0,
        }
    except Exception as e:
        _logger.exception("get_booking_stats failed: %s", e)
        return {
            "period": "24h",
            "total_sessions": 0,
            "confirmed_bookings": 0,
            "transferred": 0,
            "intent_router": 0,
            "conversion_rate": 0,
            "abandon_rate": 0,
            "error": str(e),
        }


def _health_checks_sync() -> dict:
    """Partie synchrone des checks (slots, PG). Timeout géré par l'appelant."""
    out = {}
    try:
        out["free_slots"] = count_free_slots()
    except Exception:
        out["free_slots"] = -1
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("PG_TENANTS_URL")
    out["database_url_set"] = bool(db_url)
    postgres_ok = False
    postgres_error = None
    if db_url:
        try:
            import psycopg
            with psycopg.connect(db_url, connect_timeout=2) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            postgres_ok = True
        except Exception as e:
            postgres_error = str(e)[:100]
    out["postgres_ok"] = postgres_ok
    out["postgres_error"] = postgres_error
    return out


@app.get("/health")
async def health() -> dict:
    """
    Health check pour Railway : répond toujours 200 (HTTP 200 requis par Railway).
    Détails optionnels ; toute exception est capturée pour ne jamais faire échouer le healthcheck.
    """
    out: dict = {"status": "ok"}
    try:
        out["streams"] = len(STREAMS)
        # Infos instantanées (pas d'I/O)
        service_account_file = getattr(config, "SERVICE_ACCOUNT_FILE", None)
        file_exists = False
        if isinstance(service_account_file, str):
            file_exists = os.path.exists(service_account_file)
        has_base64_env = bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_BASE64"))
        credentials_loaded = getattr(config, "GOOGLE_CALENDAR_ENABLED", False) or file_exists
        out["service_account_file"] = service_account_file
        out["file_exists"] = file_exists
        out["credentials_loaded"] = credentials_loaded
        out["calendar_id_set"] = bool(getattr(config, "GOOGLE_CALENDAR_ID", None))
        out["google_base64_set"] = has_base64_env
        out["google_calendar_enabled"] = getattr(config, "GOOGLE_CALENDAR_ENABLED", False)
        out["google_calendar_disable_reason"] = getattr(config, "GOOGLE_CALENDAR_DISABLE_REASON", None)
        out["runtime_env_count"] = len(os.environ)

        # Checks I/O (slots, Postgres) avec timeout 2s
        try:
            detail = await asyncio.wait_for(
                asyncio.to_thread(_health_checks_sync),
                timeout=2.0,
            )
            out.update(detail)
        except asyncio.TimeoutError:
            out["health_timeout"] = True
            out["free_slots"] = -1
            out["postgres_ok"] = False
            out["postgres_error"] = "health check timeout (2s)"
        except Exception as e:
            _logger.warning("health check partial failure: %s", e)
            out["health_detail_error"] = str(e)[:200]
            out.setdefault("free_slots", -1)
            out.setdefault("postgres_ok", False)
    except Exception as e:
        _logger.warning("health check error: %s", e, exc_info=True)
        out["health_detail_error"] = str(e)[:200]
    return out


@app.get("/")
async def root():
    """Redirige vers le frontend"""
    return RedirectResponse(url="/frontend/")


@app.get("/debug/slots")
async def debug_slots() -> dict:
    slots = list_free_slots(limit=30)
    return {"free": count_free_slots(), "slots": slots}


@app.post("/chat")
async def chat(
    payload: dict,
    request: Request,
    tenant_id: TenantIdWeb = Depends(require_tenant_web),
) -> dict:
    """Résolution tenant via Depends(require_tenant_web) — X-Tenant-Key → tenant_id, current_tenant_id déjà posé."""
    message = (payload.get("message") or "")
    conv_id = payload.get("conversation_id") or str(uuid.uuid4())
    channel = payload.get("channel", "web")

    session = ENGINE.session_store.get_or_create(conv_id)
    session.tenant_id = tenant_id

    ensure_stream(conv_id)

    asyncio.create_task(run_engine(conv_id, message, channel))
    return {"conversation_id": conv_id}


@app.get("/stream/{conv_id}")
async def stream(conv_id: str):
    # Tenant déjà fixé sur la session au premier POST /chat ; sinon défaut
    session = ENGINE.session_store.get_or_create(conv_id)
    tid = getattr(session, "tenant_id", None)
    if tid is not None:
        current_tenant_id.set(str(tid))
    else:
        current_tenant_id.set(str(config.DEFAULT_TENANT_ID))

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

        engine = _get_engine(conv_id)
        events = engine.handle_message(conv_id, message)

        for ev in events:
            await emit_event(conv_id, ev)

        # Sécurité : si aucun event "final" avec texte (ex. liste vide), le client reste sur "…"
        if not events or not any(getattr(ev, "type", None) == "final" and (getattr(ev, "text", None) or "").strip() for ev in events):
            from backend.engine import Event as Evt
            from backend import prompts
            fallback = getattr(prompts, "MSG_UNCLEAR_1", "Je n'ai pas bien compris. Pouvez-vous répéter ?")
            await emit_event(conv_id, Evt("final", fallback, conv_state="START"))

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
