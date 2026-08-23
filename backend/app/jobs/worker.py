import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_factory
from app.jobs.models import Job, JobStage, JobStatus

from pathlib import Path

from app.core.config import settings
from app.repo.git_service import clone_repository, CloneError, CloneTimeoutError
from app.repo.models import Repository
from app.analysis.service import analyze_repository
from app.analysis.service import analyze_repository
from app.search.service import embed_repository
from app.ai.errors import AIUnavailableError
from app.ai.summary_service import generate_repository_summary

logger = logging.getLogger(__name__)

STAGE_ORDER = [JobStage.CLONE, JobStage.PARSE, JobStage.EMBED, JobStage.SUMMARIZE]

POLL_INTERVAL_SECONDS = 5


MAX_RETRIES = 3
RETRYABLE_EXCEPTIONS = (CloneTimeoutError,)


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
        is_retryable = isinstance(exc, RETRYABLE_EXCEPTIONS)
        can_retry = is_retryable and job.retry_count < MAX_RETRIES

        if can_retry:
            job.retry_count += 1
            job.status = JobStatus.PENDING
            job.error = str(exc)
            job.started_at = None
            logger.warning(
                "Job %s (stage=%s) failed transiently (attempt %d/%d), will retry: %s",
                job.id, job.stage, job.retry_count, MAX_RETRIES, exc,
            )
        else:
            job.status = JobStatus.FAILED
            job.error = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            logger.exception(
                "Job %s (stage=%s, repo=%s) failed permanently",
                job.id, job.stage, job.repository_id,
            )
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
        await _run_clone_stage(job)
    elif job.stage == JobStage.PARSE:
        await _run_parse_stage(job)
    elif job.stage == JobStage.EMBED:
        await _run_embed_stage(job)
    elif job.stage == JobStage.SUMMARIZE:
        await _run_summarize_stage(job)


async def _run_clone_stage(job: Job) -> None:
    """
    Clones the job's repository into a deterministic, repository_id-keyed
    directory under settings.repo_storage_dir. Later stages (parse) can
    recompute this same path from repository_id alone, so we don't need
    to persist the clone path anywhere.
    """
    dest_dir = Path(settings.repo_storage_dir) / str(job.repository_id)

    async with async_session_factory() as db:
        repo = await db.get(Repository, job.repository_id)
        if repo is None:
            raise RuntimeError(f"Repository {job.repository_id} not found")
        github_url = repo.github_url

    try:
        cloned = await asyncio.to_thread(
            clone_repository, github_url, dest_dir
        )
    except CloneError as exc:
        # Let this propagate — _run_stage's try/except will catch it,
        # mark the job FAILED, and store str(exc) as job.error.
        raise

    logger.info(
        "Cloned repository %s (%d bytes) to %s",
        job.repository_id, cloned.size_bytes, cloned.path,
    )

async def _run_parse_stage(job: Job) -> None:
    """
    Runs static analysis (Tree-sitter symbol extraction + import
    resolution) over the repository's already-cloned files on disk,
    and persists symbols/import edges to Postgres.

    Reuses the same deterministic, repository_id-keyed directory the
    clone stage wrote to — no need to look anything up.
    """
    repo_dir = Path(settings.repo_storage_dir) / str(job.repository_id)

    async with async_session_factory() as db:
        await analyze_repository(db, job.repository_id, repo_dir)

async def _run_embed_stage(job: Job) -> None:
    """
    Chunks + embeds the repository's already-analyzed files and writes
    vectors to Qdrant. Reuses the same deterministic repository_id-keyed
    directory the clone/parse stages already worked against.
    """
    repo_dir = Path(settings.repo_storage_dir) / str(job.repository_id)

    async with async_session_factory() as db:
        await embed_repository(db, job.repository_id, repo_dir)


async def _run_summarize_stage(job: Job) -> None:
    """
    Generates a one-time repository summary via the AI Module and marks
    the repository ready. A Gemini failure here is non-fatal to the
    pipeline (PROJECT.md §6.2, 'AI is an enhancement'): the summarize
    job itself still ends up FAILED so it's visible in job status, but
    the repository still becomes browsable/searchable without a summary.
    """
    async with async_session_factory() as db:
        repo = await db.get(Repository, job.repository_id)
        if repo is None:
            raise RuntimeError(f"Repository {job.repository_id} not found")

        try:
            repo.summary = await generate_repository_summary(db, job.repository_id)
        except AIUnavailableError:
            repo.status = "ready"
            await db.commit()
            raise  # let _run_stage record the job itself as FAILED

        repo.status = "ready"
        await db.commit()