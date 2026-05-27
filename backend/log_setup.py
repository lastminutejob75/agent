"""Logs structures + buffer en memoire (audit observabilite 2026-05).

Trois fonctionnalites :

1. **JsonFormatter** : formate chaque log en JSON (ts, level, logger, msg, extra...).
   Active uniquement si `LOG_JSON=true` (defaut : format texte standard, comme avant).

2. **request_id contextvar** : un middleware HTTP genere un UUID par requete et le
   pousse dans un `contextvars.ContextVar`. Tous les logs emis pendant la requete
   recuperent automatiquement ce `request_id` (pratique pour tracer une requete
   bout-en-bout dans les logs).

3. **LogBuffer en memoire** : un `deque(maxlen=N)` qui garde les N derniers
   records (defaut 1000). Expose via `GET /api/admin/logs/recent` pour
   inspection rapide depuis l'admin sans avoir a se connecter en SSH.

## Variables d'env

| Variable | Defaut | Role |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Niveau racine (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LOG_JSON` | `false` | Si `true` : JsonFormatter, sinon format texte classique |
| `LOG_BUFFER_ENABLED` | `true` | Active le buffer en memoire (utile en prod pour AdminMonitoring) |
| `LOG_BUFFER_SIZE` | `1000` | Nombre de logs gardes en memoire |

## Usage

```python
# main.py
from backend.log_setup import configure_logging, install_request_logging_middleware
configure_logging()
install_request_logging_middleware(app)
```

```python
# code metier
import logging
logger = logging.getLogger(__name__)
logger.info("user_action", extra={"user_id": 42, "action": "login"})
# → JSON : {"ts":"...", "level":"INFO", "logger":"...", "msg":"user_action",
#           "request_id":"...", "user_id":42, "action":"login"}
```
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

# ---- ContextVar pour le request_id ----------------------------------------

# Defaut "" plutot que None pour faciliter la concatenation dans les logs.
_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)


def get_request_id() -> str:
    """Retourne le request_id courant (ou "" hors contexte HTTP)."""
    return _request_id_var.get() or ""


def set_request_id(rid: str) -> contextvars.Token:
    """Set le request_id courant. Retourne un token pour reset."""
    return _request_id_var.set(rid or "")


# ---- Buffer en memoire -----------------------------------------------------


class LogBuffer:
    """Ring buffer thread-safe des derniers records (sous forme de dicts)."""

    def __init__(self, maxlen: int = 1000) -> None:
        self._buf: Deque[Dict[str, Any]] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def append(self, entry: Dict[str, Any]) -> None:
        with self._lock:
            self._buf.append(entry)

    def recent(self, limit: int = 100, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retourne au plus `limit` entrees, optionnellement filtrees par level."""
        with self._lock:
            items = list(self._buf)
        if level:
            level_up = level.upper()
            items = [e for e in items if (e.get("level") or "").upper() == level_up]
        # Plus recent en premier
        items.reverse()
        return items[: max(0, int(limit))]

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._buf)


# Singleton partage par toute l'app
_LOG_BUFFER = LogBuffer(maxlen=int(os.environ.get("LOG_BUFFER_SIZE") or "1000"))


def get_log_buffer() -> LogBuffer:
    return _LOG_BUFFER


# ---- Metrics agregees -----------------------------------------------------


def compute_metrics(buffer: Optional["LogBuffer"] = None) -> Dict[str, Any]:
    """Calcule des metriques agregees a partir du buffer de logs.

    Exploite uniquement les logs `request_end` (emis par le middleware HTTP).
    Pas de dependance externe (Prometheus/Datadog) : tout est calcule en RAM.

    Returns:
        ```json
        {
          "total_requests": 47,
          "by_status": {"200": 40, "404": 5, "500": 2},
          "by_method": {"GET": 30, "POST": 17},
          "errors_4xx": 5,
          "errors_5xx": 2,
          "latency": {
            "p50_ms": 12,
            "p95_ms": 156,
            "p99_ms": 487,
            "max_ms": 1024,
            "avg_ms": 47
          },
          "top_paths": [
            {"path": "/api/admin/calls", "count": 12, "avg_ms": 87, "errors": 0},
            ...
          ],
          "logs_by_level": {"INFO": 80, "WARNING": 5, "ERROR": 1}
        }
        ```
    """
    buf = buffer or _LOG_BUFFER
    items = buf.recent(limit=10_000)  # Lit tout le buffer

    # Comptage par niveau
    by_level: Dict[str, int] = {}
    for item in items:
        lvl = (item.get("level") or "INFO").upper()
        by_level[lvl] = by_level.get(lvl, 0) + 1

    # Filtre les request_end pour les stats HTTP
    requests = [
        e for e in items
        if e.get("msg") == "request_end" and "status_code" in e
    ]

    by_status: Dict[str, int] = {}
    by_method: Dict[str, int] = {}
    latencies: list = []
    by_path: Dict[str, Dict[str, Any]] = {}

    for r in requests:
        status = str(r.get("status_code", "0"))
        by_status[status] = by_status.get(status, 0) + 1
        method = str(r.get("method", "?"))
        by_method[method] = by_method.get(method, 0) + 1
        dur = r.get("duration_ms")
        if isinstance(dur, (int, float)):
            latencies.append(int(dur))
        path = str(r.get("path", "?"))
        if path not in by_path:
            by_path[path] = {"count": 0, "total_ms": 0, "errors": 0}
        by_path[path]["count"] += 1
        if isinstance(dur, (int, float)):
            by_path[path]["total_ms"] += int(dur)
        try:
            sc = int(status)
            if sc >= 400:
                by_path[path]["errors"] += 1
        except Exception:
            pass

    # Latency percentiles
    latency_stats: Dict[str, int] = {}
    if latencies:
        sorted_lat = sorted(latencies)
        n = len(sorted_lat)
        latency_stats = {
            "p50_ms": sorted_lat[max(0, int(n * 0.50) - 1)],
            "p95_ms": sorted_lat[max(0, int(n * 0.95) - 1)],
            "p99_ms": sorted_lat[max(0, int(n * 0.99) - 1)],
            "max_ms": sorted_lat[-1],
            "avg_ms": int(sum(sorted_lat) / n),
        }

    # Compte 4xx et 5xx
    errors_4xx = sum(c for s, c in by_status.items() if s.startswith("4"))
    errors_5xx = sum(c for s, c in by_status.items() if s.startswith("5"))

    # Top paths par count
    top_paths = []
    for path, stats in sorted(by_path.items(), key=lambda kv: -kv[1]["count"])[:10]:
        avg = int(stats["total_ms"] / stats["count"]) if stats["count"] else 0
        top_paths.append({
            "path": path,
            "count": stats["count"],
            "avg_ms": avg,
            "errors": stats["errors"],
        })

    return {
        "total_requests": len(requests),
        "by_status": by_status,
        "by_method": by_method,
        "errors_4xx": errors_4xx,
        "errors_5xx": errors_5xx,
        "latency": latency_stats,
        "top_paths": top_paths,
        "logs_by_level": by_level,
        "buffer_size": buf.size(),
    }


# ---- Formatter JSON --------------------------------------------------------


class JsonFormatter(logging.Formatter):
    """Formatter qui serialise chaque record en JSON.

    Inclut systematiquement : ts, level, logger, msg, request_id.
    Inclut aussi tout `extra={...}` passe au logger (champs custom).
    """

    # Cles standards de LogRecord qu'on ne veut pas dupliquer dans `extra`
    _STANDARD_ATTRS = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "asctime", "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        # ts en ISO8601 UTC avec millisecondes
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(
            timespec="milliseconds"
        )
        out: Dict[str, Any] = {
            "ts": ts,
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": get_request_id(),
        }
        # Champs extras passes au logger
        for k, v in record.__dict__.items():
            if k in self._STANDARD_ATTRS:
                continue
            if k.startswith("_"):
                continue
            try:
                json.dumps(v)
                out[k] = v
            except Exception:
                out[k] = repr(v)
        # Exception info
        if record.exc_info:
            out["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(out, ensure_ascii=False, default=str)


# ---- Handler buffer --------------------------------------------------------


class BufferHandler(logging.Handler):
    """Pousse chaque record (sous forme dict) dans le LogBuffer global."""

    def __init__(self, buffer: LogBuffer, level: int = logging.INFO) -> None:
        super().__init__(level=level)
        self._buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = {
                "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(
                    timespec="milliseconds"
                ),
                "level": record.levelname,
                "logger": record.name,
                "msg": record.getMessage(),
                "request_id": get_request_id(),
            }
            for k, v in record.__dict__.items():
                if k in JsonFormatter._STANDARD_ATTRS:
                    continue
                if k.startswith("_"):
                    continue
                try:
                    json.dumps(v)
                    entry[k] = v
                except Exception:
                    entry[k] = repr(v)
            if record.exc_info:
                entry["exc_info"] = self.format(record)
            self._buffer.append(entry)
        except Exception:
            # Ne jamais casser l'app a cause du logging
            pass


# ---- Configuration ---------------------------------------------------------


def _truthy(val: Optional[str]) -> bool:
    return (val or "").strip().lower() in ("true", "1", "yes", "on")


def configure_logging() -> None:
    """Configure le logging racine selon les env vars.

    Idempotent : peut etre appele plusieurs fois sans dupliquer les handlers.
    """
    root = logging.getLogger()

    # Niveau
    level_name = (os.environ.get("LOG_LEVEL") or "INFO").upper().strip()
    level = getattr(logging, level_name, logging.INFO)
    root.setLevel(level)

    # Marqueur idempotence : on tague nos handlers pour pouvoir les reset
    for h in list(root.handlers):
        if getattr(h, "_uwi_log_handler", False):
            root.removeHandler(h)

    # Handler stdout
    stream_h = logging.StreamHandler()
    stream_h._uwi_log_handler = True  # type: ignore[attr-defined]
    if _truthy(os.environ.get("LOG_JSON")):
        stream_h.setFormatter(JsonFormatter())
    else:
        # Format texte classique mais avec request_id si present
        stream_h.setFormatter(_TextFormatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s %(request_id_tag)s%(message)s"
        ))
    root.addHandler(stream_h)

    # Handler buffer en memoire
    if _truthy(os.environ.get("LOG_BUFFER_ENABLED") or "true"):
        buf_h = BufferHandler(_LOG_BUFFER, level=level)
        buf_h._uwi_log_handler = True  # type: ignore[attr-defined]
        root.addHandler(buf_h)


class _TextFormatter(logging.Formatter):
    """Formatter texte standard avec ajout de [rid=...] si request_id present."""

    def format(self, record: logging.LogRecord) -> str:
        rid = get_request_id()
        record.request_id_tag = f"[rid={rid}] " if rid else ""
        return super().format(record)


# ---- Middleware HTTP -------------------------------------------------------


def install_request_logging_middleware(app: Any) -> None:
    """Installe un middleware FastAPI qui :

    - Genere un request_id (uuid4) ou recupere depuis le header `X-Request-ID`.
    - Le pousse dans le contextvar pour que tous les logs en aval l'incluent.
    - Mesure la duree (ms) et log un evenement `request_end` avec status_code.
    - Ajoute le header `X-Request-ID` dans la reponse pour tracage cote client.
    """
    from fastapi import Request

    log = logging.getLogger("uwi.request")

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        # Reuse client request id si fourni, sinon en genere un
        rid = (request.headers.get("x-request-id") or "").strip() or str(uuid.uuid4())
        token = set_request_id(rid)
        t0 = time.monotonic()
        status_code: Optional[int] = None
        try:
            response = await call_next(request)
            status_code = getattr(response, "status_code", None)
            try:
                response.headers["X-Request-ID"] = rid
            except Exception:
                pass
            return response
        except Exception:
            status_code = 500
            log.exception(
                "request_error",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                },
            )
            raise
        finally:
            duration_ms = int((time.monotonic() - t0) * 1000)
            try:
                log.info(
                    "request_end",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": status_code,
                        "duration_ms": duration_ms,
                    },
                )
            except Exception:
                pass
            _request_id_var.reset(token)
