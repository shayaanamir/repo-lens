import re
from urllib.parse import urlparse

# Only accept these exact hosts. Using an exact-match set (not "endswith
# github.com") blocks lookalike domains like "github.com.evil.com".
ALLOWED_HOSTS = {"github.com"}

# owner/repo segments: letters, digits, hyphens, underscores, dots.
# GitHub's real rules are a bit more nuanced, but this is a solid MVP filter.
SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


class InvalidRepoUrlError(ValueError):
    """Raised when a submitted URL isn't a valid public GitHub repo URL."""
    pass


def validate_github_url(url: str) -> str:
    """
    Validates that `url` points at a public GitHub repository, in the
    shape https://github.com/{owner}/{repo}.

    Returns a normalized URL (scheme + host + /owner/repo, no trailing
    slash, no .git suffix, no query string) on success.
    Raises InvalidRepoUrlError on any validation failure.
    """
    url = url.strip()

    try:
        parsed = urlparse(url)
    except ValueError as e:
        raise InvalidRepoUrlError(f"Could not parse URL: {e}") from e

    if parsed.scheme != "https":
        raise InvalidRepoUrlError("URL must use https://")

    if parsed.hostname not in ALLOWED_HOSTS:
        raise InvalidRepoUrlError(
            f"Host must be one of {sorted(ALLOWED_HOSTS)}, got '{parsed.hostname}'"
        )

    # Split the path into segments, dropping empty strings from
    # leading/trailing slashes (e.g. "/owner/repo/" -> ["owner", "repo"])
    segments = [seg for seg in parsed.path.split("/") if seg]

    if len(segments) != 2:
        raise InvalidRepoUrlError(
            "URL path must be exactly /{owner}/{repo}, "
            f"got {len(segments)} segment(s)"
        )

    owner, repo = segments

    # Strip a trailing ".git" if present (https://github.com/x/y.git is
    # a valid clone URL people commonly paste)
    if repo.endswith(".git"):
        repo = repo[: -len(".git")]

    for name, value in (("owner", owner), ("repo", repo)):
        if not value or not SEGMENT_PATTERN.match(value):
            raise InvalidRepoUrlError(f"Invalid {name} segment: '{value}'")

    return f"https://github.com/{owner}/{repo}"