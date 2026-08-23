import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.errors import AIUnavailableError
from app.ai.gemini_client import GeminiError, generate_content
from app.ai.prompts import ContextChunk, build_summary_prompt
from app.analysis.models import Symbol
from app.repo.models import File, Repository

logger = logging.getLogger(__name__)

# A large repo might have thousands of symbols — this just needs a
# representative sample for the prompt, not the whole codebase.
MAX_SUMMARY_SYMBOLS = 40


async def generate_repository_summary(db: AsyncSession, repository_id: uuid.UUID) -> str:
    """
    Generates a one-time, high-level repository summary from its README,
    primary language, and a sample of top-level symbols. Raises
    AIUnavailableError if Gemini can't be reached.
    """
    repository = await db.get(Repository, repository_id)
    if repository is None:
        raise ValueError(f"Repository {repository_id} not found")

    rows = (
        await db.execute(
            select(File.path, Symbol.name, Symbol.kind)
            .join(Symbol, Symbol.file_id == File.id)
            .where(Symbol.repository_id == repository_id, Symbol.kind.in_(("class", "function")))
            .limit(MAX_SUMMARY_SYMBOLS)
        )
    ).all()
    symbols = [
        ContextChunk(path=path, start_line=0, end_line=0, content="", symbol_name=name, symbol_kind=kind)
        for path, name, kind in rows
    ]

    prompt = build_summary_prompt(repository.name, repository.readme_content, repository.primary_language, symbols)

    try:
        return await generate_content(prompt)
    except GeminiError as e:
        logger.warning("Summary generation failed for repository %s: %s", repository_id, e)
        raise AIUnavailableError(str(e)) from e