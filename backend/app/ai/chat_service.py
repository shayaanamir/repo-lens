import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.errors import AIUnavailableError
from app.ai.gemini_client import GeminiError, generate_content
from app.ai.prompts import SourceRef, build_chat_prompt
from app.ai.retrieval import MAX_CHAT_CHUNKS, retrieve_chat_context
from app.repo.models import Repository

logger = logging.getLogger(__name__)


class ChatResult:
    def __init__(self, answer: str, sources: list[SourceRef]):
        self.answer = answer
        self.sources = sources


async def answer_chat_question(
    db: AsyncSession, repository: Repository, question: str
) -> ChatResult:
    chunks = await retrieve_chat_context(repository.id, question, limit=MAX_CHAT_CHUNKS)
    prompt = build_chat_prompt(repository.name, question, chunks)

    try:
        answer = await generate_content(prompt)
    except GeminiError as e:
        logger.warning("Chat generation failed for repository %s: %s", repository.id, e)
        raise AIUnavailableError(str(e)) from e

    sources = [SourceRef(path=c.path, start_line=c.start_line, end_line=c.end_line) for c in chunks]
    return ChatResult(answer=answer, sources=sources)