import asyncio
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.import_extractor import extract_imports
from app.analysis.import_resolver import resolve_import
from app.analysis.models import ImportEdge, Symbol
from app.analysis.symbol_extractor import extract_symbols
from app.analysis.treesitter_parser import SUPPORTED_EXTENSIONS
from app.repo.metadata_service import scan_files
from app.repo.models import File

logger = logging.getLogger(__name__)


@dataclass
class _SymbolRecord:
    file_id: uuid.UUID
    name: str
    kind: str
    start_line: int
    end_line: int


@dataclass
class _EdgeCandidate:
    source_file_id: uuid.UUID
    target_path: str  # resolved repo-relative path; turned into target_file_id by the caller


@dataclass
class _AnalysisResult:
    symbols: list[_SymbolRecord]
    edges: list[_EdgeCandidate]


async def analyze_repository(db: AsyncSession, repository_id: uuid.UUID, repo_dir: Path) -> None:
    """
    Runs static analysis (symbol extraction + import resolution) over
    every file belonging to `repository_id`, and persists the results
    as Symbol and ImportEdge rows.

    Safe to re-run: existing symbols/edges for this repository are
    cleared first, so retries don't create duplicates.
    """
    result = await db.execute(
        select(File.id, File.path).where(File.repository_id == repository_id)
    )
    files = result.all()  # list of (id, path)

    if not files:
        # File records are written here, as part of the parse stage,
        # rather than by the clone stage — matches ARCHITECTURE.md §5's
        # data flow (the Analysis Module "writes files, symbols, imports").
        # If this repo already has File rows (e.g. imported via the
        # synchronous POST /repositories path), this is a no-op — we
        # only backfill when nothing exists yet.
        await _scan_and_persist_files(db, repository_id, repo_dir)
        result = await db.execute(
            select(File.id, File.path).where(File.repository_id == repository_id)
        )
        files = result.all()

    if not files:
        logger.info("No files found on disk for repository %s", repository_id)
        return

    analysis = await _analyze_files_sync(repo_dir, files)

    path_to_file_id = {path: file_id for file_id, path in files}

    # Clear prior results for this repo before inserting fresh ones —
    # makes this stage safe to retry without duplicating rows.
    await db.execute(delete(Symbol).where(Symbol.repository_id == repository_id))
    await db.execute(delete(ImportEdge).where(ImportEdge.repository_id == repository_id))

    for sym in analysis.symbols:
        db.add(
            Symbol(
                file_id=sym.file_id,
                repository_id=repository_id,
                name=sym.name,
                kind=sym.kind,
                start_line=sym.start_line,
                end_line=sym.end_line,
            )
        )

    # Dedupe edges: multiple import lines in one file pointing at the
    # same target file would otherwise create redundant edges.
    seen_edges: set[tuple[uuid.UUID, uuid.UUID]] = set()
    edges_created = 0
    for edge in analysis.edges:
        target_file_id = path_to_file_id.get(edge.target_path)
        if target_file_id is None:
            continue  # resolved path isn't a known file (shouldn't happen, but defensive)
        if target_file_id == edge.source_file_id:
            continue  # skip self-imports (e.g. a package's __init__.py importing itself)

        key = (edge.source_file_id, target_file_id)
        if key in seen_edges:
            continue
        seen_edges.add(key)

        db.add(
            ImportEdge(
                repository_id=repository_id,
                source_file_id=edge.source_file_id,
                target_file_id=target_file_id,
            )
        )
        edges_created += 1

    await db.commit()

    logger.info(
        "Analyzed repository %s: %d symbols, %d import edges across %d files",
        repository_id, len(analysis.symbols), edges_created, len(files),
    )


async def _scan_and_persist_files(db: AsyncSession, repository_id: uuid.UUID, repo_dir: Path) -> None:
    """Walks the cloned repo on disk and writes File rows for it. Used
    when the parse stage runs against a repository that has no File
    records yet (the normal case for repos indexed via the background
    job pipeline, where clone only writes to disk)."""
    file_records = await asyncio.to_thread(scan_files, repo_dir)
    for rec in file_records:
        db.add(
            File(
                repository_id=repository_id,
                path=rec["path"],
                language=rec["language"],
                size=rec["size"],
                content_hash=rec["content_hash"],
            )
        )
    await db.commit()


async def _analyze_files_sync(repo_dir: Path, files: list) -> _AnalysisResult:
    """Wraps the CPU-bound parse/extract work in a thread so it doesn't
    block the event loop, mirroring the clone stage's use of
    asyncio.to_thread for blocking work."""
    return await asyncio.to_thread(_run_analysis, repo_dir, files)


def _run_analysis(repo_dir: Path, files: list) -> _AnalysisResult:
    known_paths = {path for _, path in files}

    symbols: list[_SymbolRecord] = []
    edges: list[_EdgeCandidate] = []

    for file_id, rel_path in files:
        extension = Path(rel_path).suffix
        if extension.lower() not in SUPPORTED_EXTENSIONS:
            continue  # unsupported file type — skip gracefully, don't fail the stage

        disk_path = repo_dir / rel_path
        try:
            source = disk_path.read_bytes()
        except OSError:
            logger.warning("Could not read %s during analysis, skipping", disk_path)
            continue

        for sym in extract_symbols(source, extension):
            symbols.append(
                _SymbolRecord(
                    file_id=file_id,
                    name=sym.name,
                    kind=sym.kind,
                    start_line=sym.start_line,
                    end_line=sym.end_line,
                )
            )

        for imp in extract_imports(source, extension):
            resolved_path = resolve_import(rel_path, imp, known_paths)
            if resolved_path is not None:
                edges.append(_EdgeCandidate(source_file_id=file_id, target_path=resolved_path))

    return _AnalysisResult(symbols=symbols, edges=edges)