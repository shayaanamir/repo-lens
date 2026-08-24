from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.queue import enqueue_indexing_pipeline
from app.repo.models import Repository
from app.repo.validators import validate_github_url


class RepositoryAlreadyExistsError(Exception):
    pass


async def import_repository(db: AsyncSession, github_url: str) -> Repository:
    """
    Validates and registers a new repository, then hands off to the
    background indexing pipeline (clone -> parse -> embed -> summarize)
    and returns immediately with status "pending".

    Actual cloning, metadata extraction, static analysis, embedding, and
    summarization all happen asynchronously via app.jobs.worker — see
    ARCHITECTURE.md §5 and §13. This function's only job now is to
    validate, register, and enqueue; it used to do the clone/scan work
    inline, which was Phase 1-era behavior that never got moved over
    once the Jobs Module (Phase 2) landed.
    """
    normalized_url = validate_github_url(github_url)  # raises InvalidRepoUrlError

    existing = await db.scalar(
        select(Repository).where(Repository.github_url == normalized_url)
    )
    if existing:
        raise RepositoryAlreadyExistsError(
            f"Repository already imported: {normalized_url}"
        )

    repo_id = uuid4()
    name = normalized_url.rstrip("/").split("/")[-1]

    repository = Repository(
        id=repo_id,
        github_url=normalized_url,
        name=name,
    )
    db.add(repository)

    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise RepositoryAlreadyExistsError(
            f"Repository already imported: {normalized_url}"
        ) from e

    await db.refresh(repository)

    await enqueue_indexing_pipeline(db, repo_id)

    return repository