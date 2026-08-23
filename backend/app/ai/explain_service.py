import logging
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.errors import AIUnavailableError
from app.ai.gemini_client import GeminiError, generate_content
from app.ai.prompts import ContextChunk, SourceRef, build_explain_prompt
from app.analysis.models import Symbol
from app.repo.models import File, Repository

logger = logging.getLogger(__name__)

# Caps how much of a file's content is sent to Gemini — bounds token
# usage for very large files (ARCHITECTURE.md §10).
MAX_EXPLAIN_FILE_CHARS = 12_000


class FileNotFoundForExplainError(Exception):
    pass


class ExplainResult:
    def __init__(self, explanation: str, sources: list[SourceRef]):
        self.explanation = explanation
        self.sources = sources


async def explain_file(
    db: AsyncSession, repository: Repository, repo_dir: Path, file_path: str
) -> ExplainResult:
    disk_path = _resolve_safe_path(repo_dir, file_path)
    if not disk_path.is_file():
        raise FileNotFoundForExplainError(file_path)

    content = disk_path.read_text(encoding="utf-8", errors="replace")
    truncated = content[:MAX_EXPLAIN_FILE_CHARS]

    file_id = await db.scalar(
        select(File.id).where(File.repository_id == repository.id, File.path == file_path)
    )

    symbols: list[ContextChunk] = []
    if file_id is not None:
        rows = (
            await db.execute(
                select(Symbol.name, Symbol.kind, Symbol.start_line, Symbol.end_line)
                .where(Symbol.file_id == file_id)
                .order_by(Symbol.start_line)
            )
        ).all()
        symbols = [
            ContextChunk(path=file_path, start_line=s, end_line=e, content="", symbol_name=n, symbol_kind=k)
            for n, k, s, e in rows
        ]

    prompt = build_explain_prompt(repository.name, file_path, truncated, symbols)

    try:
        explanation = await generate_content(prompt)
    except GeminiError as e:
        logger.warning("Explain generation failed for %s/%s: %s", repository.id, file_path, e)
        raise AIUnavailableError(str(e)) from e

    line_count = max(len(content.splitlines()), 1)
    sources = [SourceRef(path=file_path, start_line=1, end_line=line_count)]
    return ExplainResult(explanation=explanation, sources=sources)


def _resolve_safe_path(repo_dir: Path, file_path: str) -> Path:
    """Prevents path traversal — mirrors repo/router.py's get_file_content
    guard, duplicated here since that guard lives inline in a route
    handler rather than as a shared utility."""
    repo_root = repo_dir.resolve()
    candidate = (repo_dir / file_path).resolve()
    if not candidate.is_relative_to(repo_root):
        raise FileNotFoundForExplainError(file_path)
    return candidate