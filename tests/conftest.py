"""
Configuration pytest : secrets pour E2E / API (éviter 503 en CI ou local sans .env).
Les variables sont définies avant le chargement de l'app pour que auth/tenant/admin ne renvoient pas 503.
"""
from __future__ import annotations

import os

import pytest


def pytest_configure(config):
    """Au démarrage de pytest : secrets minimaux avant import de backend.main."""
    if not (os.environ.get("JWT_SECRET") or "").strip():
        os.environ["JWT_SECRET"] = "test-secret-pytest-min-32-bytes-long-for-hmac"
    if not (os.environ.get("ADMIN_API_TOKEN") or "").strip():
        os.environ["ADMIN_API_TOKEN"] = "test-admin-token-pytest"
    if not (os.environ.get("GOOGLE_CLIENT_ID") or "").strip():
        os.environ["GOOGLE_CLIENT_ID"] = "test-google-client-id"
    if not (os.environ.get("GOOGLE_CLIENT_SECRET") or "").strip():
        os.environ["GOOGLE_CLIENT_SECRET"] = "test-google-client-secret"
    os.environ.setdefault("ALLOW_GOOGLE_SELF_SIGNUP", "false")
    if not (os.environ.get("ADMIN_EMAIL") or "").strip():
        os.environ["ADMIN_EMAIL"] = "admin@uwiapp.com"
    if not (os.environ.get("ADMIN_PASSWORD") or "").strip() and not (
        os.environ.get("ADMIN_PASSWORD_HASH") or ""
    ).strip():
        os.environ["ADMIN_PASSWORD"] = "adminuwi123"


@pytest.fixture(autouse=True)
def admin_db_sqlite(request, tmp_path, monkeypatch):
    """
    Pour test_admin_dashboard et test_admin_api : force SQLite + DB isolée,
    garantit que tenant 1 et 2 existent (évite 404 quand USE_PG_TENANTS=True par défaut).
    """
    if "test_admin" not in request.module.__name__:
        return
    monkeypatch.setattr("backend.config.USE_PG_TENANTS", False)
    monkeypatch.setattr("backend.db.DB_PATH", str(tmp_path / "agent.db"))
    import backend.db as db
    db.init_db()
    # Tenant 2 pour test_admin_add_user_email_conflict_other_tenant_409
    conn = db.get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO tenants (tenant_id, name, timezone, status) VALUES (2, 'Second', 'Europe/Paris', 'active')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO tenant_config (tenant_id, flags_json, params_json) VALUES (2, '{}', '{}')"
        )
        conn.commit()
    finally:
        conn.close()
