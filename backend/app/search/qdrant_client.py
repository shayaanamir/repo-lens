import logging
import uuid

from qdrant_client import AsyncQdrantClient, models

from app.core.config import settings

logger = logging.getLogger(__name__)

VECTOR_SIZE = 384  # must match app/search/embeddings.py's OUTPUT_DIMENSIONALITY

_client: AsyncQdrantClient | None = None


def get_qdrant_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
            cloud_inference=settings.embedding_provider == "qdrant_cloud",
        )
    return _client


async def ensure_collection() -> None:
    """
    Creates the shared code-chunks collection if it doesn't already
    exist. Called once at app startup (main.py lifespan), so every
    request/job can assume the collection is present without checking.

    Safe to call repeatedly (e.g. across container restarts) — a no-op
    if the collection already exists.
    """
    client = get_qdrant_client()
    collection_name = settings.qdrant_collection_name

    exists = await client.collection_exists(collection_name)
    if exists:
        logger.info("Qdrant collection '%s' already exists", collection_name)
        return

    await client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(
            size=VECTOR_SIZE,
            distance=models.Distance.COSINE,
        ),
    )

    # Index repository_id so per-repo filtered search (and delete-before-
    # reindex) doesn't fall back to a full collection scan. Mirrors
    # ARCHITECTURE.md §15's "Qdrant queries are scoped by repository_id
    # payload filter" note.
    await client.create_payload_index(
        collection_name=collection_name,
        field_name="repository_id",
        field_schema=models.PayloadSchemaType.KEYWORD,
    )

    logger.info("Created Qdrant collection '%s' (size=%d, cosine)", collection_name, VECTOR_SIZE)


UPSERT_BATCH_SIZE = 64

async def upsert_chunk_vectors(
    repository_id: uuid.UUID,
    points: list[tuple[uuid.UUID, object, dict]],
) -> None:
    if not points:
        return

    client = get_qdrant_client()
    for start in range(0, len(points), UPSERT_BATCH_SIZE):
        batch = points[start : start + UPSERT_BATCH_SIZE]
        await client.upsert(
            collection_name=settings.qdrant_collection_name,
            points=[
                models.PointStruct(id=str(point_id), vector=vector, payload=payload)
                for point_id, vector, payload in batch
            ],
        )


async def delete_repository_vectors(repository_id: uuid.UUID) -> None:
    """Deletes all vectors for a repository — used before re-embedding
    on retry, so a partial prior run doesn't leave stale chunks behind
    (mirrors analysis/service.py's delete-before-insert pattern for
    Symbol/ImportEdge)."""
    client = get_qdrant_client()
    await client.delete(
        collection_name=settings.qdrant_collection_name,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="repository_id",
                        match=models.MatchValue(value=str(repository_id)),
                    )
                ]
            )
        ),
    )


async def count_repository_vectors(repository_id: uuid.UUID) -> int:
    """Returns the number of chunks indexed for a repository — used by
    the dashboard's 'extracted facts' stats, not on any hot path."""
    client = get_qdrant_client()
    result = await client.count(
        collection_name=settings.qdrant_collection_name,
        count_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="repository_id",
                    match=models.MatchValue(value=str(repository_id)),
                )
            ]
        ),
        exact=True,
    )
    return result.count


async def search_chunks(
    repository_id: uuid.UUID,
    query_vector: list[float],
    limit: int = 10,
) -> list[models.ScoredPoint]:
    """Nearest-neighbor search scoped to a single repository via payload
    filter — never searches across repos (ARCHITECTURE.md §15)."""
    client = get_qdrant_client()
    results = await client.query_points(
        collection_name=settings.qdrant_collection_name,
        query=query_vector,
        query_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="repository_id",
                    match=models.MatchValue(value=str(repository_id)),
                )
            ]
        ),
        limit=limit,
    )
    return results.points