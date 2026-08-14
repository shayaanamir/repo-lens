import asyncio
import hashlib
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repo.git_service import clone_repository, CloneError
from app.repo.models import File, Repository
from app.repo.validators import InvalidRepoUrlError, validate_github_url
from app.repo.metadata_service import extract_metadata, scan_files

class RepositoryAlreadyExistsError(Exception):
    pass


async def import_repository(db: AsyncSession, github_url: str) -> Repository:
    """
    Synchronous end-to-end import: validate -> clone -> extract metadata
    -> scan files -> persist. Runs inline within the HTTP request for now;
    Phase 2 will move the clone/extract/scan work into a background job.
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
    dest_dir = Path(settings.repo_storage_dir) / str(repo_id)

    # Cloning and disk-walking are blocking (I/O + subprocess) calls.
    # asyncio.to_thread runs them in a worker thread so they don't block
    # the event loop other requests are relying on.
    cloned = await asyncio.to_thread(clone_repository, normalized_url, dest_dir)
    metadata = await asyncio.to_thread(extract_metadata, cloned.path)
    file_records = await asyncio.to_thread(scan_files, cloned.path)

    name = normalized_url.rstrip("/").split("/")[-1]

    repository = Repository(
        id=repo_id,
        github_url=normalized_url,
        name=name,
        status="ready",  # sync for now; Phase 2 introduces pending/indexing states
        primary_language=metadata.primary_language,
        readme_content=metadata.readme_content,
    )
    db.add(repository)

    for rec in file_records:
        db.add(
            File(
                repository_id=repo_id,
                path=rec["path"],
                language=rec["language"],
                size=rec["size"],
                content_hash=rec["content_hash"],
            )
        )

    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise RepositoryAlreadyExistsError(
            f"Repository already imported: {normalized_url}"
        ) from e

    await db.refresh(repository)
    return repository
