"""Persistent submission limits and production-origin enforcement; no external infrastructure calls."""

import os
from uuid import uuid4
import pytest
from redis.asyncio import Redis
from starlette.requests import Request
from app.api.v1.endpoints import admission as routes
from app.core.config import get_settings
from app.models.domain import User
from app.services.feature_common import FeatureError, digest, now


def request(origin: str, host: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/me/history-imports",
            "headers": [(b"origin", origin.encode())],
            "client": (host, 1234),
        }
    )


async def test_production_cross_origin_mutation_is_rejected(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "environment", "production")
    monkeypatch.setattr(cfg, "cors_origins", "https://trusted.example")
    with pytest.raises(FeatureError) as failure:
        await routes.guard(
            request("https://wrong.example", "local-test"),
            User(id=uuid4(), email="guard@example.com", display_name="Guard"),
        )
    assert failure.value.code == "ORIGIN_REJECTED"


@pytest.mark.skipif(
    not os.environ.get("TEST_REDIS_URL"), reason="Disposable Redis required"
)
async def test_redis_limits_shared_between_requests_and_fail_closed(monkeypatch):
    cfg = get_settings()
    url = os.environ["TEST_REDIS_URL"]
    monkeypatch.setattr(cfg, "redis_url", url)
    moment = now()
    monkeypatch.setattr(routes, "now", lambda: moment)
    identity, host = str(uuid4()), str(uuid4())
    req = request("http://localhost", host)
    keys = [
        f"admission:user:{identity}:{int(moment.timestamp())//60}",
        f"admission:ip:{digest(host)}:{int(moment.timestamp())//60}",
    ]
    try:
        for _ in range(30):
            await routes.mutation_limit(req, identity)
        with pytest.raises(FeatureError) as failure:
            await routes.mutation_limit(req, identity)
        assert (
            failure.value.code == "SUBMISSION_LIMIT" and failure.value.retry_after == 60
        )
        # A second identity shares the same IP budget across replicas.
        other = str(uuid4())
        keys.append(f"admission:user:{other}:{int(moment.timestamp())//60}")
        async with Redis.from_url(url) as redis:
            await redis.set(keys[1], 120, ex=60)
        with pytest.raises(FeatureError) as failure:
            await routes.mutation_limit(req, other)
        assert failure.value.status == 429
    finally:
        async with Redis.from_url(url) as redis:
            await redis.delete(*keys)
    monkeypatch.setattr(cfg, "redis_url", "redis://127.0.0.1:9/0")
    with pytest.raises(FeatureError) as failure:
        await routes.mutation_limit(req, identity)
    assert failure.value.code == "LIMITER_UNAVAILABLE"
