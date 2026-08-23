from dataclasses import dataclass


@dataclass
class ContextChunk:
    path: str
    start_line: int
    end_line: int
    content: str
    symbol_name: str | None = None
    symbol_kind: str | None = None


@dataclass
class SourceRef:
    path: str
    start_line: int
    end_line: int


def _format_chunk(chunk: ContextChunk, index: int) -> str:
    label = f"{chunk.path}:{chunk.start_line}-{chunk.end_line}"
    if chunk.symbol_name:
        label += f" ({chunk.symbol_kind} {chunk.symbol_name})"
    return f"[{index}] {label}\n```\n{chunk.content}\n```"


def build_chat_prompt(repo_name: str, question: str, chunks: list[ContextChunk]) -> str:
    context = "\n\n".join(_format_chunk(c, i + 1) for i, c in enumerate(chunks))
    return f"""You are a code assistant helping a developer understand the "{repo_name}" repository.
Answer the question using ONLY the code excerpts below. Reference excerpts by their
[number] and file path/line range when relevant. If the excerpts don't contain enough
information to answer confidently, say so plainly instead of guessing.

Code excerpts:
{context if context else "(no relevant code excerpts were found)"}

Question: {question}

Answer:"""


def build_explain_prompt(
    repo_name: str, file_path: str, file_content: str, symbols: list[ContextChunk]
) -> str:
    symbol_lines = "\n".join(
        f"- {c.symbol_kind} {c.symbol_name} (lines {c.start_line}-{c.end_line})"
        for c in symbols if c.symbol_name
    )
    return f"""You are a code assistant explaining a file from the "{repo_name}" repository to a
developer unfamiliar with it. Explain what this file does, its main responsibilities,
and how its key symbols fit together. Be concise but concrete.

File: {file_path}

Known symbols in this file:
{symbol_lines if symbol_lines else "(none extracted)"}

File content:
{file_content}


Explanation:"""


def build_summary_prompt(
    repo_name: str,
    readme_content: str | None,
    primary_language: str | None,
    top_symbols: list[ContextChunk],
) -> str:
    readme_excerpt = (readme_content or "")[:3000]
    symbol_lines = "\n".join(f"- {c.path}: {c.symbol_kind} {c.symbol_name}" for c in top_symbols)
    return f"""Write a concise, high-level summary (3-5 sentences) of the "{repo_name}" repository
for a developer seeing it for the first time. Focus on its purpose and overall
architecture, not implementation detail.

Primary language: {primary_language or "unknown"}

README excerpt:
{readme_excerpt if readme_excerpt else "(no README found)"}

Sample of top-level symbols:
{symbol_lines if symbol_lines else "(none extracted)"}

Summary:"""