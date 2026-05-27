"""
System info pour l'admin : version build, git sha, Python/Node, env (sans secrets), uptime.

Exposed via GET /api/admin/system/info (auth admin requise).
"""

from __future__ import annotations

import logging
import os
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Timestamp de demarrage du process. Mis a jour au premier import.
_START_TIME = time.time()

# Pattern pour identifier les variables sensibles (case-insensitive substring)
_SECRET_KEY_PATTERNS = (
    "secret",
    "password",
    "passwd",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "privatekey",
    "auth",
    "client_secret",
    "credentials",
    "stripe_key",
    "stripe_secret",
    "twilio_auth_token",
    "vapi_api_key",
    "jwt",
    "sentry_dsn",
)

# Variables d'env safes (whitelist) — uniquement celles-ci sont retournees
# en clair. Tout le reste est masque ou exclu.
_SAFE_ENV_VARS = (
    "ENV",
    "RAILWAY_ENVIRONMENT",
    "PORT",
    "PYTHONUNBUFFERED",
    "PYTHON_VERSION",
    "NODE_VERSION",
    "TZ",
    "LOG_LEVEL",
    "LOG_JSON",
    "LOG_BUFFER_ENABLED",
    "LOG_BUFFER_SIZE",
    "ADMIN_DEMO_MODE",
    "ENABLE_DEBUG_ENDPOINTS",
    "RATE_LIMIT_ENABLED",
    "RATE_LIMIT_LOGIN_MAX",
    "RATE_LIMIT_LOGIN_WINDOW_S",
    "RATE_LIMIT_ONBOARDING_MAX",
    "RATE_LIMIT_ONBOARDING_WINDOW_S",
    "ADMIN_AUDIT_LOG_ENABLED",
    "ADMIN_AUDIT_LOG_RETENTION_DAYS",
    "VAPI_REQUIRE_SIGNATURE",
    "VAPI_SIGNATURE_DISABLED",
    "DISABLE_SCHEDULER",
    "REPORT_CHANNEL",
    "SUSPENSION_PAST_DUE_DAYS",
    "ADMIN_COOKIE_SAMESITE",
    "CORS_ORIGINS",
    "ADMIN_CORS_ORIGINS",
    "ADMIN_SESSION_EXPIRES_HOURS",
    # Indicateurs de presence (sans valeur) traites a part en _env_status
)

# Variables dont on veut savoir si elles sont *configurees* (sans exposer la valeur)
_PRESENCE_ONLY_VARS = (
    "DATABASE_URL",
    "PG_EVENTS_URL",
    "JWT_SECRET",
    "ADMIN_PASSWORD_HASH",
    "ADMIN_PASSWORD",
    "ADMIN_API_TOKEN",
    "VAPI_API_KEY",
    "VAPI_WEBHOOK_SECRET",
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TELEGRAM_BOT_TOKEN",
    "SMTP_HOST",
    "SMTP_EMAIL",
    "SMTP_PASSWORD",
    "GOOGLE_SERVICE_ACCOUNT_JSON",
    "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_OAUTH_CLIENT_SECRET",
    "SENTRY_DSN",
)


def _is_secret_key(key: str) -> bool:
    k = key.lower()
    return any(p in k for p in _SECRET_KEY_PATTERNS)


def _filtered_env() -> Dict[str, Any]:
    """Retourne les variables d'environnement safe : whitelist + presence-only."""
    safe: Dict[str, str] = {}
    for k in _SAFE_ENV_VARS:
        v = os.environ.get(k)
        if v is not None:
            safe[k] = v

    presence: Dict[str, bool] = {}
    for k in _PRESENCE_ONLY_VARS:
        presence[k] = bool((os.environ.get(k) or "").strip())

    return {"vars": safe, "configured": presence}


def _git_sha_short() -> Optional[str]:
    """Retourne le sha court de HEAD si disponible (build local + railway).

    Cherche en ordre :
    1. RAILWAY_GIT_COMMIT_SHA / GIT_COMMIT_SHA / SOURCE_COMMIT (CI/PaaS)
    2. .git/HEAD si on est dans un checkout
    3. None
    """
    for var in ("RAILWAY_GIT_COMMIT_SHA", "GIT_COMMIT_SHA", "SOURCE_COMMIT", "VERCEL_GIT_COMMIT_SHA"):
        v = (os.environ.get(var) or "").strip()
        if v:
            return v[:8]

    # Fallback : lire .git/HEAD (sans subprocess pour eviter les surprises)
    try:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        head_path = os.path.join(repo_root, ".git", "HEAD")
        if os.path.exists(head_path):
            with open(head_path) as f:
                head = f.read().strip()
            if head.startswith("ref: "):
                ref = head[5:]
                ref_path = os.path.join(repo_root, ".git", ref)
                if os.path.exists(ref_path):
                    with open(ref_path) as f:
                        return f.read().strip()[:8]
            else:
                return head[:8]
    except Exception:
        pass

    # Dernier recours : git CLI (peut etre absent en docker)
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short=8", "HEAD"],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        return out.decode().strip()[:8]
    except Exception:
        return None


def _git_branch() -> Optional[str]:
    """Retourne le nom de branche si dispo."""
    for var in ("RAILWAY_GIT_BRANCH", "GIT_BRANCH", "VERCEL_GIT_COMMIT_REF"):
        v = (os.environ.get(var) or "").strip()
        if v:
            return v

    try:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        head_path = os.path.join(repo_root, ".git", "HEAD")
        if os.path.exists(head_path):
            with open(head_path) as f:
                head = f.read().strip()
            if head.startswith("ref: refs/heads/"):
                return head[len("ref: refs/heads/"):]
    except Exception:
        pass
    return None


def _build_version() -> Optional[str]:
    """Tag/version du build (CI ou Railway)."""
    for var in ("BUILD_VERSION", "APP_VERSION", "RAILWAY_DEPLOYMENT_ID", "VERCEL_DEPLOYMENT_ID"):
        v = (os.environ.get(var) or "").strip()
        if v:
            return v
    return None


def _format_uptime(seconds: float) -> str:
    """Format `Xj Yh Zm` ou `Yh Zm` selon duree."""
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m {s % 60:02d}s"
    if s < 86400:
        return f"{s // 3600}h {(s % 3600) // 60:02d}m"
    days = s // 86400
    rest = s % 86400
    return f"{days}j {rest // 3600}h {(rest % 3600) // 60:02d}m"


def get_system_info() -> Dict[str, Any]:
    """
    Retourne un dict avec les infos systeme/runtime/build.

    Pas de secrets (filtrage par whitelist + presence-only).
    """
    now = time.time()
    uptime_sec = max(0.0, now - _START_TIME)

    # Versions Python + Node + uname
    py_version = sys.version.split()[0]
    py_impl = platform.python_implementation()
    uname = platform.uname()

    # Node version (best-effort, depuis env ou subprocess)
    node_version = (os.environ.get("NODE_VERSION") or "").strip() or None
    if not node_version:
        try:
            out = subprocess.check_output(
                ["node", "--version"], stderr=subprocess.DEVNULL, timeout=2
            )
            node_version = out.decode().strip()
        except Exception:
            node_version = None

    return {
        "build": {
            "git_sha": _git_sha_short(),
            "git_branch": _git_branch(),
            "version": _build_version(),
        },
        "runtime": {
            "python_version": py_version,
            "python_implementation": py_impl,
            "node_version": node_version,
            "platform": f"{uname.system} {uname.release}",
            "machine": uname.machine,
        },
        "process": {
            "pid": os.getpid(),
            "started_at": datetime.fromtimestamp(_START_TIME, tz=timezone.utc).isoformat(),
            "uptime_seconds": int(uptime_sec),
            "uptime_label": _format_uptime(uptime_sec),
        },
        "env": _filtered_env(),
        "now": datetime.now(timezone.utc).isoformat(),
    }


def reset_start_time_for_tests(ts: Optional[float] = None) -> None:
    """Reset _START_TIME (uniquement pour tests)."""
    global _START_TIME
    _START_TIME = ts if ts is not None else time.time()
