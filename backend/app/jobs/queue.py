import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.models import Job, JobStage, JobStatus


async def enqueue_indexing_pipeline(
    db: AsyncSession, repository_id: uuid.UUID
) -> list[Job]:
    """
    Create the full set of job rows for a repository's indexing pipeline,
    one per stage, all starting in 'pending' status.

    The worker picks these up and advances them in order: clone -> parse
    -> embed -> summarize. Creating all 4 rows upfront (rather than one
    at a time) lets the frontend show full pipeline progress immediately,
    even before the worker has started on stage 1.
    """
    stages = [JobStage.CLONE, JobStage.PARSE, JobStage.EMBED, JobStage.SUMMARIZE]

    jobs = [
        Job(repository_id=repository_id, stage=stage, status=JobStatus.PENDING)
        for stage in stages
    ]

    db.add_all(jobs)
    await db.commit()

    for job in jobs:
        await db.refresh(job)

    return jobs