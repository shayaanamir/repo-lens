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

@dataclass
class ModuleSummary:
    path: str
    symbol_count: int
    in_degree: int
    out_degree: int


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


def build_interview_prep_prompt(
    repo_name: str,
    readme_content: str | None,
    primary_language: str | None,
    modules: list[ModuleSummary],
    user_context: str | None = None,
) -> str:
    readme_excerpt = (readme_content or "")[:3000]

    module_lines = "\n".join(
        f"- {m.path} (symbols: {m.symbol_count}, referenced by {m.in_degree}, imports {m.out_degree})"
        for m in modules
    )

    context_section = (
        user_context.strip()
        if user_context and user_context.strip()
        else "(no additional context provided by the candidate)"
    )

    return f"""You are helping a developer prepare to discuss the "{repo_name}" repository in a technical
interview, as if they built or worked deeply on it. Ground everything in the facts given below —
do not invent features, metrics, or design decisions that aren't supported by them.

Respond with ONLY a single valid JSON object, no markdown code fences, no preamble, matching
exactly this shape:
{{
  "pitch": "<2-4 sentence elevator pitch for the project>",
  "talking_points": ["<ordered architecture walkthrough point>", ...],
  "questions": [
    {{"question": "<likely interview question>", "answer": "<concise model answer>"}}
  ]
}}

Include 3-6 talking_points and 4-6 questions. Questions should cover a mix of design tradeoffs,
failure handling, and "what would you change at scale" — the kind of thing an interviewer actually
probes on, not generic trivia. If the candidate's own notes below describe a hard problem they
solved, weave at least one question/answer around it using their own framing.

Primary language: {primary_language or "unknown"}

README excerpt:
{readme_excerpt if readme_excerpt else "(no README found)"}

Most-referenced modules:
{module_lines if module_lines else "(no module reference data available)"}

Candidate's own notes on challenges/decisions:
{context_section}

JSON response:"""