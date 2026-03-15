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
from backend.routes import voice, whatsapp, bland, reports, admin, auth, tenant, stripe_webhook, pre_onboarding, checkout_embedded

app = FastAPI()
_logger = logging.getLogger(__name__)

# CORS : origines exactes (pas *). Inclure www et non-www (uwiapp.com) pour éviter 401 si l’user arrive sans www.
# Défaut = prod + localhost (admin/dev). Si le front admin est sur Vercel, ajouter son URL dans CORS_ORIGINS sur Railway.
_default_cors = (
    "https://www.uwiapp.com,https://uwiapp.com,"
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"
)
_cors_raw = (os.environ.get("CORS_ORIGINS") or "").strip()
_cors_origins = (_cors_raw if _cors_raw else _default_cors).split(",")
_cors_origins_list = [o.strip() for o in _cors_origins if o.strip()]
if not _cors_origins_list:
    _cors_origins_list = [o.strip() for o in _default_cors.split(",") if o.strip()]
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
    """Refuse /api/admin/* si Origin présente et non autorisée. Ne jamais bloquer OPTIONS (preflight CORS)."""
    if not request.url.path.startswith("/api/admin/"):
        return await call_next(request)
    if request.method == "OPTIONS":
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
app.include_router(stripe_webhook.router)  # POST /api/stripe/webhook
app.include_router(pre_onboarding.router)  # POST /api/pre-onboarding/commit
app.include_router(checkout_embedded.router)  # POST /create-checkout-session (embedded, pour landing /checkout)

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

# Scheduler (rapports + suspension past_due à 03:00 UTC)
try:
    from backend.reports import setup_scheduler
    setup_scheduler()
except Exception as e:
    import logging
    logging.warning("Scheduler setup failed (reports/suspension): %s", e)

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
    # Fix vapi_calls rows where started_at is NULL (backfill from created_at)
    try:
        _pg_url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
        if _pg_url:
            import psycopg
            with psycopg.connect(_pg_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE vapi_calls SET started_at = created_at WHERE started_at IS NULL AND created_at IS NOT NULL")
                    fixed = cur.rowcount
                conn.commit()
            if fixed:
                print(f"✅ Backfilled {fixed} vapi_calls.started_at from created_at")
    except Exception as e:
        _logger.debug("vapi_calls backfill skipped: %s", str(e)[:80])
    # Table ivr_events (dashboards) : création automatique si USE_PG_EVENTS et DATABASE_URL
    if getattr(config, "USE_PG_EVENTS", False):
        try:
            from backend.ivr_events_pg import ensure_ivr_events_table
            if ensure_ivr_events_table():
                print("✅ ivr_events table ready")
            else:
                print("⚠️ ivr_events table skip (no DATABASE_URL)")
        except Exception as e:
            _logger.warning("ivr_events ensure table failed: %s", e)
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
    # Dashboard : si on lit les stats depuis Postgres (DATABASE_URL) mais qu'on n'écrit pas les events (USE_PG_EVENTS=false), les dashboards restent vides.
    if (os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")) and not getattr(config, "USE_PG_EVENTS", False):
        _logger.warning(
            "DASHBOARD_EMPTY: DATABASE_URL (or PG_EVENTS_URL) is set but USE_PG_EVENTS is false. "
            "Admin and tenant dashboards read from Postgres ivr_events, which will stay empty. Set USE_PG_EVENTS=true and run migrations/003_postgres_ivr_events.sql."
        )
        print("⚠️ DASHBOARD: Set USE_PG_EVENTS=true so appels/RDV appear in dashboards (see .env.example)")
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
            from backend.pg_pool import pg_connection
            with pg_connection() as conn:
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
        # Wizard lead : lien dashboard dans l'email fondateur (éviter lien relatif en prod)
        out["admin_base_url_configured"] = bool(
            (os.environ.get("ADMIN_BASE_URL") or os.environ.get("FRONT_BASE_URL") or os.environ.get("APP_BASE_URL") or "").strip()
        )

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


@app.get("/debug/call-durations")
async def debug_call_durations():
    """Temporaire : vérifie les données de durée dans vapi_calls et vapi_call_usage."""
    import os
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    if not url:
        return {"error": "no PG URL"}
    try:
        from backend.pg_pool import pg_connection
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT call_id, tenant_id, status,
                           started_at::text AS started_at,
                           ended_at::text AS ended_at,
                           updated_at::text AS updated_at,
                           created_at::text AS created_at,
                           EXTRACT(EPOCH FROM (updated_at - COALESCE(started_at, created_at)))::int AS calc_sec
                    FROM vapi_calls
                    ORDER BY COALESCE(ended_at, updated_at, started_at) DESC NULLS LAST
                    LIMIT 5
                """)
                calls = [dict(r) for r in cur.fetchall()]
                usage_exists = False
                usage_rows = []
                try:
                    cur.execute("""
                        SELECT vapi_call_id, duration_sec,
                               started_at::text AS started_at,
                               ended_at::text AS ended_at
                        FROM vapi_call_usage ORDER BY updated_at DESC LIMIT 5
                    """)
                    usage_rows = [dict(r) for r in cur.fetchall()]
                    usage_exists = True
                except Exception as ue:
                    usage_exists = str(ue)[:100]
                return {
                    "version": "v3_updated_at",
                    "vapi_calls": calls,
                    "vapi_call_usage_exists": usage_exists,
                    "vapi_call_usage": usage_rows,
                }
    except Exception as e:
        return {"error": str(e)[:200]}


@app.get("/debug/calls-diag")
async def debug_calls_diag():
    """Diagnostic : teste _get_calls_list pour chaque tenant trouvé."""
    import os
    from datetime import datetime, timedelta
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")
    if not url:
        return {"error": "no PG URL"}
    now = datetime.utcnow()
    start = (now - timedelta(days=30)).strftime("%Y-%m-%d 00:00:00")
    end = now.strftime("%Y-%m-%d %H:%M:%S")
    try:
        from backend.pg_pool import pg_connection
        from backend.routes.admin import _get_calls_list
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT tenant_id FROM vapi_calls WHERE updated_at >= %s LIMIT 5", (start,))
                tenant_ids = [r["tenant_id"] for r in cur.fetchall()]
                cur.execute(
                    """SELECT tenant_id, COUNT(*) as cnt FROM vapi_calls
                       WHERE ((started_at >= %s AND started_at <= %s) OR (updated_at >= %s AND updated_at <= %s))
                       GROUP BY tenant_id""",
                    (start, end, start, end),
                )
                counts_by_tenant = {r["tenant_id"]: r["cnt"] for r in cur.fetchall()}
        results = {}
        for tid in tenant_ids:
            try:
                raw = _get_calls_list(tenant_id=tid, days=30, limit=5)
                items = raw.get("items") or []
                results[str(tid)] = {"items_count": len(items), "first_call_id": items[0].get("call_id") if items else None}
            except Exception as e:
                results[str(tid)] = {"error": str(e)[:200]}
        cur_users = []
        try:
            with pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, email, tenant_id, role FROM tenant_users LIMIT 10")
                    cur_users = [dict(r) for r in cur.fetchall()]
        except Exception:
            pass
        return {
            "start": start, "end": end,
            "raw_counts_by_tenant": counts_by_tenant,
            "get_calls_list_results": results,
            "tenant_users": cur_users,
        }
    except Exception as e:
        return {"error": str(e)[:300]}


@app.get("/debug/vapi-assistant")
async def debug_vapi_assistant():
    """Diagnostic : inspecte la config de l'assistant Vapi (tools, server.url) via l'API Vapi."""
    import os
    import httpx
    results = {}
    try:
        api_key = (os.environ.get("VAPI_API_KEY") or "").strip()
        if not api_key:
            return {"error": "VAPI_API_KEY non configuré"}

        from backend.pg_pool import pg_connection
        assistants_db = []
        try:
            with pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, tenant_id, vapi_assistant_id, name FROM tenant_assistants WHERE vapi_assistant_id IS NOT NULL LIMIT 10"
                    )
                    assistants_db = [dict(r) for r in cur.fetchall()]
        except Exception as e:
            results["db_error"] = str(e)[:200]

        env_id = (os.environ.get("VAPI_ASSISTANT_ID") or "").strip()
        if env_id:
            assistants_db.insert(0, {"vapi_assistant_id": env_id, "name": "env_default", "tenant_id": "?"})
        vapi_ids_seen = set()
        deduped = []
        for a in assistants_db:
            vid = a.get("vapi_assistant_id") or ""
            if vid and vid not in vapi_ids_seen:
                vapi_ids_seen.add(vid)
                deduped.append(a)
        assistants_db = deduped

        async with httpx.AsyncClient() as client:
            for a in assistants_db[:3]:
                vapi_id = a.get("vapi_assistant_id") or ""
                if not vapi_id:
                    continue
                try:
                    res = await client.get(
                        f"https://api.vapi.ai/assistant/{vapi_id}",
                        headers={"Authorization": f"Bearer {api_key}"},
                        timeout=10,
                    )
                    if res.status_code != 200:
                        results[vapi_id[:24]] = {"http_status": res.status_code, "body": res.text[:300]}
                        continue
                    data = res.json()
                    top_tools = data.get("tools") or []
                    model_tools = (data.get("model") or {}).get("tools") or []
                    all_tools = top_tools + model_tools
                    tools_summary = []
                    for t in all_tools:
                        t_info = {
                            "type": t.get("type"),
                            "name": (t.get("function") or {}).get("name") or t.get("name"),
                            "server_url": (t.get("server") or {}).get("url"),
                        }
                        tools_summary.append(t_info)
                    model = data.get("model") or {}
                    messages = model.get("messages") or []
                    sys_prompt = ""
                    for m in messages:
                        if isinstance(m, dict) and m.get("role") == "system":
                            sys_prompt = str(m.get("content") or "")[:3000]
                            break
                    results[vapi_id[:24]] = {
                        "name": data.get("name"),
                        "tenant_id": a.get("tenant_id"),
                        "server_url": (data.get("server") or {}).get("url"),
                        "top_tools_count": len(top_tools),
                        "model_tools_count": len(model_tools),
                        "tools": tools_summary,
                        "model_provider": model.get("provider"),
                        "system_prompt": sys_prompt,
                    }
                except Exception as e:
                    results[vapi_id[:24]] = {"error": str(e)[:200]}
        return {"assistants": results}
    except Exception as e:
        return {"error": str(e)[:300]}


@app.post("/debug/vapi-patch-tools")
async def debug_vapi_patch_tools():
    """Ajoute function_tool à tous les assistants Vapi existants (one-shot migration)."""
    import os
    from backend.vapi_utils import patch_vapi_assistant_add_tool
    results = {}
    try:
        api_key = (os.environ.get("VAPI_API_KEY") or "").strip()
        if not api_key:
            return {"error": "VAPI_API_KEY non configuré"}

        vapi_ids = set()
        env_id = (os.environ.get("VAPI_ASSISTANT_ID") or "").strip()
        if env_id:
            vapi_ids.add(env_id)

        try:
            from backend.pg_pool import pg_connection
            with pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT DISTINCT vapi_assistant_id FROM tenant_assistants WHERE vapi_assistant_id IS NOT NULL")
                    for r in cur.fetchall():
                        vid = (r.get("vapi_assistant_id") or "").strip()
                        if vid:
                            vapi_ids.add(vid)
        except Exception as e:
            results["db_warn"] = str(e)[:200]

        for vid in vapi_ids:
            try:
                data = await patch_vapi_assistant_add_tool(vid)
                tools = (data.get("model") or {}).get("tools") or []
                results[vid[:24]] = {"ok": True, "tools_count": len(tools)}
            except Exception as e:
                results[vid[:24]] = {"ok": False, "error": str(e)[:200]}

        return {"patched": results, "total": len(vapi_ids)}
    except Exception as e:
        return {"error": str(e)[:300]}


@app.post("/debug/vapi-cleanup-inline-tools")
async def debug_vapi_cleanup_inline_tools(tool_id: str = None):
    """
    Nettoie tous les assistants Vapi :
    1. Supprime function_tool inline de model.tools (garde endCall)
    2. Garantit que VAPI_FUNCTION_TOOL_ID est dans model.toolIds
    Stratégie unique : model.toolIds pour le tool persisté.
    Accepte ?tool_id=xxx en query param ou lit VAPI_FUNCTION_TOOL_ID.
    """
    import os
    import httpx
    results = {}
    try:
        api_key = (os.environ.get("VAPI_API_KEY") or "").strip()
        if not api_key:
            return {"error": "VAPI_API_KEY non configuré"}

        function_tool_id = (tool_id or "").strip() or (os.environ.get("VAPI_FUNCTION_TOOL_ID") or "").strip()
        if not function_tool_id:
            return {"error": "VAPI_FUNCTION_TOOL_ID non configuré et ?tool_id non fourni"}

        vapi_ids = set()
        env_id = (os.environ.get("VAPI_ASSISTANT_ID") or "").strip()
        if env_id:
            vapi_ids.add(env_id)
        try:
            from backend.pg_pool import pg_connection
            with pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT DISTINCT vapi_assistant_id FROM tenant_assistants WHERE vapi_assistant_id IS NOT NULL")
                    for r in cur.fetchall():
                        vid = (r.get("vapi_assistant_id") or "").strip()
                        if vid:
                            vapi_ids.add(vid)
        except Exception:
            pass

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient() as client:
            for vid in vapi_ids:
                try:
                    res = await client.get(f"https://api.vapi.ai/assistant/{vid}", headers=headers, timeout=15)
                    res.raise_for_status()
                    data = res.json()
                    model = data.get("model") or {}
                    inline_tools = model.get("tools") or []
                    current_tool_ids = set(model.get("toolIds") or [])

                    kept = [t for t in inline_tools if t.get("type") != "function"]
                    removed = [t for t in inline_tools if t.get("type") == "function"]

                    needs_patch = False
                    patch_model = {**model}

                    if removed:
                        patch_model["tools"] = kept
                        needs_patch = True

                    if function_tool_id not in current_tool_ids:
                        current_tool_ids.add(function_tool_id)
                        needs_patch = True
                    patch_model["toolIds"] = list(current_tool_ids)

                    if not needs_patch:
                        results[vid[:24]] = {
                            "skipped": "already clean",
                            "toolIds": list(current_tool_ids),
                        }
                        continue

                    patch_res = await client.patch(
                        f"https://api.vapi.ai/assistant/{vid}",
                        json={"model": patch_model},
                        headers=headers, timeout=15,
                    )
                    patch_res.raise_for_status()
                    new_model = patch_res.json().get("model") or {}
                    results[vid[:24]] = {
                        "ok": True,
                        "removed_inline": len(removed),
                        "kept_inline": len(kept),
                        "toolIds": new_model.get("toolIds") or [],
                        "remaining_inline_tools": [t.get("type") for t in (new_model.get("tools") or [])],
                    }
                except Exception as e:
                    results[vid[:24]] = {"error": str(e)[:200]}
        return {"cleaned": results, "function_tool_id": function_tool_id}
    except Exception as e:
        return {"error": str(e)[:300]}


FAQ_PROMPT_RULE = """[RÈGLE ABSOLUE — FAQ / INFORMATIONS]
Pour toute question d'information (horaires, tarifs, adresse, vacances, fermetures, moyens de paiement, etc.) :
→ Répondre DIRECTEMENT depuis la section FAQ ci-dessous.
→ Ne JAMAIS appeler function_tool pour une question d'information.
→ Ne JAMAIS inventer de réponse. Utiliser UNIQUEMENT les informations de la FAQ.
→ Si l'information n'est pas dans la FAQ : "Je n'ai pas cette information. Souhaitez-vous que je vous mette en relation avec le cabinet ?"
"""


@app.post("/debug/vapi-sync-faq")
async def debug_vapi_sync_faq(tenant_id: int = 1):
    """Force la synchronisation de la FAQ du tenant dans le system prompt Vapi."""
    import os
    try:
        from backend.vapi_utils import patch_vapi_assistant_system_prompt
        from backend.tenant_config import faq_to_prompt_text, get_faq, get_params

        faq = get_faq(tenant_id)
        faq_text = faq_to_prompt_text(faq)

        params = get_params(tenant_id)
        vapi_id = str(params.get("vapi_assistant_id") or "").strip()
        source = "tenant_params"
        if not vapi_id:
            vapi_id = (os.environ.get("VAPI_ASSISTANT_ID") or "").strip()
            source = "env_var"
        if not vapi_id:
            return {"error": "Aucun vapi_assistant_id trouvé (ni params, ni env var)", "tenant_id": tenant_id}

        await patch_vapi_assistant_system_prompt(vapi_id, faq_text)
        return {
            "ok": True,
            "tenant_id": tenant_id,
            "vapi_assistant_id": vapi_id[:24],
            "source": source,
            "faq_categories": len(faq),
            "faq_text_preview": faq_text[:500],
        }
    except Exception as e:
        return {"error": str(e)[:300], "tenant_id": tenant_id}


@app.post("/debug/vapi-patch-prompt-faq-rule")
async def debug_vapi_patch_prompt_faq_rule():
    """Injecte la règle FAQ dans le system prompt de tous les assistants Vapi."""
    import os
    import httpx
    results = {}
    try:
        api_key = (os.environ.get("VAPI_API_KEY") or "").strip()
        if not api_key:
            return {"error": "VAPI_API_KEY non configuré"}

        vapi_ids = set()
        env_id = (os.environ.get("VAPI_ASSISTANT_ID") or "").strip()
        if env_id:
            vapi_ids.add(env_id)
        try:
            from backend.pg_pool import pg_connection
            with pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT DISTINCT vapi_assistant_id FROM tenant_assistants WHERE vapi_assistant_id IS NOT NULL")
                    for r in cur.fetchall():
                        vid = (r.get("vapi_assistant_id") or "").strip()
                        if vid:
                            vapi_ids.add(vid)
        except Exception:
            pass

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient() as client:
            for vid in vapi_ids:
                try:
                    res = await client.get(f"https://api.vapi.ai/assistant/{vid}", headers=headers, timeout=15)
                    res.raise_for_status()
                    data = res.json()
                    model = data.get("model") or {}
                    messages = model.get("messages") or []
                    sys_idx = next((i for i, m in enumerate(messages) if isinstance(m, dict) and m.get("role") == "system"), None)
                    if sys_idx is None:
                        results[vid[:24]] = {"skipped": "no system message"}
                        continue
                    current_content = str(messages[sys_idx].get("content") or "")
                    if "[RÈGLE ABSOLUE — FAQ / INFORMATIONS]" in current_content:
                        results[vid[:24]] = {"skipped": "rule already present"}
                        continue
                    insert_before = current_content.find("[CONTRAT TOOL")
                    if insert_before == -1:
                        insert_before = current_content.find("[RÈGLE ABSOLUE")
                    if insert_before == -1:
                        new_content = current_content + "\n\n" + FAQ_PROMPT_RULE
                    else:
                        new_content = current_content[:insert_before] + FAQ_PROMPT_RULE + "\n" + current_content[insert_before:]
                    messages[sys_idx] = {**messages[sys_idx], "content": new_content}
                    patch_res = await client.patch(
                        f"https://api.vapi.ai/assistant/{vid}",
                        json={"model": {**model, "messages": messages}},
                        headers=headers, timeout=15,
                    )
                    patch_res.raise_for_status()
                    results[vid[:24]] = {"ok": True, "prompt_length": len(new_content)}
                except Exception as e:
                    results[vid[:24]] = {"error": str(e)[:200]}
        return {"patched": results}
    except Exception as e:
        return {"error": str(e)[:300]}


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
    Suspension multi-canal : si tenant suspendu → message fixe, pas d'appel engine (zéro LLM).
    """
    try:
        session = ENGINE.session_store.get_or_create(conv_id)
        session.channel = channel
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
                await push_event(conv_id, {"type": "final", "text": msg, "conv_state": "START", "timestamp": now_iso()})
                return

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
