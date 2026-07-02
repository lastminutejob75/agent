"""
Logs style console.time / console.timeEnd pour tracer API, SQL et fonctions.

Sortie (stdout + logger uwi.timing) :
  TIMING START <label>
  TIMING END <label> 12.34ms

Désactiver : TIMING_LOG=0
"""
from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Optional, TypeVar

logger = logging.getLogger("uwi.timing")

F = TypeVar("F", bound=Callable[..., Any])

_active_starts: dict[str, float] = {}
_sqlite_installed = False


def _enabled() -> bool:
    import os

    # Désactivé par défaut : ce traçage émet 2 lignes (logger + print flush) par
    # appel de fonction et par requête SQL, ce qui sature les logs Railway
    # (rate limit 500 logs/s, messages perdus) et masque les vraies erreurs.
    # Opt-in explicite via TIMING_LOG=1 pour du debug ponctuel.
    value = (os.environ.get("TIMING_LOG") or "0").strip().lower()
    return value in ("1", "true", "yes", "on")


def time_start(label: str) -> None:
    if not _enabled():
        return
    logger.info("TIMING START %s", label)
    print(f"TIMING START {label}", flush=True)
    _active_starts[label] = time.perf_counter()


def time_end(label: str) -> float:
    if not _enabled():
        return 0.0
    started = _active_starts.pop(label, None)
    if started is None:
        started = time.perf_counter()
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    logger.info("TIMING END %s %.2fms", label, elapsed_ms)
    print(f"TIMING END {label} {elapsed_ms:.2f}ms", flush=True)
    return elapsed_ms


@contextmanager
def time_block(label: str) -> Iterator[None]:
    time_start(label)
    try:
        yield
    finally:
        time_end(label)


def _sql_label(query: Any) -> str:
    if query is None:
        return "?"
    text = " ".join(str(query).split())
    if len(text) > 140:
        text = text[:137] + "..."
    return text


class _TimedCursorProxy:
    def __init__(self, cursor: Any, source: str) -> None:
        self._cursor = cursor
        self._source = source

    def execute(self, query: Any, params: Any = None, **kwargs: Any) -> Any:
        label = f"SQL[{self._source}] {_sql_label(query)}"
        with time_block(label):
            if params is None and not kwargs:
                return self._cursor.execute(query)
            if params is not None and kwargs:
                return self._cursor.execute(query, params, **kwargs)
            if params is not None:
                return self._cursor.execute(query, params)
            return self._cursor.execute(query, **kwargs)

    def executemany(self, query: Any, params_seq: Any, **kwargs: Any) -> Any:
        label = f"SQL[{self._source}] executemany {_sql_label(query)}"
        with time_block(label):
            if kwargs:
                return self._cursor.executemany(query, params_seq, **kwargs)
            return self._cursor.executemany(query, params_seq)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)

    def __setattr__(self, name: str, value: Any) -> None:
        # Attributs internes du proxy : rester sur le proxy.
        # Tout le reste (ex: arraysize) doit être posé sur le vrai curseur,
        # sinon on masque l'attribut réel derrière le proxy.
        if name in ("_cursor", "_source"):
            object.__setattr__(self, name, value)
        else:
            setattr(self._cursor, name, value)

    def __enter__(self) -> "_TimedCursorProxy":
        self._cursor.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
        return self._cursor.__exit__(exc_type, exc, tb)


class _TimedConnectionProxy:
    def __init__(self, conn: Any, source: str) -> None:
        self._conn = conn
        self._source = source

    def cursor(self, *args: Any, **kwargs: Any) -> _TimedCursorProxy:
        return _TimedCursorProxy(self._conn.cursor(*args, **kwargs), self._source)

    def execute(self, query: Any, params: Any = None, **kwargs: Any) -> Any:
        label = f"SQL[{self._source}] {_sql_label(query)}"
        with time_block(label):
            if params is None and not kwargs:
                return self._conn.execute(query)
            if params is not None and kwargs:
                return self._conn.execute(query, params, **kwargs)
            if params is not None:
                return self._conn.execute(query, params)
            return self._conn.execute(query, **kwargs)

    def executemany(self, query: Any, params_seq: Any, **kwargs: Any) -> Any:
        label = f"SQL[{self._source}] executemany {_sql_label(query)}"
        with time_block(label):
            if kwargs:
                return self._conn.executemany(query, params_seq, **kwargs)
            return self._conn.executemany(query, params_seq)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)

    def __setattr__(self, name: str, value: Any) -> None:
        # Attributs internes du proxy : rester sur le proxy.
        # Les autres (ex: row_factory, isolation_level) DOIVENT être
        # propagés à la vraie connexion, sinon `conn.row_factory = Row`
        # est silencieusement ignoré et les curseurs renvoient des tuples
        # -> "tuple indices must be integers" sur tout accès row["clé"].
        if name in ("_conn", "_source"):
            object.__setattr__(self, name, value)
        else:
            setattr(self._conn, name, value)

    def __enter__(self) -> "_TimedConnectionProxy":
        self._conn.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
        return self._conn.__exit__(exc_type, exc, tb)


def wrap_connection(conn: Any, source: str = "pg") -> Any:
    if isinstance(conn, _TimedConnectionProxy):
        return conn
    return _TimedConnectionProxy(conn, source)


def timed_fn(label: Optional[str] = None) -> Callable[[F], F]:
    def decorator(fn: F) -> F:
        name = label or f"{fn.__module__}.{fn.__qualname__}"

        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with time_block(name):
                    return await fn(*args, **kwargs)

            async_wrapper._uwi_timed = True  # type: ignore[attr-defined]
            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with time_block(name):
                return fn(*args, **kwargs)

        sync_wrapper._uwi_timed = True  # type: ignore[attr-defined]
        return sync_wrapper  # type: ignore[return-value]

    return decorator


def instrument_module(module: Any, *, prefix: Optional[str] = None) -> int:
    """Enveloppe toutes les fonctions définies dans un module avec timed_fn."""
    mod_name = getattr(module, "__name__", repr(module))
    wrapped_count = 0
    for attr_name, obj in list(vars(module).items()):
        if not inspect.isfunction(obj):
            continue
        if getattr(obj, "__module__", None) != mod_name:
            continue
        if getattr(obj, "_uwi_timed", False):
            continue
        # Certaines fonctions sont utilisées comme dépendances FastAPI et
        # importées par d'autres modules APRÈS instrumentation. Les envelopper
        # casse la résolution des annotations (le wrapper porte les globals de
        # timing_log, pas ceux du module d'origine), ce qui transforme un
        # paramètre `request: Request` en query param requis -> 422.
        # Cf. backend/admin_demo/router.py qui importe `_verify_admin`.
        if getattr(obj, "_uwi_no_timing", False):
            continue
        label = f"{prefix or mod_name}.{attr_name}"
        setattr(module, attr_name, timed_fn(label)(obj))
        wrapped_count += 1
    return wrapped_count


def install_sqlite_timing() -> None:
    global _sqlite_installed
    if _sqlite_installed:
        return

    original_connect = sqlite3.connect

    def timed_connect(database: Any, *args: Any, **kwargs: Any) -> Any:
        db_label = str(database)
        with time_block(f"sqlite.connect({db_label})"):
            conn = original_connect(database, *args, **kwargs)
        return wrap_connection(conn, source=f"sqlite:{db_label}")

    sqlite3.connect = timed_connect  # type: ignore[assignment]
    _sqlite_installed = True


def install_api_timing(*, extra_modules: tuple[Any, ...] = ()) -> int:
    """Active le timing SQL + instrumentation des modules routes/services."""
    install_sqlite_timing()

    from backend.routes import (
        admin,
        auth,
        bland,
        checkout_embedded,
        client,
        pre_onboarding,
        public_pages,
        public_praticien,
        public_questionnaire,
        reports,
        stripe_webhook,
        tenant,
        voice,
        whatsapp,
    )

    route_modules = (
        admin,
        auth,
        bland,
        checkout_embedded,
        client,
        pre_onboarding,
        public_pages,
        public_praticien,
        public_questionnaire,
        reports,
        stripe_webhook,
        tenant,
        voice,
        whatsapp,
        *extra_modules,
    )

    service_module_paths = (
        "backend.cabinet_profile_pg",
        "backend.public_slug_cache",
        "backend.tenants_pg",
        "backend.public_bookings_pg",
        "backend.tools_booking",
        "backend.db",
    )

    total = 0
    for mod in route_modules:
        total += instrument_module(mod)

    import importlib

    for mod_path in service_module_paths:
        try:
            mod = importlib.import_module(mod_path)
            total += instrument_module(mod)
        except Exception as exc:
            logger.debug("timing_log skip module %s: %s", mod_path, exc)

    logger.info("timing_log installed: %s functions instrumented", total)
    print(f"timing_log installed: {total} functions instrumented", flush=True)
    return total
