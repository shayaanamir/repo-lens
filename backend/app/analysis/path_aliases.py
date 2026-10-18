import json
import posixpath
import re
from dataclasses import dataclass, field
from typing import Callable

# tsconfig.json, jsconfig.json, tsconfig.app.json, tsconfig.base.json, ...
CONFIG_NAME_PATTERN = re.compile(r"^(tsconfig(\..+)?|jsconfig)\.json$")
MAX_EXTENDS_DEPTH = 5

ReadFile = Callable[[str], "str | None"]


@dataclass(frozen=True)
class AliasConfig:
    base_url: str | None  # repo-relative directory, "" = repo root
    paths_root: str  # directory of the config that defined `paths`
    paths: dict[str, list[str]] = field(default_factory=dict)

    @property
    def targets_root(self) -> str:
        """`paths` targets resolve against baseUrl when set, otherwise
        against the config file that defined them (TypeScript semantics)."""
        return self.base_url if self.base_url is not None else self.paths_root


@dataclass
class PathMappings:
    by_dir: dict[str, AliasConfig]

    def find_for(self, source_file_path: str) -> AliasConfig | None:
        """Nearest config at or above the file's directory."""
        directory = posixpath.dirname(source_file_path)
        while True:
            config = self.by_dir.get(directory)
            if config is not None:
                return config
            if not directory:
                return None
            directory = posixpath.dirname(directory)


def load_path_mappings(read_file: ReadFile, known_paths: set[str]) -> PathMappings:
    """Finds and parses every tsconfig/jsconfig in the repo. `read_file`
    takes a repo-relative path and returns its text, or None."""
    by_dir: dict[str, AliasConfig] = {}

    config_paths = sorted(
        (p for p in known_paths if CONFIG_NAME_PATTERN.match(posixpath.basename(p))),
        key=lambda p: (posixpath.dirname(p), _config_priority(posixpath.basename(p)), p),
    )
    for path in config_paths:
        config = _resolve_config(path, read_file, known_paths, depth=0)
        if config is None:
            continue
        directory = posixpath.dirname(path)
        existing = by_dir.get(directory)
        by_dir[directory] = config if existing is None else _merge(existing, config)

    return PathMappings(by_dir)


def alias_candidates(specifier: str, config: AliasConfig) -> list[str]:
    """Extension-less, repo-relative path stems a non-relative specifier
    could refer to under this config, best match first."""
    stems: list[str] = []

    for target in _match_alias(specifier, config.paths):
        stem = _norm_dir(posixpath.join(config.targets_root, target))
        if stem:
            stems.append(stem)

    if config.base_url is not None:
        stem = _norm_dir(posixpath.join(config.base_url, specifier))
        if stem:
            stems.append(stem)

    return stems


def strip_jsonc(text: str) -> str:
    """tsconfig files are JSON with comments and trailing commas. Strips
    both without touching string contents (note "@/*" contains `/*`)."""
    return _strip_trailing_commas(_strip_comments(text))


# ---------------------------------------------------------------------


def _config_priority(name: str) -> int:
    if name == "tsconfig.json":
        return 0
    if name == "jsconfig.json":
        return 1
    return 2


def _merge(primary: AliasConfig, secondary: AliasConfig) -> AliasConfig:
    return AliasConfig(
        base_url=primary.base_url if primary.base_url is not None else secondary.base_url,
        paths_root=primary.paths_root if primary.paths else secondary.paths_root,
        paths={**secondary.paths, **primary.paths},
    )


def _norm_dir(path: str) -> str | None:
    """Normalizes a repo-relative path. "" means the repo root; None means
    the path escapes the repository."""
    normalized = posixpath.normpath(path)
    if normalized == ".":
        return ""
    if normalized == ".." or normalized.startswith("../") or normalized.startswith("/"):
        return None
    return normalized


def _read_jsonc(path: str, read_file: ReadFile) -> dict | None:
    text = read_file(path)
    if text is None:
        return None
    try:
        data = json.loads(strip_jsonc(text.lstrip("\ufeff")))
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _resolve_config(
    path: str, read_file: ReadFile, known_paths: set[str], depth: int
) -> AliasConfig | None:
    if depth > MAX_EXTENDS_DEPTH:
        return None
    data = _read_jsonc(path, read_file)
    if data is None:
        return None

    config_dir = posixpath.dirname(path)
    base_url: str | None = None
    paths_root = config_dir
    paths: dict[str, list[str]] = {}

    extends = data.get("extends")
    if isinstance(extends, str) and extends.startswith("."):
        parent_path = posixpath.normpath(posixpath.join(config_dir, extends))
        if not parent_path.endswith(".json"):
            parent_path += ".json"
        if parent_path in known_paths:
            parent = _resolve_config(parent_path, read_file, known_paths, depth + 1)
            if parent is not None:
                base_url = parent.base_url
                paths_root = parent.paths_root
                paths = dict(parent.paths)

    options = data.get("compilerOptions")
    if isinstance(options, dict):
        raw_base_url = options.get("baseUrl")
        if isinstance(raw_base_url, str):
            normalized = _norm_dir(posixpath.join(config_dir, raw_base_url))
            if normalized is not None:
                base_url = normalized
        raw_paths = options.get("paths")
        if isinstance(raw_paths, dict):
            # A child's `paths` replaces the parent's entirely.
            paths = {
                key: [t for t in targets if isinstance(t, str)]
                for key, targets in raw_paths.items()
                if isinstance(targets, list)
            }
            paths_root = config_dir

    if base_url is None and not paths:
        return None
    return AliasConfig(base_url=base_url, paths_root=paths_root, paths=paths)


def _match_alias(specifier: str, paths: dict[str, list[str]]) -> list[str]:
    """Targets (with `*` filled in) of the best alias for `specifier`:
    an exact alias wins, otherwise the wildcard with the longest prefix."""
    best_prefix_len = -1
    best: list[str] = []
    for pattern, targets in paths.items():
        if "*" not in pattern:
            if pattern == specifier:
                return list(targets)
            continue
        prefix, _, suffix = pattern.partition("*")
        if (
            specifier.startswith(prefix)
            and specifier.endswith(suffix)
            and len(specifier) >= len(prefix) + len(suffix)
        ):
            captured = specifier[len(prefix) : len(specifier) - len(suffix)]
            if len(prefix) > best_prefix_len:
                best_prefix_len = len(prefix)
                best = [t.replace("*", captured, 1) for t in targets]
    return best


def _strip_comments(text: str) -> str:
    out: list[str] = []
    i, n = 0, len(text)
    in_string = False
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _strip_trailing_commas(text: str) -> str:
    out: list[str] = []
    i, n = 0, len(text)
    in_string = False
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
        elif ch == ",":
            j = i + 1
            while j < n and text[j] in " \t\r\n":
                j += 1
            if j < n and text[j] in "}]":
                i += 1  # drop the trailing comma
                continue
        out.append(ch)
        i += 1
    return "".join(out)