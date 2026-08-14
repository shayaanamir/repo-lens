import posixpath

from app.analysis.import_extractor import ExtractedImport

# Extensions tried, in order, when a specifier doesn't include one
# (JS/TS resolution — mirrors Node/bundler resolution order).
JS_TS_CANDIDATE_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")

PYTHON_PACKAGE_INIT = "__init__.py"


def resolve_import(
    source_file_path: str,
    imp: ExtractedImport,
    known_paths: set[str],
) -> str | None:
    """
    Resolves a single extracted import to a repo-relative file path,
    or None if it can't be resolved against `known_paths` (typically
    because it's an external package, not a bug in resolution).

    `source_file_path` and everything in `known_paths` must be
    repo-relative, forward-slash paths (as produced by
    Path.relative_to(...).as_posix() in repo/service.py's _scan_files).
    """
    if source_file_path.endswith(".py"):
        return _resolve_python(source_file_path, imp, known_paths)
    return _resolve_js_ts(source_file_path, imp, known_paths)


def _resolve_python(
    source_file_path: str, imp: ExtractedImport, known_paths: set[str]
) -> str | None:
    source_dir = posixpath.dirname(source_file_path)

    if not imp.is_relative:
        # Absolute import, e.g. "import a.b.c" / "from a.b import c".
        # Try it as a repo-root-relative module path. Most of these are
        # third-party packages and simply won't match — that's expected,
        # not an error.
        module_path = imp.specifier.replace(".", "/")
        return _try_python_module_candidates(module_path, known_paths)

    # Relative import: count leading dots to find how many levels up
    # from the current file's directory the base package sits.
    # level=1 ("from . import x" / "from .foo import x") means the
    # current directory; level=2 ("from ..pkg import x") means one
    # directory up, etc.
    specifier = imp.specifier
    level = 0
    while level < len(specifier) and specifier[level] == ".":
        level += 1
    module_part = specifier[level:]  # e.g. "foo" in ".foo", "" in "."

    base_dir = source_dir
    for _ in range(level - 1):
        base_dir = posixpath.dirname(base_dir)

    if module_part:
        # "from .foo import bar" / "from ..pkg import bar" — foo/pkg
        # is itself the module to resolve; the imported names are
        # attributes of it, not separate files.
        module_path = posixpath.join(base_dir, module_part.replace(".", "/")) if base_dir else module_part.replace(".", "/")
        return _try_python_module_candidates(module_path, known_paths)

    # "from . import sibling[, other]" — no module part, so each
    # imported name is itself a candidate sibling module. Resolve the
    # first one that matches an actual file; this is a graph over
    # files, and multi-name imports from a bare "." would otherwise
    # need multiple edges from one specifier, which the current
    # one-specifier-to-one-edge model doesn't support. Taking the
    # first match keeps the common single-name case fully correct.
    for name in imp.imported_names:
        candidate_dir = posixpath.join(base_dir, name) if base_dir else name
        resolved = _try_python_module_candidates(candidate_dir, known_paths)
        if resolved is not None:
            return resolved

    # Fall back to the package's __init__.py itself (covers "from .
    # import some_attribute_defined_in_init").
    init_path = posixpath.join(base_dir, PYTHON_PACKAGE_INIT) if base_dir else PYTHON_PACKAGE_INIT
    return init_path if init_path in known_paths else None


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


def _resolve_js_ts(
    source_file_path: str, imp: ExtractedImport, known_paths: set[str]
) -> str | None:
    if not imp.is_relative:
        # Bare specifier ("react", "lodash", or an unconfigured path
        # alias like "@/components/Foo") — out of MVP scope per
        # ARCHITECTURE.md §8's tsconfig-paths note; no edge created.
        return None

    source_dir = posixpath.dirname(source_file_path)
    joined = posixpath.normpath(posixpath.join(source_dir, imp.specifier))
    # normpath collapses "a/b/../c" -> "a/c"; on a root-level relative
    # import normpath can leave a leading "./" or convert "" -> ".",
    # which posixpath.join/normpath already handle consistently here.

    # Exact match (specifier already included an extension).
    if joined in known_paths:
        return joined

    # Try appending each candidate extension.
    for ext in JS_TS_CANDIDATE_EXTENSIONS:
        candidate = f"{joined}{ext}"
        if candidate in known_paths:
            return candidate

    # Try as a directory with an index file (e.g. "./components" -> "./components/index.ts").
    for ext in JS_TS_CANDIDATE_EXTENSIONS:
        candidate = posixpath.join(joined, f"index{ext}")
        if candidate in known_paths:
            return candidate

    return None