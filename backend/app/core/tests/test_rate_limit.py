from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.core.rate_limit import SlidingWindowLimiter, rate_limit


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_allows_up_to_the_limit_then_blocks():
    limiter = SlidingWindowLimiter(2, 60, clock=FakeClock())

    assert limiter.check("a") is None
    assert limiter.check("a") is None
    assert limiter.check("a") == pytest.approx(60)


def test_slot_frees_after_the_window():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(1, 60, clock=clock)
    assert limiter.check("a") is None
    assert limiter.check("a") is not None

    clock.now = 61
    assert limiter.check("a") is None


def test_keys_are_limited_independently():
    limiter = SlidingWindowLimiter(1, 60, clock=FakeClock())
    assert limiter.check("a") is None
    assert limiter.check("b") is None


@pytest.mark.anyio
async def test_dependency_raises_429_with_retry_after(monkeypatch):
    monkeypatch.setattr(settings, "rate_limiting_enabled", True)
    dependency = rate_limit(1, 60)
    request = SimpleNamespace(client=SimpleNamespace(host="1.2.3.4"))

    await dependency(request)
    with pytest.raises(HTTPException) as exc:
        await dependency(request)

    assert exc.value.status_code == 429
    assert "Retry-After" in exc.value.headers