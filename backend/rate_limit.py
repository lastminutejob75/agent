"""
Rate limiting partagé (auth, pré-onboarding, API publiques).
Utilise Redis si REDIS_URL est défini, sinon mémoire process (développement / mono-réplica).
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import List, Optional

logger = logging.getLogger(__name__)

_memory: defaultdict[str, List[float]] = defaultdict(list)
_redis_client = None
_redis_unavailable = False


def _get_redis():
    global _redis_client, _redis_unavailable
    if _redis_unavailable:
        return None
    if _redis_client is not None:
        return _redis_client
    import os

    url = (os.environ.get("REDIS_URL") or "").strip()
    if not url:
        _redis_unavailable = True
        return None
    try:
        import redis

        client = redis.from_url(url, decode_responses=True)
        client.ping()
        _redis_client = client
        logger.info("rate_limit: backend Redis actif")
        return _redis_client
    except Exception as e:
        logger.warning("rate_limit: Redis indisponible, fallback mémoire: %s", e)
        _redis_unavailable = True
        return None


def client_ip(request) -> str:
    forwarded = (getattr(request, "headers", None) or {}).get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if getattr(request, "client", None) and request.client:
        return request.client.host or "0.0.0.0"
    return "0.0.0.0"


def check_sliding_window(key: str, limit: int, window_sec: int = 60, message: Optional[str] = None) -> None:
    """
    Lève RuntimeError si la limite est dépassée (à convertir en HTTP 429).
    """
    if limit < 1:
        return
    msg = message or "Trop de requêtes. Réessayez dans une minute."
    redis = _get_redis()
    now = time.time()
    if redis is not None:
        redis_key = f"uwi:rl:{key}"
        try:
            pipe = redis.pipeline()
            pipe.zremrangebyscore(redis_key, 0, now - window_sec)
            member = f"{now:.6f}"
            pipe.zadd(redis_key, {member: now})
            pipe.zcard(redis_key)
            pipe.expire(redis_key, window_sec + 10)
            _, _, count, _ = pipe.execute()
            if int(count) > limit:
                logger.warning("rate_limit redis key=%s count=%s limit=%s", key[:48], count, limit)
                raise RuntimeError(msg)
            return
        except RuntimeError:
            raise
        except Exception as e:
            logger.warning("rate_limit redis error key=%s: %s", key[:48], e)

    cutoff = now - window_sec
    bucket = _memory[key]
    _memory[key] = [t for t in bucket if t > cutoff]
    _memory[key].append(now)
    if len(_memory[key]) > limit:
        logger.warning("rate_limit memory key=%s count=%s limit=%s", key[:48], len(_memory[key]), limit)
        raise RuntimeError(msg)
