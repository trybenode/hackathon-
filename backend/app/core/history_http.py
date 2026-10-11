"""Scoped history rate limiting and browser origin protection."""
from fastapi import Request
from redis.asyncio import Redis
from redis.exceptions import RedisError
from app.core.config import get_settings
from app.services.portability import FeatureError, digest, now


async def history_guard(request: Request) -> None:
    """Reject disabled features/cross-origin mutations and bound per-IP attempts."""
    cfg = get_settings()
    if not cfg.history_enabled:
        raise FeatureError(503, "HISTORY_DISABLED", "Work-history capture is unavailable.")
    if request.method in {"POST", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        if origin and origin not in cfg.cors_origin_list:
            raise FeatureError(403, "ORIGIN_REJECTED", "This request origin is not permitted.")
    ip = request.client.host if request.client else "unknown"
    bucket = int(now().timestamp()) // 60
    # No bearer tokens, destination numbers or message text enter Redis keys.
    keys = [f"history:ip:{digest(ip)}:{bucket}"]
    cookie = request.cookies.get("guarantor_session") or request.cookies.get("history_recipient")
    if cookie and request.method != "GET":
        keys.append(f"history:actor:{digest(cookie)}:{bucket}")
    script = "local r={} for i,k in ipairs(KEYS) do local n=redis.call('INCR',k) if n==1 then redis.call('EXPIRE',k,60) end r[i]=n end return r"
    try:
        async with Redis.from_url(cfg.redis_url, socket_connect_timeout=2, socket_timeout=2) as client:
            values = await client.eval(script, len(keys), *keys)
    except (RedisError, OSError) as error:
        raise FeatureError(503, "LIMITER_UNAVAILABLE", "Please retry when the service is available.", 60) from error
    if values[0] > 30 or (len(values) > 1 and values[1] > 5):
        raise FeatureError(429, "HISTORY_RATE_LIMIT", "Please wait before retrying.", 60)
