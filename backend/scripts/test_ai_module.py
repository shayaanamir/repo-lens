# backend/scripts/test_ai_module.py
"""
Smoke-tests the AI Module (Phase 5) against an already-indexed repository:
asks a chat question, then requests a file explanation. Calls the service
functions directly (not over HTTP), same as check_jobs.py/retry_job.py,
so it can be run without the API server needing to be up separately.

Usage (cmd):
    python -m scripts.test_ai_module <repository_id>
    python -m scripts.test_ai_module <repository_id> "How does routing work?"
    python -m scripts.test_ai_module <repository_id> "How does routing work?" app/main.py

If no question is given, a generic default is used. If no file_path is
given, the first file on disk (by path) is picked automatically.

Requires GEMINI_API_KEY to be configured and today's Gemini quota not
yet exhausted — this makes real API calls.
"""
import asyncio
import sys
import uuid
from pathlib import Path

from sqlalchemy import select

from app.ai.chat_service import answer_chat_question
from app.ai.errors import AIUnavailableError
from app.ai.explain_service import FileNotFoundForExplainError, explain_file
from app.analysis.models import Symbol, ImportEdge  # noqa: F401
from app.core.config import settings
from app.core.db import async_session_factory
from app.jobs.models import Job  # noqa: F401
from app.repo.models import File, Repository

DEFAULT_QUESTION = "What does this repository do, at a high level?"


async def main(repository_id_str: str, question: str | None, file_path: str | None):
    repository_id = uuid.UUID(repository_id_str)

    async with async_session_factory() as db:
        repository = await db.get(Repository, repository_id)
        if repository is None:
            print(f"No repository found with id {repository_id}")
            return

        print(f"Repository: {repository.name} ({repository.github_url})")
        print(f"Status: {repository.status}")
        if repository.status != "ready":
            print(
                "Warning: repository isn't 'ready' yet — chat/explain may run "
                "against incomplete data. Check `python -m scripts.check_jobs`."
            )
        print()

        # ------------------------------------------------------------
        # Chat
        # ------------------------------------------------------------
        chat_question = question or DEFAULT_QUESTION
        print(f"--- CHAT ---")
        print(f"Q: {chat_question}")
        try:
            result = await answer_chat_question(db, repository, chat_question)
        except AIUnavailableError as e:
            print(f"AI unavailable: {e}")
        else:
            print(f"A: {result.answer}")
            print("Sources:")
            if not result.sources:
                print("  (none — no relevant chunks retrieved)")
            for s in result.sources:
                print(f"  - {s.path}:{s.start_line}-{s.end_line}")
        print()

        # ------------------------------------------------------------
        # Explain
        # ------------------------------------------------------------
        target_path = file_path or await _pick_default_file(db, repository_id)
        if target_path is None:
            print("--- EXPLAIN ---")
            print("No files found for this repository, skipping explain.")
            return

        repo_dir = Path(settings.repo_storage_dir) / str(repository_id)

        print(f"--- EXPLAIN ---")
        print(f"File: {target_path}")
        try:
            explain_result = await explain_file(db, repository, repo_dir, target_path)
        except FileNotFoundForExplainError:
            print(f"File not found on disk: {repo_dir / target_path}")
        except AIUnavailableError as e:
            print(f"AI unavailable: {e}")
        else:
            print(f"Explanation: {explain_result.explanation}")
            print("Sources:")
            for s in explain_result.sources:
                print(f"  - {s.path}:{s.start_line}-{s.end_line}")


async def _pick_default_file(db, repository_id: uuid.UUID) -> str | None:
    """Picks a reasonable default file to explain when none is given —
    prefers .py/.js/.ts files over config/markdown, falls back to
    whatever's first alphabetically."""
    result = await db.execute(
        select(File.path).where(File.repository_id == repository_id).order_by(File.path)
    )
    paths = [row[0] for row in result.all()]
    if not paths:
        return None

    code_extensions = (".py", ".js", ".ts", ".jsx", ".tsx")
    for path in paths:
        if path.endswith(code_extensions):
            return path

    return paths[0]


if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 4:
        print('Usage: python -m scripts.test_ai_module <repository_id> ["question"] [file_path]')
        sys.exit(1)

    repo_id_arg = sys.argv[1]
    question_arg = sys.argv[2] if len(sys.argv) >= 3 else None
    file_path_arg = sys.argv[3] if len(sys.argv) >= 4 else None

    asyncio.run(main(repo_id_arg, question_arg, file_path_arg))