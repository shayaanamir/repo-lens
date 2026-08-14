import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import get_db
from app.main import app
from app.analysis import graph_service as graph_service_module
from app.analysis.graph_service import DependencyGraph, GraphEdge, GraphNode
from app.repo.models import Repository


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def _override_db(mock_session):
    async def _fake_get_db():
        yield mock_session
    app.dependency_overrides[get_db] = _fake_get_db


@pytest.mark.anyio
async def test_get_graph_repository_not_found_returns_404(client):
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=None)
    _override_db(mock_session)

    response = await client.get(f"/repositories/{uuid.uuid4()}/graph")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_get_graph_returns_nodes_and_edges(client, monkeypatch):
    fake_repo = Repository(
        id=uuid.uuid4(),
        github_url="https://github.com/octocat/Hello-World",
        name="Hello-World",
    )

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=fake_repo)
    _override_db(mock_session)

    fake_graph = DependencyGraph(
        nodes=[GraphNode(id="a", label="main.py", language="Python")],
        edges=[GraphEdge(id="a-b", source="a", target="b")],
    )
    monkeypatch.setattr(
        graph_service_module, "build_dependency_graph", AsyncMock(return_value=fake_graph)
    )

    response = await client.get(f"/repositories/{fake_repo.id}/graph")

    assert response.status_code == 200
    body = response.json()
    assert body["nodes"] == [{"id": "a", "label": "main.py", "language": "Python"}]
    assert body["edges"] == [{"id": "a-b", "source": "a", "target": "b"}]


@pytest.mark.anyio
async def test_get_graph_empty_repository_returns_empty_lists(client, monkeypatch):
    fake_repo = Repository(
        id=uuid.uuid4(),
        github_url="https://github.com/octocat/Hello-World",
        name="Hello-World",
    )

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=fake_repo)
    _override_db(mock_session)

    monkeypatch.setattr(
        graph_service_module,
        "build_dependency_graph",
        AsyncMock(return_value=DependencyGraph(nodes=[], edges=[])),
    )

    response = await client.get(f"/repositories/{fake_repo.id}/graph")

    assert response.status_code == 200
    assert response.json() == {"nodes": [], "edges": []}