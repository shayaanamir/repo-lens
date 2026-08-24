"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { useTheme } from "next-themes";
import Editor from "@monaco-editor/react";
import { MarkdownContent } from "@/components/markdown-content";
import {
    ArrowLeft,
    Check,
    Copy,
    Loader2,
    RefreshCw,
    Sparkles,
} from "lucide-react";

import { AppHeader } from "@/components/app-header";
import { FileTreeView } from "@/components/file-tree-view";
import { buildFileTree, type FileTreeNode } from "@/lib/file-tree";
import {
    listFiles,
    getFileContent,
    getRepository,
    explainFile,
    ApiError,
    type FileEntry,
    type Repository,
    type SourceRef,
} from "@/lib/api-client";

const LANGUAGE_TO_MONACO: Record<string, string> = {
    Python: "python",
    JavaScript: "javascript",
    TypeScript: "typescript",
    Java: "java",
    Go: "go",
    Ruby: "ruby",
    Rust: "rust",
    C: "c",
    "C++": "cpp",
    "C#": "csharp",
    PHP: "php",
    Swift: "swift",
    Kotlin: "kotlin",
    Scala: "scala",
    HTML: "html",
    CSS: "css",
    SCSS: "scss",
    Shell: "shell",
    SQL: "sql",
    Markdown: "markdown",
    JSON: "json",
    YAML: "yaml",
};

function monacoLanguageFor(language: string | null): string {
    return language ? LANGUAGE_TO_MONACO[language] ?? "plaintext" : "plaintext";
}

function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function RepositoryExplorer() {
    const params = useParams<{ id: string }>();
    const repositoryId = params.id;
    const { resolvedTheme } = useTheme();

    const [repo, setRepo] = useState<Repository | null>(null);
    const [files, setFiles] = useState<FileEntry[] | null>(null);
    const [loadError, setLoadError] = useState<string | null>(null);

    const [selected, setSelected] = useState<FileTreeNode | null>(null);
    const [content, setContent] = useState<string | null>(null);
    const [contentLoading, setContentLoading] = useState(false);
    const [contentError, setContentError] = useState<string | null>(null);
    const [copied, setCopied] = useState(false);

    const [explanation, setExplanation] = useState<string | null>(null);
    const [explanationSources, setExplanationSources] = useState<SourceRef[]>([]);
    const [explanationLoading, setExplanationLoading] = useState(false);
    const [explanationError, setExplanationError] = useState<string | null>(null);

    const searchParams = useSearchParams();
    const initialFile = searchParams.get("file");

    useEffect(() => {
        if (!repositoryId) return;
        let cancelled = false;

        async function load() {
            try {
                const [repoData, fileData] = await Promise.all([
                    getRepository(repositoryId),
                    listFiles(repositoryId),
                ]);
                if (cancelled) return;
                setRepo(repoData);
                setFiles(fileData);
                if (initialFile) {
                    const match = fileData.find((f) => f.path === initialFile);
                    if (match) {
                        handleSelect({ name: match.path.split("/").pop() ?? match.path, path: match.path, type: "file", file: match });
                    }
                }
            } catch (err) {
                if (cancelled) return;
                setLoadError(err instanceof ApiError ? err.detail : "Couldn't load this repository.");
            }
        }

        load();
        return () => {
            cancelled = true;
        };
    }, [repositoryId]);

    const tree = useMemo(() => (files ? buildFileTree(files) : []), [files]);
    const lineCount = useMemo(() => (content ? content.split("\n").length : 0), [content]);

    async function handleSelect(node: FileTreeNode) {
        setSelected(node);
        setContent(null);
        setContentError(null);
        setContentLoading(true);
        setCopied(false);
        setExplanation(null);
        setExplanationError(null);
        setExplanationLoading(false);
        try {
            const data = await getFileContent(repositoryId, node.path);
            setContent(data.content);
        } catch (err) {
            setContentError(err instanceof ApiError ? err.detail : "Couldn't load this file.");
        } finally {
            setContentLoading(false);
        }
    }

    async function handleCopy() {
        if (!content) return;
        try {
            await navigator.clipboard.writeText(content);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
        } catch {
            // clipboard permissions can silently fail — not worth surfacing as an error state
        }
    }

    async function handleExplain() {
        if (!selected || explanationLoading) return;
        setExplanationLoading(true);
        setExplanationError(null);
        try {
            const result = await explainFile(repositoryId, selected.path);
            setExplanation(result.explanation);
            setExplanationSources(result.sources);
        } catch (err) {
            setExplanationError(
                err instanceof ApiError ? err.detail : "Couldn't reach RepoLens. Check that the backend is running."
            );
        } finally {
            setExplanationLoading(false);
        }
    }

    if (loadError) {
        return (
            <div className="min-h-screen bg-rl-bg text-rl-text">
                <AppHeader />
                <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 px-6 text-center">
                    <p className="font-[family-name:var(--font-display)] text-lg">Couldn't load repository</p>
                    <p className="font-mono text-xs text-rl-text-dim">{loadError}</p>
                    <Link href="/" className="mt-2 font-mono text-xs text-rl-trace underline underline-offset-4">
                        ← back home
                    </Link>
                </div>
            </div>
        );
    }

    return (
        <div className="flex h-screen flex-col bg-rl-bg text-rl-text">
            <AppHeader />

            {/* Sub-bar: back link + repo name */}
            <div className="flex items-center gap-2 border-b border-rl-border px-6 py-2">
                <Link
                    href={`/repo/${repositoryId}`}
                    className="flex items-center gap-1 font-mono text-xs text-rl-text-dim hover:text-rl-trace"
                >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    {repo?.name ?? "repository"}
                </Link>
            </div>

            <div className="flex flex-1 overflow-hidden">
                {/* File tree sidebar */}
                <aside className="flex w-64 shrink-0 flex-col overflow-hidden border-r border-rl-border bg-rl-surface">
                    <div className="shrink-0 border-b border-rl-border px-4 py-2.5">
                        <span className="font-mono text-[11px] font-medium uppercase tracking-widest text-rl-text-dim">
                            File tree
                        </span>
                    </div>
                    <div className="flex-1 overflow-y-auto">
                        {files === null ? (
                            <div className="flex items-center justify-center py-12">
                                <Loader2 className="h-4 w-4 animate-spin text-rl-text-dim" />
                            </div>
                        ) : files.length === 0 ? (
                            <p className="px-4 py-6 font-mono text-xs text-rl-text-dim">no files found</p>
                        ) : (
                            <FileTreeView nodes={tree} selectedPath={selected?.path ?? null} onSelect={handleSelect} />
                        )}
                    </div>
                </aside>

                {/* Editor pane */}
                <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
                    {!selected ? (
                        <div className="flex flex-1 items-center justify-center">
                            <p className="font-mono text-sm text-rl-text-dim">
                // select a file to view its contents
                            </p>
                        </div>
                    ) : (
                        <>
                            {/* Path + meta header, mirrors the file tree's header row */}
                            <div className="flex shrink-0 items-center justify-between gap-4 border-b border-rl-border px-5 py-2.5">
                                <div className="min-w-0">
                                    <p className="truncate font-mono text-sm text-rl-text">{selected.path}</p>
                                    <p className="mt-0.5 truncate font-mono text-[11px] text-rl-text-dim">
                                        {selected.file?.language ?? "Plain text"}
                                        {content !== null && ` · ${lineCount} line${lineCount === 1 ? "" : "s"}`}
                                        {selected.file && ` · ${formatSize(selected.file.size)}`}
                                    </p>
                                </div>
                                <button
                                    type="button"
                                    onClick={handleCopy}
                                    disabled={!content}
                                    className="flex shrink-0 items-center gap-1.5 rounded-md border border-rl-border px-2.5 py-1.5 font-mono text-[11px] text-rl-text-dim transition-colors hover:border-rl-trace hover:text-rl-trace disabled:opacity-40"
                                >
                                    {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                                    {copied ? "Copied" : "Copy"}
                                </button>
                            </div>

                            {contentLoading ? (
                                <div className="flex flex-1 items-center justify-center">
                                    <Loader2 className="h-5 w-5 animate-spin text-rl-text-dim" />
                                </div>
                            ) : contentError ? (
                                <div className="flex flex-1 items-center justify-center px-6 text-center">
                                    <p className="font-mono text-xs text-rl-danger">{contentError}</p>
                                </div>
                            ) : (
                                <div className="min-h-0 flex-1">
                                    <Editor
                                        height="100%"
                                        language={monacoLanguageFor(selected.file?.language ?? null)}
                                        value={content ?? ""}
                                        theme={resolvedTheme === "dark" ? "vs-dark" : "vs"}
                                        options={{
                                            readOnly: true,
                                            minimap: { enabled: false },
                                            fontSize: 13,
                                            fontFamily: "var(--font-mono), ui-monospace, monospace",
                                            scrollBeyondLastLine: false,
                                            renderLineHighlight: "none",
                                        }}
                                        loading={
                                            <div className="flex h-full items-center justify-center font-mono text-xs text-rl-text-dim">
                                                loading editor…
                                            </div>
                                        }
                                    />
                                </div>
                            )}
                        </>
                    )}
                </main>

                {/* Right rail — AI context, mirrors the file tree's header row */}
                <aside className="flex w-80 shrink-0 flex-col overflow-hidden border-l border-rl-border bg-rl-surface">
                    <div className="shrink-0 border-b border-rl-border px-4 py-2.5">
                        <span className="font-mono text-[11px] font-medium uppercase tracking-widest text-rl-text-dim">
                            AI Explanation
                        </span>
                    </div>

                    <div className="flex-1 overflow-y-auto px-4 py-4">
                        {!selected ? (
                            <p className="font-mono text-xs text-rl-text-dim">
                // select a file to generate an explanation
                            </p>
                        ) : explanation ? (
                            <div>
                                <MarkdownContent content={explanation} />

                                {explanationSources.length > 0 && (
                                    <div className="mt-5">
                                        <p className="font-mono text-[11px] uppercase tracking-widest text-rl-text-dim">
                                            Sources
                                        </p>
                                        <ul className="mt-2 space-y-1">
                                            {explanationSources.map((s, i) => (
                                                <li
                                                    key={`${s.path}-${s.start_line}-${i}`}
                                                    className="truncate font-mono text-[11px] text-rl-trace"
                                                >
                                                    {s.path}:{s.start_line}-{s.end_line}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}

                                <button
                                    type="button"
                                    onClick={handleExplain}
                                    disabled={explanationLoading}
                                    className="mt-5 flex items-center gap-1.5 font-mono text-[11px] text-rl-text-dim hover:text-rl-trace disabled:opacity-50"
                                >
                                    {explanationLoading ? (
                                        <Loader2 className="h-3 w-3 animate-spin" />
                                    ) : (
                                        <RefreshCw className="h-3 w-3" />
                                    )}
                                    Regenerate
                                </button>
                            </div>
                        ) : (
                            <div className="rounded-lg border border-l-2 border-rl-border border-l-rl-signal bg-rl-bg/40 p-4">
                                <div className="flex items-center gap-2 font-mono text-[11px] font-semibold uppercase tracking-widest text-rl-signal">
                                    <Sparkles className="h-3.5 w-3.5" />
                                    Explain this file
                                </div>
                                <p className="mt-2 text-xs leading-relaxed text-rl-text-dim">
                                    Uses the file&apos;s parsed symbols as context and cites the lines it relied on.
                                </p>

                                {explanationError && (
                                    <p className="mt-3 font-mono text-[11px] text-rl-danger">{explanationError}</p>
                                )}

                                <button
                                    type="button"
                                    onClick={handleExplain}
                                    disabled={explanationLoading}
                                    className="mt-4 flex w-full items-center justify-center gap-2 rounded-md border border-rl-signal/40 px-3 py-2 font-mono text-[11px] font-medium uppercase tracking-widest text-rl-signal transition-colors hover:bg-rl-signal/10 disabled:opacity-50"
                                >
                                    {explanationLoading ? (
                                        <>
                                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                            Generating…
                                        </>
                                    ) : (
                                        "Generate explanation"
                                    )}
                                </button>
                            </div>
                        )}
                    </div>
                </aside>
            </div>
        </div>
    );
}