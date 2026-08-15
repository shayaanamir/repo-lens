import uuid
from dataclasses import dataclass

from app.search.chunker import chunk_file


@dataclass
class FakeSymbol:
    name: str
    kind: str
    start_line: int
    end_line: int


FILE_ID = uuid.uuid4()


def test_symbol_level_chunking_extracts_correct_slices():
    content = "\n".join([
        "def foo():",       # 1
        "    return 1",     # 2
        "",                 # 3
        "def bar():",       # 4
        "    return 2",     # 5
    ])
    symbols = [
        FakeSymbol("foo", "function", 1, 2),
        FakeSymbol("bar", "function", 4, 5),
    ]

    chunks = chunk_file(FILE_ID, "main.py", content, symbols)

    assert len(chunks) == 2
    assert chunks[0].content == "def foo():\n    return 1"
    assert chunks[0].symbol_name == "foo"
    assert chunks[0].start_line == 1 and chunks[0].end_line == 2
    assert chunks[1].content == "def bar():\n    return 2"


def test_nested_symbols_each_get_their_own_chunk():
    content = "\n".join([
        "class Foo:",           # 1
        "    def method(self):",  # 2
        "        pass",          # 3
    ])
    symbols = [
        FakeSymbol("Foo", "class", 1, 3),
        FakeSymbol("method", "method", 2, 3),
    ]

    chunks = chunk_file(FILE_ID, "main.py", content, symbols)

    assert len(chunks) == 2
    assert chunks[0].symbol_kind == "class"
    assert chunks[1].symbol_kind == "method"
    assert chunks[1].content == "    def method(self):\n        pass"


def test_empty_symbol_slice_is_skipped():
    content = "x = 1"
    symbols = [FakeSymbol("weird", "function", 5, 10)]  # out of range

    assert chunk_file(FILE_ID, "main.py", content, symbols) == []


def test_fallback_window_chunking_small_file_single_chunk():
    content = "\n".join(f"line {i}" for i in range(10))

    chunks = chunk_file(FILE_ID, "notes.txt", content, symbols=[])

    assert len(chunks) == 1
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 10
    assert chunks[0].symbol_name is None


def test_fallback_window_chunking_large_file_overlaps():
    content = "\n".join(f"line {i}" for i in range(100))

    chunks = chunk_file(
        FILE_ID, "big.txt", content, symbols=[], window_lines=40, overlap_lines=5
    )

    # step = 35, windows: [1-40], [36-75], [71-100]
    assert [ (c.start_line, c.end_line) for c in chunks ] == [
        (1, 40), (36, 75), (71, 100),
    ]
    # confirm overlap: last 5 lines of chunk 1 == first 5 lines of chunk 2
    assert chunks[0].content.splitlines()[-5:] == chunks[1].content.splitlines()[:5]


def test_empty_content_returns_no_chunks():
    assert chunk_file(FILE_ID, "empty.py", "", symbols=[]) == []
    assert chunk_file(FILE_ID, "whitespace.py", "   \n  \n", symbols=[]) == []