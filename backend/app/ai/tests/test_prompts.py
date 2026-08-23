from app.ai.prompts import ContextChunk, build_chat_prompt, build_explain_prompt, build_summary_prompt


# ---------------------------------------------------------------------
# Chat prompt
# ---------------------------------------------------------------------

def test_chat_prompt_includes_question_and_repo_name():
    prompt = build_chat_prompt("Flask", "How does routing work?", [])

    assert "Flask" in prompt
    assert "How does routing work?" in prompt


def test_chat_prompt_numbers_chunks_and_includes_file_refs():
    chunks = [
        ContextChunk(path="app/routing.py", start_line=10, end_line=20, content="def route(): pass"),
        ContextChunk(path="app/app.py", start_line=1, end_line=5, content="class App: pass"),
    ]

    prompt = build_chat_prompt("Flask", "How does routing work?", chunks)

    assert "[1] app/routing.py:10-20" in prompt
    assert "[2] app/app.py:1-5" in prompt
    assert "def route(): pass" in prompt
    assert "class App: pass" in prompt


def test_chat_prompt_includes_symbol_label_when_present():
    chunks = [
        ContextChunk(
            path="app/routing.py", start_line=10, end_line=20,
            content="def route(): pass", symbol_name="route", symbol_kind="function",
        )
    ]

    prompt = build_chat_prompt("Flask", "q", chunks)

    assert "(function route)" in prompt


def test_chat_prompt_handles_no_chunks_gracefully():
    prompt = build_chat_prompt("Flask", "q", [])

    assert "no relevant code excerpts were found" in prompt


# ---------------------------------------------------------------------
# Explain prompt
# ---------------------------------------------------------------------

def test_explain_prompt_includes_file_path_and_content():
    prompt = build_explain_prompt("Flask", "app/routing.py", "def route(): pass", [])

    assert "app/routing.py" in prompt
    assert "def route(): pass" in prompt


def test_explain_prompt_lists_known_symbols():
    symbols = [
        ContextChunk(path="app/routing.py", start_line=1, end_line=5, content="", symbol_name="route", symbol_kind="function"),
        ContextChunk(path="app/routing.py", start_line=10, end_line=5, content="", symbol_name=None, symbol_kind=None),
    ]

    prompt = build_explain_prompt("Flask", "app/routing.py", "code", symbols)

    assert "function route (lines 1-5)" in prompt
    # the symbol-less entry shouldn't produce a stray "- None None" line
    assert "None" not in prompt


def test_explain_prompt_handles_no_symbols():
    prompt = build_explain_prompt("Flask", "app/routing.py", "code", [])

    assert "(none extracted)" in prompt


# ---------------------------------------------------------------------
# Summary prompt
# ---------------------------------------------------------------------

def test_summary_prompt_includes_readme_and_language():
    prompt = build_summary_prompt("Flask", "A lightweight WSGI framework.", "Python", [])

    assert "A lightweight WSGI framework." in prompt
    assert "Python" in prompt


def test_summary_prompt_truncates_long_readme():
    long_readme = "R" * 10_000
    prompt = build_summary_prompt("Flask", long_readme, "Python", [])

    # Extract just the README excerpt section rather than counting a
    # character across the whole prompt — the template's own boilerplate
    # text isn't guaranteed to be free of any given letter.
    excerpt_section = prompt.split("README excerpt:\n")[1].split("\n\nSample of top-level symbols:")[0]

    assert len(excerpt_section) == 3000


def test_summary_prompt_handles_missing_readme_and_language():
    prompt = build_summary_prompt("Flask", None, None, [])

    assert "(no README found)" in prompt
    assert "unknown" in prompt


def test_summary_prompt_lists_sample_symbols():
    symbols = [ContextChunk(path="app/app.py", start_line=0, end_line=0, content="", symbol_name="App", symbol_kind="class")]

    prompt = build_summary_prompt("Flask", None, "Python", symbols)

    assert "app/app.py: class App" in prompt