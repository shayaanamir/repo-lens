import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.ai import router as router_module
from app.ai.chat_service import ChatResult
from app.ai.errors import AIUnavailableError
from app.ai.explain_service import ExplainResult, FileNotFoundForExplainError
from app.ai.prompts import SourceRef
from app.core.db import get_db
from app.main import app
from app.repo.models import Repository
from app.ai.interview_prep_service import InterviewPrepResult, QAPair

@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def _fake_repo() -> Repository:
    return Repository(id=uuid.uuid4(), github_url="https://github.com/octocat/Hello-World", name="Hello-World")


def _override_db(repo: Repository | None):
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=repo)

    async def _fake_get_db():
        yield mock_session
    app.dependency_overrides[get_db] = _fake_get_db


# ---------------------------------------------------------------------
# /chat
# ---------------------------------------------------------------------

@pytest.mark.anyio
async def test_chat_repository_not_found_returns_404(client):
    _override_db(None)

    response = await client.post(f"/repositories/{uuid.uuid4()}/chat", json={"question": "q"})

    assert response.status_code == 404


@pytest.mark.anyio
async def test_chat_success_returns_answer_and_sources(client, monkeypatch):
    repo = _fake_repo()
    _override_db(repo)

    fake_result = ChatResult(answer="It works like this.", sources=[SourceRef(path="main.py", start_line=1, end_line=3)])
    monkeypatch.setattr(router_module, "answer_chat_question", AsyncMock(return_value=fake_result))

    response = await client.post(f"/repositories/{repo.id}/chat", json={"question": "How does it work?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "It works like this."
    assert body["sources"] == [{"path": "main.py", "start_line": 1, "end_line": 3}]


@pytest.mark.anyio
async def test_chat_ai_unavailable_returns_503_not_500(client, monkeypatch):
    repo = _fake_repo()
    _override_db(repo)

    monkeypatch.setattr(router_module, "answer_chat_question", AsyncMock(side_effect=AIUnavailableError("rate limited")))

    response = await client.post(f"/repositories/{repo.id}/chat", json={"question": "q"})

    assert response.status_code == 503


@pytest.mark.anyio
async def test_chat_empty_question_returns_422(client):
    repo = _fake_repo()
    _override_db(repo)

    response = await client.post(f"/repositories/{repo.id}/chat", json={"question": ""})

    assert response.status_code == 422


# ---------------------------------------------------------------------
# /files/{path}/explain
# ---------------------------------------------------------------------

@pytest.mark.anyio
async def test_explain_repository_not_found_returns_404(client):
    _override_db(None)

    response = await client.post(f"/repositories/{uuid.uuid4()}/files/main.py/explain")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_explain_missing_file_returns_404(client, monkeypatch):
    repo = _fake_repo()
    _override_db(repo)

    monkeypatch.setattr(router_module, "explain_file", AsyncMock(side_effect=FileNotFoundForExplainError("nope.py")))

    response = await client.post(f"/repositories/{repo.id}/files/nope.py/explain")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_explain_success_returns_explanation_and_sources(client, monkeypatch):
    repo = _fake_repo()
    _override_db(repo)

    fake_result = ExplainResult(explanation="This file does X.", sources=[SourceRef(path="main.py", start_line=1, end_line=10)])
    monkeypatch.setattr(router_module, "explain_file", AsyncMock(return_value=fake_result))

    response = await client.post(f"/repositories/{repo.id}/files/main.py/explain")

    assert response.status_code == 200
    body = response.json()
    assert body["explanation"] == "This file does X."
    assert body["sources"] == [{"path": "main.py", "start_line": 1, "end_line": 10}]


@pytest.mark.anyio
async def test_explain_ai_unavailable_returns_503(client, monkeypatch):
    repo = _fake_repo()
    _override_db(repo)

    monkeypatch.setattr(router_module, "explain_file", AsyncMock(side_effect=AIUnavailableError("down")))

    response = await client.post(f"/repositories/{repo.id}/files/main.py/explain")

    assert response.status_code == 503


# ---------------------------------------------------------------------
# /interview-prep
# ---------------------------------------------------------------------

@pytest.mark.anyio
async def test_interview_prep_repository_not_found_returns_404(client):
    _override_db(None)

    response = await client.post(f"/repositories/{uuid.uuid4()}/interview-prep", json={})

    assert response.status_code == 404


@pytest.mark.anyio
async def test_interview_prep_success_returns_structured_result(client, monkeypatch):
    repo = _fake_repo()
    _override_db(repo)

    fake_result = InterviewPrepResult(
        pitch="A demo project.",
        talking_points=["Point one", "Point two"],
        questions=[QAPair(question="Why X?", answer="Because Y.")],
    )
    monkeypatch.setattr(
        router_module, "generate_interview_prep", AsyncMock(return_value=fake_result)
    )

    response = await client.post(f"/repositories/{repo.id}/interview-prep", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["pitch"] == "A demo project."
    assert body["talking_points"] == ["Point one", "Point two"]
    assert body["questions"] == [{"question": "Why X?", "answer": "Because Y."}]


@pytest.mark.anyio
async def test_interview_prep_passes_context_through(client, monkeypatch):
    repo = _fake_repo()
    _override_db(repo)

    fake_result = InterviewPrepResult(pitch="p", talking_points=[], questions=[])
    mock_generate = AsyncMock(return_value=fake_result)
    monkeypatch.setattr(router_module, "generate_interview_prep", mock_generate)

    await client.post(
        f"/repositories/{repo.id}/interview-prep",
        json={"context": "I debugged a nasty deadlock."},
    )

    _, call_args, _ = mock_generate.mock_calls[0]
    assert call_args[2] == "I debugged a nasty deadlock."


@pytest.mark.anyio
async def test_interview_prep_omitted_context_defaults_to_none(client, monkeypatch):
    repo = _fake_repo()
    _override_db(repo)

    fake_result = InterviewPrepResult(pitch="p", talking_points=[], questions=[])
    mock_generate = AsyncMock(return_value=fake_result)
    monkeypatch.setattr(router_module, "generate_interview_prep", mock_generate)

    response = await client.post(f"/repositories/{repo.id}/interview-prep", json={})

    assert response.status_code == 200
    _, call_args, _ = mock_generate.mock_calls[0]
    assert call_args[2] is None


@pytest.mark.anyio
async def test_interview_prep_ai_unavailable_returns_503(client, monkeypatch):
    repo = _fake_repo()
    _override_db(repo)

    monkeypatch.setattr(
        router_module,
        "generate_interview_prep",
        AsyncMock(side_effect=AIUnavailableError("rate limited")),
    )

    response = await client.post(f"/repositories/{repo.id}/interview-prep", json={})

    assert response.status_code == 503

@pytest.mark.anyio
async def test_interview_prep_includes_grounded_in_sources(client, monkeypatch):
    repo = _fake_repo()
    _override_db(repo)

    fake_result = InterviewPrepResult(
        pitch="p", talking_points=[], questions=[],
        grounded_in=[SourceRef(path="app/main.py", start_line=1, end_line=40)],
    )
    monkeypatch.setattr(router_module, "generate_interview_prep", AsyncMock(return_value=fake_result))

    response = await client.post(f"/repositories/{repo.id}/interview-prep", json={})

    assert response.json()["grounded_in"] == [{"path": "app/main.py", "start_line": 1, "end_line": 40}]