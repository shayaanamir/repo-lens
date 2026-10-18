import shutil
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.jobs.queue import enqueue_indexing_pipeline
from app.repo.models import Repository, VisitorRepository
from app.repo.validators import validate_github_url
from app.search.qdrant_client import delete_repository_vectors


class RepositoryAlreadyExistsError(Exception):
    pass


class RepositoryLimitReachedError(Exception):
    """The deployment-wide cap on indexed repositories was hit."""
    pass


class VisitorLimitReachedError(Exception):
    """This visitor's own list is full."""
    pass


async def import_repository(
    db: AsyncSession, github_url: str, visitor_id: UUID, _retry: bool = True
) -> Repository:
    """
    Adds a repository to a visitor's list.

    - Already in their list: returned as-is (idempotent).
    - Already indexed for someone else: linked instantly, no re-indexing.
    - New: registered, linked, and handed to the background pipeline
      (clone -> parse -> embed -> summarize); returns immediately.
    """
    normalized_url = validate_github_url(github_url)  # raises InvalidRepoUrlError

    existing = await db.scalar(
        select(Repository).where(Repository.github_url == normalized_url)
    )

    if existing is not None:
        already_in_list = await db.scalar(
            select(VisitorRepository.repository_id).where(
                VisitorRepository.visitor_id == visitor_id,
                VisitorRepository.repository_id == existing.id,
            )
        )
        if already_in_list is not None:
            return existing

    if settings.max_repositories_per_visitor:
        in_list = await db.scalar(
            select(func.count())
            .select_from(VisitorRepository)
            .where(VisitorRepository.visitor_id == visitor_id)
        )
        if (in_list or 0) >= settings.max_repositories_per_visitor:
            raise VisitorLimitReachedError(
                f"You can keep up to {settings.max_repositories_per_visitor} "
                "repositories at a time. Remove one to add another."
            )

    if existing is not None:
        db.add(VisitorRepository(visitor_id=visitor_id, repository_id=existing.id))
        try:
            await db.commit()
        except IntegrityError as e:
            # e.g. a double-click inserted the same link twice
            await db.rollback()
            if _retry:
                return await import_repository(db, github_url, visitor_id, _retry=False)
            raise RepositoryAlreadyExistsError(
                f"Repository already imported: {normalized_url}"
            ) from e
        return existing

    if settings.max_repositories:
        total = await db.scalar(select(func.count(Repository.id)))
        if (total or 0) >= settings.max_repositories:
            raise RepositoryLimitReachedError(
                f"This demo is limited to {settings.max_repositories} indexed "
                "repositories. Please try again later."
            )

    repo_id = uuid4()
    name = normalized_url.rstrip("/").split("/")[-1]
    repository = Repository(id=repo_id, github_url=normalized_url, name=name)
    db.add(repository)

    try:
        await db.flush()  # raises IntegrityError if the same URL was just imported
        db.add(VisitorRepository(visitor_id=visitor_id, repository_id=repo_id))
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        if _retry:
            # Someone imported it a moment ago: second pass links to theirs.
            return await import_repository(db, github_url, visitor_id, _retry=False)
        raise RepositoryAlreadyExistsError(
            f"Repository already imported: {normalized_url}"
        ) from e

    await db.refresh(repository)
    await enqueue_indexing_pipeline(db, repo_id)
    return repository


async def purge_repository(db: AsyncSession, repository_id: UUID) -> bool:
    """Deletes a repository everywhere: Postgres row first (cascades to
    jobs, files, symbols, edges, links), then what the DB can't reach:
    Qdrant vectors and the clone on disk. Returns False if it didn't exist."""
    repository = await db.get(Repository, repository_id)
    if repository is None:
        return False

    await db.delete(repository)
    await db.commit()

    await delete_repository_vectors(repository_id)
    shutil.rmtree(Path(settings.repo_storage_dir) / str(repository_id), ignore_errors=True)
    return True


async def remove_repository_from_visitor(
    db: AsyncSession, repository_id: UUID, visitor_id: UUID
) -> bool:
    """Removes a repository from one visitor's list. If nobody else has it,
    its data is purged so storage stays bounded. Returns False if it
    wasn't in this visitor's list."""
    result = await db.execute(
        delete(VisitorRepository).where(
            VisitorRepository.visitor_id == visitor_id,
            VisitorRepository.repository_id == repository_id,
        )
    )
    if result.rowcount == 0:
        return False

    remaining = await db.scalar(
        select(func.count())
        .select_from(VisitorRepository)
        .where(VisitorRepository.repository_id == repository_id)
    )
    await db.commit()

    if not remaining:
        await purge_repository(db, repository_id)
    return True