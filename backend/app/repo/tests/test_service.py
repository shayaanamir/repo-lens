import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.repo import service as service_module
from app.repo.models import Repository, VisitorRepository
from app.repo.service import (
    RepositoryLimitReachedError,
    VisitorLimitReachedError,
    import_repository,
    remove_repository_from_visitor,
)

URL = "https://github.com/octocat/Hello-World"
VISITOR = uuid.uuid4()


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _repo() -> Repository:
    return Repository(id=uuid.uuid4(), github_url=URL, name="Hello-World")


def _db(scalar_results: list) -> MagicMock:
    db = MagicMock()
    db.scalar = AsyncMock(side_effect=scalar_results)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.fixture(autouse=True)
def _no_caps(monkeypatch):
    monkeypatch.setattr(settings, "max_repositories", 0)
    monkeypatch.setattr(settings, "max_repositories_per_visitor", 0)


@pytest.mark.anyio
async def test_repo_already_in_visitors_list_is_returned_as_is(monkeypatch):
    existing = _repo()
    enqueue = AsyncMock()
    monkeypatch.setattr(service_module, "enqueue_indexing_pipeline", enqueue)
    db = _db([existing, existing.id])  # repo exists; link exists

    result = await import_repository(db, URL, VISITOR)

    assert result is existing
    db.add.assert_not_called()
    enqueue.assert_not_awaited()


@pytest.mark.anyio
async def test_existing_repo_is_linked_without_reindexing(monkeypatch):
    existing = _repo()
    enqueue = AsyncMock()
    monkeypatch.setattr(service_module, "enqueue_indexing_pipeline", enqueue)
    db = _db([existing, None])  # repo exists; this visitor has no link yet

    result = await import_repository(db, URL, VISITOR)

    assert result is existing
    link = db.add.call_args.args[0]
    assert isinstance(link, VisitorRepository)
    assert link.visitor_id == VISITOR and link.repository_id == existing.id
    db.commit.assert_awaited_once()
    enqueue.assert_not_awaited()


@pytest.mark.anyio
async def test_new_repository_is_created_linked_and_enqueued(monkeypatch):
    enqueue = AsyncMock()
    monkeypatch.setattr(service_module, "enqueue_indexing_pipeline", enqueue)
    db = _db([None])  # nothing exists yet

    repo = await import_repository(db, URL, VISITOR)

    assert repo.name == "Hello-World"
    added = [call.args[0] for call in db.add.call_args_list]
    assert isinstance(added[0], Repository)
    assert isinstance(added[1], VisitorRepository) and added[1].visitor_id == VISITOR
    enqueue.assert_awaited_once()


@pytest.mark.anyio
async def test_visitor_cap_blocks_import(monkeypatch):
    monkeypatch.setattr(settings, "max_repositories_per_visitor", 3)
    db = _db([None, 3])  # no existing repo; visitor already has 3

    with pytest.raises(VisitorLimitReachedError):
        await import_repository(db, URL, VISITOR)

    db.add.assert_not_called()


@pytest.mark.anyio
async def test_global_cap_blocks_new_repository_but_not_linking(monkeypatch):
    monkeypatch.setattr(settings, "max_repositories", 5)
    monkeypatch.setattr(service_module, "enqueue_indexing_pipeline", AsyncMock())

    # brand new repo while the deployment is full: blocked
    full_db = _db([None, 5])
    with pytest.raises(RepositoryLimitReachedError):
        await import_repository(full_db, URL, VISITOR)

    # repo that's already indexed: linking is still allowed
    existing = _repo()
    linking_db = _db([existing, None])
    assert await import_repository(linking_db, URL, VISITOR) is existing


@pytest.mark.anyio
async def test_remove_returns_false_when_not_in_visitors_list():
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(rowcount=0))

    assert await remove_repository_from_visitor(db, uuid.uuid4(), VISITOR) is False


@pytest.mark.anyio
async def test_removing_last_link_purges_the_repository(monkeypatch):
    purge = AsyncMock()
    monkeypatch.setattr(service_module, "purge_repository", purge)
    repo_id = uuid.uuid4()
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(rowcount=1))
    db.scalar = AsyncMock(return_value=0)  # nobody else has it
    db.commit = AsyncMock()

    assert await remove_repository_from_visitor(db, repo_id, VISITOR) is True
    purge.assert_awaited_once_with(db, repo_id)


@pytest.mark.anyio
async def test_removing_one_of_several_links_keeps_the_repository(monkeypatch):
    purge = AsyncMock()
    monkeypatch.setattr(service_module, "purge_repository", purge)
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(rowcount=1))
    db.scalar = AsyncMock(return_value=2)  # others still have it
    db.commit = AsyncMock()

    assert await remove_repository_from_visitor(db, uuid.uuid4(), VISITOR) is True
    purge.assert_not_awaited()