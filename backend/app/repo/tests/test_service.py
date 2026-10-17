from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.repo import service as service_module
from app.repo.service import RepositoryLimitReachedError, import_repository


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_import_blocked_when_repository_cap_reached(monkeypatch):
    monkeypatch.setattr(settings, "max_repositories", 3)
    db = MagicMock()
    db.scalar = AsyncMock(side_effect=[None, 3])  # not a duplicate; 3 already exist
    db.add = MagicMock()

    with pytest.raises(RepositoryLimitReachedError):
        await import_repository(db, "https://github.com/octocat/Hello-World")

    db.add.assert_not_called()


@pytest.mark.anyio
async def test_import_allowed_when_cap_disabled(monkeypatch):
    monkeypatch.setattr(settings, "max_repositories", 0)
    monkeypatch.setattr(service_module, "enqueue_indexing_pipeline", AsyncMock())
    db = MagicMock()
    db.scalar = AsyncMock(return_value=None)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    repo = await import_repository(db, "https://github.com/octocat/Hello-World")

    assert repo.name == "Hello-World"
    db.add.assert_called_once()