import shutil
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer
from app.core.config import settings
from app.core.db import get_db
from app.repo.git_service import CloneError
from app.repo.schemas import (
    FileContentOut,
    FileOut,
    LanguageStatOut,
    ModuleStatOut,
    RepositoryCreate,
    RepositoryListItemOut,
    RepositoryOut,
    RepositoryStatsOut,
    StageStatOut,
)
from app.repo.stats_service import get_repository_stats
from app.repo.validators import InvalidRepoUrlError
from app.search.qdrant_client import delete_repository_vectors
from app.core.rate_limit import rate_limit
from app.core.security import require_admin
from app.core.visitor import get_visitor_id
from app.repo.models import File, Repository, VisitorRepository
from app.repo.service import (
    RepositoryAlreadyExistsError,
    RepositoryLimitReachedError,
    VisitorLimitReachedError,
    import_repository,
    purge_repository,
    remove_repository_from_visitor,
)
router = APIRouter(prefix="/repositories", tags=["repositories"])

@router.post(
    "",
    response_model=RepositoryOut,
    status_code=201,
    dependencies=[
        Depends(rate_limit(5, 3600)),
        Depends(rate_limit(20, 3600, scope="global")),
    ],
)
async def create_repository(
    payload: RepositoryCreate,
    visitor_id: UUID = Depends(get_visitor_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        repository = await import_repository(db, payload.github_url, visitor_id)
    except InvalidRepoUrlError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RepositoryAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except (VisitorLimitReachedError, RepositoryLimitReachedError) as e:
        raise HTTPException(status_code=429, detail=str(e)) from e
    except CloneError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return repository


@router.get("", response_model=list[RepositoryListItemOut])
async def list_repositories(
    visitor_id: UUID = Depends(get_visitor_id), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(
            Repository.id,
            Repository.github_url,
            Repository.name,
            Repository.status,
            Repository.primary_language,
            Repository.imported_at,
            func.count(File.id).label("file_count"),
        )
        .join(VisitorRepository, VisitorRepository.repository_id == Repository.id)
        .outerjoin(File, File.repository_id == Repository.id)
        .where(VisitorRepository.visitor_id == visitor_id)
        .group_by(Repository.id)
        .order_by(Repository.imported_at.desc())
    )
    return [
        RepositoryListItemOut(
            id=row.id,
            github_url=row.github_url,
            name=row.name,
            status=row.status,
            primary_language=row.primary_language,
            imported_at=row.imported_at,
            file_count=row.file_count,
        )
        for row in result.all()
    ]


@router.delete(
    "/{repository_id}", status_code=204, dependencies=[Depends(require_admin)]
)
async def delete_repository(repository_id: UUID, db: AsyncSession = Depends(get_db)):
    """Admin hard delete: removes the repository for every visitor."""
    if not await purge_repository(db, repository_id):
        raise HTTPException(status_code=404, detail="Repository not found")


@router.delete("/{repository_id}/membership", status_code=204)
async def remove_repository_from_my_list(
    repository_id: UUID,
    visitor_id: UUID = Depends(get_visitor_id),
    db: AsyncSession = Depends(get_db),
):
    """Removes a repository from the calling visitor's list. Its data is
    deleted only when no other visitor still has it."""
    removed = await remove_repository_from_visitor(db, repository_id, visitor_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Repository not found in your list")


@router.get("/{repository_id}", response_model=RepositoryOut)
async def get_repository(repository_id: UUID, db: AsyncSession = Depends(get_db)):
    repository = await db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repository


@router.get("/{repository_id}/files", response_model=list[FileOut])
async def list_files(repository_id: UUID, db: AsyncSession = Depends(get_db)):
    repository = await db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    result = await db.scalars(
        select(File).where(File.repository_id == repository_id).order_by(File.path)
    )
    return result.all()


@router.get("/{repository_id}/files/{file_path:path}", response_model=FileContentOut)
async def get_file_content(
    repository_id: UUID, file_path: str, db: AsyncSession = Depends(get_db)
):
    repository = await db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Prefer content stored in Postgres: the on-disk clone doesn't survive
    # restarts on free hosting.
    file_record = await db.scalar(
        select(File)
        .options(undefer(File.content))
        .where(File.repository_id == repository_id, File.path == file_path)
    )
    if file_record is not None and file_record.content is not None:
        return FileContentOut(path=file_path, content=file_record.content)

    # Fallback to the clone on disk (repos indexed before content was stored).
    repo_root = (Path(settings.repo_storage_dir) / str(repository_id)).resolve()
    resolved = (repo_root / file_path).resolve()

    # Prevent path traversal (e.g. "../../etc/passwd").
    if not resolved.is_relative_to(repo_root):
        raise HTTPException(status_code=400, detail="Invalid file path")

    if not resolved.is_file():
        if file_record is not None:
            raise HTTPException(
                status_code=404,
                detail="File content isn't available (binary or too large to display)",
            )
        raise HTTPException(status_code=404, detail="File not found")

    try:
        content = resolved.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Could not read file: {e}") from e

    return FileContentOut(path=file_path, content=content)

@router.get("/{repository_id}/stats", response_model=RepositoryStatsOut)
async def get_repository_statistics(repository_id: UUID, db: AsyncSession = Depends(get_db)):
    repository = await db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    stats = await get_repository_stats(db, repository_id)
    return RepositoryStatsOut(
        file_count=stats.file_count,
        total_size_bytes=stats.total_size_bytes,
        symbol_count=stats.symbol_count,
        edge_count=stats.edge_count,
        chunk_count=stats.chunk_count,
        vector_dim=stats.vector_dim,
        languages=[LanguageStatOut(language=l.language, percentage=l.percentage) for l in stats.languages],
        stages=[StageStatOut(stage=s.stage, status=s.status, detail=s.detail) for s in stats.stages],
        modules=[
            ModuleStatOut(
                path=m.path,
                symbol_count=m.symbol_count,
                in_degree=m.in_degree,
                out_degree=m.out_degree,
                start_line=m.start_line,
                end_line=m.end_line,
            )
            for m in stats.modules
        ],
        completed_at=stats.completed_at,
        duration_seconds=stats.duration_seconds,
    )