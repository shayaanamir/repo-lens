import uuid

from app.ai.prompts import ContextChunk
from app.search.embeddings import EmbeddingTaskType, embed_texts
from app.search.qdrant_client import search_chunks

# Caps how many retrieved chunks get sent to Gemini per chat question —
# bounds token usage (ARCHITECTURE.md §10) regardless of how many the
# vector search would otherwise return.
MAX_CHAT_CHUNKS = 8


async def retrieve_chat_context(
    repository_id: uuid.UUID, question: str, limit: int = MAX_CHAT_CHUNKS
) -> list[ContextChunk]:
    """Embeds the question and retrieves the top-K most relevant code
    chunks for it via Qdrant, scoped to this repository."""
    query_vector = (await embed_texts([question], task_type=EmbeddingTaskType.CODE_QUERY))[0]
    points = await search_chunks(repository_id, query_vector, limit=limit)

    return [
        ContextChunk(
            path=point.payload["path"],
            start_line=point.payload["start_line"],
            end_line=point.payload["end_line"],
            content=point.payload.get("content", ""),
            symbol_name=point.payload.get("symbol_name"),
            symbol_kind=point.payload.get("symbol_kind"),
        )
        for point in points
    ]