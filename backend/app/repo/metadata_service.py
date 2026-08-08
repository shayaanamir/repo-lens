from dataclasses import dataclass
from pathlib import Path

# Common directories that don't represent "real" source content and
# would otherwise skew file counts / language detection.
IGNORED_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".pytest_cache", "vendor",
}

# Extension -> human-readable language name. Extend this list over time
# as you encounter repos with languages not yet covered.
EXTENSION_LANGUAGE_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sh": "Shell",
    ".sql": "SQL",
    ".md": "Markdown",
    ".json": "JSON",
    ".yml": "YAML",
    ".yaml": "YAML",
}

README_CANDIDATES = ("README.md", "README", "README.rst", "README.txt")


@dataclass
class RepoMetadata:
    readme_content: str | None
    primary_language: str | None
    file_count: int
    language_breakdown: dict[str, int]  # language -> file count, for reference


def extract_metadata(repo_path: Path) -> RepoMetadata:
    """
    Walks a cloned repo on disk and extracts:
    - README contents (if present)
    - primary language (by file count, using extension matching)
    - total file count (excluding ignored directories like .git)

    This is pure local filesystem inspection — no network calls,
    no AI. Deterministic, per ARCHITECTURE.md's core principle.
    """
    readme_content = _read_readme(repo_path)

    file_count = 0
    language_counts: dict[str, int] = {}

    for path in repo_path.rglob("*"):
        if not path.is_file():
            continue
        if _is_in_ignored_dir(path, repo_path):
            continue

        file_count += 1

        language = EXTENSION_LANGUAGE_MAP.get(path.suffix.lower())
        if language:
            language_counts[language] = language_counts.get(language, 0) + 1

    primary_language = (
        max(language_counts, key=language_counts.get) if language_counts else None
    )

    return RepoMetadata(
        readme_content=readme_content,
        primary_language=primary_language,
        file_count=file_count,
        language_breakdown=language_counts,
    )


def _read_readme(repo_path: Path) -> str | None:
    """Looks for a README file at the repo root (case-sensitive first,
    then case-insensitive fallback since READMEs vary in casing)."""
    for candidate in README_CANDIDATES:
        candidate_path = repo_path / candidate
        if candidate_path.exists():
            return _safe_read_text(candidate_path)

    # Fallback: case-insensitive scan of the root directory only
    for entry in repo_path.iterdir():
        if entry.is_file() and entry.name.upper().startswith("README"):
            return _safe_read_text(entry)

    return None


def _safe_read_text(path: Path) -> str | None:
    """Reads a text file defensively — repos can contain files with
    unexpected encodings, and a bad README shouldn't crash indexing."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _is_in_ignored_dir(path: Path, repo_root: Path) -> bool:
    """True if any parent directory between repo_root and path is in
    IGNORED_DIRS (e.g. skips anything under .git/ or node_modules/)."""
    relative = path.relative_to(repo_root)
    return any(part in IGNORED_DIRS for part in relative.parts[:-1])