import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.jobs.models import Job, JobStage
from app.jobs.schemas import JobListResponse, JobRead
from app.repo.models import Repository

router = APIRouter(prefix="/repositories", tags=["jobs"])

STAGE_ORDER = [JobStage.CLONE, JobStage.PARSE, JobStage.EMBED, JobStage.SUMMARIZE]


@router.get("/{repository_id}/jobs", response_model=JobListResponse)
async def get_repository_jobs(
    repository_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> JobListResponse:
    repo_result = await db.execute(
        select(Repository).where(Repository.id == repository_id)
    )
    if repo_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    jobs_result = await db.execute(
        select(Job).where(Job.repository_id == repository_id)
    )
    jobs = jobs_result.scalars().all()

    # Sort by pipeline order (clone -> parse -> embed -> summarize),
    # not insertion order, so the response always reads top-to-bottom
    # as the pipeline progresses, regardless of DB row order.
    jobs_sorted = sorted(jobs, key=lambda j: STAGE_ORDER.index(j.stage))

    return JobListResponse(
        repository_id=repository_id,
        jobs=[JobRead.model_validate(j) for j in jobs_sorted],
    )