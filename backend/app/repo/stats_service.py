import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.models import ImportEdge, Symbol
from app.jobs.models import Job, JobStage, JobStatus
from app.repo.models import File
from app.search.embeddings import OUTPUT_DIMENSIONALITY
from app.search.qdrant_client import count_repository_vectors

STAGE_ORDER = [JobStage.CLONE, JobStage.PARSE, JobStage.EMBED, JobStage.SUMMARIZE]
TOP_MODULES_LIMIT = 8


@dataclass
class StageStat:
    stage: str
    status: str
    detail: str | None


@dataclass
class LanguageStat:
    language: str
    percentage: float


@dataclass
class ModuleStat:
    path: str
    symbol_count: int
    in_degree: int
    out_degree: int
    start_line: int | None
    end_line: int | None


@dataclass
class RepositoryStats:
    file_count: int
    total_size_bytes: int
    symbol_count: int
    edge_count: int
    chunk_count: int
    vector_dim: int
    languages: list[LanguageStat]
    stages: list[StageStat]
    modules: list[ModuleStat]
    completed_at: datetime | None
    duration_seconds: float | None


def _format_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.1f} MB"


async def get_repository_stats(db: AsyncSession, repository_id: uuid.UUID) -> RepositoryStats:
    file_count, total_size = (
        await db.execute(
            select(func.count(File.id), func.coalesce(func.sum(File.size), 0))
            .where(File.repository_id == repository_id)
        )
    ).one()

    symbol_count = (
        await db.scalar(select(func.count(Symbol.id)).where(Symbol.repository_id == repository_id))
        or 0
    )
    edge_count = (
        await db.scalar(select(func.count(ImportEdge.id)).where(ImportEdge.repository_id == repository_id))
        or 0
    )

    chunk_count = await count_repository_vectors(repository_id)

    lang_rows = (
        await db.execute(
            select(File.language, func.count(File.id))
            .where(File.repository_id == repository_id, File.language.is_not(None))
            .group_by(File.language)
        )
    ).all()
    total_lang_files = sum(count for _, count in lang_rows) or 1
    languages = sorted(
        (
            LanguageStat(language=lang, percentage=round(count / total_lang_files * 100, 1))
            for lang, count in lang_rows
        ),
        key=lambda l: l.percentage,
        reverse=True,
    )

    modules = await _compute_top_modules(db, repository_id)

    jobs_result = await db.execute(select(Job).where(Job.repository_id == repository_id))
    jobs_by_stage = {j.stage: j for j in jobs_result.scalars().all()}

    stage_details = {
        JobStage.CLONE: f"{file_count} files · {_format_size(total_size or 0)}",
        JobStage.PARSE: f"{symbol_count} symbols · {edge_count} edges",
        JobStage.EMBED: f"{chunk_count} chunks · {OUTPUT_DIMENSIONALITY}-dim",
        JobStage.SUMMARIZE: "Gemini · 1 call",
    }

    stages = [
        StageStat(
            stage=stage.value,
            status=str(jobs_by_stage[stage].status) if stage in jobs_by_stage else "pending",
            detail=(
                stage_details.get(stage)
                if stage in jobs_by_stage and str(jobs_by_stage[stage].status) == JobStatus.COMPLETED.value
                else None
            ),
        )
        for stage in STAGE_ORDER
    ]

    clone_job = jobs_by_stage.get(JobStage.CLONE)
    summarize_job = jobs_by_stage.get(JobStage.SUMMARIZE)
    completed_at = (
        summarize_job.completed_at
        if summarize_job and str(summarize_job.status) == JobStatus.COMPLETED.value
        else None
    )
    duration_seconds = None
    if completed_at and clone_job and clone_job.started_at:
        duration_seconds = (completed_at - clone_job.started_at).total_seconds()

    return RepositoryStats(
        file_count=file_count or 0,
        total_size_bytes=total_size or 0,
        symbol_count=symbol_count,
        edge_count=edge_count,
        chunk_count=chunk_count,
        vector_dim=OUTPUT_DIMENSIONALITY,
        languages=languages,
        stages=stages,
        modules=modules,
        completed_at=completed_at,
        duration_seconds=duration_seconds,
    )


async def get_top_modules(db: AsyncSession, repository_id: uuid.UUID) -> list[ModuleStat]:
    """Public entry point for callers outside this module (e.g. the AI
    Module's interview-prep service) that want the same 'most referenced
    modules' ranking the dashboard uses, without reaching into the
    private helper below."""
    return await _compute_top_modules(db, repository_id)


async def _compute_top_modules(db: AsyncSession, repository_id: uuid.UUID) -> list[ModuleStat]:
    """Ranks files by total import-edge degree (in + out) — the same
    'most referenced' signal the frontend graph page already uses,
    computed here so the dashboard doesn't have to fetch the full graph
    just to show a top-8 table."""
    edge_rows = (
        await db.execute(
            select(ImportEdge.source_file_id, ImportEdge.target_file_id)
            .where(ImportEdge.repository_id == repository_id)
        )
    ).all()

    if not edge_rows:
        return []

    out_degree: dict[uuid.UUID, int] = {}
    in_degree: dict[uuid.UUID, int] = {}
    for source_id, target_id in edge_rows:
        out_degree[source_id] = out_degree.get(source_id, 0) + 1
        in_degree[target_id] = in_degree.get(target_id, 0) + 1

    all_ids = set(out_degree) | set(in_degree)
    ranked_ids = sorted(
        all_ids,
        key=lambda fid: in_degree.get(fid, 0) + out_degree.get(fid, 0),
        reverse=True,
    )[:TOP_MODULES_LIMIT]

    if not ranked_ids:
        return []

    files_result = await db.execute(select(File.id, File.path).where(File.id.in_(ranked_ids)))
    path_by_id = {fid: path for fid, path in files_result.all()}

    symbol_rows = (
        await db.execute(
            select(
                Symbol.file_id,
                func.count(Symbol.id),
                func.min(Symbol.start_line),
                func.max(Symbol.end_line),
            )
            .where(Symbol.file_id.in_(ranked_ids))
            .group_by(Symbol.file_id)
        )
    ).all()
    symbol_info = {fid: (count, start, end) for fid, count, start, end in symbol_rows}

    modules = []
    for fid in ranked_ids:
        path = path_by_id.get(fid)
        if path is None:
            continue
        count, start, end = symbol_info.get(fid, (0, None, None))
        modules.append(
            ModuleStat(
                path=path,
                symbol_count=count,
                in_degree=in_degree.get(fid, 0),
                out_degree=out_degree.get(fid, 0),
                start_line=start,
                end_line=end,
            )
        )

    return modules