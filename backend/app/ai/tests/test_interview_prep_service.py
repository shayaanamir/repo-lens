import uuid
from unittest.mock import AsyncMock

import pytest

from app.ai import interview_prep_service as interview_prep_service_module
from app.ai.errors import AIUnavailableError
from app.ai.gemini_client import GeminiError
from app.repo.models import Repository
from app.repo.stats_service import ModuleStat


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _fake_repo(**overrides) -> Repository:
    defaults = dict(
        id=uuid.uuid4(),
        github_url="https://github.com/octocat/Hello-World",
        name="Hello-World",
        readme_content="A demo repo.",
        primary_language="Python",
    )
    defaults.update(overrides)
    return Repository(**defaults)


VALID_JSON_RESPONSE = """{
  "pitch": "A demo project.",
  "talking_points": ["Point one", "Point two"],
  "questions": [
    {"question": "Why X?", "answer": "Because Y."}
  ]
}"""


@pytest.mark.anyio
async def test_generates_result_from_valid_json(monkeypatch):
    monkeypatch.setattr(interview_prep_service_module, "get_top_modules", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        interview_prep_service_module, "generate_content", AsyncMock(return_value=VALID_JSON_RESPONSE)
    )

    result = await interview_prep_service_module.generate_interview_prep(db=None, repository=_fake_repo())

    assert result.pitch == "A demo project."
    assert result.talking_points == ["Point one", "Point two"]
    assert len(result.questions) == 1
    assert result.questions[0].question == "Why X?"
    assert result.questions[0].answer == "Because Y."


@pytest.mark.anyio
async def test_gemini_failure_raises_ai_unavailable(monkeypatch):
    monkeypatch.setattr(interview_prep_service_module, "get_top_modules", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        interview_prep_service_module, "generate_content", AsyncMock(side_effect=GeminiError("down"))
    )

    with pytest.raises(AIUnavailableError):
        await interview_prep_service_module.generate_interview_prep(db=None, repository=_fake_repo())


@pytest.mark.anyio
async def test_malformed_json_raises_ai_unavailable(monkeypatch):
    monkeypatch.setattr(interview_prep_service_module, "get_top_modules", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        interview_prep_service_module, "generate_content", AsyncMock(return_value="not json at all")
    )

    with pytest.raises(AIUnavailableError):
        await interview_prep_service_module.generate_interview_prep(db=None, repository=_fake_repo())


@pytest.mark.anyio
async def test_missing_expected_key_raises_ai_unavailable(monkeypatch):
    monkeypatch.setattr(interview_prep_service_module, "get_top_modules", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        interview_prep_service_module,
        "generate_content",
        AsyncMock(return_value='{"pitch": "hi", "talking_points": []}'),  # missing "questions"
    )

    with pytest.raises(AIUnavailableError):
        await interview_prep_service_module.generate_interview_prep(db=None, repository=_fake_repo())


@pytest.mark.anyio
async def test_strips_markdown_code_fences_before_parsing(monkeypatch):
    fenced = f"```json\n{VALID_JSON_RESPONSE}\n```"
    monkeypatch.setattr(interview_prep_service_module, "get_top_modules", AsyncMock(return_value=[]))
    monkeypatch.setattr(interview_prep_service_module, "generate_content", AsyncMock(return_value=fenced))

    result = await interview_prep_service_module.generate_interview_prep(db=None, repository=_fake_repo())

    assert result.pitch == "A demo project."


@pytest.mark.anyio
async def test_maps_top_modules_into_prompt(monkeypatch):
    modules = [
        ModuleStat(path="app/main.py", symbol_count=3, in_degree=1, out_degree=2, start_line=1, end_line=10),
    ]
    monkeypatch.setattr(interview_prep_service_module, "get_top_modules", AsyncMock(return_value=modules))

    captured = {}

    async def fake_generate_content(prompt, *args, **kwargs):
        captured["prompt"] = prompt
        return VALID_JSON_RESPONSE

    monkeypatch.setattr(interview_prep_service_module, "generate_content", fake_generate_content)

    await interview_prep_service_module.generate_interview_prep(db=None, repository=_fake_repo())

    assert "app/main.py" in captured["prompt"]


@pytest.mark.anyio
async def test_passes_user_context_into_prompt(monkeypatch):
    monkeypatch.setattr(interview_prep_service_module, "get_top_modules", AsyncMock(return_value=[]))

    captured = {}

    async def fake_generate_content(prompt, *args, **kwargs):
        captured["prompt"] = prompt
        return VALID_JSON_RESPONSE

    monkeypatch.setattr(interview_prep_service_module, "generate_content", fake_generate_content)

    await interview_prep_service_module.generate_interview_prep(
        db=None, repository=_fake_repo(), user_context="I debugged a nasty deadlock."
    )

    assert "I debugged a nasty deadlock." in captured["prompt"]



@pytest.mark.anyio
async def test_grounded_in_derived_from_top_modules(monkeypatch):
    modules = [
        ModuleStat(path="app/main.py", symbol_count=3, in_degree=1, out_degree=2, start_line=1, end_line=40),
        ModuleStat(path="app/utils.py", symbol_count=2, in_degree=2, out_degree=0, start_line=None, end_line=None),
    ]
    monkeypatch.setattr(interview_prep_service_module, "get_top_modules", AsyncMock(return_value=modules))
    monkeypatch.setattr(interview_prep_service_module, "generate_content", AsyncMock(return_value=VALID_JSON_RESPONSE))

    result = await interview_prep_service_module.generate_interview_prep(db=None, repository=_fake_repo())

    assert [(s.path, s.start_line, s.end_line) for s in result.grounded_in] == [
        ("app/main.py", 1, 40),
        ("app/utils.py", 1, 1),
    ]


@pytest.mark.anyio
async def test_grounded_in_capped_at_limit(monkeypatch):
    modules = [
        ModuleStat(path=f"app/m{i}.py", symbol_count=1, in_degree=0, out_degree=0, start_line=1, end_line=1)
        for i in range(5)
    ]
    monkeypatch.setattr(interview_prep_service_module, "get_top_modules", AsyncMock(return_value=modules))
    monkeypatch.setattr(interview_prep_service_module, "generate_content", AsyncMock(return_value=VALID_JSON_RESPONSE))

    result = await interview_prep_service_module.generate_interview_prep(db=None, repository=_fake_repo())

    assert len(result.grounded_in) == 3