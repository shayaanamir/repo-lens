import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.search import service as service_module
from app.search.embeddings import EmbeddingTaskType


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _file_row(file_id: uuid.UUID, path: str) -> tuple:
    return (file_id, path)


def _symbol_row(file_id: uuid.UUID, name: str, kind: str, start: int, end: int) -> tuple:
    return (file_id, name, kind, start, end)


def _mock_db(file_rows: list[tuple], symbol_rows: list[tuple]) -> MagicMock:
    """Builds a mock AsyncSession whose db.execute(...) returns file rows
    on the first call and symbol rows on the second — matching the two
    sequential queries embed_repository issues."""
    files_result = MagicMock()
    files_result.all.return_value = file_rows

    symbols_result = MagicMock()
    symbols_result.all.return_value = symbol_rows

    db = MagicMock()
    db.execute = AsyncMock(side_effect=[files_result, symbols_result])
    return db


# ---------------------------------------------------------------------
# No files / no chunks
# ---------------------------------------------------------------------

@pytest.mark.anyio
async def test_no_files_skips_entirely(tmp_path, monkeypatch):
    db = MagicMock()
    files_result = MagicMock()
    files_result.all.return_value = []
    db.execute = AsyncMock(return_value=files_result)

    embed_texts_mock = AsyncMock()
    delete_mock = AsyncMock()
    upsert_mock = AsyncMock()
    monkeypatch.setattr(service_module, "embed_texts", embed_texts_mock)
    monkeypatch.setattr(service_module, "delete_repository_vectors", delete_mock)
    monkeypatch.setattr(service_module, "upsert_chunk_vectors", upsert_mock)

    await service_module.embed_repository(db, uuid.uuid4(), tmp_path)

    embed_texts_mock.assert_not_awaited()
    delete_mock.assert_not_awaited()
    upsert_mock.assert_not_awaited()
    # only the files query should have run — no symbols query needed
    assert db.execute.await_count == 1


@pytest.mark.anyio
async def test_files_with_no_chunks_deletes_stale_vectors_only(tmp_path, monkeypatch):
    repo_id = uuid.uuid4()
    file_id = uuid.uuid4()

    (tmp_path / "empty.py").write_text("   \n  \n")  # whitespace-only -> chunk_file returns []

    db = _mock_db(
        file_rows=[_file_row(file_id, "empty.py")],
        symbol_rows=[],
    )

    embed_texts_mock = AsyncMock()
    delete_mock = AsyncMock()
    upsert_mock = AsyncMock()
    monkeypatch.setattr(service_module, "embed_texts", embed_texts_mock)
    monkeypatch.setattr(service_module, "delete_repository_vectors", delete_mock)
    monkeypatch.setattr(service_module, "upsert_chunk_vectors", upsert_mock)

    await service_module.embed_repository(db, repo_id, tmp_path)

    embed_texts_mock.assert_not_awaited()
    delete_mock.assert_awaited_once_with(repo_id)
    upsert_mock.assert_not_awaited()


# ---------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------

@pytest.mark.anyio
async def test_happy_path_chunks_embeds_and_upserts(tmp_path, monkeypatch):
    repo_id = uuid.uuid4()
    py_file_id = uuid.uuid4()
    txt_file_id = uuid.uuid4()

    (tmp_path / "main.py").write_text("def foo():\n    return 1\n")
    (tmp_path / "notes.txt").write_text("line one\nline two\n")

    db = _mock_db(
        file_rows=[
            _file_row(py_file_id, "main.py"),
            _file_row(txt_file_id, "notes.txt"),
        ],
        symbol_rows=[
            _symbol_row(py_file_id, "foo", "function", 1, 2),
        ],
    )

    call_order: list[str] = []

    async def fake_embed_texts(texts, task_type):
        call_order.append("embed")
        assert task_type == EmbeddingTaskType.DOCUMENT
        return [[0.1, 0.2] for _ in texts]

    async def fake_delete(repository_id):
        call_order.append("delete")

    async def fake_upsert(repository_id, points):
        call_order.append("upsert")
        fake_upsert.captured = points
        fake_upsert.repository_id = repository_id

    monkeypatch.setattr(service_module, "embed_texts", fake_embed_texts)
    monkeypatch.setattr(service_module, "delete_repository_vectors", fake_delete)
    monkeypatch.setattr(service_module, "upsert_chunk_vectors", fake_upsert)

    await service_module.embed_repository(db, repo_id, tmp_path)

    # one symbol-level chunk (foo) + one fallback-window chunk (notes.txt)
    points = fake_upsert.captured
    assert len(points) == 2
    assert fake_upsert.repository_id == repo_id

    # embed happens before delete, delete happens before upsert — so a
    # failed Gemini call never leaves the repo with zero search results
    assert call_order == ["embed", "delete", "upsert"]

    by_path = {p[2]["path"]: p for p in points}

    py_point = by_path["main.py"]
    point_id, vector, payload = py_point
    assert isinstance(point_id, uuid.UUID)
    assert vector == [0.1, 0.2]
    assert payload["repository_id"] == str(repo_id)
    assert payload["file_id"] == str(py_file_id)
    assert payload["symbol_name"] == "foo"
    assert payload["symbol_kind"] == "function"
    assert payload["start_line"] == 1
    assert payload["end_line"] == 2

    txt_point = by_path["notes.txt"]
    _, _, txt_payload = txt_point
    assert txt_payload["file_id"] == str(txt_file_id)
    assert txt_payload["symbol_name"] is None
    assert txt_payload["symbol_kind"] is None


@pytest.mark.anyio
async def test_unreadable_file_is_skipped_others_still_processed(tmp_path, monkeypatch):
    repo_id = uuid.uuid4()
    missing_file_id = uuid.uuid4()
    ok_file_id = uuid.uuid4()

    (tmp_path / "present.py").write_text("def bar():\n    return 2\n")
    # "missing.py" deliberately has no file on disk — simulates an
    # unreadable/vanished file without needing OS-level permission tricks.

    db = _mock_db(
        file_rows=[
            _file_row(missing_file_id, "missing.py"),
            _file_row(ok_file_id, "present.py"),
        ],
        symbol_rows=[
            _symbol_row(ok_file_id, "bar", "function", 1, 2),
        ],
    )

    async def fake_embed_texts(texts, task_type):
        return [[0.5, 0.5] for _ in texts]

    upserted = {}

    async def fake_upsert(repository_id, points):
        upserted["points"] = points

    monkeypatch.setattr(service_module, "embed_texts", fake_embed_texts)
    monkeypatch.setattr(service_module, "delete_repository_vectors", AsyncMock())
    monkeypatch.setattr(service_module, "upsert_chunk_vectors", fake_upsert)

    await service_module.embed_repository(db, repo_id, tmp_path)

    points = upserted["points"]
    assert len(points) == 1  # only present.py's chunk — missing.py silently skipped
    assert points[0][2]["path"] == "present.py"


@pytest.mark.anyio
async def test_embed_texts_receives_chunk_contents_in_order(tmp_path, monkeypatch):
    repo_id = uuid.uuid4()
    file_id = uuid.uuid4()

    (tmp_path / "main.py").write_text("def foo():\n    return 1\n\ndef bar():\n    return 2\n")

    db = _mock_db(
        file_rows=[_file_row(file_id, "main.py")],
        symbol_rows=[
            _symbol_row(file_id, "foo", "function", 1, 2),
            _symbol_row(file_id, "bar", "function", 4, 5),
        ],
    )

    received_texts = []

    async def fake_embed_texts(texts, task_type):
        received_texts.extend(texts)
        return [[0.0] for _ in texts]

    monkeypatch.setattr(service_module, "embed_texts", fake_embed_texts)
    monkeypatch.setattr(service_module, "delete_repository_vectors", AsyncMock())
    monkeypatch.setattr(service_module, "upsert_chunk_vectors", AsyncMock())

    await service_module.embed_repository(db, repo_id, tmp_path)

    assert received_texts == [
        "def foo():\n    return 1",
        "def bar():\n    return 2",
    ]