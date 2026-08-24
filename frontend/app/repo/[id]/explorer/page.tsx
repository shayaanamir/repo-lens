"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { useTheme } from "next-themes";
import Editor from "@monaco-editor/react";
import { ArrowLeft, Loader2 } from "lucide-react";

import { AppHeader } from "@/components/app-header";
import { FileTreeView } from "@/components/file-tree-view";
import { buildFileTree, type FileTreeNode } from "@/lib/file-tree";
import {
    listFiles,
    getFileContent,
    getRepository,
    ApiError,
    type FileEntry,
    type Repository,
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

    async function handleSelect(node: FileTreeNode) {
        setSelected(node);
        setContent(null);
        setContentError(null);
        setContentLoading(true);
        try {
            const data = await getFileContent(repositoryId, node.path);
            setContent(data.content);
        } catch (err) {
            setContentError(err instanceof ApiError ? err.detail : "Couldn't load this file.");
        } finally {
            setContentLoading(false);
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

            {/* Sub-bar: back link + repo name + breadcrumb */}
            <div className="flex items-center gap-3 border-b border-rl-border px-6 py-2.5">
                <Link
                    href={`/repo/${repositoryId}`}
                    className="flex items-center gap-1 font-mono text-xs text-rl-text-dim hover:text-rl-trace"
                >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    {repo?.name ?? "repository"}
                </Link>
                {selected && (
                    <>
                        <span className="font-mono text-xs text-rl-text-dim">/</span>
                        <span className="truncate font-mono text-xs text-rl-text">{selected.path}</span>
                    </>
                )}
            </div>

            <div className="flex flex-1 overflow-hidden">
                {/* File tree sidebar */}
                <aside className="w-64 shrink-0 overflow-y-auto border-r border-rl-border bg-rl-surface">
                    {files === null ? (
                        <div className="flex items-center justify-center py-12">
                            <Loader2 className="h-4 w-4 animate-spin text-rl-text-dim" />
                        </div>
                    ) : files.length === 0 ? (
                        <p className="px-4 py-6 font-mono text-xs text-rl-text-dim">no files found</p>
                    ) : (
                        <FileTreeView nodes={tree} selectedPath={selected?.path ?? null} onSelect={handleSelect} />
                    )}
                </aside>

                {/* Editor pane */}
                <main className="flex flex-1 flex-col overflow-hidden">
                    {!selected ? (
                        <div className="flex flex-1 items-center justify-center">
                            <p className="font-mono text-sm text-rl-text-dim">
                // select a file to view its contents
                            </p>
                        </div>
                    ) : contentLoading ? (
                        <div className="flex flex-1 items-center justify-center">
                            <Loader2 className="h-5 w-5 animate-spin text-rl-text-dim" />
                        </div>
                    ) : contentError ? (
                        <div className="flex flex-1 items-center justify-center px-6 text-center">
                            <p className="font-mono text-xs text-rl-danger">{contentError}</p>
                        </div>
                    ) : (
                        <div className="flex-1">
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

                    {selected?.file && (
                        <div className="flex items-center gap-3 border-t border-rl-border px-4 py-1.5 font-mono text-[11px] text-rl-text-dim">
                            <span>{selected.file.language ?? "plaintext"}</span>
                            <span>·</span>
                            <span>{formatSize(selected.file.size)}</span>
                        </div>
                    )}
                </main>
            </div>
        </div>
    );
}