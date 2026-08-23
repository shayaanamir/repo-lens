"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
    CheckCircle2,
    Circle,
    ExternalLink,
    FileCode2,
    Loader2,
    MessageSquare,
    Network,
    Search,
    XCircle,
} from "lucide-react";

import { AppHeader } from "@/components/app-header";
import {
    getRepository,
    ApiError,
    type Repository,
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

    if (repoLoading) {
        return (
            <Page>
                <Centered>
                    <Loader2 className="h-5 w-5 animate-spin text-rl-text-dim" />
                </Centered>
            </Page>
        );
    }

    if (repoError || !repo) {
        return (
            <Page>
                <Centered>
                    <p className="font-[family-name:var(--font-display)] text-lg text-rl-text">
                        Repository not found
                    </p>
                    <p className="mt-1 font-mono text-xs text-rl-text-dim">{repoError}</p>
                    <Link href="/" className="mt-6 font-mono text-xs text-rl-trace underline underline-offset-4">
                        ← back to import a repository
                    </Link>
                </Centered>
            </Page>
        );
    }

    const isFailed = repo.status === "failed" || jobsPhase === "failed";
    const isReady = repo.status === "ready";

    return (
        <Page>
            <div className="mx-auto max-w-3xl px-6 py-12">
                <RepoHeader repo={repo} />

                {isFailed && <FailedState jobs={jobs} fallbackError={jobsError} />}

                {!isFailed && !isReady && <IndexingState jobs={jobs} jobsLoading={jobsLoading} />}

                {!isFailed && isReady && <ReadyState repo={repo} />}
            </div>
        </Page>
    );
}

// ---------------------------------------------------------------------
// Layout helpers
// ---------------------------------------------------------------------

function Page({ children }: { children: React.ReactNode }) {
    return (
        <div className="min-h-screen bg-rl-bg text-rl-text">
            <AppHeader />
            {children}
        </div>
    );
}

function Centered({ children }: { children: React.ReactNode }) {
    return (
        <div className="flex min-h-[60vh] flex-col items-center justify-center px-6 text-center">
            {children}
        </div>
    );
}

// ---------------------------------------------------------------------
// Header — name, url, language, imported date
// ---------------------------------------------------------------------

function RepoHeader({ repo }: { repo: Repository }) {
    const importedDate = new Date(repo.imported_at).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
    });

    return (
        <div className="border-b border-rl-border pb-6">
            <Link href="/" className="font-mono text-xs text-rl-text-dim hover:text-rl-trace">
                ← all repositories
            </Link>

            <div className="mt-3 flex flex-wrap items-center gap-3">
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
                <a href={repo.github_url}
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
        </div >
    );
}

// ---------------------------------------------------------------------
// Indexing state — mirrors the landing page's pipeline strip, live
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

// ---------------------------------------------------------------------
// Failed state
// ---------------------------------------------------------------------

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
// Ready state
// ---------------------------------------------------------------------

function ReadyState({ repo }: { repo: Repository }) {
    return (
        <div className="space-y-10 py-8">
            <section>
                <p className="font-mono text-xs uppercase tracking-widest text-rl-text-dim">summary</p>
                {repo.summary ? (
                    <p className="mt-2 text-sm leading-relaxed text-rl-text">{repo.summary}</p>
                ) : (
                    <p className="mt-2 text-sm italic text-rl-text-dim">
                        No AI summary available for this repository — everything else still works.
                    </p>
                )}
            </section>

            {repo.readme_content && <ReadmePreview content={repo.readme_content} />}

            <section>
                <p className="font-mono text-xs uppercase tracking-widest text-rl-text-dim">explore</p>
                <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <NavCard
                        href={`/repo/${repo.id}/explorer`}
                        icon={<FileCode2 className="h-5 w-5" />}
                        title="Explorer"
                        description="Browse the file tree and read source."
                    />
                    <NavCard
                        href={`/repo/${repo.id}/graph`}
                        icon={<Network className="h-5 w-5" />}
                        title="Dependency Graph"
                        description="See how files import one another."
                    />
                    <NavCard
                        href={`/repo/${repo.id}/search`}
                        icon={<Search className="h-5 w-5" />}
                        title="Search"
                        description="Find code by describing what it does."
                    />
                    <NavCard
                        href={`/repo/${repo.id}/chat`}
                        icon={<MessageSquare className="h-5 w-5" />}
                        title="Chat"
                        description="Ask questions, grounded in real source."
                    />
                </div>
            </section>
        </div>
    );
}

function ReadmePreview({ content }: { content: string }) {
    const [expanded, setExpanded] = useState(false);
    const TRUNCATE_AT = 600;
    const isLong = content.length > TRUNCATE_AT;
    const shown = expanded || !isLong ? content : content.slice(0, TRUNCATE_AT) + "…";

    return (
        <section>
            <p className="font-mono text-xs uppercase tracking-widest text-rl-text-dim">readme</p>
            <div className="mt-2 overflow-hidden rounded-lg border border-rl-border bg-rl-surface">
                <div className="border-b border-rl-border px-4 py-2">
                    <span className="font-mono text-xs text-rl-text-dim">$ cat README.md</span>
                </div>
                <pre className="max-h-96 overflow-auto whitespace-pre-wrap px-4 py-3 font-mono text-xs leading-relaxed text-rl-text">
                    {shown}
                </pre>
            </div>
            {isLong && (
                <button
                    type="button"
                    onClick={() => setExpanded((v) => !v)}
                    className="mt-2 font-mono text-xs text-rl-trace underline underline-offset-4"
                >
                    {expanded ? "show less" : "show more"}
                </button>
            )}
        </section>
    );
}

function NavCard({
    href,
    icon,
    title,
    description,
}: {
    href: string;
    icon: React.ReactNode;
    title: string;
    description: string;
}) {
    return (
        <Link
            href={href}
            className="group flex items-start gap-3 rounded-lg border border-rl-border bg-rl-surface p-4 transition-colors hover:border-rl-trace"
        >
            <span className="text-rl-text-dim transition-colors group-hover:text-rl-trace">
                {icon}
            </span>
            <span>
                <span className="block font-[family-name:var(--font-display)] text-sm text-rl-text">
                    {title}
                </span>
                <span className="block font-mono text-xs text-rl-text-dim">{description}</span>
            </span>
        </Link>
    );
}