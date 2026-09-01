import json
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.errors import AIUnavailableError
from app.ai.gemini_client import GeminiError, generate_content
from app.ai.prompts import ModuleSummary, SourceRef, build_interview_prep_prompt
from app.repo.models import Repository
from app.repo.stats_service import get_top_modules

logger = logging.getLogger(__name__)

GROUNDED_IN_LIMIT = 3

class QAPair:
    def __init__(self, question: str, answer: str):
        self.question = question
        self.answer = answer


class InterviewPrepResult:
    def __init__(self, pitch: str, talking_points: list[str], questions: list[QAPair]):
        self.pitch = pitch
        self.talking_points = talking_points
        self.questions = questions


async def generate_interview_prep(
    db: AsyncSession, repository: Repository, user_context: str | None = None
) -> InterviewPrepResult:
    """
    Builds interview-prep material for a repository: an elevator pitch,
    ordered architecture talking points, and likely Q&A — grounded in
    the repo's README, primary language, and most-referenced modules
    (the same ranking the dashboard's "most referenced modules" table
    uses). `user_context` is optional free text from the candidate
    about hard problems they solved, woven into the questions if given.
    """
    modules = await get_top_modules(db, repository.id)
    module_summaries = [
        ModuleSummary(
            path=m.path,
            symbol_count=m.symbol_count,
            in_degree=m.in_degree,
            out_degree=m.out_degree,
        )
        for m in modules
    ]

    prompt = build_interview_prep_prompt(
        repository.name,
        repository.readme_content,
        repository.primary_language,
        module_summaries,
        user_context,
    )

    try:
        raw = await generate_content(prompt)
    except GeminiError as e:
        logger.warning(
            "Interview prep generation failed for repository %s: %s", repository.id, e
        )
        raise AIUnavailableError(str(e)) from e

    return _parse_response(raw, repository.id)


def _parse_response(raw: str, repository_id: uuid.UUID) -> InterviewPrepResult:
    cleaned = _strip_code_fences(raw)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning(
            "Interview prep response for repository %s wasn't valid JSON: %s", repository_id, e
        )
        raise AIUnavailableError("AI returned an unexpected response format") from e

    try:
        pitch = data["pitch"]
        talking_points = list(data["talking_points"])
        questions = [
            QAPair(question=q["question"], answer=q["answer"]) for q in data["questions"]
        ]
    except (KeyError, TypeError) as e:
        logger.warning(
            "Interview prep response for repository %s had unexpected shape: %s", repository_id, e
        )
        raise AIUnavailableError("AI returned an unexpected response format") from e

    return InterviewPrepResult(pitch=pitch, talking_points=talking_points, questions=questions)


def _strip_code_fences(text: str) -> str:
    """Gemini sometimes wraps JSON in ```json ... ``` despite the prompt
    saying not to — strip that defensively rather than failing the
    whole request over formatting."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


class InterviewPrepResult:
    def __init__(
        self,
        pitch: str,
        talking_points: list[str],
        questions: list[QAPair],
        grounded_in: list[SourceRef] | None = None,
    ):
        self.pitch = pitch
        self.talking_points = talking_points
        self.questions = questions
        self.grounded_in = grounded_in or []


async def generate_interview_prep(
    db: AsyncSession, repository: Repository, user_context: str | None = None
) -> InterviewPrepResult:
    modules = await get_top_modules(db, repository.id)
    module_summaries = [
        ModuleSummary(
            path=m.path, symbol_count=m.symbol_count, in_degree=m.in_degree, out_degree=m.out_degree
        )
        for m in modules
    ]
    grounded_in = [
        SourceRef(path=m.path, start_line=m.start_line or 1, end_line=m.end_line or 1)
        for m in modules[:GROUNDED_IN_LIMIT]
    ]

    prompt = build_interview_prep_prompt(
        repository.name, repository.readme_content, repository.primary_language,
        module_summaries, user_context,
    )

    try:
        raw = await generate_content(prompt)
    except GeminiError as e:
        logger.warning("Interview prep generation failed for repository %s: %s", repository.id, e)
        raise AIUnavailableError(str(e)) from e

    result = _parse_response(raw, repository.id)
    result.grounded_in = grounded_in
    return result