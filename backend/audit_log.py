"""
Audit-log admin : trace les actions ecriture (POST/PUT/PATCH/DELETE) sur /api/admin/*.

Strategie :
- Middleware FastAPI qui intercepte chaque requete admin sur method != GET.
- Best-effort : si la table n'existe pas (ex: SQLite-only, dev local), on log mais on
  n'echoue pas la requete. On garde toujours un log applicatif pour traçabilite.
- Sanitise les payloads pour eviter de stocker des secrets (mot de passe, tokens, etc.)

Usage minimal :
    from backend.audit_log import install_audit_middleware
    install_audit_middleware(app)

Usage explicite (action critique) :
    from backend.audit_log import write_audit_entry
    write_audit_entry(
        actor_email=admin_email,
        method="POST",
        path="/api/admin/tenants/42/suspend",
        status_code=200,
        tenant_id=42,
        description="Suspended tenant 42 (reason: unpaid)",
    )
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Mapping, Optional

logger = logging.getLogger(__name__)

# Cle des champs a masquer dans les payloads logges (case-insensitive substring match)
_SENSITIVE_KEYS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "auth",
    "client_secret",
    "stripe_key",
    "twilio_auth_token",
    "vapi_api_key",
)

# Taille max d'un payload stocke (bytes JSON). Au-dela on tronque.
_MAX_PAYLOAD_BYTES = 4096

# Methodes a tracer (writes uniquement)
_TRACKED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Routes ignorees (login = sensible, deja loggee separement; login GET pas concerne)
_IGNORED_PATHS = (
    "/api/admin/auth/login",  # contient mot de passe en clair
    "/api/admin/auth/logout",
    "/api/admin/auth/me",
    "/api/admin/logs/recent",
    "/api/admin/logs/metrics",
)


def _is_admin_write_path(method: str, path: str) -> bool:
    """True si la requete doit etre tracee (admin write hors routes ignorees)."""
    if method.upper() not in _TRACKED_METHODS:
        return False
    if not path.startswith("/api/admin/"):
        return False
    for prefix in _IGNORED_PATHS:
        if path.startswith(prefix):
            return False
    return True


def _redact(value: Any, depth: int = 0) -> Any:
    """Recursivement remplace les valeurs des cles sensibles par '***REDACTED***'."""
    if depth > 6:
        return "***DEPTH_LIMIT***"
    if isinstance(value, Mapping):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            if isinstance(k, str) and any(s in k.lower() for s in _SENSITIVE_KEYS):
                out[k] = "***REDACTED***"
            else:
                out[k] = _redact(v, depth + 1)
        return out
    if isinstance(value, list):
        return [_redact(v, depth + 1) for v in value]
    if isinstance(value, str) and len(value) > 1024:
        # tronque les longues strings (eviter de stocker un upload base64 par ex)
        return value[:1024] + f"...[truncated {len(value) - 1024} chars]"
    return value


def _sanitize_payload(body: Optional[bytes]) -> Optional[Dict[str, Any]]:
    """Parse + redact un body de requete. Retourne None si vide/invalide."""
    if not body:
        return None
    try:
        text = body.decode("utf-8", errors="replace")
        obj = json.loads(text)
    except Exception:
        return {"_raw": body[:512].decode("utf-8", errors="replace"), "_note": "non-json"}
    if not isinstance(obj, (dict, list)):
        return {"_value": obj}
    redacted = _redact(obj)
    # Tronque si JSON trop volumineux
    serialized = json.dumps(redacted, ensure_ascii=False)
    if len(serialized.encode("utf-8")) > _MAX_PAYLOAD_BYTES:
        return {
            "_truncated": True,
            "_size_bytes": len(serialized.encode("utf-8")),
            "_preview": serialized[:1024],
        }
    return redacted if isinstance(redacted, dict) else {"_value": redacted}


def _client_ip_from_headers(headers: Mapping[str, str], fallback: Optional[str]) -> Optional[str]:
    """Recupere l'IP cliente, prioritise X-Forwarded-For (premier element)."""
    xff = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For")
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    real = headers.get("x-real-ip") or headers.get("X-Real-IP")
    if real:
        return real.strip()
    return fallback


_TENANT_ID_PATTERNS = (
    re.compile(r"/api/admin/tenants/(\d+)"),
    re.compile(r"/api/admin/clients/(\d+)"),
)


def _extract_tenant_id_from_path(path: str) -> Optional[int]:
    """Best-effort extraction du tenant_id depuis l'URL."""
    for pat in _TENANT_ID_PATTERNS:
        m = pat.search(path)
        if m:
            try:
                return int(m.group(1))
            except (ValueError, IndexError):
                pass
    return None


def write_audit_entry(
    *,
    actor_email: Optional[str],
    method: str,
    path: str,
    status_code: Optional[int] = None,
    actor_role: Optional[str] = None,
    tenant_id: Optional[int] = None,
    request_id: Optional[str] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    description: Optional[str] = None,
) -> bool:
    """
    Insert une ligne dans admin_audit_log. Best-effort : retourne False sur erreur.

    Toujours log applicatif via logger (meme si DB indispo) pour traçabilite minimale.
    """
    # Log applicatif d'abord (toujours)
    logger.info(
        "[ADMIN_AUDIT] actor=%s role=%s method=%s path=%s status=%s tenant_id=%s ip=%s rid=%s desc=%s",
        actor_email or "?",
        actor_role or "?",
        method,
        path,
        status_code,
        tenant_id,
        ip,
        request_id,
        description,
    )

    # Tentative d'insert PG
    try:
        from backend.pg_pool import pg_connection
    except Exception:
        return False

    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO admin_audit_log
                      (actor_email, actor_role, tenant_id, method, path, status_code,
                       request_id, ip, user_agent, payload, description)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                    """,
                    (
                        actor_email,
                        actor_role,
                        tenant_id,
                        method.upper(),
                        path,
                        status_code,
                        request_id,
                        ip,
                        (user_agent or "")[:500] or None,
                        json.dumps(payload, ensure_ascii=False) if payload else None,
                        description,
                    ),
                )
                conn.commit()
        return True
    except Exception as e:
        # Table n'existe pas, PG indispo, etc. : on log et on continue.
        logger.debug("admin_audit_log insert failed (best-effort): %s", e)
        return False


def fetch_recent_audit_entries(
    *,
    limit: int = 100,
    offset: int = 0,
    actor_email: Optional[str] = None,
    tenant_id: Optional[int] = None,
    method: Optional[str] = None,
    path_prefix: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Recupere les dernieres entrees audit-log avec filtres optionnels.

    Retourne [] si la table n'existe pas ou PG indispo.
    """
    try:
        from backend.pg_pool import pg_connection
    except Exception:
        return []

    where_clauses: List[str] = []
    params: List[Any] = []
    if actor_email:
        where_clauses.append("actor_email = %s")
        params.append(actor_email)
    if tenant_id is not None:
        where_clauses.append("tenant_id = %s")
        params.append(tenant_id)
    if method:
        where_clauses.append("method = %s")
        params.append(method.upper())
    if path_prefix:
        where_clauses.append("path LIKE %s")
        params.append(path_prefix.rstrip("%") + "%")

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    params.extend([limit, offset])

    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, actor_email, actor_role, tenant_id, method, path,
                           status_code, request_id, ip, user_agent, payload, description,
                           created_at
                    FROM admin_audit_log
                    {where_sql}
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s OFFSET %s
                    """,
                    tuple(params),
                )
                rows = cur.fetchall() or []
                # rows sont des dict_row (cf. pg_pool)
                out = []
                for r in rows:
                    if hasattr(r, "items"):
                        d = dict(r)
                    else:
                        # tuple fallback (n'arrive pas avec dict_row mais defensive)
                        d = {
                            "id": r[0],
                            "actor_email": r[1],
                            "actor_role": r[2],
                            "tenant_id": r[3],
                            "method": r[4],
                            "path": r[5],
                            "status_code": r[6],
                            "request_id": r[7],
                            "ip": r[8],
                            "user_agent": r[9],
                            "payload": r[10],
                            "description": r[11],
                            "created_at": r[12],
                        }
                    if d.get("created_at"):
                        d["created_at"] = d["created_at"].isoformat()
                    out.append(d)
                return out
    except Exception as e:
        logger.debug("fetch_recent_audit_entries failed: %s", e)
        return []


def purge_old_audit_entries(*, retention_days: int = 365) -> int:
    """
    Supprime les entrees audit-log plus anciennes que `retention_days`.

    Retourne le nombre de lignes supprimees. 0 si PG indispo ou table vide.
    Best-effort : capture les exceptions et log uniquement.

    Conformite RGPD : limite la duree de conservation des donnees personnelles
    (actor_email, ip). A appeler regulierement via le scheduler (cf.
    backend/reports.py setup_scheduler).
    """
    if retention_days <= 0:
        logger.warning("purge_old_audit_entries: retention_days <= 0, no-op")
        return 0

    try:
        from backend.pg_pool import pg_connection
    except Exception:
        return 0

    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM admin_audit_log
                    WHERE created_at < now() - (%s || ' days')::interval
                    """,
                    (str(retention_days),),
                )
                deleted = cur.rowcount or 0
                conn.commit()
                if deleted:
                    logger.info(
                        "[ADMIN_AUDIT_PURGE] deleted=%s retention_days=%s",
                        deleted, retention_days,
                    )
                return int(deleted)
    except Exception as e:
        logger.warning("purge_old_audit_entries failed: %s", e)
        return 0


def install_audit_middleware(app) -> None:
    """
    Installe le middleware FastAPI qui logge automatiquement les writes admin.

    Idempotent : pose un flag sur l'app pour eviter le double-install.
    """
    if getattr(app, "_audit_middleware_installed", False):
        return
    app._audit_middleware_installed = True

    if os.environ.get("ADMIN_AUDIT_LOG_ENABLED", "true").strip().lower() in ("0", "false", "no"):
        logger.info("admin_audit_log: disabled via ADMIN_AUDIT_LOG_ENABLED=false")
        return

    @app.middleware("http")
    async def audit_admin_writes(request, call_next):
        method = request.method
        path = request.url.path

        if not _is_admin_write_path(method, path):
            return await call_next(request)

        # Capture body avant call_next (Request le met en cache).
        body = await request.body()

        # Execute la requete
        response = await call_next(request)

        # Identifie l'admin (best-effort, sans bloquer si erreur)
        actor_email = None
        actor_role = None
        try:
            # Cookie session
            from backend.routes.admin import _get_admin_email_from_cookie
            actor_email = _get_admin_email_from_cookie(request)
            if actor_email:
                actor_role = "admin"
        except Exception:
            pass

        if not actor_email:
            # Fallback : Bearer token (legacy) — on ne stocke pas le token en clair
            auth = request.headers.get("authorization") or ""
            if auth.lower().startswith("bearer "):
                actor_email = "bearer-token"
                actor_role = "admin"

        # request_id (genere par log_setup middleware si actif)
        request_id = response.headers.get("x-request-id") or request.headers.get("x-request-id")

        ip = _client_ip_from_headers(
            request.headers, request.client.host if request.client else None
        )
        user_agent = request.headers.get("user-agent")

        payload = _sanitize_payload(body)
        tenant_id = _extract_tenant_id_from_path(path)

        try:
            write_audit_entry(
                actor_email=actor_email,
                actor_role=actor_role,
                tenant_id=tenant_id,
                method=method,
                path=path,
                status_code=response.status_code,
                request_id=request_id,
                ip=ip,
                user_agent=user_agent,
                payload=payload,
            )
        except Exception as e:
            logger.debug("audit middleware insert failed: %s", e)

        return response

    logger.info("admin_audit_log middleware installed")
