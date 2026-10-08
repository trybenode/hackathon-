"""Exercise the shared Lua limiter against Redis when a test server is supplied."""
import asyncio
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.services import reviews
from app.services.portability import FeatureError


@pytest.mark.asyncio
async def test_limiter_fails_closed(monkeypatch):
    # A deliberately unused local port; no production Redis is contacted.
    monkeypatch.setattr(reviews, "get_settings", lambda: SimpleNamespace(redis_url="redis://127.0.0.1:1/0"))
    with pytest.raises(FeatureError) as result:
        await reviews.limit_attempts("test", "127.0.0.1")
    assert result.value.code == "LIMITER_UNAVAILABLE"
    assert result.value.status == 503
    assert result.value.retry_after == 60


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("TEST_REDIS_URL"), reason="Set TEST_REDIS_URL to an isolated Redis server")
async def test_concurrent_redis_attempt_limits(monkeypatch):
    config = SimpleNamespace(redis_url=os.environ["TEST_REDIS_URL"], review_user_attempts_per_minute=5, review_ip_attempts_per_minute=30)
    monkeypatch.setattr(reviews, "get_settings", lambda: config)
    user, ip = str(uuid4()), str(uuid4())
    results = await asyncio.gather(*(reviews.limit_attempts(user, ip) for _ in range(12)), return_exceptions=True)
    assert results.count(None) == 5
    errors = [r for r in results if isinstance(r, FeatureError)]
    assert len(errors) == 7
    assert all(e.code == "REVIEW_RATE_LIMIT" and 1 <= e.retry_after <= 60 for e in errors)
    # Different users still share the IP budget.
    shared_ip = str(uuid4())
    results = await asyncio.gather(*(reviews.limit_attempts(str(uuid4()), shared_ip) for _ in range(35)), return_exceptions=True)
    assert results.count(None) == 30
    assert all(isinstance(e, FeatureError) for e in results if e is not None)
