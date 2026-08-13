import functools
from pathlib import Path

import tree_sitter_javascript as tsjavascript
import tree_sitter_python as tspython
import tree_sitter_typescript as tstypescript
from tree_sitter import Language, Parser, Tree

# Maps file extension -> internal grammar key. Note .jsx and .tsx need
# their own JSX-aware grammar variants, so this is keyed by extension,
# not by the human-readable language name in metadata_service.py.
EXTENSION_TO_GRAMMAR = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
}

SUPPORTED_EXTENSIONS = frozenset(EXTENSION_TO_GRAMMAR)


@functools.lru_cache(maxsize=None)
def _get_language(grammar: str) -> Language:
    """Loads (and caches) the compiled Language object for a grammar key.
    Cached because each Language wraps a native library handle — no need
    to reconstruct it per file, or even per parser."""
    if grammar == "python":
        return Language(tspython.language())
    if grammar == "javascript":
        return Language(tsjavascript.language())
    if grammar == "typescript":
        return Language(tstypescript.language_typescript())
    if grammar == "tsx":
        return Language(tstypescript.language_tsx())
    raise ValueError(f"Unsupported grammar: {grammar}")


def get_parser_for_extension(extension: str) -> Parser | None:
    """Returns a ready-to-use Parser for a file extension (e.g. '.py'),
    or None if the extension isn't supported by any installed grammar.
    Building a Parser itself is cheap (unlike Language, which is cached
    above) so we construct a fresh one per call."""
    grammar = EXTENSION_TO_GRAMMAR.get(extension.lower())
    if grammar is None:
        return None
    return Parser(_get_language(grammar))


def parse_source(source: bytes, extension: str) -> Tree | None:
    """Parses source bytes into a Tree-sitter syntax tree, or returns
    None if the extension has no supported grammar."""
    parser = get_parser_for_extension(extension)
    if parser is None:
        return None
    return parser.parse(source)


def parse_file(path: Path) -> Tree | None:
    """Reads a file from disk and parses it. Returns None for unsupported
    extensions or unreadable files — mirrors metadata_service.py's
    defensive read pattern, since one bad/binary file shouldn't crash
    the whole parse stage (TASKS.md Phase 3: 'handle unparsed/unsupported
    file types gracefully')."""
    parser = get_parser_for_extension(path.suffix)
    if parser is None:
        return None

    try:
        source = path.read_bytes()
    except OSError:
        return None

    return parser.parse(source)