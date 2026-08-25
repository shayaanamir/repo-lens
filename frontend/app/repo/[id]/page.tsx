"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
    CheckCircle2,
    Circle,
    ExternalLink,
    Loader2,
    Sparkles,
    XCircle,
} from "lucide-react";

import {
    getRepository,
    getRepositoryStats,
    ApiError,
    type Repository,
    type RepositoryStats,
    type Job,
    type JobStage,
    type JobStatus,
} from "@/lib/api-client";
import { useJobStatus } from "@/hooks/useJobStatus";

const STAGE_LABELS: Record<JobStage, string> = {
    clone: "Clone",
    parse: "Parse",
    embed: "Embed",
    summarize: "Summarize",
};

const STAGE_ORDER: JobStage[] = ["clone", "parse", "embed", "summarize"];

export default function RepositoryDashboard() {
    const params = useParams<{ id: string }>();
    const repositoryId = params.id;

    const [repo, setRepo] = useState<Repository | null>(null);
    const [repoError, setRepoError] = useState<string | null>(null);
    const [repoLoading, setRepoLoading] = useState(true);
    const [stats, setStats] = useState<RepositoryStats | null>(null);

    const {
        jobs,
        phase: jobsPhase,
        error: jobsError,
        isLoading: jobsLoading,
    } = useJobStatus(repositoryId ?? null);

    useEffect(() => {
        if (!repositoryId) return;
        let cancelled = false;

        async function load() {
            try {
                const data = await getRepository(repositoryId);
                if (!cancelled) setRepo(data);
            } catch (err) {
                if (cancelled) return;
                setRepoError(err instanceof ApiError ? err.detail : "Couldn't load this repository.");
            } finally {
                if (!cancelled) setRepoLoading(false);
            }
        }

        load();
        const interval = setInterval(load, 3000);
        return () => {
            cancelled = true;
            clearInterval(interval);
        };
    }, [repositoryId]);

    useEffect(() => {
        if (!repositoryId || repo?.status !== "ready") return;
        let cancelled = false;
        getRepositoryStats(repositoryId)
            .then((data) => {
                if (!cancelled) setStats(data);
            })
            .catch(() => {
                // stats are supplementary — a failure here shouldn't block the dashboard
            });
        return () => {
            cancelled = true;
        };
    }, [repositoryId, repo?.status]);

    if (repoLoading) {
        return (
            <Centered>
                <Loader2 className="h-5 w-5 animate-spin text-rl-text-dim" />
            </Centered>
        );
    }

    if (repoError || !repo) {
        return (
            <Centered>
                <p className="font-[family-name:var(--font-display)] text-lg text-rl-text">
                    Repository not found
                </p>
                <p className="mt-1 font-mono text-xs text-rl-text-dim">{repoError}</p>
                <Link href="/" className="mt-6 font-mono text-xs text-rl-trace underline underline-offset-4">
                    ← back to import a repository
                </Link>
            </Centered>
        );
    }

    const isFailed = repo.status === "failed" || jobsPhase === "failed";
    const isReady = repo.status === "ready";

    return (
        <div className="flex-1 overflow-y-auto">
            <div className="mx-auto max-w-6xl px-8 py-8">
                <RepoHeader repo={repo} />

                {isFailed && <FailedState jobs={jobs} fallbackError={jobsError} />}
                {!isFailed && !isReady && <IndexingState jobs={jobs} jobsLoading={jobsLoading} />}
                {!isFailed && isReady && <DashboardBody repo={repo} stats={stats} />}
            </div>
        </div>
    );
}

function Centered({ children }: { children: React.ReactNode }) {
    return (
        <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
            {children}
        </div>
    );
}

function RepoHeader({ repo }: { repo: Repository }) {
    const importedDate = new Date(repo.imported_at).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
    });

    return (
        <div className="border-b border-rl-border pb-6">
            <div className="flex flex-wrap items-center gap-3">
                <h1 className="font-[family-name:var(--font-display)] text-3xl text-rl-text">
                    {repo.name}
                </h1>
                {repo.primary_language && (
                    <span className="rounded-full border border-rl-trace/40 px-2.5 py-0.5 font-mono text-xs text-rl-trace">
                        {repo.primary_language}
                    </span>
                )}
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-xs text-rl-text-dim">
                <a
                    href={repo.github_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 hover:text-rl-trace"
                >
                    {repo.github_url.replace("https://", "")}
                    <ExternalLink className="h-3 w-3" />
                </a>
                <span>·</span>
                <span>imported {importedDate}</span>
                <span>·</span>
                <span>{repo.status}</span>
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------
// Indexing / failed states
// ---------------------------------------------------------------------

function IndexingState({ jobs, jobsLoading }: { jobs: Job[]; jobsLoading: boolean }) {
    if (jobsLoading && jobs.length === 0) {
        return (
            <div className="flex flex-col items-center gap-3 py-20 text-center">
                <Loader2 className="h-5 w-5 animate-spin text-rl-text-dim" />
                <p className="font-mono text-xs text-rl-text-dim">getting things started…</p>
            </div>
        );
    }

    return (
        <div className="py-10">
            <p className="font-mono text-xs uppercase tracking-widest text-rl-text-dim">
                indexing in progress
            </p>
            <div className="mt-6 grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-rl-border sm:grid-cols-4">
                {STAGE_ORDER.map((stage, i) => {
                    const job = jobs.find((j) => j.stage === stage);
                    const status = job?.status ?? "pending";
                    return (
                        <div key={stage} className="bg-rl-surface px-5 py-6">
                            <div className="flex items-center justify-between">
                                <span className="font-mono text-xs text-rl-trace">
                                    {String(i + 1).padStart(2, "0")}
                                </span>
                                <StageIcon status={status} />
                            </div>
                            <h3 className="mt-3 font-[family-name:var(--font-display)] text-base text-rl-text">
                                {STAGE_LABELS[stage]}
                            </h3>
                            <p className="mt-1 font-mono text-[11px] text-rl-text-dim">
                                {status === "running" ? "in progress…" : status}
                            </p>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

function StageIcon({ status }: { status: JobStatus }) {
    if (status === "completed") return <CheckCircle2 className="h-4 w-4 text-rl-trace" />;
    if (status === "running") return <Loader2 className="h-4 w-4 animate-spin text-rl-signal" />;
    if (status === "failed") return <XCircle className="h-4 w-4 text-rl-danger" />;
    return <Circle className="h-4 w-4 text-rl-text-dim/40" />;
}

function FailedState({ jobs, fallbackError }: { jobs: Job[]; fallbackError: string | null }) {
    const failedJob = jobs.find((j) => j.status === "failed");

    return (
        <div className="mt-8 rounded-lg border border-rl-danger/30 bg-rl-danger-bg p-5">
            <p className="font-medium text-rl-danger">
                Indexing failed{failedJob ? ` at the ${STAGE_LABELS[failedJob.stage]} stage` : ""}
            </p>
            <p className="mt-1 text-sm text-rl-text-dim">
                {failedJob?.error ?? fallbackError ?? "Something went wrong during indexing."}
            </p>
            <p className="mt-3 font-mono text-xs text-rl-text-dim">
                retry with{" "}
                <code className="rounded bg-rl-surface px-1 py-0.5 text-rl-text">
                    python -m scripts.retry_job
                </code>
            </p>
        </div>
    );
}

// ---------------------------------------------------------------------
// Ready state — the redesigned two-column dashboard
// ---------------------------------------------------------------------

function DashboardBody({ repo, stats }: { repo: Repository; stats: RepositoryStats | null }) {
    return (
        <div className="grid grid-cols-1 gap-8 py-8 lg:grid-cols-[1fr_320px]">
            <div className="space-y-8">
                <SummaryCard repo={repo} stats={stats} />
                <StartHere modules={stats?.modules ?? []} />
                <ModulesTable modules={stats?.modules ?? []} repositoryId={repo.id} />
            </div>
            <div className="space-y-8">
                <PipelineCard stats={stats} />
                <ExtractedFacts stats={stats} />
                <LanguagesCard stats={stats} />
            </div>
        </div>
    );
}

function SummaryCard({ repo, stats }: { repo: Repository; stats: RepositoryStats | null }) {
    const groundedIn = (stats?.modules ?? []).slice(0, 3);

    return (
        <section className="rounded-lg border-l-2 border-rl-trace bg-rl-surface p-6">
            <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-rl-trace">
                <Sparkles className="h-3.5 w-3.5" />
                Repository summary · generated once at index time
            </div>

            {repo.summary ? (
                <p className="mt-4 text-[15px] leading-relaxed text-rl-text">{repo.summary}</p>
            ) : (
                <p className="mt-4 text-sm italic text-rl-text-dim">
                    No AI summary available for this repository — everything else still works.
                </p>
            )}

            {groundedIn.length > 0 && (
                <div className="mt-5 border-t border-rl-border pt-4">
                    <p className="font-mono text-[11px] uppercase tracking-widest text-rl-text-dim">
                        ↳ grounded in
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2">
                        {groundedIn.map((m) => (
                            <Link
                                key={m.path}
                                href={`/repo/${repo.id}/explorer?file=${encodeURIComponent(m.path)}`}
                                className="rounded border border-rl-border px-2.5 py-1 font-mono text-[11px] text-rl-text-dim hover:border-rl-trace hover:text-rl-trace"
                            >
                                {m.path}
                                {m.start_line && m.end_line ? ` L${m.start_line}-${m.end_line}` : ""}
                            </Link>
                        ))}
                    </div>
                </div>
            )}
        </section>
    );
}

function describeModule(m: { in_degree: number; out_degree: number }): string {
    if (m.in_degree === 0 && m.out_degree > 0) {
        return `Entry point — imports ${m.out_degree} file${m.out_degree === 1 ? "" : "s"}, referenced by none in-repo`;
    }
    if (m.out_degree === 0 && m.in_degree > 0) {
        return `Leaf module — referenced by ${m.in_degree} file${m.in_degree === 1 ? "" : "s"}, imports nothing else`;
    }
    return `Core module — referenced by ${m.in_degree}, imports ${m.out_degree}`;
}

function StartHere({ modules }: { modules: RepositoryStats["modules"] }) {
    const top = modules.slice(0, 3);
    if (top.length === 0) return null;

    return (
        <section>
            <p className="font-mono text-xs uppercase tracking-widest text-rl-text-dim">start here</p>
            <div className="mt-3 divide-y divide-rl-border border-y border-rl-border">
                {top.map((m, i) => (
                    <div key={m.path} className="flex items-start justify-between gap-4 py-4">
                        <div className="flex gap-4">
                            <span className="font-mono text-xs text-rl-signal">
                                {String(i + 1).padStart(2, "0")}
                            </span>
                            <div>
                                <p className="font-mono text-sm text-rl-text">{m.path}</p>
                                <p className="mt-1 text-xs text-rl-text-dim">{describeModule(m)}</p>
                            </div>
                        </div>
                        <span className="shrink-0 font-mono text-xs text-rl-text-dim">
                            {m.in_degree + m.out_degree} refs
                        </span>
                    </div>
                ))}
            </div>
        </section>
    );
}

function ModulesTable({
    modules,
    repositoryId,
}: {
    modules: RepositoryStats["modules"];
    repositoryId: string;
}) {
    if (modules.length === 0) return null;

    return (
        <section>
            <div className="flex items-center justify-between">
                <p className="font-mono text-xs uppercase tracking-widest text-rl-text-dim">
                    most referenced modules
                </p>
                <Link
                    href={`/repo/${repositoryId}/graph`}
                    className="font-mono text-xs text-rl-signal hover:underline"
                >
                    Open dependency graph
                </Link>
            </div>

            <table className="mt-3 w-full border-collapse font-mono text-xs">
                <thead>
                    <tr className="border-b border-rl-border text-rl-text-dim">
                        <th className="py-2 text-left font-normal">Path</th>
                        <th className="py-2 text-right font-normal">Symbols</th>
                        <th className="py-2 text-right font-normal">In</th>
                        <th className="py-2 text-right font-normal">Out</th>
                    </tr>
                </thead>
                <tbody>
                    {modules.map((m) => (
                        <tr key={m.path} className="border-b border-rl-border/60">
                            <td className="py-2.5 text-rl-text">
                                <Link
                                    href={`/repo/${repositoryId}/explorer?file=${encodeURIComponent(m.path)}`}
                                    className="hover:text-rl-trace"
                                >
                                    {m.path}
                                </Link>
                            </td>
                            <td className="py-2.5 text-right text-rl-text-dim">{m.symbol_count}</td>
                            <td className="py-2.5 text-right text-rl-text-dim">{m.in_degree}</td>
                            <td className="py-2.5 text-right text-rl-text-dim">{m.out_degree}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </section>
    );
}

function PipelineCard({ stats }: { stats: RepositoryStats | null }) {
    return (
        <section>
            <p className="font-mono text-xs uppercase tracking-widest text-rl-text-dim">index pipeline</p>
            <div className="mt-3 space-y-4">
                {STAGE_ORDER.map((stage) => {
                    const s = stats?.stages.find((x) => x.stage === stage);
                    return (
                        <div key={stage} className="flex items-start gap-2.5">
                            {s?.status === "completed" ? (
                                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-rl-signal" />
                            ) : s?.status === "failed" ? (
                                <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-rl-danger" />
                            ) : (
                                <Circle className="mt-0.5 h-4 w-4 shrink-0 text-rl-text-dim/40" />
                            )}
                            <div>
                                <p className="font-mono text-xs font-medium tracking-wide text-rl-text">
                                    {STAGE_LABELS[stage].toUpperCase()}
                                </p>
                                <p className="mt-0.5 font-mono text-[11px] text-rl-text-dim">
                                    {s?.detail ?? "—"}
                                </p>
                            </div>
                        </div>
                    );
                })}
            </div>

            {stats?.completed_at && (
                <p className="mt-4 border-t border-rl-border pt-3 font-mono text-[11px] text-rl-text-dim">
                    Completed in {formatDuration(stats.duration_seconds)} ·{" "}
                    {new Date(stats.completed_at).toLocaleString(undefined, {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                    })}
                </p>
            )}
        </section>
    );
}

function formatDuration(seconds: number | null): string {
    if (seconds == null) return "—";
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function ExtractedFacts({ stats }: { stats: RepositoryStats | null }) {
    const items = [
        { label: "Files", value: stats?.file_count },
        { label: "Symbols", value: stats?.symbol_count },
        { label: "Edges", value: stats?.edge_count },
        { label: "Chunks", value: stats?.chunk_count },
    ];

    return (
        <section>
            <p className="font-mono text-xs uppercase tracking-widest text-rl-text-dim">extracted facts</p>
            <div className="mt-3 grid grid-cols-2 gap-4">
                {items.map((item) => (
                    <div key={item.label}>
                        <p className="font-mono text-[11px] uppercase tracking-widest text-rl-text-dim">
                            {item.label}
                        </p>
                        <p className="mt-1 font-[family-name:var(--font-display)] text-2xl text-rl-text">
                            {item.value ?? "—"}
                        </p>
                    </div>
                ))}
            </div>
        </section>
    );
}

function LanguagesCard({ stats }: { stats: RepositoryStats | null }) {
    const languages = stats?.languages ?? [];
    if (languages.length === 0) return null;

    return (
        <section>
            <p className="font-mono text-xs uppercase tracking-widest text-rl-text-dim">languages</p>
            <div className="mt-3 space-y-3">
                {languages.map((l) => (
                    <div key={l.language}>
                        <div className="flex items-center justify-between font-mono text-xs text-rl-text">
                            <span>{l.language}</span>
                            <span className="text-rl-text-dim">{l.percentage}%</span>
                        </div>
                        <div className="mt-1 h-1 overflow-hidden rounded-full bg-rl-border">
                            <div className="h-full bg-rl-signal" style={{ width: `${l.percentage}%` }} />
                        </div>
                    </div>
                ))}
            </div>
        </section>
    );
}