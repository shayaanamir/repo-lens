# backend/scripts/retry_job.py
import asyncio
import sys
import uuid

from sqlalchemy import select

from app.core.db import async_session_factory
from app.jobs.models import Job, JobStatus
from app.repo.models import Repository  # noqa: F401 — registers Job.repository's mapper target
from app.analysis.models import Symbol, ImportEdge  # noqa: F401


async def main(repository_id: str, stage: str):
    async with async_session_factory() as db:
        result = await db.execute(
            select(Job).where(
                Job.repository_id == uuid.UUID(repository_id),
                Job.stage == stage,
            )
        )
        job = result.scalar_one_or_none()
        if job is None:
            print(f"No {stage} job found for repository {repository_id}")
            return

        job.status = JobStatus.PENDING
        job.error = None
        job.started_at = None
        job.completed_at = None
        await db.commit()
        print(f"Reset {stage} job {job.id} to pending")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m scripts.retry_job <repository_id> <stage>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2]))