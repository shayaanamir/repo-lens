"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ExternalLink, Loader2, Trash2 } from "lucide-react";
import {
  createRepository,
  listRepositories,
  deleteRepository,
  ApiError,
  type RepositoryListItem,
} from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const EXAMPLE_REPOS = ["pallets/flask", "octocat/Hello-World", "tiangolo/fastapi"];

/** Accepts "owner/repo" shorthand and expands it to a full GitHub URL,
 * so people can paste either form — the backend still validates the
 * real thing either way. */
function normalizeRepoInput(raw: string): string {
  const trimmed = raw.trim();
  if (/^[\w.-]+\/[\w.-]+$/.test(trimmed)) {
    return `https://github.com/${trimmed}`;
  }
  return trimmed;
}

export default function Home() {
  const router = useRouter();
  const [input, setInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!input.trim() || isSubmitting) return;

    setError(null);
    setIsSubmitting(true);

    try {
      const repo = await createRepository(normalizeRepoInput(input));
      router.push(`/repo/${repo.id}`);
      // isSubmitting intentionally stays true — we're navigating away.
    } catch (err) {
      setIsSubmitting(false);
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Couldn't reach RepoLens. Check that the backend is running.");
      }
    }
  }

  return (
    <div className="flex-1 bg-[#0B1220] text-[#ECE7D8]">
      <style>{`
        @keyframes rl-sweep {
          0%   { transform: translateY(0); opacity: 0; }
          8%   { opacity: 1; }
          92%  { opacity: 1; }
          100% { transform: translateY(190px); opacity: 0; }
        }
        @keyframes rl-dot-pulse {
          0%, 100% { opacity: 0.35; r: 3.4; }
          50%      { opacity: 1; r: 4.6; }
        }
        .rl-scanbar { animation: rl-sweep 5s ease-in-out infinite; }
        .rl-dot { animation: rl-dot-pulse 5s ease-in-out infinite; transform-origin: center; }
        @media (prefers-reduced-motion: reduce) {
          .rl-scanbar { animation: none; opacity: 0; }
          .rl-dot { animation: none; opacity: 0.6; }
        }
      `}</style>

      {/* ---------------------------------------------------------- */}
      {/* Header                                                      */}
      {/* ---------------------------------------------------------- */}
      <header className="mx-auto flex max-w-5xl items-center justify-between px-6 py-8">
        <span className="font-[family-name:var(--font-mono)] text-sm font-medium tracking-[0.2em] text-[#ECE7D8]">
          REPOLENS
        </span>
        <span className="hidden font-[family-name:var(--font-mono)] text-xs tracking-widest text-[#8B98AC] sm:block">
          STATIC ANALYSIS → SEMANTIC SEARCH → GROUNDED AI
        </span>
      </header>

      {/* ---------------------------------------------------------- */}
      {/* Hero                                                        */}
      {/* ---------------------------------------------------------- */}
      <section className="mx-auto grid max-w-5xl gap-12 px-6 pb-20 pt-8 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
        <div>
          <h1 className="font-[family-name:var(--font-display)] text-[2.75rem] font-normal leading-[1.05] tracking-tight text-[#F5F2E8] sm:text-6xl">
            Read the blueprint
            <br />
            before you read the code.
          </h1>
          <p className="mt-6 max-w-md text-[1.05rem] leading-relaxed text-[#B7C0CE]">
            Paste a public GitHub repository. RepoLens parses it, maps how
            the pieces connect, and answers questions grounded in what it
            actually found — not what a model guesses.
          </p>

          <form onSubmit={handleSubmit} className="mt-9 max-w-md">
            <div className="rounded-lg border border-[#D8D2BC] bg-[#ECE7D8] p-1.5 shadow-[0_20px_50px_-20px_rgba(0,0,0,0.6)]">
              <div className="flex items-center gap-2 px-3 py-2">
                <span className="select-none font-[family-name:var(--font-mono)] text-sm text-[#8A8368]">
                  $
                </span>
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="github.com/pallets/flask"
                  disabled={isSubmitting}
                  className="flex-1 bg-transparent font-[family-name:var(--font-mono)] text-sm text-[#0B1220] placeholder:text-[#A6A085] outline-none disabled:opacity-60"
                  autoComplete="off"
                  spellCheck={false}
                />
                <Button
                  type="submit"
                  disabled={isSubmitting || !input.trim()}
                  suppressHydrationWarning
                  className="shrink-0 bg-[#F2A93C] text-[#0B1220] hover:bg-[#e0972a] disabled:opacity-50"
                >
                  {isSubmitting ? "Cloning…" : "Scan repository"}
                </Button>
              </div>
            </div>

            {error && (
              <p className="mt-3 text-sm text-[#F2A93C]">{error}</p>
            )}

            <div className="mt-4 flex flex-wrap items-center gap-2 font-[family-name:var(--font-mono)] text-xs text-[#8B98AC]">
              <span>try:</span>
              {EXAMPLE_REPOS.map((repo) => (
                <button
                  key={repo}
                  type="button"
                  onClick={() => setInput(repo)}
                  className="rounded border border-[#2A3A50] px-2 py-1 text-[#B7C0CE] transition-colors hover:border-[#5FD3C4] hover:text-[#5FD3C4]"
                >
                  {repo}
                </button>
              ))}
            </div>
          </form>
        </div>

        {/* Signature element: code being scanned into structure */}
        <div className="hidden justify-self-end lg:block">
          <svg
            viewBox="0 0 380 220"
            width="380"
            height="220"
            className="rounded-xl border border-[#1E2C40] bg-[#121C2B]"
          >
            <text
              x="20" y="34"
              className="font-[family-name:var(--font-mono)]"
              fontSize="13" fill="#6E7B8F"
            >
              def <tspan fill="#5FD3C4">clone_repository</tspan>(url, dest):
            </text>
            <text x="20" y="60" className="font-[family-name:var(--font-mono)]" fontSize="13" fill="#6E7B8F">
              {"    "}<tspan fill="#F2A93C">validate_github_url</tspan>(url)
            </text>
            <text x="20" y="86" className="font-[family-name:var(--font-mono)]" fontSize="13" fill="#4A5771">
              {"    "}run([&quot;git&quot;, &quot;clone&quot;, url])
            </text>
            <text x="20" y="112" className="font-[family-name:var(--font-mono)]" fontSize="13" fill="#6E7B8F">
              {"    "}return <tspan fill="#5FD3C4">ClonedRepo</tspan>(dest)
            </text>
            <text x="20" y="164" className="font-[family-name:var(--font-mono)]" fontSize="13" fill="#6E7B8F">
              class <tspan fill="#F2A93C">AnalysisService</tspan>:
            </text>

            {/* extracted structure, right margin */}
            <line x1="330" y1="30" x2="330" y2="56" stroke="#3A4A62" strokeWidth="1.5" />
            <line x1="330" y1="30" x2="330" y2="108" stroke="#3A4A62" strokeWidth="1.5" />
            <circle cx="330" cy="30" r="4" fill="#5FD3C4" className="rl-dot" style={{ animationDelay: "0.5s" }} />
            <circle cx="330" cy="56" r="4" fill="#F2A93C" className="rl-dot" style={{ animationDelay: "1.7s" }} />
            <circle cx="330" cy="108" r="4" fill="#5FD3C4" className="rl-dot" style={{ animationDelay: "3s" }} />
            <circle cx="330" cy="160" r="4" fill="#F2A93C" className="rl-dot" style={{ animationDelay: "4.2s" }} />

            <rect
              x="0" y="0" width="380" height="3"
              fill="url(#rl-gradient)"
              className="rl-scanbar"
            />
            <defs>
              <linearGradient id="rl-gradient" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#5FD3C4" stopOpacity="0" />
                <stop offset="50%" stopColor="#5FD3C4" stopOpacity="0.9" />
                <stop offset="100%" stopColor="#F2A93C" stopOpacity="0" />
              </linearGradient>
            </defs>
          </svg>
        </div>
      </section>
      <RepositoryList />
      {/* ---------------------------------------------------------- */}
      {/* Pipeline strip — real sequence, so numbering is earned      */}
      {/* ---------------------------------------------------------- */}
      <section className="border-y border-[#1E2C40] bg-[#0E1826]">
        <div className="mx-auto grid max-w-5xl grid-cols-2 gap-px sm:grid-cols-4">
          {[
            { n: "01", label: "Clone", desc: "Shallow git clone, isolated and size-limited." },
            { n: "02", label: "Parse", desc: "Tree-sitter extracts symbols and import edges." },
            { n: "03", label: "Embed", desc: "Chunks are embedded and indexed in Qdrant." },
            { n: "04", label: "Summarize", desc: "Gemini writes a grounded, one-time overview." },
          ].map((stage) => (
            <div key={stage.n} className="px-6 py-8">
              <span className="font-[family-name:var(--font-mono)] text-xs text-[#5FD3C4]">
                {stage.n}
              </span>
              <h3 className="mt-2 font-[family-name:var(--font-display)] text-lg text-[#ECE7D8]">
                {stage.label}
              </h3>
              <p className="mt-1 text-sm leading-snug text-[#8B98AC]">{stage.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ---------------------------------------------------------- */}
      {/* Principles                                                  */}
      {/* ---------------------------------------------------------- */}
      <section className="mx-auto max-w-5xl px-6 py-20">
        <div className="grid gap-10 sm:grid-cols-3">
          <div>
            <h3 className="font-[family-name:var(--font-display)] text-xl text-[#F5F2E8]">
              Deterministic before AI
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-[#8B98AC]">
              Static analysis always runs first. The AI layer only
              explains what parsing already proved.
            </p>
          </div>
          <div>
            <h3 className="font-[family-name:var(--font-display)] text-xl text-[#F5F2E8]">
              Every answer, sourced
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-[#8B98AC]">
              Chat and file explanations cite the exact files and lines
              they're grounded in.
            </p>
          </div>
          <div>
            <h3 className="font-[family-name:var(--font-display)] text-xl text-[#F5F2E8]">
              Works without AI, too
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-[#8B98AC]">
              Browsing, search, and the dependency graph never depend on
              a model being available.
            </p>
          </div>
        </div>
      </section>

      <footer className="border-t border-[#1E2C40] px-6 py-8">
        <p className="mx-auto max-w-5xl font-[family-name:var(--font-mono)] text-xs text-[#5A6880]">
          RepoLens — static analysis first, AI second.
        </p>
      </footer>
    </div>
  );
}

function RepositoryList() {
  const [repos, setRepos] = useState<RepositoryListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  async function load() {
    try {
      const data = await listRepositories();
      setRepos(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't load your repositories.");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleDelete(id: string, name: string) {
    if (!window.confirm(`Delete "${name}"? This removes its indexed data and cannot be undone.`)) {
      return;
    }
    setDeletingId(id);
    try {
      await deleteRepository(id);
      setRepos((prev) => prev?.filter((r) => r.id !== id) ?? null);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't delete this repository.");
    } finally {
      setDeletingId(null);
    }
  }

  if (repos === null && !error) {
    return (
      <section className="mx-auto max-w-5xl px-6 py-16">
        <div className="flex items-center gap-2 font-[family-name:var(--font-mono)] text-xs text-[#8B98AC]">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          loading your repositories…
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="mx-auto max-w-5xl px-6 py-16">
        <p className="font-[family-name:var(--font-mono)] text-xs text-[#F2555C]">{error}</p>
      </section>
    );
  }

  if (!repos || repos.length === 0) {
    return null; // nothing imported yet — the hero form is invitation enough
  }

  return (
    <section className="mx-auto max-w-5xl px-6 py-16">
      <p className="font-[family-name:var(--font-mono)] text-xs uppercase tracking-widest text-[#5FD3C4]">
        Your repositories
      </p>
      <div className="mt-4 divide-y divide-[#1E2C40] overflow-hidden rounded-lg border border-[#1E2C40]">
        {repos.map((repo) => (
          <div
            key={repo.id}
            className="flex items-center justify-between gap-4 bg-[#121C2B] px-5 py-4 transition-colors hover:bg-[#16202F]"
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="truncate font-[family-name:var(--font-display)] text-base text-[#ECE7D8]">
                  {repo.name}
                </span>
                <StatusBadge status={repo.status} />
                {repo.primary_language && (
                  <span className="shrink-0 rounded-full border border-[#5FD3C4]/40 px-2 py-0.5 font-[family-name:var(--font-mono)] text-[10px] text-[#5FD3C4]">
                    {repo.primary_language}
                  </span>
                )}
              </div>
              <p className="mt-1 truncate font-[family-name:var(--font-mono)] text-xs text-[#8B98AC]">
                {repo.github_url.replace("https://", "")} · {repo.file_count} files · imported{" "}
                {new Date(repo.imported_at).toLocaleDateString(undefined, {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                })}
              </p>
            </div>

            <div className="flex shrink-0 items-center gap-3">
              <Link
                href={`/repo/${repo.id}`}
                className="flex items-center gap-1 font-[family-name:var(--font-mono)] text-xs text-[#8B98AC] hover:text-[#5FD3C4]"
              >
                Open
                <ExternalLink className="h-3 w-3" />
              </Link>
              <button
                type="button"
                onClick={() => handleDelete(repo.id, repo.name)}
                disabled={deletingId === repo.id}
                aria-label={`Delete ${repo.name}`}
                className="rounded p-1.5 text-[#8B98AC] transition-colors hover:bg-[#F2555C]/10 hover:text-[#F2555C] disabled:opacity-50"
              >
                {deletingId === repo.id ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Trash2 className="h-3.5 w-3.5" />
                )}
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    ready: "border-[#5FD3C4]/40 text-[#5FD3C4]",
    pending: "border-[#F2A93C]/40 text-[#F2A93C]",
    failed: "border-[#F2555C]/40 text-[#F2555C]",
  };
  return (
    <span
      className={cn(
        "shrink-0 rounded-full border px-2 py-0.5 font-[family-name:var(--font-mono)] text-[10px] uppercase tracking-wide",
        styles[status] ?? "border-[#8B98AC]/40 text-[#8B98AC]"
      )}
    >
      {status}
    </span>
  );
}