import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai import explain_service as explain_service_module
from app.ai.errors import AIUnavailableError
from app.ai.explain_service import FileNotFoundForExplainError
from app.ai.gemini_client import GeminiError
from app.repo.models import Repository


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _fake_repo() -> Repository:
    return Repository(id=uuid.uuid4(), github_url="https://github.com/octocat/Hello-World", name="Hello-World")


def _mock_db_no_symbols():
    db = MagicMock()
    db.scalar = AsyncMock(return_value=None)  # no matching File row
    return db


@pytest.mark.anyio
async def test_explain_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundForExplainError):
        await explain_service_module.explain_file(
            db=_mock_db_no_symbols(), repository=_fake_repo(), repo_dir=tmp_path, file_path="nope.py"
        )


@pytest.mark.anyio
async def test_explain_path_traversal_blocked(tmp_path):
    with pytest.raises(FileNotFoundForExplainError):
        await explain_service_module.explain_file(
            db=_mock_db_no_symbols(), repository=_fake_repo(), repo_dir=tmp_path,
            file_path="../../etc/passwd",
        )


@pytest.mark.anyio
async def test_explain_success_returns_full_file_as_single_source(tmp_path, monkeypatch):
    (tmp_path / "main.py").write_text("def foo():\n    return 1\n")

    monkeypatch.setattr(explain_service_module, "generate_content", AsyncMock(return_value="This file defines foo()."))

    result = await explain_service_module.explain_file(
        db=_mock_db_no_symbols(), repository=_fake_repo(), repo_dir=tmp_path, file_path="main.py"
    )

    assert result.explanation == "This file defines foo()."
    assert len(result.sources) == 1
    assert result.sources[0].path == "main.py"
    assert result.sources[0].start_line == 1
    assert result.sources[0].end_line == 2


@pytest.mark.anyio
async def test_explain_truncates_large_files(tmp_path, monkeypatch):
    huge_content = "x = 1\n" * 10_000  # well over MAX_EXPLAIN_FILE_CHARS
    (tmp_path / "big.py").write_text(huge_content)

    captured_prompt = {}

    async def fake_generate_content(prompt, *args, **kwargs):
        captured_prompt["value"] = prompt
        return "explanation"

    monkeypatch.setattr(explain_service_module, "generate_content", fake_generate_content)

    await explain_service_module.explain_file(
        db=_mock_db_no_symbols(), repository=_fake_repo(), repo_dir=tmp_path, file_path="big.py"
    )

    assert len(captured_prompt["value"]) < len(huge_content)


@pytest.mark.anyio
async def test_explain_gemini_failure_raises_ai_unavailable(tmp_path, monkeypatch):
    (tmp_path / "main.py").write_text("def foo(): pass\n")
    monkeypatch.setattr(explain_service_module, "generate_content", AsyncMock(side_effect=GeminiError("down")))

    with pytest.raises(AIUnavailableError):
        await explain_service_module.explain_file(
            db=_mock_db_no_symbols(), repository=_fake_repo(), repo_dir=tmp_path, file_path="main.py"
        )