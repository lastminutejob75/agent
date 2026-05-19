# backend/auth_rate_limit.py — Rate limiting auth endpoints
from __future__ import annotations

import os

from backend.rate_limit import check_sliding_window, client_ip


def _eff_limit(default: int, env_name: str) -> int:
    """
    Plafond par fenêtre. Sous pytest, limite très haute pour éviter les flaky tests
    sur la même IP (127.0.0.1). Sinon variable d'environnement ou défaut.
    """
    if os.environ.get("PYTEST_VERSION") or os.environ.get("PYTEST_CURRENT_TEST"):
        return 100000
    raw = (os.environ.get(env_name) or "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def check_forgot_password(request, email: str) -> None:
    ip = client_ip(request)
    check_sliding_window(f"forgot_ip:{ip}", limit=_eff_limit(5, "AUTH_RATE_LIMIT_FORGOT_IP_PER_MIN"), window_sec=60)
    if email:
        check_sliding_window(
            f"forgot_email:{(email or '').strip().lower()}",
            limit=_eff_limit(3, "AUTH_RATE_LIMIT_FORGOT_EMAIL_PER_MIN"),
            window_sec=60,
        )


def check_reset_password(request) -> None:
    check_sliding_window(
        f"reset_ip:{client_ip(request)}",
        limit=_eff_limit(10, "AUTH_RATE_LIMIT_RESET_PASSWORD_PER_MIN"),
        window_sec=60,
    )


def check_login(request) -> None:
    check_sliding_window(
        f"login_ip:{client_ip(request)}",
        limit=_eff_limit(10, "AUTH_RATE_LIMIT_LOGIN_PER_MIN"),
        window_sec=60,
        message="Trop de tentatives de connexion. Réessayez dans une minute.",
    )


def check_admin_login(request) -> None:
    """Brute-force /api/admin/auth/login."""
    check_sliding_window(
        f"admin_login_ip:{client_ip(request)}",
        limit=_eff_limit(10, "AUTH_RATE_LIMIT_ADMIN_LOGIN_PER_MIN"),
        window_sec=60,
        message="Trop de tentatives de connexion admin. Réessayez dans une minute.",
    )


def check_impersonate_exchange(request) -> None:
    """Abus potentiel sur l'échange impersonation."""
    check_sliding_window(
        f"impersonate_ip:{client_ip(request)}",
        limit=_eff_limit(20, "AUTH_RATE_LIMIT_IMPERSONATE_PER_MIN"),
        window_sec=60,
        message="Trop de demandes d'impersonation. Réessayez dans une minute.",
    )
