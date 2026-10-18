import json

from app.analysis.import_extractor import extract_imports
from app.analysis.import_resolver import resolve_import
from app.analysis.path_aliases import load_path_mappings, strip_jsonc


def _setup(files: dict[str, str]):
    known = set(files)
    return known, load_path_mappings(files.get, known)


def test_strip_jsonc_handles_comments_trailing_commas_and_glob_strings():
    text = """{
      // a line comment
      "compilerOptions": {
        "paths": { "@/*": ["./*"], }, /* block comment */
      },
    }"""

    data = json.loads(strip_jsonc(text))

    assert data["compilerOptions"]["paths"] == {"@/*": ["./*"]}


def test_next_style_wildcard_alias_resolves():
    known, mappings = _setup({
        "frontend/tsconfig.json": '{"compilerOptions": {"paths": {"@/*": ["./*"]}}}',
        "frontend/lib/utils.ts": "",
        "frontend/components/ui/button.tsx": "",
    })
    imp = extract_imports(b'import { cn } from "@/lib/utils";\n', ".tsx")[0]

    result = resolve_import("frontend/components/ui/button.tsx", imp, known, mappings)

    assert result == "frontend/lib/utils.ts"


def test_base_url_resolves_bare_specifiers():
    known, mappings = _setup({
        "tsconfig.json": '{"compilerOptions": {"baseUrl": "src"}}',
        "src/index.ts": "",
        "src/components/Button.tsx": "",
    })
    imp = extract_imports(b'import B from "components/Button";\n', ".ts")[0]

    assert resolve_import("src/index.ts", imp, known, mappings) == "src/components/Button.tsx"


def test_paths_with_base_url_resolve_against_base_url():
    known, mappings = _setup({
        "tsconfig.json": '{"compilerOptions": {"baseUrl": ".", "paths": {"@app/*": ["src/app/*"]}}}',
        "src/app/store.ts": "",
        "src/index.ts": "",
    })
    imp = extract_imports(b'import s from "@app/store";\n', ".ts")[0]

    assert resolve_import("src/index.ts", imp, known, mappings) == "src/app/store.ts"


def test_relative_extends_inherits_paths():
    known, mappings = _setup({
        "tsconfig.base.json": '{"compilerOptions": {"paths": {"@lib/*": ["src/lib/*"]}}}',
        "packages/web/tsconfig.json": '{"extends": "../../tsconfig.base.json"}',
        "src/lib/format.ts": "",
        "packages/web/src/a.ts": "",
    })
    imp = extract_imports(b'import f from "@lib/format";\n', ".ts")[0]

    assert resolve_import("packages/web/src/a.ts", imp, known, mappings) == "src/lib/format.ts"


def test_alias_does_not_apply_outside_its_config_directory():
    known, mappings = _setup({
        "frontend/tsconfig.json": '{"compilerOptions": {"paths": {"@/*": ["./*"]}}}',
        "frontend/lib/utils.ts": "",
        "backend/tool.ts": "",
    })
    imp = extract_imports(b'import { cn } from "@/lib/utils";\n', ".ts")[0]

    assert resolve_import("backend/tool.ts", imp, known, mappings) is None


def test_unmapped_package_import_still_returns_none():
    known, mappings = _setup({
        "tsconfig.json": '{"compilerOptions": {"paths": {"@/*": ["./*"]}}}',
        "index.ts": "",
    })
    imp = extract_imports(b'import React from "react";\n', ".ts")[0]

    assert resolve_import("index.ts", imp, known, mappings) is None