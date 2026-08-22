import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.repo.models import Repository
from app.search.embeddings import EmbeddingTaskType, embed_texts
from app.search.qdrant_client import search_chunks
from app.search.schemas import SearchResponseOut, SearchResultOut

router = APIRouter(prefix="/repositories", tags=["search"])


@router.get("/{repository_id}/search", response_model=SearchResponseOut)
async def search_repository(
    repository_id: uuid.UUID,
    q: str = Query(..., min_length=1, description="Natural-language search query"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> SearchResponseOut:
    repository = await db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    query_vector = (await embed_texts([q], task_type=EmbeddingTaskType.CODE_QUERY))[0]

    points = await search_chunks(repository_id, query_vector, limit=limit)

    results = [
        SearchResultOut(
            file_id=point.payload["file_id"],
            path=point.payload["path"],
            start_line=point.payload["start_line"],
            end_line=point.payload["end_line"],
            symbol_name=point.payload.get("symbol_name"),
            symbol_kind=point.payload.get("symbol_kind"),
            score=point.score,
        )
        for point in points
    ]

    return SearchResponseOut(query=q, results=results)