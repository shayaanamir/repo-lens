import uuid

from app.analysis.service import _run_analysis


def _write(root, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_run_analysis_links_aliased_ts_and_nested_python_imports(tmp_path):
    sources = {
        "frontend/tsconfig.json": '{"compilerOptions": {"paths": {"@/*": ["./*"]}}}',
        "frontend/lib/utils.ts": "export const cn = () => 1;\n",
        "frontend/app/page.tsx": (
            'import { cn } from "@/lib/utils";\n'
            "export default function Page() { return cn(); }\n"
        ),
        "backend/app/core/config.py": "settings = 1\n",
        "backend/app/main.py": "from app.core.config import settings\n",
    }
    for relative, content in sources.items():
        _write(tmp_path, relative, content)
    ids = {relative: uuid.uuid4() for relative in sources}
    files = [(file_id, relative) for relative, file_id in ids.items()]

    result = _run_analysis(tmp_path, files)

    edges = {(e.source_file_id, e.target_path) for e in result.edges}
    assert (ids["frontend/app/page.tsx"], "frontend/lib/utils.ts") in edges
    assert (ids["backend/app/main.py"], "backend/app/core/config.py") in edges