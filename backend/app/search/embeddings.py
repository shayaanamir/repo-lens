import asyncio
import logging
import threading

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# General-purpose, CPU-friendly embedding model — zero rate limits, no
# daily quota, fully offline. Not code-specialized; a reasonable
# zero-budget default per ARCHITECTURE.md §17. Swappable for a
# code-specific model later (e.g. jinaai/jina-embeddings-v2-base-code)
# without touching chunker.py, service.py, qdrant_client.py, or the
# router — they only depend on embed_texts()'s signature.
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Must match qdrant_client.py's VECTOR_SIZE — changing the model
# requires recreating the Qdrant collection if this changes.
OUTPUT_DIMENSIONALITY = 384

_model: SentenceTransformer | None = None
_model_lock = threading.Lock()


class EmbeddingError(Exception):
    """Raised when local embedding generation fails unexpectedly."""
    pass


class EmbeddingTaskType:
    """Kept for interface compatibility with callers (and with the
    prior Gemini-based client) — all-MiniLM-L6-v2 is symmetric (no
    distinct query/document mode), so both currently behave the same.
    A future code-specific model that *does* distinguish them can use
    these without any caller-side changes."""
    DOCUMENT = "document"
    CODE_QUERY = "query"


def _get_model() -> SentenceTransformer:
    """Lazily loads and caches the embedding model — loaded once per
    process (first call pays the load cost; every call after is free).
    Double-checked locking since this can be reached from concurrent
    requests once both search and embed-stage code paths are live."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                logger.info("Loading embedding model %s...", EMBEDDING_MODEL_NAME)
                _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
                logger.info("Embedding model loaded")
    return _model


async def embed_texts(texts: list[str], task_type: str) -> list[list[float]]:
    """
    Embeds a list of texts locally via sentence-transformers. No
    network calls, no rate limits. `task_type` is accepted for
    interface compatibility with callers but unused by this symmetric
    model.

    Model load and inference are both synchronous/CPU-bound, so both
    run in a thread to avoid blocking the event loop — mirrors the
    to_thread pattern already used for clone/parse's blocking work.
    """
    if not texts:
        return []

    model = await asyncio.to_thread(_get_model)
    embeddings = await asyncio.to_thread(
        model.encode,
        texts,
        normalize_embeddings=True,  # match prior Gemini path's manual normalization
        show_progress_bar=False,
    )
    return embeddings.tolist()