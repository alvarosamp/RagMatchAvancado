"""Small Redis-backed fixed-window limiter for sensitive public endpoints."""

from __future__ import annotations

import hashlib
import os

from app.logs.config import logger


def _key(scope: str, identity: str) -> str:
    digest = hashlib.sha256(identity.strip().lower().encode("utf-8")).hexdigest()
    return f"rate-limit:{scope}:{digest}"


def rate_limit_exceeded(scope: str, identity: str, *, limit: int, window_seconds: int) -> bool:
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        return False
    key = _key(scope, identity)
    try:
        from redis import Redis

        client = Redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
        count = int(client.eval(
            "local n=redis.call('INCR',KEYS[1]); "
            "if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]); end; return n",
            1,
            key,
            window_seconds,
        ))
        return count > limit
    except Exception as exc:
        # Availability is handled by /health/ready; avoid locking every user out
        # during a transient Redis problem.
        logger.warning("[RateLimit] Redis indisponivel: %s", exc)
        return False


def reset_rate_limit(scope: str, identity: str) -> None:
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        return
    try:
        from redis import Redis

        Redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1).delete(
            _key(scope, identity)
        )
    except Exception as exc:
        logger.warning("[RateLimit] Falha ao limpar contador: %s", exc)
