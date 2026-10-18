import posixpath

from app.analysis.import_extractor import ExtractedImport
from app.analysis.path_aliases import PathMappings, alias_candidates

# Extensions tried, in order, when a specifier doesn't include one
# (JS/TS resolution, mirroring Node/bundler resolution order).
JS_TS_CANDIDATE_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")

PYTHON_PACKAGE_INIT = "__init__.py"


def resolve_imports(
    source_file_path: str,
    imp: ExtractedImport,
    known_paths: set[str],
    aliases: PathMappings | None = None,
) -> list[str]:
    """
    Resolves one extracted import to the repo-relative files it points at
    (several for `from pkg import a, b`), or [] if none are in the repo,
    typically because it's an external package, not a bug.

    `source_file_path` and everything in `known_paths` must be
    repo-relative, forward-slash paths.
    """
    if source_file_path.endswith(".py"):
        return _resolve_python(source_file_path, imp, known_paths)
    return _resolve_js_ts(source_file_path, imp, known_paths, aliases)


def resolve_import(
    source_file_path: str,
    imp: ExtractedImport,
    known_paths: set[str],
    aliases: PathMappings | None = None,
) -> str | None:
    """Single-target convenience wrapper around resolve_imports()."""
    resolved = resolve_imports(source_file_path, imp, known_paths, aliases)
    return resolved[0] if resolved else None


# ---------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------

def _join(base: str, name: str) -> str:
    return posixpath.join(base, name) if base else name


def _resolve_python(
    source_file_path: str, imp: ExtractedImport, known_paths: set[str]
) -> list[str]:
    if not imp.is_relative:
        return _resolve_python_absolute(source_file_path, imp, known_paths)

    # Relative import: count leading dots to find how many levels up
    # from the current file's directory the base package sits.
    # level=1 ("from . import x" / "from .foo import x") is the current
    # directory; level=2 ("from ..pkg import x") is one directory up.
    specifier = imp.specifier
    level = 0
    while level < len(specifier) and specifier[level] == ".":
        level += 1
    module_part = specifier[level:]  # "foo" in ".foo", "" in "."

    base_dir = posixpath.dirname(source_file_path)
    for _ in range(level - 1):
        base_dir = posixpath.dirname(base_dir)

    if module_part:
        module_path = _join(base_dir, module_part.replace(".", "/"))
        return _python_targets(module_path, imp.imported_names, known_paths)

    # "from . import a, b": each imported name may itself be a sibling module.
    submodules = _python_submodules(base_dir, imp.imported_names, known_paths)
    if submodules:
        return submodules

    # Fall back to the package's __init__.py (covers "from . import
    # some_attribute_defined_in_init").
    init_path = _join(base_dir, PYTHON_PACKAGE_INIT)
    return [init_path] if init_path in known_paths else []


def _python_source_roots(source_file_path: str) -> list[str]:
    """Directories to try as import roots, nearest first: the file's own
    directory, each parent in turn, and finally the repo root ("")."""
    roots: list[str] = []
    directory = posixpath.dirname(source_file_path)
    while True:
        roots.append(directory)
        if not directory:
            return roots
        directory = posixpath.dirname(directory)


def _resolve_python_absolute(
    source_file_path: str, imp: ExtractedImport, known_paths: set[str]
) -> list[str]:
    # "import a.b.c" / "from a.b import c". Python projects are often
    # nested ("backend/app/..."), so the import root isn't necessarily
    # the repo root. Try each ancestor directory as the root. Third-party
    # packages simply won't match anywhere, which is expected.
    module_path = imp.specifier.replace(".", "/")
    for root in _python_source_roots(source_file_path):
        targets = _python_targets(_join(root, module_path), imp.imported_names, known_paths)
        if targets:
            return targets
    return []


def _python_targets(
    module_path: str, imported_names: tuple[str, ...], known_paths: set[str]
) -> list[str]:
    """For "from <module> import a, b": the submodules a and b when they
    exist, otherwise the module itself (the names are then attributes)."""
    submodules = _python_submodules(module_path, imported_names, known_paths)
    if submodules:
        return submodules
    module_file = _try_python_module_candidates(module_path, known_paths)
    return [module_file] if module_file else []


def _python_submodules(
    module_path: str, names: tuple[str, ...], known_paths: set[str]
) -> list[str]:
    found: list[str] = []
    for name in names:
        candidate = _try_python_module_candidates(_join(module_path, name), known_paths)
        if candidate is not None and candidate not in found:
            found.append(candidate)
    return found


def _try_python_module_candidates(module_path: str, known_paths: set[str]) -> str | None:
    """Given a module path with no extension (e.g. "pkg/sub/foo"), try
    it as a plain module file, then as a package (__init__.py)."""
    as_module = f"{module_path}.py"
    if as_module in known_paths:
        return as_module

    as_package = posixpath.join(module_path, PYTHON_PACKAGE_INIT)
    if as_package in known_paths:
        return as_package

    return None


# ---------------------------------------------------------------------
# JavaScript / TypeScript
# ---------------------------------------------------------------------

def _resolve_js_ts(
    source_file_path: str,
    imp: ExtractedImport,
    known_paths: set[str],
    aliases: PathMappings | None,
) -> list[str]:
    if imp.is_relative:
        source_dir = posixpath.dirname(source_file_path)
        joined = posixpath.normpath(posixpath.join(source_dir, imp.specifier))
        resolved = _find_js_ts_file(joined, known_paths)
        return [resolved] if resolved else []

    # Non-relative: either an npm package (no edge), or a path alias or
    # baseUrl import configured in the nearest tsconfig/jsconfig.
    config = aliases.find_for(source_file_path) if aliases is not None else None
    if config is None:
        return []
    for stem in alias_candidates(imp.specifier, config):
        resolved = _find_js_ts_file(stem, known_paths)
        if resolved:
            return [resolved]
    return []


def _find_js_ts_file(path_stem: str, known_paths: set[str]) -> str | None:
    # Exact match (specifier already included an extension).
    if path_stem in known_paths:
        return path_stem

    # Try appending each candidate extension.
    for ext in JS_TS_CANDIDATE_EXTENSIONS:
        candidate = f"{path_stem}{ext}"
        if candidate in known_paths:
            return candidate

    # Try as a directory with an index file ("./components" -> "./components/index.ts").
    for ext in JS_TS_CANDIDATE_EXTENSIONS:
        candidate = posixpath.join(path_stem, f"index{ext}")
        if candidate in known_paths:
            return candidate

    return None