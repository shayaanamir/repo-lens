import uuid
from dataclasses import dataclass
from typing import Protocol

DEFAULT_WINDOW_LINES = 40
DEFAULT_OVERLAP_LINES = 5

# Hard ceiling on a single chunk's character length. Gemini's embedding
# model has its own input token limit regardless of our rate budget, and
# an oversized chunk (e.g. a huge generated class) also blows out the
# token-throttle's per-batch estimate. Truncate rather than skip, so the
# chunk still contributes *something* searchable.
MAX_CHUNK_CHARS = 6000

class SymbolLike(Protocol):
    """Structural type for anything with symbol-shaped fields — lets the
    chunker accept ORM Symbol rows directly without importing app.analysis
    (keeps this module dependency-light and easy to unit test with plain
    dataclasses/namedtuples)."""
    name: str
    kind: str
    start_line: int  # 1-indexed, inclusive
    end_line: int    # 1-indexed, inclusive


@dataclass
class ChunkRecord:
    file_id: uuid.UUID
    path: str
    content: str
    start_line: int  # 1-indexed, inclusive
    end_line: int    # 1-indexed, inclusive
    symbol_name: str | None
    symbol_kind: str | None


def chunk_file(
    file_id: uuid.UUID,
    path: str,
    content: str,
    symbols: list[SymbolLike],
    window_lines: int = DEFAULT_WINDOW_LINES,
    overlap_lines: int = DEFAULT_OVERLAP_LINES,
) -> list[ChunkRecord]:
    """
    Chunks a single file's content for embedding.

    Prefers symbol-level chunks (ARCHITECTURE.md §9: "prefer symbol-level
    chunks using Analysis Module output"). Every extracted symbol
    (function/class/method) becomes its own chunk — nested symbols (e.g.
    a method and its enclosing class) each get a chunk at their own
    granularity, which is intentional: it lets search match either the
    whole class or just the one method a query is about.

    Falls back to fixed-line-count windows when a file has no symbols at
    all — either because Tree-sitter doesn't support its extension, or
    it's a supported language file with no top-level functions/classes
    (e.g. a constants/config module).
    """
    if not content.strip():
        return []

    if symbols:
        return _chunk_by_symbol(file_id, path, content, symbols)

    return _chunk_by_window(file_id, path, content, window_lines, overlap_lines)


def _chunk_by_symbol(
    file_id: uuid.UUID, path: str, content: str, symbols: list[SymbolLike]
) -> list[ChunkRecord]:
    lines = content.splitlines()
    chunks: list[ChunkRecord] = []

    for sym in symbols:
        # Symbol lines are 1-indexed inclusive; slice is 0-indexed exclusive-end.
        start = max(sym.start_line, 1)
        end = min(sym.end_line, len(lines))
        if start > end:
            continue  # defensive: shouldn't happen, but don't emit a garbage chunk

        body = "\n".join(lines[start - 1 : end])
        if not body.strip():
            continue
        if len(body) > MAX_CHUNK_CHARS:
            body = body[:MAX_CHUNK_CHARS]
        chunks.append(
            ChunkRecord(
                file_id=file_id,
                path=path,
                content=body,
                start_line=start,
                end_line=end,
                symbol_name=sym.name,
                symbol_kind=sym.kind,
            )
        )

    return chunks


def _chunk_by_window(
    file_id: uuid.UUID,
    path: str,
    content: str,
    window_lines: int,
    overlap_lines: int,
) -> list[ChunkRecord]:
    lines = content.splitlines()
    if not lines:
        return []

    step = max(window_lines - overlap_lines, 1)  # guard against overlap >= window
    chunks: list[ChunkRecord] = []

    start = 0  # 0-indexed
    while start < len(lines):
        end = min(start + window_lines, len(lines))
        body = "\n".join(lines[start:end])

        if body.strip():
            if len(body) > MAX_CHUNK_CHARS:
                body = body[:MAX_CHUNK_CHARS]
            chunks.append(
                ChunkRecord(
                    file_id=file_id,
                    path=path,
                    content=body,
                    start_line=start + 1,
                    end_line=end,
                    symbol_name=None,
                    symbol_kind=None,
                )
            )

        if end == len(lines):
            break
        start += step

    return chunks