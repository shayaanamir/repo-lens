import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
import os
import stat

DEFAULT_CLONE_TIMEOUT_SECONDS = 120       # 2 minutes
DEFAULT_MAX_REPO_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB


class CloneError(Exception):
    """Raised when cloning a repository fails for any reason
    (timeout, git error, or the repo exceeding the size limit)."""
    pass

class CloneTimeoutError(CloneError):
    """Raised specifically when the clone times out — a transient
    failure that may succeed on retry, unlike other CloneErrors."""
    pass

@dataclass
class ClonedRepo:
    path: Path       # local filesystem path to the cloned repo (temp dir)
    size_bytes: int


def clone_repository(
    github_url: str,
    dest_dir: Path | str | None = None,
    timeout_seconds: int = DEFAULT_CLONE_TIMEOUT_SECONDS,
    max_size_bytes: int = DEFAULT_MAX_REPO_SIZE_BYTES,
) -> ClonedRepo:
    """
    Shallow-clones a public GitHub repository.

    If dest_dir is given, clones there (creating parent directories as
    needed) — used for persistent, long-lived clones. If omitted, clones
    into a fresh system temp directory — used for tests/one-off inspection.

    Caller is responsible for calling cleanup_clone() when using the
    temp-dir mode. Persistent clones (dest_dir given) are NOT auto-cleaned.
    """
    if dest_dir is not None:
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
    else:
        dest = Path(tempfile.mkdtemp(prefix="repolens-clone-"))

    command = [
        "git", "clone",
        "--depth", "1",          # shallow: only the latest commit, not full history
        "--single-branch",       # only the default branch, not every branch/tag
        github_url,
        str(dest),
    ]

    try:
        subprocess.run(
            command,
            timeout=timeout_seconds,
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},  # inherit env, just disable prompts
        )
    except subprocess.TimeoutExpired as e:
        shutil.rmtree(dest, ignore_errors=True)
        raise CloneTimeoutError(
            f"git clone timed out after {timeout_seconds}s for {github_url}"
        ) from e
    except subprocess.CalledProcessError as e:
        shutil.rmtree(dest, ignore_errors=True)
        raise CloneError(
            f"git clone failed for {github_url}: {e.stderr.strip()}"
        ) from e

    size_bytes = _dir_size(dest)
    if size_bytes > max_size_bytes:
        shutil.rmtree(dest, ignore_errors=True)
        raise CloneError(
            f"Repository exceeds max allowed size "
            f"({size_bytes} > {max_size_bytes} bytes)"
        )

    return ClonedRepo(path=dest, size_bytes=size_bytes)


def cleanup_clone(cloned: ClonedRepo) -> None:
    """Deletes the cloned repo's temp directory. Always call this when
    you're done with the files — on both success and failure paths."""
    shutil.rmtree(cloned.path, onerror=_remove_readonly)


def _remove_readonly(func, path, exc_info):
    """shutil.rmtree error handler: on Windows, git's .git/ objects are
    often marked read-only, which blocks deletion. This clears the
    read-only flag and retries the operation once."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _dir_size(path: Path) -> int:
    """Recursively sums file sizes under `path`, in bytes."""
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return total