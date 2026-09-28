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
    readme_excerpt = (readme_content or "")[:5000]

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
do not invent features, metrics, or design decisions that aren't supported by them. Where the
facts don't cover something (e.g. exact algorithms, historical reasoning), say so honestly inside
the relevant answer rather than fabricating specifics — but don't let that stop you from reasoning
in depth about what IS knowable: architecture, data flow, tradeoffs implied by the structure itself,
and how the pieces fit together.

Depth matters more than polish here. A candidate who gives one-sentence answers fails technical
interviews. Write like a senior engineer walking a peer through the codebase, not like a summary
blurb — explain mechanisms, not just labels.

Respond with ONLY a single valid JSON object, no markdown code fences, no preamble, matching
exactly this shape:
{{
  "pitch": "<elevator pitch, 6-10 sentences>",
  "talking_points": ["<detailed architecture walkthrough point>", ...],
  "questions": [
    {{"question": "<likely interview question>", "answer": "<thorough model answer>"}}
  ]
}}

Requirements for depth:
- "pitch": 6-10 sentences. Cover what the project does, WHY it's built the way it is (the core
  design tension it resolves), and what would break or degrade if a key piece were removed.
- "talking_points": 5-8 points, each 3-5 sentences. For each module/mechanism, explain not just
  what it does but HOW — the actual flow of data or control through it, what problem it solves,
  and what would happen without it. Reference concrete file paths from the module list below where
  relevant so the candidate can point at real code.
- "questions": 5-7 questions covering a mix of: design tradeoffs ("why X over Y"), failure/edge-case
  handling, scaling concerns, and "what would you change." Each answer should be 4-8 sentences —
  give real engineering reasoning (tradeoffs considered, what breaks at scale, alternative
  approaches and why they weren't chosen), not a one-line dictionary definition. If the candidate's
  own notes below describe a hard problem they solved, include at least one question built directly
  around it, using their own framing and going deep on the mechanism they describe.

Primary language: {primary_language or "unknown"}

README excerpt:
{readme_excerpt if readme_excerpt else "(no README found)"}

Most-referenced modules:
{module_lines if module_lines else "(no module reference data available)"}

Candidate's own notes on challenges/decisions:
{context_section}

JSON response:"""