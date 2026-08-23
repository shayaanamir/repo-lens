import uuid
from unittest.mock import AsyncMock

import pytest

from app.ai import chat_service as chat_service_module
from app.ai.errors import AIUnavailableError
from app.ai.gemini_client import GeminiError
from app.ai.prompts import ContextChunk
from app.repo.models import Repository


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _fake_repo() -> Repository:
    return Repository(id=uuid.uuid4(), github_url="https://github.com/octocat/Hello-World", name="Hello-World")


@pytest.mark.anyio
async def test_answer_includes_sources_from_retrieved_chunks(monkeypatch):
    chunks = [
        ContextChunk(path="main.py", start_line=1, end_line=3, content="def foo(): pass"),
        ContextChunk(path="utils.py", start_line=5, end_line=8, content="def bar(): pass"),
    ]
    monkeypatch.setattr(chat_service_module, "retrieve_chat_context", AsyncMock(return_value=chunks))
    monkeypatch.setattr(chat_service_module, "generate_content", AsyncMock(return_value="Here's how it works."))

    result = await chat_service_module.answer_chat_question(db=None, repository=_fake_repo(), question="How does foo work?")

    assert result.answer == "Here's how it works."
    assert [ (s.path, s.start_line, s.end_line) for s in result.sources ] == [
        ("main.py", 1, 3), ("utils.py", 5, 8),
    ]


@pytest.mark.anyio
async def test_no_retrieved_chunks_still_returns_answer_with_no_sources(monkeypatch):
    monkeypatch.setattr(chat_service_module, "retrieve_chat_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(chat_service_module, "generate_content", AsyncMock(return_value="I don't have enough context."))

    result = await chat_service_module.answer_chat_question(db=None, repository=_fake_repo(), question="q")

    assert result.sources == []


@pytest.mark.anyio
async def test_gemini_failure_raises_ai_unavailable_not_gemini_error(monkeypatch):
    monkeypatch.setattr(chat_service_module, "retrieve_chat_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(chat_service_module, "generate_content", AsyncMock(side_effect=GeminiError("quota exceeded")))

    with pytest.raises(AIUnavailableError):
        await chat_service_module.answer_chat_question(db=None, repository=_fake_repo(), question="q")