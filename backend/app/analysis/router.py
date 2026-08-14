import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.graph_service import build_dependency_graph
from app.analysis.schemas import DependencyGraphOut
from app.core.db import get_db
from app.repo.models import Repository

router = APIRouter(prefix="/repositories", tags=["analysis"])


@router.get("/{repository_id}/graph", response_model=DependencyGraphOut)
async def get_dependency_graph(
    repository_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> DependencyGraphOut:
    repository = await db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    graph = await build_dependency_graph(db, repository_id)

    return DependencyGraphOut(
        nodes=[
            {"id": n.id, "label": n.label, "language": n.language} for n in graph.nodes
        ],
        edges=[
            {"id": e.id, "source": e.source, "target": e.target} for e in graph.edges
        ],
    )