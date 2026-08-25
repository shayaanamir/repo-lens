"use client";

import { useState, type FormEvent } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ExternalLink, Loader2, Search as SearchIcon } from "lucide-react";

import {
    searchRepository,
    getFileContent,
    getRepository,
    ApiError,
    type SearchResult,
    type Repository,
} from "@/lib/api-client";

export default function SearchPage() {
    const params = useParams<{ id: string }>();
    const repositoryId = params.id;

    const [repo, setRepo] = useState<Repository | null>(null);
    const [query, setQuery] = useState("");
    const [submittedQuery, setSubmittedQuery] = useState<string | null>(null);
    const [results, setResults] = useState<SearchResult[] | null>(null);
    const [isSearching, setIsSearching] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [expandedKey, setExpandedKey] = useState<string | null>(null);

    // Fetch repo name lazily, just for the breadcrumb — not blocking search.
    useState(() => {
        getRepository(repositoryId).then(setRepo).catch(() => { });
    });

    async function handleSubmit(e: FormEvent) {
        e.preventDefault();
        if (!query.trim() || isSearching) return;

        setIsSearching(true);
        setError(null);
        setExpandedKey(null);

        try {
            const data = await searchRepository(repositoryId, query.trim());
            setResults(data.results);
            setSubmittedQuery(data.query);
        } catch (err) {
            setResults(null);
            setError(err instanceof ApiError ? err.detail : "Search failed. Is the backend running?");
        } finally {
            setIsSearching(false);
        }
    }

    return (
        <div className="flex flex-1 flex-col overflow-y-auto">
            <div className="flex items-center gap-2 border-b border-rl-border px-6 py-2.5">
                <Link
                    href={`/repo/${repositoryId}`}
                    className="flex items-center gap-1 font-mono text-xs text-rl-text-dim hover:text-rl-trace"
                >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    {repo?.name ?? "repository"}
                </Link>
                <span className="font-mono text-xs text-rl-text-dim">/ search</span>
            </div>

            <div className="mx-auto max-w-2xl px-6 py-12">
                <h1 className="font-[family-name:var(--font-display)] text-2xl text-rl-text">
                    Search by what code does
                </h1>
                <p className="mt-1 text-sm text-rl-text-dim">
                    Describe the behavior you're looking for — RepoLens matches by meaning, not just keywords.
                </p>

                <form onSubmit={handleSubmit} className="mt-6">
                    <div className="rounded-lg border border-rl-border bg-rl-surface p-1.5">
                        <div className="flex items-center gap-2 px-3 py-2">
                            <SearchIcon className="h-4 w-4 shrink-0 text-rl-text-dim" />
                            <input
                                type="text"
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                                placeholder="e.g. retries a failed network request"
                                className="flex-1 bg-transparent font-mono text-sm text-rl-text placeholder:text-rl-text-dim outline-none"
                                autoComplete="off"
                                spellCheck={false}
                            />
                            <button
                                type="submit"
                                disabled={isSearching || !query.trim()}
                                suppressHydrationWarning
                                className="shrink-0 rounded-md bg-rl-signal px-3 py-1.5 font-mono text-xs font-medium text-rl-bg transition-opacity hover:opacity-90 disabled:opacity-50"
                            >
                                {isSearching ? "Searching…" : "Search"}
                            </button>
                        </div>
                    </div>
                </form>

                <div className="mt-8">
                    {isSearching && (
                        <div className="flex items-center gap-2 py-8 font-mono text-xs text-rl-text-dim">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            embedding query and searching…
                        </div>
                    )}

                    {!isSearching && error && (
                        <p className="rounded-lg border border-rl-danger/30 bg-rl-danger-bg px-4 py-3 text-sm text-rl-danger">
                            {error}
                        </p>
                    )}

                    {!isSearching && !error && results !== null && results.length === 0 && (
                        <p className="font-mono text-sm text-rl-text-dim">
              // no results for &quot;{submittedQuery}&quot;
                        </p>
                    )}

                    {!isSearching && !error && results !== null && results.length > 0 && (
                        <div className="space-y-2">
                            <p className="font-mono text-xs text-rl-text-dim">
                                {results.length} result{results.length === 1 ? "" : "s"} for &quot;{submittedQuery}&quot;
                            </p>
                            {results.map((result) => {
                                const key = `${result.file_id}:${result.start_line}`;
                                return (
                                    <SearchResultRow
                                        key={key}
                                        result={result}
                                        repositoryId={repositoryId}
                                        expanded={expandedKey === key}
                                        onToggle={() => setExpandedKey(expandedKey === key ? null : key)}
                                    />
                                );
                            })}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

function SearchResultRow({
    result,
    repositoryId,
    expanded,
    onToggle,
}: {
    result: SearchResult;
    repositoryId: string;
    expanded: boolean;
    onToggle: () => void;
}) {
    const [snippet, setSnippet] = useState<string | null>(null);
    const [snippetLoading, setSnippetLoading] = useState(false);
    const [snippetError, setSnippetError] = useState<string | null>(null);

    async function handleToggle() {
        onToggle();
        if (!expanded && snippet === null && !snippetLoading) {
            setSnippetLoading(true);
            setSnippetError(null);
            try {
                const data = await getFileContent(repositoryId, result.path);
                const lines = data.content.split("\n");
                const excerpt = lines.slice(result.start_line - 1, result.end_line).join("\n");
                setSnippet(excerpt);
            } catch (err) {
                setSnippetError(err instanceof ApiError ? err.detail : "Couldn't load this snippet.");
            } finally {
                setSnippetLoading(false);
            }
        }
    }

    const scorePct = Math.round(Math.max(0, Math.min(1, result.score)) * 100);

    return (
        <div className="overflow-hidden rounded-lg border border-rl-border bg-rl-surface">
            <button
                type="button"
                onClick={handleToggle}
                className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-rl-border/30"
            >
                <div className="min-w-0">
                    <div className="flex items-center gap-2">
                        <span className="truncate font-mono text-xs text-rl-text">{result.path}</span>
                        <span className="shrink-0 font-mono text-[11px] text-rl-text-dim">
                            :{result.start_line}-{result.end_line}
                        </span>
                    </div>
                    {result.symbol_name && (
                        <span className="mt-1 inline-block rounded-full border border-rl-trace/40 px-2 py-0.5 font-mono text-[10px] text-rl-trace">
                            {result.symbol_kind} {result.symbol_name}
                        </span>
                    )}
                </div>
                <div className="flex shrink-0 items-center gap-2">
                    <div className="h-1 w-14 overflow-hidden rounded-full bg-rl-border">
                        <div className="h-full bg-rl-signal" style={{ width: `${scorePct}%` }} />
                    </div>
                    <span className="w-8 text-right font-mono text-[10px] text-rl-text-dim">{scorePct}%</span>
                </div>
            </button>

            {expanded && (
                <div className="border-t border-rl-border">
                    {snippetLoading ? (
                        <div className="flex items-center gap-2 px-4 py-3 font-mono text-xs text-rl-text-dim">
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            loading snippet…
                        </div>
                    ) : snippetError ? (
                        <p className="px-4 py-3 font-mono text-xs text-rl-danger">{snippetError}</p>
                    ) : (
                        <pre className="overflow-x-auto px-4 py-3 font-mono text-xs leading-relaxed text-rl-text">
                            {snippet}
                        </pre>
                    )}
                    <div className="border-t border-rl-border px-4 py-2">
                        <Link
                            href={`/repo/${repositoryId}/explorer?file=${encodeURIComponent(result.path)}`}
                            className="inline-flex items-center gap-1 font-mono text-[11px] text-rl-trace hover:underline"
                        >
                            Open in Explorer
                            <ExternalLink className="h-3 w-3" />
                        </Link>
                    </div>
                </div>
            )}
        </div>
    );
}