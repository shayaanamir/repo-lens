import asyncio
import logging
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.models import Symbol
from app.repo.models import File
from app.search.chunker import ChunkRecord, chunk_file
from app.search.embeddings import EmbeddingTaskType, embed_texts
from app.search.qdrant_client import delete_repository_vectors, upsert_chunk_vectors

logger = logging.getLogger(__name__)


async def embed_repository(db: AsyncSession, repository_id: uuid.UUID, repo_dir: Path) -> None:
    """
    Chunks + embeds every analyzable file in a repository and writes the
    resulting vectors to Qdrant. Runs as the `embed` job stage, after
    `parse` has populated File/Symbol rows.

    Safe to re-run: existing vectors for this repository are deleted
    first (mirrors analysis/service.py's delete-before-insert pattern),
    so retries don't leave stale or duplicate chunks behind.
    """
    files_result = await db.execute(
        select(File.id, File.path).where(File.repository_id == repository_id)
    )
    files = files_result.all()  # list of (id, path)

    if not files:
        logger.info("No files found for repository %s, skipping embed stage", repository_id)
        return

    symbols_result = await db.execute(
        select(Symbol.file_id, Symbol.name, Symbol.kind, Symbol.start_line, Symbol.end_line)
        .where(Symbol.repository_id == repository_id)
    )
    symbols_by_file: dict[uuid.UUID, list] = {}
    for file_id, name, kind, start_line, end_line in symbols_result.all():
        symbols_by_file.setdefault(file_id, []).append(
            _SymbolTuple(name=name, kind=kind, start_line=start_line, end_line=end_line)
        )

    chunks = await asyncio.to_thread(_chunk_all_files, repo_dir, files, symbols_by_file)

    if not chunks:
        logger.info("No chunks produced for repository %s", repository_id)
        await delete_repository_vectors(repository_id)
        return

    logger.info("Embedding %d chunks for repository %s", len(chunks), repository_id)

    vectors = await embed_texts(
        [c.content for c in chunks], task_type=EmbeddingTaskType.DOCUMENT
    )

    points = [
        (
            uuid.uuid4(),
            vector,
            {
                "repository_id": str(repository_id),
                "file_id": str(chunk.file_id),
                "path": chunk.path,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "symbol_name": chunk.symbol_name,
                "symbol_kind": chunk.symbol_kind,
                "content": chunk.content,
            },
        )
        for chunk, vector in zip(chunks, vectors)
    ]

    # Clear any prior vectors for this repo only after successfully
    # embedding the new ones — avoids leaving a repo with zero search
    # results if the Gemini call fails partway through a retry.
    await delete_repository_vectors(repository_id)
    await upsert_chunk_vectors(repository_id, points)

    logger.info(
        "Wrote %d vectors to Qdrant for repository %s across %d files",
        len(points), repository_id, len(files),
    )


class _SymbolTuple:
    """Minimal stand-in satisfying chunker.SymbolLike, built from a plain
    query result rather than a full ORM Symbol object."""
    __slots__ = ("name", "kind", "start_line", "end_line")

    def __init__(self, name: str, kind: str, start_line: int, end_line: int):
        self.name = name
        self.kind = kind
        self.start_line = start_line
        self.end_line = end_line


def _chunk_all_files(repo_dir: Path, files: list, symbols_by_file: dict) -> list[ChunkRecord]:
    """Reads each file from disk and chunks it. Runs in a thread (via
    asyncio.to_thread in the caller) since file I/O is blocking, mirroring
    analysis/service.py's _run_analysis pattern."""
    all_chunks: list[ChunkRecord] = []

    for file_id, rel_path in files:
        disk_path = repo_dir / rel_path
        try:
            content = disk_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            logger.warning("Could not read %s during embedding, skipping", disk_path)
            continue

        file_symbols = symbols_by_file.get(file_id, [])
        all_chunks.extend(chunk_file(file_id, rel_path, content, file_symbols))

    return all_chunks