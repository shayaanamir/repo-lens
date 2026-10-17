import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def _disable_rate_limiting(monkeypatch):
    monkeypatch.setattr(settings, "rate_limiting_enabled", False)