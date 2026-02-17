from __future__ import annotations

from typing import Dict, Optional

from backend import config
from backend.session import Session
from backend.session_store_sqlite import SQLiteSessionStore
from backend.tenant_routing import current_tenant_id
from backend import session_pg


class HybridSessionStore:
    """
    Session store hybride :
    - Web multi-tenant : PG web_sessions scopé par (tenant_id, conv_id) quand PG est dispo.
    - Sinon / legacy : SQLiteSessionStore (sessions.db) inchangé.
    """

    def __init__(self, db_path: str = "sessions.db") -> None:
        self._sqlite = SQLiteSessionStore(db_path=db_path)
        self._memory_cache: Dict[str, Session] = {}

    def _can_use_pg_web(self) -> bool:
        """Vrai si on doit utiliser PG pour les sessions web."""
        try:
            return config.USE_PG_TENANTS and bool(session_pg._pg_url())
        except Exception:
            return False

    def _cache_put(self, session: Session) -> None:
        if not session or not session.conv_id:
            return
        self._memory_cache[session.conv_id] = session
        tenant_id = getattr(session, "tenant_id", None)
        if tenant_id:
            try:
                session_pg.pg_web_register_conv_tenant(session.conv_id, int(tenant_id))
            except Exception:
                # Cache best-effort, ne doit jamais casser le flux
                pass

    def _cache_get(self, conv_id: str) -> Optional[Session]:
        return self._memory_cache.get(conv_id)

    # -------- API publique compatible SQLiteSessionStore --------

    def get(self, conv_id: str) -> Optional[Session]:
        """Récupère une session existante (PG web ou SQLite)."""
        # 1) Cache mémoire
        s = self._cache_get(conv_id)
        if s is not None:
            return s

        # 2) PG web (si actif) — résolution tenant_id via cache conv_id -> tenant_id
        if self._can_use_pg_web():
            try:
                tenant_id = session_pg.pg_web_resolve_tenant_for_conv(conv_id)
            except Exception:
                tenant_id = None
            if tenant_id is not None:
                try:
                    s = session_pg.pg_get_web_session(tenant_id, conv_id)
                except Exception:
                    s = None
                if s is not None:
                    self._cache_put(s)
                    return s

        # 3) Fallback : SQLite (legacy / mono-tenant)
        s = self._sqlite.get(conv_id)
        if s is not None:
            self._cache_put(s)
        return s

    def get_or_create(self, conv_id: str) -> Session:
        """
        Récupère ou crée une session.
        - Si PG web dispo + tenant_id connu (ContextVar ou cache) → web_sessions (tenant_id, conv_id).
        - Sinon → SQLite (sessions.db, comportement legacy).
        """
        # 1) Déjà en mémoire ?
        s = self._cache_get(conv_id)
        if s is not None:
            return s

        # 2) PG web (multi-tenant) si possible
        if self._can_use_pg_web():
            tenant_id: Optional[int] = None

            # a) Tenant explicite dans le ContextVar (typique POST /chat)
            try:
                tid_str = current_tenant_id.get()
                if tid_str is not None:
                    tenant_id = int(tid_str)
            except Exception:
                tenant_id = None

            # b) Sinon, tenter résolution depuis le cache conv_id -> tenant_id (typique GET /stream)
            if tenant_id is None:
                try:
                    cached_tid = session_pg.pg_web_resolve_tenant_for_conv(conv_id)
                    if cached_tid is not None:
                        tenant_id = int(cached_tid)
                except Exception:
                    tenant_id = None

            if tenant_id is not None:
                try:
                    s = session_pg.pg_get_or_create_web_session(tenant_id, conv_id)
                except Exception:
                    s = None
                if s is not None:
                    self._cache_put(s)
                    return s

        # 3) Fallback : SQLite (legacy) — avec garde multi-tenant côté SQLiteSessionStore
        s = self._sqlite.get_or_create(conv_id)
        self._cache_put(s)
        return s

    def save(self, session: Session) -> None:
        """Sauvegarde la session (PG web si possible, sinon SQLite)."""
        self._cache_put(session)

        used_pg = False
        if self._can_use_pg_web():
            tenant_id = getattr(session, "tenant_id", None)
            if tenant_id:
                try:
                    used_pg = session_pg.pg_save_web_session(int(tenant_id), session.conv_id, session)
                except Exception:
                    used_pg = False

        if not used_pg and hasattr(self._sqlite, "save"):
            self._sqlite.save(session)

    def set_for_resume(self, session: Session) -> None:
        """
        Injecte une session reprise (ex: depuis PG vocal). Best-effort pour la
        garder cohérente avec le cache web.
        """
        self._cache_put(session)
        if hasattr(self._sqlite, "set_for_resume"):
            self._sqlite.set_for_resume(session)

    def delete(self, conv_id: str) -> None:
        """Supprime une session (cache + SQLite + best-effort PG web)."""
        self._memory_cache.pop(conv_id, None)

        if self._can_use_pg_web():
            try:
                tenant_id = session_pg.pg_web_resolve_tenant_for_conv(conv_id)
            except Exception:
                tenant_id = None
            if tenant_id is not None:
                try:
                    session_pg.pg_delete_web_session(int(tenant_id), conv_id)
                except Exception:
                    # Rien de bloquant : on continue avec SQLite
                    pass

        if hasattr(self._sqlite, "delete"):
            self._sqlite.delete(conv_id)

    def cleanup_old_sessions(self, hours: int = 24) -> int:
        """
        Nettoyage des anciennes sessions.
        - SQLite : on garde le comportement existant.
        - PG web : pas de cleanup automatique ici (sera géré côté DB/cron si besoin).
        """
        if hasattr(self._sqlite, "cleanup_old_sessions"):
            return self._sqlite.cleanup_old_sessions(hours)
        return 0

# backend/session_store_hybrid.py
"""
Store hybride : PG pour sessions web (tenant_id, conv_id) quand USE_PG_TENANTS,
sinon SQLite. Utilise current_tenant_id (ContextVar) et un cache conv_id -> tenant_id
pour GET /stream qui n'envoie pas X-Tenant-Key.
"""
from __future__ import annotations

from typing import Dict, Optional

from backend.session import Session
from backend.session_store_sqlite import SQLiteSessionStore
from backend import config
from backend.tenant_routing import current_tenant_id


class HybridSessionStore:
    """
    Délègue au SQLite store ; quand USE_PG_TENANTS et tenant_id connu (context ou cache),
    utilise session_pg pour les sessions web (get/get_or_create/save).
    """

    def __init__(self, db_path: str = "sessions.db"):
        self._sqlite = SQLiteSessionStore(db_path=db_path)
        self._memory_cache: Dict[str, Session] = {}

    def get(self, conv_id: str) -> Optional[Session]:
        if conv_id in self._memory_cache:
            return self._memory_cache[conv_id]
        if config.USE_PG_TENANTS:
            from backend.session_pg import pg_web_resolve_tenant_for_conv, pg_get_web_session
            tid = pg_web_resolve_tenant_for_conv(conv_id)
            if tid is not None:
                session = pg_get_web_session(tid, conv_id)
                if session is not None:
                    self._memory_cache[conv_id] = session
                    return session
        return self._sqlite.get(conv_id)

    def get_or_create(self, conv_id: str) -> Session:
        session = self.get(conv_id)
        if session is not None:
            return session
        if config.USE_PG_TENANTS:
            tid_val = current_tenant_id.get()
            if tid_val is not None and tid_val.strip():
                try:
                    tid = int(tid_val)
                except (ValueError, TypeError):
                    pass
                else:
                    from backend.session_pg import (
                        pg_get_or_create_web_session,
                        pg_web_register_conv_tenant,
                    )
                    session = pg_get_or_create_web_session(tid, conv_id)
                    pg_web_register_conv_tenant(conv_id, tid)
                    self._memory_cache[conv_id] = session
                    return session
        return self._sqlite.get_or_create(conv_id)

    def save(self, session: Session) -> None:
        self._memory_cache[session.conv_id] = session
        channel = getattr(session, "channel", "web")
        if config.USE_PG_TENANTS and channel == "web":
            tid = getattr(session, "tenant_id", None)
            if tid is not None:
                from backend.session_pg import pg_save_web_session, pg_web_register_conv_tenant
                pg_save_web_session(tid, session.conv_id, session)
                pg_web_register_conv_tenant(session.conv_id, tid)
                if hasattr(self._sqlite, "save"):
                    return  # pas d'écriture SQLite pour session web en PG
        if hasattr(self._sqlite, "save"):
            self._sqlite.save(session)

    def set_for_resume(self, session: Session) -> None:
        self._memory_cache[session.conv_id] = session
        # Ne pas enregistrer les sessions vocales dans le cache web (elles sont dans call_sessions).
        if getattr(session, "channel", "") == "web":
            tid = getattr(session, "tenant_id", None)
            if tid is not None and config.USE_PG_TENANTS:
                from backend.session_pg import pg_web_register_conv_tenant
                pg_web_register_conv_tenant(session.conv_id, tid)
        if hasattr(self._sqlite, "set_for_resume"):
            self._sqlite.set_for_resume(session)

    def delete(self, conv_id: str) -> None:
        self._memory_cache.pop(conv_id, None)
        if config.USE_PG_TENANTS:
            from backend.session_pg import pg_web_resolve_tenant_for_conv, pg_delete_web_session
            tid = pg_web_resolve_tenant_for_conv(conv_id)
            if tid is not None:
                pg_delete_web_session(tid, conv_id)
        if hasattr(self._sqlite, "delete"):
            self._sqlite.delete(conv_id)

    def cleanup_old_sessions(self, hours: int = 24) -> int:
        if hasattr(self._sqlite, "cleanup_old_sessions"):
            return self._sqlite.cleanup_old_sessions(hours)
        return 0
