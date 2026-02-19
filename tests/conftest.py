"""
Configuration pytest : secrets pour E2E / API (éviter 503 en CI ou local sans .env).
Les variables sont définies avant le chargement de l'app pour que auth/tenant/admin ne renvoient pas 503.
"""
from __future__ import annotations

import os


def pytest_configure(config):
    """Au démarrage de pytest : définir JWT_SECRET et ADMIN_API_TOKEN si absents."""
    if not (os.environ.get("JWT_SECRET") or "").strip():
        os.environ["JWT_SECRET"] = "test-secret-pytest-min-32-bytes-long-for-hmac"
    if not (os.environ.get("ADMIN_API_TOKEN") or "").strip():
        os.environ["ADMIN_API_TOKEN"] = "test-admin-token-pytest"
