"""
Sentry integration : capture des exceptions non gerees + ERROR du log buffer.

Initialise Sentry uniquement si `SENTRY_DSN` est configure dans l'env.
Si non configure : no-op (pas d'erreur, pas d'overhead).

Configuration via env :
- SENTRY_DSN : DSN du projet Sentry (sans = pas d'init)
- SENTRY_ENVIRONMENT : production / staging / development (auto-detecte)
- SENTRY_TRACES_SAMPLE_RATE : 0.0-1.0 (defaut 0.0 = pas de tracing)
- SENTRY_RELEASE : version (auto-detecte via git sha si dispo)
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_initialized = False


def _detect_environment() -> str:
    """Detecte l'environnement (prod / staging / dev)."""
    env = (os.environ.get("SENTRY_ENVIRONMENT") or "").strip().lower()
    if env:
        return env
    railway_env = (os.environ.get("RAILWAY_ENVIRONMENT") or "").strip().lower()
    if railway_env:
        return railway_env
    app_env = (os.environ.get("ENV") or "").strip().lower()
    if app_env:
        return app_env
    return "development"


def _detect_release() -> Optional[str]:
    """Detecte la version (release Sentry) via env ou git sha."""
    explicit = (os.environ.get("SENTRY_RELEASE") or "").strip()
    if explicit:
        return explicit
    # Fallback : git sha (cf. backend/system_info.py pour la logique)
    try:
        from backend.system_info import _git_sha_short
        sha = _git_sha_short()
        if sha:
            return f"uwi-backend@{sha}"
    except Exception:
        pass
    return None


def init_sentry() -> bool:
    """
    Initialise Sentry si `SENTRY_DSN` est configure. No-op sinon.

    Retourne True si Sentry est actif, False sinon. Idempotent.
    """
    global _initialized
    if _initialized:
        return True

    dsn = (os.environ.get("SENTRY_DSN") or "").strip()
    if not dsn:
        logger.info("Sentry: SENTRY_DSN absent, integration desactivee")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        logger.warning("Sentry: sentry-sdk pas installe (pip install sentry-sdk[fastapi])")
        return False

    try:
        traces_rate = float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE") or "0.0")
    except (ValueError, TypeError):
        traces_rate = 0.0

    # LoggingIntegration : envoie les ERROR+ comme events. INFO+ comme breadcrumbs.
    logging_integration = LoggingIntegration(
        level=logging.INFO,         # niveau pour breadcrumbs
        event_level=logging.ERROR,  # niveau pour events captures
    )

    sentry_sdk.init(
        dsn=dsn,
        environment=_detect_environment(),
        release=_detect_release(),
        traces_sample_rate=traces_rate,
        send_default_pii=False,  # ne jamais envoyer cookies/IP/headers complets
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            StarletteIntegration(transaction_style="endpoint"),
            logging_integration,
        ],
        # Ne pas envoyer les exceptions HTTP "normales" (4xx)
        before_send=_before_send,
    )

    _initialized = True
    logger.info(
        "Sentry: initialise (env=%s, release=%s, traces=%s)",
        _detect_environment(), _detect_release(), traces_rate,
    )
    return True


def _before_send(event, hint):
    """Filtre avant envoi : skip les exceptions HTTP 4xx (pas vraiment des erreurs)."""
    try:
        if "exc_info" in (hint or {}):
            exc_type, exc_value, _ = hint["exc_info"]
            # FastAPI HTTPException avec status < 500 = pas une erreur applicative
            try:
                from fastapi import HTTPException
                if isinstance(exc_value, HTTPException) and exc_value.status_code < 500:
                    return None
            except Exception:
                pass
    except Exception:
        pass
    return event


def capture_exception(exc: BaseException) -> None:
    """Capture une exception explicitement. No-op si Sentry pas init."""
    if not _initialized:
        return
    try:
        import sentry_sdk
        sentry_sdk.capture_exception(exc)
    except Exception as e:
        logger.debug("Sentry capture_exception failed: %s", e)


def capture_message(message: str, level: str = "info") -> None:
    """Capture un message arbitraire."""
    if not _initialized:
        return
    try:
        import sentry_sdk
        sentry_sdk.capture_message(message, level=level)
    except Exception as e:
        logger.debug("Sentry capture_message failed: %s", e)


def is_initialized() -> bool:
    return _initialized


def reset_for_tests() -> None:
    """Reset l'etat pour les tests unitaires."""
    global _initialized
    _initialized = False
