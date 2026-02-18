# backend/session_pg.py
"""
P0 Option B: Journal + checkpoints pour persistance sessions vocales.
Phase 1: dual-write uniquement (on écrit en PG, session in-memory inchangée).
Réutilise DATABASE_URL / PG_EVENTS_URL comme ivr_events_pg.
Retry léger 1x sur erreurs transitoires.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from backend.pg_tenant_context import set_tenant_id_on_connection

logger = logging.getLogger(__name__)

# Phase 2.1: connexion du lock en cours (pour journal sans deadlock)
_lock_conn: ContextVar[Any] = ContextVar("pg_lock_conn", default=None)

_TRANSIENT_ERRORS = (
    "connection",
    "timeout",
    "Connection refused",
    "could not connect",
    "server closed",
    "terminating connection",
)


def _pg_url() -> Optional[str]:
    return os.environ.get("DATABASE_URL") or os.environ.get("PG_EVENTS_URL")


def _is_transient(e: Exception) -> bool:
    msg = str(e).lower()
    return any(x.lower() in msg for x in _TRANSIENT_ERRORS)


def _execute_with_retry(op_name: str, fn):
    """Exécute fn(), retry 1x si erreur transitoire. Les _do() doivent faire conn.rollback() en cas d'exception pour éviter InFailedSqlTransaction."""
    try:
        import psycopg
    except ImportError:
        logger.debug("session_pg: psycopg not installed")
        return None
    try:
        return fn()
    except Exception as e:
        if _is_transient(e):
            try:
                return fn()
            except Exception as e2:
                logger.warning("[CALL_JOURNAL_WARN] pg_down reason=%s retry=%s", op_name, e2)
                return None
        logger.warning("[CALL_JOURNAL_WARN] pg_down reason=%s", op_name, exc_info=True)
        return None


def pg_ensure_call_session(
    tenant_id: int,
    call_id: str,
    initial_state: str = "START",
) -> bool:
    """UPSERT call_sessions (insert if absent). Returns True si succès."""
    url = _pg_url()
    if not url:
        return False

    def _do():
        import psycopg
        with psycopg.connect(url) as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO call_sessions (tenant_id, call_id, status, last_state, last_seq)
                    VALUES (%s, %s, 'active', %s, 0)
                    ON CONFLICT (tenant_id, call_id) DO NOTHING
                    """,
                    (tenant_id, call_id, initial_state),
                )
                conn.commit()
        return True

    result = _execute_with_retry("pg_ensure_call_session", _do)
    return result is True


def pg_next_seq(tenant_id: int, call_id: str) -> Optional[int]:
    """Incrémente last_seq atomiquement et retourne la nouvelle valeur."""
    conn = _lock_conn.get()
    if conn is not None:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE call_sessions
                    SET last_seq = last_seq + 1, updated_at = now()
                    WHERE tenant_id = %s AND call_id = %s
                    RETURNING last_seq
                    """,
                    (tenant_id, call_id),
                )
                row = cur.fetchone()
                return int(row[0]) if row else None
        except Exception as e:
            logger.warning("[CALL_JOURNAL_WARN] pg_next_seq (lock_conn) %s", e)
            return None
    url = _pg_url()
    if not url:
        return None

    def _do():
        import psycopg
        with psycopg.connect(url) as c:
            set_tenant_id_on_connection(c, tenant_id)
            with c.cursor() as cur:
                cur.execute(
                    """
                    UPDATE call_sessions
                    SET last_seq = last_seq + 1, updated_at = now()
                    WHERE tenant_id = %s AND call_id = %s
                    RETURNING last_seq
                    """,
                    (tenant_id, call_id),
                )
                row = cur.fetchone()
                c.commit()
                return int(row[0]) if row else None

    return _execute_with_retry("pg_next_seq", _do)


def pg_add_message(
    tenant_id: int,
    call_id: str,
    role: str,
    text: str,
    ts: Optional[datetime] = None,
) -> Optional[int]:
    """Ajoute un message, retourne seq ou None."""
    url = _pg_url()
    if not url:
        return None

    seq = pg_next_seq(tenant_id, call_id)
    if seq is None:
        return None

    def _do():
        import psycopg
        with psycopg.connect(url) as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO call_messages (tenant_id, call_id, seq, role, text, ts)
                    VALUES (%s, %s, %s, %s, %s, COALESCE(%s::timestamptz, now()))
                    """,
                    (tenant_id, call_id, seq, role, text[:10000], ts.isoformat() if ts else None),
                )
                conn.commit()
        return seq

    result = _execute_with_retry("pg_add_message", _do)
    if result is not None:
        logger.info("[CALL_JOURNAL] tenant_id=%s call_id=%s seq=%s role=%s", tenant_id, call_id[:16], seq, role)
    return result


def pg_update_last_state(tenant_id: int, call_id: str, state: str) -> bool:
    """Met à jour last_state et updated_at."""
    url = _pg_url()
    if not url:
        return False

    def _do():
        import psycopg
        with psycopg.connect(url) as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE call_sessions
                    SET last_state = %s, updated_at = now()
                    WHERE tenant_id = %s AND call_id = %s
                    """,
                    (state, tenant_id, call_id),
                )
                conn.commit()
        return True

    return _execute_with_retry("pg_update_last_state", _do) is True


def pg_write_checkpoint(
    tenant_id: int,
    call_id: str,
    seq: int,
    state_json: Dict[str, Any],
) -> bool:
    """INSERT checkpoint. ON CONFLICT DO NOTHING (idempotent)."""
    url = _pg_url()
    if not url:
        return False

    import json

    def _do():
        import psycopg
        with psycopg.connect(url) as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO call_state_checkpoints (tenant_id, call_id, seq, state_json)
                    VALUES (%s, %s, %s, %s::jsonb)
                    ON CONFLICT (tenant_id, call_id, seq) DO NOTHING
                    """,
                    (tenant_id, call_id, seq, json.dumps(state_json)),
                )
                conn.commit()
        return True

    result = _execute_with_retry("pg_write_checkpoint", _do)
    if result:
        logger.info("[CHECKPOINT] tenant_id=%s call_id=%s seq=%s state=%s", tenant_id, call_id[:16], seq, state_json.get("state", ""))
    return result is True


def pg_get_latest_checkpoint(
    tenant_id: int,
    call_id: str,
) -> Optional[Tuple[int, Dict[str, Any]]]:
    """SELECT checkpoint le plus récent. Returns (seq, state_json) ou None."""
    url = _pg_url()
    if not url:
        return None

    def _do():
        import json
        import psycopg
        with psycopg.connect(url) as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT seq, state_json
                    FROM call_state_checkpoints
                    WHERE tenant_id = %s AND call_id = %s
                    ORDER BY seq DESC
                    LIMIT 1
                    """,
                    (tenant_id, call_id),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return (int(row[0]), row[1] if isinstance(row[1], dict) else json.loads(row[1]))

    return _execute_with_retry("pg_get_latest_checkpoint", _do)


def pg_list_messages_since(
    tenant_id: int,
    call_id: str,
    seq_exclusive: int,
) -> List[Tuple[int, str, str, datetime]]:
    """SELECT messages WHERE seq > seq_exclusive ORDER BY seq ASC. Returns [(seq, role, text, ts), ...]."""
    url = _pg_url()
    if not url:
        return []

    def _do():
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(url, row_factory=dict_row) as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT seq, role, text, ts
                    FROM call_messages
                    WHERE tenant_id = %s AND call_id = %s AND seq > %s
                    ORDER BY seq ASC
                    """,
                    (tenant_id, call_id, seq_exclusive),
                )
                rows = cur.fetchall()
                return [(int(r["seq"]), r["role"], r["text"] or "", r["ts"]) for r in rows]

    result = _execute_with_retry("pg_list_messages_since", _do)
    return result or []


class LockTimeout(Exception):
    """Levée quand le lock call_sessions expire (timeout). Phase 2.1."""


@contextmanager
def pg_lock_call_session(tenant_id: int, call_id: str, timeout_seconds: int = 2):
    """
    Phase 2.1: Lock court anti webhooks simultanés.
    SELECT ... FOR UPDATE sur call_sessions avec lock_timeout.
    Appelle pg_ensure_call_session avant (la ligne doit exister).
    Lève LockTimeout si timeout.
    """
    url = _pg_url()
    if not url:
        yield
        return
    pg_ensure_call_session(tenant_id, call_id)
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute("SET LOCAL lock_timeout = %s", (f"{timeout_seconds * 1000}ms",))
                cur.execute(
                    "SELECT 1 FROM call_sessions WHERE tenant_id = %s AND call_id = %s FOR UPDATE",
                    (tenant_id, call_id),
                )
                logger.info("[CALL_LOCK] acquired tenant_id=%s call_id=%s", tenant_id, call_id[:20])
            token = _lock_conn.set(conn)
            try:
                yield
            finally:
                try:
                    conn.commit()
                except Exception:
                    conn.rollback()
                _lock_conn.reset(token)
    except Exception as e:
        err_msg = str(e).lower()
        if "lock" in err_msg or "timeout" in err_msg or "55p03" in err_msg or "canceling" in err_msg:
            logger.warning("[CALL_LOCK_TIMEOUT] tenant_id=%s call_id=%s", tenant_id, call_id[:20])
            raise LockTimeout(f"lock timeout: {e}") from e
        logger.warning("[CALL_LOCK_WARN] err=%s", e, exc_info=True)
        raise


def pg_get_call_session_info(tenant_id: int, call_id: str) -> Optional[Tuple[str, int]]:
    """Retourne (last_state, last_seq) ou None si pas de row."""
    url = _pg_url()
    if not url:
        return None

    def _do():
        import psycopg
        with psycopg.connect(url) as conn:
            set_tenant_id_on_connection(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT last_state, last_seq FROM call_sessions WHERE tenant_id = %s AND call_id = %s",
                    (tenant_id, call_id),
                )
                row = cur.fetchone()
                return (row[0], int(row[1])) if row else None

    return _execute_with_retry("pg_get_call_session_info", _do)


def load_session_pg_first(tenant_id: int, call_id: str) -> Optional[Tuple["Session", int, int]]:
    """
    Phase 2: charge session depuis PG (Option A snapshot-only).
    Returns (session, ck_seq, last_seq) ou None si pas de checkpoint.
    Pas de replay messages — snapshot suffit pour reprendre le flow.
    """
    from backend.session_codec import session_from_dict

    cp = pg_get_latest_checkpoint(tenant_id, call_id)
    if not cp:
        return None
    ck_seq, state_json = cp
    session = session_from_dict(conv_id=call_id, d=state_json)
    session.tenant_id = tenant_id
    session.channel = "vocal"
    info = pg_get_call_session_info(tenant_id, call_id)
    last_seq = info[1] if info else ck_seq
    return (session, ck_seq, last_seq)


# ---------- Web sessions (tenant_id, conv_id) ----------
# Cache conv_id -> tenant_id pour GET /stream qui n'a pas le header X-Tenant-Key.
_WEB_CONV_TENANT_CACHE: Dict[str, int] = {}
_WEB_CACHE_MAX = 10000


def _pg_ensure_web_sessions_table(conn) -> None:
    """Crée la table web_sessions si absente (idempotent). Rollback sur erreur pour éviter InFailedSqlTransaction."""
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS web_sessions (
                tenant_id BIGINT NOT NULL,
                conv_id TEXT NOT NULL,
                state_json JSONB NOT NULL DEFAULT '{}',
                updated_at TIMESTAMPTZ DEFAULT now(),
                PRIMARY KEY (tenant_id, conv_id)
            )
        """)
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise


def pg_get_web_session(tenant_id: int, conv_id: str) -> Optional["Session"]:
    """Charge une session web depuis PG. Retourne None si absente."""
    from backend.session_codec import session_from_dict
    import json

    url = _pg_url()
    if not url:
        return None

    def _do() -> Optional["Session"]:
        import psycopg
        with psycopg.connect(url) as conn:
            try:
                set_tenant_id_on_connection(conn, tenant_id)
                _pg_ensure_web_sessions_table(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT state_json FROM web_sessions WHERE tenant_id = %s AND conv_id = %s",
                        (tenant_id, conv_id),
                    )
                    row = cur.fetchone()
                    if not row or not row[0]:
                        return None
                    state = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                    session = session_from_dict(conv_id=conv_id, d=state)
                    session.tenant_id = tenant_id
                    session.channel = "web"
                    return session
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                raise

    result = _execute_with_retry("pg_get_web_session", _do)
    return result


def pg_save_web_session(tenant_id: int, conv_id: str, session: "Session") -> bool:
    """Enregistre une session web en PG (UPSERT)."""
    from backend.session_codec import session_to_dict
    import json

    url = _pg_url()
    if not url:
        return False

    state = session_to_dict(session)

    def _do() -> bool:
        import psycopg
        with psycopg.connect(url) as conn:
            try:
                set_tenant_id_on_connection(conn, tenant_id)
                _pg_ensure_web_sessions_table(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO web_sessions (tenant_id, conv_id, state_json, updated_at)
                        VALUES (%s, %s, %s::jsonb, now())
                        ON CONFLICT (tenant_id, conv_id) DO UPDATE SET state_json = EXCLUDED.state_json, updated_at = now()
                        """,
                        (tenant_id, conv_id, json.dumps(state)),
                    )
                    conn.commit()
                return True
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                raise

    return _execute_with_retry("pg_save_web_session", _do) is True


def pg_get_or_create_web_session(tenant_id: int, conv_id: str) -> "Session":
    """Charge ou crée une session web en PG. Scopée par (tenant_id, conv_id)."""
    from backend.session import Session

    session = pg_get_web_session(tenant_id, conv_id)
    if session is not None:
        return session
    session = Session(conv_id=conv_id)
    session.tenant_id = tenant_id
    session.channel = "web"
    pg_save_web_session(tenant_id, conv_id, session)
    return session


def pg_web_register_conv_tenant(conv_id: str, tenant_id: int) -> None:
    """Enregistre conv_id -> tenant_id pour résolution ultérieure (ex: GET /stream)."""
    if len(_WEB_CONV_TENANT_CACHE) >= _WEB_CACHE_MAX:
        to_remove = list(_WEB_CONV_TENANT_CACHE.keys())[: _WEB_CACHE_MAX // 10]
        for k in to_remove:
            del _WEB_CONV_TENANT_CACHE[k]
    _WEB_CONV_TENANT_CACHE[conv_id] = tenant_id


def pg_web_resolve_tenant_for_conv(conv_id: str) -> Optional[int]:
    """Résout tenant_id pour un conv_id (depuis le cache). Retourne None si inconnu."""
    return _WEB_CONV_TENANT_CACHE.get(conv_id)


def pg_delete_web_session(tenant_id: int, conv_id: str) -> bool:
    """Supprime une session web en PG (best-effort)."""
    url = _pg_url()
    if not url:
        return False

    def _do() -> bool:
        import psycopg
        with psycopg.connect(url) as conn:
            try:
                set_tenant_id_on_connection(conn, tenant_id)
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM web_sessions WHERE tenant_id = %s AND conv_id = %s",
                        (tenant_id, conv_id),
                    )
                    conn.commit()
                return True
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                raise

    return _execute_with_retry("pg_delete_web_session", _do) is True
