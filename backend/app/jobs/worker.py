import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_factory
from app.jobs.models import Job, JobStage, JobStatus

logger = logging.getLogger(__name__)

STAGE_ORDER = [JobStage.CLONE, JobStage.PARSE, JobStage.EMBED, JobStage.SUMMARIZE]

POLL_INTERVAL_SECONDS = 5


async def run_worker_loop() -> None:
    """
    Long-running background loop. Polls for the next runnable job every
    POLL_INTERVAL_SECONDS and processes it. Runs as an asyncio task
    started on FastAPI startup, stopped on shutdown.
    """
    logger.info("Job worker loop starting")
    while True:
        try:
            processed = await _process_next_job()
            if not processed:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            logger.info("Job worker loop stopping")
            raise
        except Exception:
            logger.exception("Unexpected error in worker loop, continuing")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def _process_next_job() -> bool:
    """
    Finds the next runnable job (earliest stage, in PENDING status, whose
    repository has no earlier stage still incomplete) and runs it.
    Returns True if a job was found and processed, False if queue is empty.
    """
    async with async_session_factory() as db:
        job = await _find_next_runnable_job(db)
        if job is None:
            return False

        await _run_stage(db, job)
        return True


async def _find_next_runnable_job(db: AsyncSession) -> Job | None:
    """
    Returns the first PENDING job (in stage order) across all repositories
    whose prior stage (if any) has COMPLETED. Returns None if nothing is
    runnable right now.
    """
    for stage in STAGE_ORDER:
        result = await db.execute(
            select(Job)
            .where(Job.stage == stage, Job.status == JobStatus.PENDING)
            .order_by(Job.created_at)
        )
        candidates = result.scalars().all()

        for job in candidates:
            if stage == STAGE_ORDER[0]:
                # clone has no prerequisite
                return job

            prior_stage = STAGE_ORDER[STAGE_ORDER.index(stage) - 1]
            prior_completed = await _stage_is_completed(
                db, job.repository_id, prior_stage
            )
            if prior_completed:
                return job

    return None


async def _stage_is_completed(db: AsyncSession, repository_id, stage: JobStage) -> bool:
    result = await db.execute(
        select(Job.status).where(
            Job.repository_id == repository_id, Job.stage == stage
        )
    )
    status = result.scalar_one_or_none()
    return status == JobStatus.COMPLETED


async def _run_stage(db: AsyncSession, job: Job) -> None:
    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(timezone.utc)
    await db.commit()

    try:
        await _execute_stage(job)
    except Exception as exc:
        logger.exception(
            "Job %s (stage=%s, repo=%s) failed", job.id, job.stage, job.repository_id
        )
        job.status = JobStatus.FAILED
        job.error = str(exc)
        job.completed_at = datetime.now(timezone.utc)
        await db.commit()
        return

    job.status = JobStatus.COMPLETED
    job.completed_at = datetime.now(timezone.utc)
    await db.commit()


async def _execute_stage(job: Job) -> None:
    """
    Dispatches to the actual stage implementation. Filled in as each
    module (Repo, Analysis, Search, AI) becomes available in later phases.
    """
    if job.stage == JobStage.CLONE:
        raise NotImplementedError("clone stage not yet wired up")
    elif job.stage == JobStage.PARSE:
        raise NotImplementedError("parse stage not yet wired up")
    elif job.stage == JobStage.EMBED:
        raise NotImplementedError("embed stage not yet wired up")
    elif job.stage == JobStage.SUMMARIZE:
        raise NotImplementedError("summarize stage not yet wired up")