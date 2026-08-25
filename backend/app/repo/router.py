from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.repo.git_service import CloneError
from app.repo.models import File, Repository
from app.repo.schemas import (
    FileContentOut,
    FileOut,
    LanguageStatOut,
    ModuleStatOut,
    RepositoryCreate,
    RepositoryOut,
    RepositoryStatsOut,
    StageStatOut,
)
from app.repo.service import RepositoryAlreadyExistsError, import_repository
from app.repo.stats_service import get_repository_stats
from app.repo.validators import InvalidRepoUrlError

router = APIRouter(prefix="/repositories", tags=["repositories"])


@router.post("", response_model=RepositoryOut, status_code=201)
async def create_repository(
    payload: RepositoryCreate, db: AsyncSession = Depends(get_db)
):
    try:
        repository = await import_repository(db, payload.github_url)
    except InvalidRepoUrlError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RepositoryAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except CloneError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return repository


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

    disk_path = Path(settings.repo_storage_dir) / str(repository_id) / file_path

    # Prevent path traversal (e.g. "../../etc/passwd") from escaping
    # the repo's own clone directory.
    repo_root = (Path(settings.repo_storage_dir) / str(repository_id)).resolve()
    resolved = disk_path.resolve()
    if not resolved.is_relative_to(repo_root):
        raise HTTPException(status_code=400, detail="Invalid file path")

    if not resolved.is_file():
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