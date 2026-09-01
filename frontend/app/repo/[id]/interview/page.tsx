"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
    ArrowLeft,
    ChevronRight,
    Loader2,
    Mic,
    RefreshCw,
    Sparkles,
    StickyNote,
} from "lucide-react";

import {
    getInterviewPrep,
    getRepository,
    getRepositoryStats,
    ApiError,
    type InterviewPrepResponse,
    type Repository,
    type RepositoryStats,
} from "@/lib/api-client";
import { MarkdownContent } from "@/components/markdown-content";
import { cn } from "@/lib/utils";

type SectionKey = "pitch" | "walkthrough" | "questions" | "tricky";

const SECTIONS: { key: SectionKey; number: string; title: string }[] = [
    { key: "pitch", number: "01", title: "Elevator pitch" },
    { key: "walkthrough", number: "02", title: "Walkthrough" },
    { key: "questions", number: "03", title: "Likely questions" },
    { key: "tricky", number: "04", title: "Tricky decisions" },
];

export default function InterviewPrepPage() {
    const params = useParams<{ id: string }>();
    const repositoryId = params.id;

    const [repo, setRepo] = useState<Repository | null>(null);
    const [stats, setStats] = useState<RepositoryStats | null>(null);
    const [result, setResult] = useState<InterviewPrepResponse | null>(null);
    const [context, setContext] = useState("");
    const [notesOpen, setNotesOpen] = useState(false);
    const [selected, setSelected] = useState<SectionKey>("pitch");
    const [isGenerating, setIsGenerating] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [hasLoadedMeta, setHasLoadedMeta] = useState(false);

    if (!hasLoadedMeta && repositoryId) {
        setHasLoadedMeta(true);
        getRepository(repositoryId).then(setRepo).catch(() => { });
        getRepositoryStats(repositoryId).then(setStats).catch(() => { });
    }

    async function handleGenerate() {
        if (isGenerating) return;
        setIsGenerating(true);
        setError(null);
        try {
            const data = await getInterviewPrep(repositoryId, context);
            setResult(data);
            setSelected("pitch");
            setNotesOpen(false);
        } catch (err) {
            setError(
                err instanceof ApiError ? err.detail : "Couldn't reach RepoLens. Check that the backend is running."
            );
        } finally {
            setIsGenerating(false);
        }
    }

    const readTime = useMemo(() => {
        if (!result) return null;
        const words =
            result.pitch.split(/\s+/).length +
            result.talking_points.join(" ").split(/\s+/).length +
            result.questions.map((q) => `${q.question} ${q.answer}`).join(" ").split(/\s+/).length;
        const seconds = Math.max(Math.round((words / 200) * 60), 10);
        return seconds < 90 ? `~${seconds}s` : `~${Math.round(seconds / 60)}m`;
    }, [result]);

    return (
        <div className="flex flex-1 flex-col overflow-hidden">
            <div className="flex items-center gap-2 border-b border-rl-border px-6 py-2.5">
                <Link
                    href={`/repo/${repositoryId}`}
                    className="flex items-center gap-1 font-mono text-xs text-rl-text-dim hover:text-rl-trace"
                >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    {repo?.name ?? "repository"}
                </Link>
                <span className="font-mono text-xs text-rl-text-dim">/ interview prep</span>
            </div>

            {!result ? (
                <PromptState
                    context={context}
                    setContext={setContext}
                    onGenerate={handleGenerate}
                    isGenerating={isGenerating}
                    error={error}
                />
            ) : (
                <div className="flex flex-1 flex-col overflow-hidden">
                    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-rl-border px-6 py-4">
                        <div>
                            <h1 className="font-[family-name:var(--font-display)] text-xl text-rl-text">
                                Interview brief
                            </h1>
                            <p className="mt-0.5 font-mono text-xs text-rl-text-dim">
                                {repo?.name ?? "repository"}
                                {stats && ` · ${stats.symbol_count} symbols · ${stats.edge_count} edges`}
                            </p>
                        </div>
                        <div className="flex items-center gap-2">
                            <button
                                type="button"
                                onClick={handleGenerate}
                                disabled={isGenerating}
                                className="flex items-center gap-1.5 rounded-md border border-rl-border px-2.5 py-1.5 font-mono text-[11px] uppercase tracking-widest text-rl-text-dim transition-colors hover:border-rl-trace hover:text-rl-trace disabled:opacity-50"
                            >
                                {isGenerating ? (
                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                ) : (
                                    <RefreshCw className="h-3.5 w-3.5" />
                                )}
                                Rebuild
                            </button>
                            <button
                                type="button"
                                onClick={() => setNotesOpen((v) => !v)}
                                className={cn(
                                    "flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 font-mono text-[11px] uppercase tracking-widest transition-colors",
                                    notesOpen
                                        ? "border-rl-signal/50 bg-rl-signal/10 text-rl-signal"
                                        : "border-rl-border text-rl-text-dim hover:border-rl-trace hover:text-rl-trace"
                                )}
                            >
                                <StickyNote className="h-3.5 w-3.5" />
                                Notes
                            </button>
                        </div>
                    </div>

                    {notesOpen && (
                        <NotesPanel
                            context={context}
                            setContext={setContext}
                            onGenerate={handleGenerate}
                            isGenerating={isGenerating}
                        />
                    )}

                    {error && (
                        <p className="border-b border-rl-danger/30 bg-rl-danger-bg px-6 py-2.5 font-mono text-xs text-rl-danger">
                            {error}
                        </p>
                    )}

                    <div className="flex flex-1 overflow-hidden">
                        <aside className="w-72 shrink-0 overflow-y-auto border-r border-rl-border">
                            {SECTIONS.map((s) => (
                                <button
                                    key={s.key}
                                    type="button"
                                    onClick={() => setSelected(s.key)}
                                    className={cn(
                                        "flex w-full items-start gap-3 border-l-2 px-5 py-4 text-left transition-colors",
                                        selected === s.key
                                            ? "border-rl-signal bg-rl-signal/5"
                                            : "border-transparent hover:bg-rl-border/20"
                                    )}
                                >
                                    <span
                                        className={cn(
                                            "font-mono text-xs",
                                            selected === s.key ? "text-rl-signal" : "text-rl-text-dim"
                                        )}
                                    >
                                        {s.number}
                                    </span>
                                    <div>
                                        <p
                                            className={cn(
                                                "font-[family-name:var(--font-display)] text-sm",
                                                selected === s.key ? "text-rl-text" : "text-rl-text-dim"
                                            )}
                                        >
                                            {s.title}
                                        </p>
                                        <p className="mt-0.5 font-mono text-[10px] uppercase tracking-widest text-rl-text-dim">
                                            {sectionSubtitle(s.key, result, context)}
                                        </p>
                                    </div>
                                </button>
                            ))}
                        </aside>

                        <main className="flex-1 overflow-y-auto px-8 py-6">
                            <p className="font-mono text-xs uppercase tracking-widest text-rl-signal">
                                {SECTIONS.find((s) => s.key === selected)!.number} ·{" "}
                                {SECTIONS.find((s) => s.key === selected)!.title}
                            </p>

                            <div className="mt-4 max-w-3xl">
                                {selected === "pitch" && <PitchView result={result} repositoryId={repositoryId} />}
                                {selected === "walkthrough" && <WalkthroughView points={result.talking_points} />}
                                {selected === "questions" && <QuestionsView questions={result.questions} />}
                                {selected === "tricky" && <TrickyDecisionsView context={context} />}
                            </div>

                            {selected === "pitch" && (
                                <div className="mt-8 grid max-w-3xl grid-cols-3 gap-6 border-t border-rl-border pt-6">
                                    <Stat label="Talking points" value={String(result.talking_points.length)} />
                                    <Stat label="Grounded modules" value={String(result.grounded_in.length)} />
                                    <Stat label="Est. read time" value={readTime ?? "—"} />
                                </div>
                            )}

                            <p className="mt-8 max-w-3xl border-t border-rl-border pt-4 font-mono text-[11px] text-rl-text-dim">
                                Generated from parsed symbols and import edges · rebuild to regenerate
                            </p>
                        </main>
                    </div>
                </div>
            )}
        </div>
    );
}

function sectionSubtitle(key: SectionKey, result: InterviewPrepResponse, context: string): string {
    switch (key) {
        case "pitch":
            return "1 paragraph";
        case "walkthrough":
            return `${result.talking_points.length} point${result.talking_points.length === 1 ? "" : "s"}`;
        case "questions":
            return `${result.questions.length} answer${result.questions.length === 1 ? "" : "s"}`;
        case "tricky":
            return context.trim() ? "1 from you" : "none added";
    }
}

function Stat({ label, value }: { label: string; value: string }) {
    return (
        <div>
            <p className="font-mono text-[11px] uppercase tracking-widest text-rl-text-dim">{label}</p>
            <p className="mt-1 font-[family-name:var(--font-display)] text-2xl text-rl-text">{value}</p>
        </div>
    );
}

function PitchView({ result, repositoryId }: { result: InterviewPrepResponse; repositoryId: string }) {
    return (
        <div className="rounded-lg border-l-2 border-rl-trace bg-rl-surface p-5">
            <MarkdownContent content={result.pitch} className="text-[15px]" />

            {result.grounded_in.length > 0 && (
                <div className="mt-5 border-t border-rl-border pt-4">
                    <p className="font-mono text-[11px] uppercase tracking-widest text-rl-trace">↳ Grounded in</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                        {result.grounded_in.map((s, i) => (
                            <Link
                                key={`${s.path}-${i}`}
                                href={`/repo/${repositoryId}/explorer?file=${encodeURIComponent(s.path)}`}
                                className="rounded border border-rl-border px-2.5 py-1 font-mono text-[11px] text-rl-text-dim hover:border-rl-trace hover:text-rl-trace"
                            >
                                {s.path} L{s.start_line}-{s.end_line}
                            </Link>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

function WalkthroughView({ points }: { points: string[] }) {
    if (points.length === 0) {
        return <p className="font-mono text-xs text-rl-text-dim">No talking points were generated.</p>;
    }
    return (
        <ol className="space-y-4">
            {points.map((point, i) => (
                <li key={i} className="flex gap-3 rounded-lg border border-rl-border bg-rl-surface p-4">
                    <span className="shrink-0 font-mono text-xs text-rl-signal">{String(i + 1).padStart(2, "0")}</span>
                    <p className="text-sm leading-relaxed text-rl-text">{point}</p>
                </li>
            ))}
        </ol>
    );
}

function QuestionsView({ questions }: { questions: { question: string; answer: string }[] }) {
    const [openIndex, setOpenIndex] = useState<number | null>(0);

    if (questions.length === 0) {
        return <p className="font-mono text-xs text-rl-text-dim">No questions were generated.</p>;
    }

    return (
        <div className="space-y-2">
            {questions.map((qa, i) => {
                const open = openIndex === i;
                return (
                    <div key={i} className="overflow-hidden rounded-lg border border-rl-border bg-rl-surface">
                        <button
                            type="button"
                            onClick={() => setOpenIndex(open ? null : i)}
                            className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-rl-border/20"
                        >
                            <span className="text-sm font-medium text-rl-text">{qa.question}</span>
                            <ChevronRight
                                className={cn("h-4 w-4 shrink-0 text-rl-text-dim transition-transform", open && "rotate-90")}
                            />
                        </button>
                        {open && (
                            <div className="border-t border-rl-border px-4 py-3">
                                <p className="text-sm leading-relaxed text-rl-text-dim">{qa.answer}</p>
                            </div>
                        )}
                    </div>
                );
            })}
        </div>
    );
}

function TrickyDecisionsView({ context }: { context: string }) {
    if (!context.trim()) {
        return (
            <div className="rounded-lg border border-dashed border-rl-border p-5">
                <p className="text-sm text-rl-text-dim">
                    You haven&apos;t added any notes yet. Open <span className="text-rl-text">Notes</span> above and
                    describe a hard problem you solved — RepoLens will weave it into a question the next time you
                    rebuild.
                </p>
            </div>
        );
    }
    return (
        <div className="rounded-lg border-l-2 border-rl-signal bg-rl-surface p-5">
            <p className="font-mono text-[11px] uppercase tracking-widest text-rl-signal">Your notes</p>
            <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-rl-text">{context}</p>
        </div>
    );
}

function NotesPanel({
    context,
    setContext,
    onGenerate,
    isGenerating,
}: {
    context: string;
    setContext: (v: string) => void;
    onGenerate: () => void;
    isGenerating: boolean;
}) {
    return (
        <div className="border-b border-rl-border bg-rl-surface px-6 py-4">
            <p className="font-mono text-[11px] uppercase tracking-widest text-rl-text-dim">
                Notes on hard problems you solved
            </p>
            <textarea
                value={context}
                onChange={(e) => setContext(e.target.value)}
                placeholder="e.g. I debugged a race condition in the retry queue that only showed up under load…"
                rows={3}
                className="mt-2 w-full resize-none rounded-md border border-rl-border bg-rl-bg p-3 text-sm text-rl-text placeholder:text-rl-text-dim outline-none focus:border-rl-trace"
            />
            <button
                type="button"
                onClick={onGenerate}
                disabled={isGenerating}
                className="mt-3 flex items-center gap-1.5 rounded-md bg-rl-signal px-3 py-1.5 font-mono text-xs font-medium text-rl-bg transition-opacity hover:opacity-90 disabled:opacity-50"
            >
                {isGenerating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                Rebuild with these notes
            </button>
        </div>
    );
}

function PromptState({
    context,
    setContext,
    onGenerate,
    isGenerating,
    error,
}: {
    context: string;
    setContext: (v: string) => void;
    onGenerate: () => void;
    isGenerating: boolean;
    error: string | null;
}) {
    return (
        <div className="flex flex-1 items-center justify-center px-6">
            <div className="w-full max-w-lg rounded-lg border border-l-2 border-rl-border border-l-rl-signal bg-rl-surface p-6">
                <div className="flex items-center gap-2 font-mono text-[11px] font-semibold uppercase tracking-widest text-rl-signal">
                    <Mic className="h-3.5 w-3.5" />
                    Interview prep
                </div>
                <p className="mt-2 text-sm leading-relaxed text-rl-text-dim">
                    Generates an elevator pitch, an architecture walkthrough, and likely interview questions —
                    grounded in this repository&apos;s parsed structure.
                </p>

                <label className="mt-5 block font-mono text-[11px] uppercase tracking-widest text-rl-text-dim">
                    Optional: a hard problem you solved
                </label>
                <textarea
                    value={context}
                    onChange={(e) => setContext(e.target.value)}
                    placeholder="e.g. I fought a nasty race condition in the connection pool…"
                    rows={3}
                    className="mt-2 w-full resize-none rounded-md border border-rl-border bg-rl-bg p-3 text-sm text-rl-text placeholder:text-rl-text-dim outline-none focus:border-rl-trace"
                />

                {error && <p className="mt-3 font-mono text-xs text-rl-danger">{error}</p>}

                <button
                    type="button"
                    onClick={onGenerate}
                    disabled={isGenerating}
                    className="mt-4 flex w-full items-center justify-center gap-2 rounded-md border border-rl-signal/40 px-3 py-2 font-mono text-[11px] font-medium uppercase tracking-widest text-rl-signal transition-colors hover:bg-rl-signal/10 disabled:opacity-50"
                >
                    {isGenerating ? (
                        <>
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            Generating…
                        </>
                    ) : (
                        <>
                            <Sparkles className="h-3.5 w-3.5" />
                            Generate interview prep
                        </>
                    )}
                </button>
            </div>
        </div>
    );
}