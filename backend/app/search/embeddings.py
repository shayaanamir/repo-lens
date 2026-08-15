import logging
from dataclasses import dataclass
from math import sqrt

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
EMBEDDING_MODEL = "gemini-embedding-001"

# 768 dims: ~25% the storage of the 3072 default with ~0.3% quality loss
# per Google's own MTEB comparison — the right zero-budget tradeoff for
# a self-hosted Qdrant instance. See ARCHITECTURE.md §17.
OUTPUT_DIMENSIONALITY = 768

# gemini-embedding-001 only pre-normalizes the full 3072-dim output;
# any truncated dimensionality (768, 1536...) must be normalized by the
# caller or cosine similarity in Qdrant will be silently wrong.
_NEEDS_MANUAL_NORMALIZATION = OUTPUT_DIMENSIONALITY != 3072

# Empirically-safe request batch size for batchEmbedContents; keeps a
# single HTTP call well under Gemini's per-request payload/token limits
# even for large files with many symbol-level chunks.
MAX_BATCH_SIZE = 50

MAX_RETRIES = 5
INITIAL_BACKOFF_SECONDS = 2.0
REQUEST_TIMEOUT_SECONDS = 30.0


class EmbeddingError(Exception):
    """Raised when the Gemini embedding API call ultimately fails
    (after retries) or returns a malformed response."""
    pass


@dataclass
class EmbeddingTaskType:
    """Gemini's asymmetric-retrieval task types. Using the right one for
    each side of a search (document vs. query) measurably improves
    retrieval quality over a generic embedding call."""
    DOCUMENT = "RETRIEVAL_DOCUMENT"       # code chunks written to Qdrant
    CODE_QUERY = "CODE_RETRIEVAL_QUERY"    # natural-language search queries


async def embed_texts(texts: list[str], task_type: str) -> list[list[float]]:
    """
    Embeds a list of texts via Gemini's batchEmbedContents endpoint,
    returning one normalized vector per input text, in the same order.

    Batches internally (MAX_BATCH_SIZE per HTTP call) and retries with
    exponential backoff on 429/5xx — Gemini's free tier is prone to
    transient rate-limit errors under any real indexing load.
    """
    if not texts:
        return []

    all_embeddings: list[list[float]] = []
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        for start in range(0, len(texts), MAX_BATCH_SIZE):
            batch = texts[start : start + MAX_BATCH_SIZE]
            embeddings = await _embed_batch(client, batch, task_type)
            all_embeddings.extend(embeddings)

    return all_embeddings


async def _embed_batch(
    client: httpx.AsyncClient, batch: list[str], task_type: str
) -> list[list[float]]:
    url = f"{GEMINI_API_BASE}/models/{EMBEDDING_MODEL}:batchEmbedContents"
    payload = {
        "requests": [
            {
                "model": f"models/{EMBEDDING_MODEL}",
                "content": {"parts": [{"text": text}]},
                "taskType": task_type,
                "outputDimensionality": OUTPUT_DIMENSIONALITY,
            }
            for text in batch
        ]
    }

    last_error: Exception | None = None
    backoff = INITIAL_BACKOFF_SECONDS

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = await client.post(
                url,
                params={"key": settings.gemini_api_key},
                json=payload,
            )
        except httpx.RequestError as exc:
            last_error = exc
        else:
            if response.status_code == 200:
                data = response.json()
                try:
                    values = [e["values"] for e in data["embeddings"]]
                except (KeyError, TypeError) as exc:
                    raise EmbeddingError(
                        f"Unexpected response shape from Gemini embeddings API: {data}"
                    ) from exc

                if len(values) != len(batch):
                    raise EmbeddingError(
                        f"Expected {len(batch)} embeddings, got {len(values)}"
                    )

                if _NEEDS_MANUAL_NORMALIZATION:
                    values = [_normalize(v) for v in values]

                return values

            if response.status_code == 429 or response.status_code >= 500:
                # Transient — rate limit or server-side issue. Worth retrying.
                last_error = EmbeddingError(
                    f"Gemini embeddings API returned {response.status_code}: {response.text}"
                )
            else:
                # Non-transient (bad request, auth failure, etc.) — retrying
                # won't help, fail immediately with the real error.
                raise EmbeddingError(
                    f"Gemini embeddings API returned {response.status_code}: {response.text}"
                )

        if attempt < MAX_RETRIES:
            logger.warning(
                "Embedding batch attempt %d/%d failed (%s), retrying in %.1fs",
                attempt, MAX_RETRIES, last_error, backoff,
            )
            await _sleep(backoff)
            backoff *= 2

    raise EmbeddingError(
        f"Gemini embeddings API failed after {MAX_RETRIES} attempts: {last_error}"
    )


def _normalize(vector: list[float]) -> list[float]:
    magnitude = sqrt(sum(v * v for v in vector))
    if magnitude == 0:
        return vector
    return [v / magnitude for v in vector]


async def _sleep(seconds: float) -> None:
    import asyncio
    await asyncio.sleep(seconds)