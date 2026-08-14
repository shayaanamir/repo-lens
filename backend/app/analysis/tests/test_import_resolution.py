from app.analysis.import_extractor import extract_imports
from app.analysis.import_resolver import resolve_import


# ---------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------

def test_python_extracts_absolute_and_relative_imports():
    src = b"""
import os
from os import path
from . import sibling
from .foo import bar
from ..pkg import baz
"""
    imports = extract_imports(src, ".py")
    by_specifier = {i.specifier: i for i in imports}

    assert by_specifier["os"].is_relative is False
    assert by_specifier["."].is_relative is True
    assert by_specifier["."].imported_names == ("sibling",)
    assert by_specifier[".foo"].imported_names == ("bar",)
    assert by_specifier["..pkg"].imported_names == ("baz",)


def test_js_extracts_import_and_require_but_not_external_require():
    src = b"""
import foo from './foo';
import react from 'react';
const x = require('./qux');
const y = require('lodash');
"""
    imports = extract_imports(src, ".js")
    specifiers = {i.specifier: i.is_relative for i in imports}

    assert specifiers == {
        "./foo": True,
        "react": False,
        "./qux": True,
        "lodash": False,
    }


def test_js_extracts_re_exports():
    src = b"""
export { thing } from './reexport';
export * from './reexport2';
"""
    imports = extract_imports(src, ".js")
    specifiers = {i.specifier for i in imports}

    assert specifiers == {"./reexport", "./reexport2"}


def test_js_skips_anonymous_inline_arrow_calls_as_non_import():
    # sanity check this module doesn't accidentally treat arbitrary
    # call_expressions as imports
    src = b"doSomething('./not-an-import');"
    assert extract_imports(src, ".js") == []


# ---------------------------------------------------------------------
# Resolution — Python
# ---------------------------------------------------------------------

PY_KNOWN = {
    "app/main.py",
    "app/utils.py",
    "app/pkg/__init__.py",
    "app/pkg/foo.py",
    "app/pkg/sub/__init__.py",
    "app/pkg/sub/deep.py",
}


def test_python_resolves_dot_import_of_sibling_module():
    imp = extract_imports(b"from . import utils\n", ".py")[0]
    assert resolve_import("app/main.py", imp, PY_KNOWN) == "app/utils.py"


def test_python_resolves_dot_import_of_sibling_package():
    imp = extract_imports(b"from . import sub\n", ".py")[0]
    assert resolve_import("app/pkg/foo.py", imp, PY_KNOWN) == "app/pkg/sub/__init__.py"


def test_python_resolves_double_dot_up_one_level():
    imp = extract_imports(b"from .. import foo\n", ".py")[0]
    assert resolve_import("app/pkg/sub/deep.py", imp, PY_KNOWN) == "app/pkg/foo.py"


def test_python_relative_import_beyond_repo_root_returns_none():
    imp = extract_imports(b"from ...nonexistent import thing\n", ".py")[0]
    assert resolve_import("app/pkg/sub/deep.py", imp, PY_KNOWN) is None


def test_python_absolute_import_of_external_package_returns_none():
    imp = extract_imports(b"import numpy\n", ".py")[0]
    assert resolve_import("app/main.py", imp, PY_KNOWN) is None


# ---------------------------------------------------------------------
# Resolution — JS/TS
# ---------------------------------------------------------------------

JS_KNOWN = {
    "src/index.ts",
    "src/utils.ts",
    "src/components/Button.tsx",
    "src/components/index.ts",
    "src/lib/helpers.js",
    "src/lib/nested/deep.ts",
}


def test_js_resolves_relative_import_with_added_extension():
    imp = extract_imports(b"import x from './utils';\n", ".ts")[0]
    assert resolve_import("src/index.ts", imp, JS_KNOWN) == "src/utils.ts"


def test_js_resolves_directory_import_to_index_file():
    imp = extract_imports(b"import c from './components';\n", ".ts")[0]
    assert resolve_import("src/index.ts", imp, JS_KNOWN) == "src/components/index.ts"


def test_js_resolves_multi_level_parent_traversal():
    imp = extract_imports(b"import u from '../../utils';\n", ".ts")[0]
    assert resolve_import("src/lib/nested/deep.ts", imp, JS_KNOWN) == "src/utils.ts"


def test_js_bare_specifier_returns_none():
    imp = extract_imports(b"import react from 'react';\n", ".ts")[0]
    assert resolve_import("src/index.ts", imp, JS_KNOWN) is None


def test_js_missing_relative_file_returns_none():
    imp = extract_imports(b"import x from './does-not-exist';\n", ".ts")[0]
    assert resolve_import("src/index.ts", imp, JS_KNOWN) is None