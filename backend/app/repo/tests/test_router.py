import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.db import get_db
from app.main import app
from app.repo import router as router_module
from app.repo.git_service import CloneError
from app.repo.models import File, Repository
from app.repo.service import RepositoryAlreadyExistsError
from app.repo.validators import InvalidRepoUrlError


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _sample_repository(**overrides) -> Repository:
    """Builds an unsaved Repository object with sensible defaults, so
    tests can override just the fields they care about."""
    defaults = dict(
        id=uuid.uuid4(),
        github_url="https://github.com/octocat/Hello-World",
        name="Hello-World",
        default_branch="main",
        status="ready",
        primary_language=None,
        readme_content="Hello World!\n",
        summary=None,
        imported_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return Repository(**defaults)


@pytest.fixture
async def client():
    """An HTTP client that talks directly to the FastAPI app in-process
    (no real network, no running server needed)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# POST /repositories
# ---------------------------------------------------------------------

@pytest.mark.anyio
async def test_create_repository_success(client, monkeypatch):
    fake_repo = _sample_repository()
    monkeypatch.setattr(
        router_module, "import_repository", AsyncMock(return_value=fake_repo)
    )

    response = await client.post(
        "/repositories", json={"github_url": "https://github.com/octocat/Hello-World"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["github_url"] == "https://github.com/octocat/Hello-World"
    assert body["status"] == "ready"


@pytest.mark.anyio
async def test_create_repository_invalid_url_returns_400(client, monkeypatch):
    monkeypatch.setattr(
        router_module,
        "import_repository",
        AsyncMock(side_effect=InvalidRepoUrlError("bad url")),
    )

    response = await client.post("/repositories", json={"github_url": "not-a-url"})

    assert response.status_code == 400


@pytest.mark.anyio
async def test_create_repository_duplicate_returns_409(client, monkeypatch):
    monkeypatch.setattr(
        router_module,
        "import_repository",
        AsyncMock(side_effect=RepositoryAlreadyExistsError("already imported")),
    )

    response = await client.post(
        "/repositories", json={"github_url": "https://github.com/octocat/Hello-World"}
    )

    assert response.status_code == 409


@pytest.mark.anyio
async def test_create_repository_clone_failure_returns_422(client, monkeypatch):
    monkeypatch.setattr(
        router_module,
        "import_repository",
        AsyncMock(side_effect=CloneError("git clone failed")),
    )

    response = await client.post(
        "/repositories", json={"github_url": "https://github.com/octocat/nonexistent"}
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------
# GET /repositories/{id}
# ---------------------------------------------------------------------

def _override_db(mock_session):
    """Swaps FastAPI's get_db dependency for one that yields our mock
    session instead of a real database connection."""
    async def _fake_get_db():
        yield mock_session
    app.dependency_overrides[get_db] = _fake_get_db


@pytest.mark.anyio
async def test_get_repository_not_found_returns_404(client):
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=None)
    _override_db(mock_session)

    response = await client.get(f"/repositories/{uuid.uuid4()}")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_get_repository_found_returns_200(client):
    fake_repo = _sample_repository()
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=fake_repo)
    _override_db(mock_session)

    response = await client.get(f"/repositories/{fake_repo.id}")

    assert response.status_code == 200
    assert response.json()["name"] == "Hello-World"


# ---------------------------------------------------------------------
# GET /repositories/{id}/files
# ---------------------------------------------------------------------

@pytest.mark.anyio
async def test_list_files_returns_file_tree(client):
    fake_repo = _sample_repository()
    fake_files = [
        File(id=uuid.uuid4(), repository_id=fake_repo.id, path="README", language=None, size=13),
        File(id=uuid.uuid4(), repository_id=fake_repo.id, path="main.py", language="Python", size=100),
    ]

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=fake_repo)

    scalars_result = MagicMock()
    scalars_result.all.return_value = fake_files
    mock_session.scalars = AsyncMock(return_value=scalars_result)

    _override_db(mock_session)

    response = await client.get(f"/repositories/{fake_repo.id}/files")

    assert response.status_code == 200
    paths = [f["path"] for f in response.json()]
    assert paths == ["README", "main.py"]


# ---------------------------------------------------------------------
# GET /repositories/{id}/files/{path}
# ---------------------------------------------------------------------

@pytest.mark.anyio
async def test_get_file_content_success(client, monkeypatch, tmp_path):
    fake_repo = _sample_repository()

    # Point repo storage at a temp dir and create a real file there,
    # since this endpoint reads directly from disk.
    monkeypatch.setattr(settings, "repo_storage_dir", str(tmp_path))
    repo_dir = Path(tmp_path) / str(fake_repo.id)
    repo_dir.mkdir(parents=True)
    (repo_dir / "README").write_text("Hello World!\n")

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=fake_repo)
    _override_db(mock_session)

    response = await client.get(f"/repositories/{fake_repo.id}/files/README")

    assert response.status_code == 200
    assert response.json()["content"] == "Hello World!\n"


@pytest.mark.anyio
async def test_get_file_content_path_traversal_blocked(client, monkeypatch, tmp_path):
    fake_repo = _sample_repository()
    monkeypatch.setattr(settings, "repo_storage_dir", str(tmp_path))
    (Path(tmp_path) / str(fake_repo.id)).mkdir(parents=True)

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=fake_repo)
    _override_db(mock_session)

    response = await client.get(
        f"/repositories/{fake_repo.id}/files/..%2F..%2F..%2Fetc%2Fpasswd"
    )

    assert response.status_code in (400, 404)


@pytest.mark.anyio
async def test_get_file_content_missing_file_returns_404(client, monkeypatch, tmp_path):
    fake_repo = _sample_repository()
    monkeypatch.setattr(settings, "repo_storage_dir", str(tmp_path))
    (Path(tmp_path) / str(fake_repo.id)).mkdir(parents=True)

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=fake_repo)
    _override_db(mock_session)

    response = await client.get(f"/repositories/{fake_repo.id}/files/nonexistent.txt")

    assert response.status_code == 404