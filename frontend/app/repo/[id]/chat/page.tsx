"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Loader2, MessageSquare, Send } from "lucide-react";

import { AppHeader } from "@/components/app-header";
import {
    chatWithRepository,
    getRepository,
    ApiError,
    type Repository,
    type SourceRef,
} from "@/lib/api-client";
import { MarkdownContent } from "@/components/markdown-content";

interface ChatMessage {
    id: string;
    role: "user" | "assistant" | "error";
    content: string;
    sources?: SourceRef[];
}

export default function ChatPage() {
    const params = useParams<{ id: string }>();
    const repositoryId = params.id;

    const [repo, setRepo] = useState<Repository | null>(null);
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [input, setInput] = useState("");
    const [isSending, setIsSending] = useState(false);
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        getRepository(repositoryId).then(setRepo).catch(() => { });
    }, [repositoryId]);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    async function handleSubmit(e: FormEvent) {
        e.preventDefault();
        const question = input.trim();
        if (!question || isSending) return;

        const userMessage: ChatMessage = { id: crypto.randomUUID(), role: "user", content: question };
        setMessages((prev) => [...prev, userMessage]);
        setInput("");
        setIsSending(true);

        try {
            const response = await chatWithRepository(repositoryId, question);
            setMessages((prev) => [
                ...prev,
                {
                    id: crypto.randomUUID(),
                    role: "assistant",
                    content: response.answer,
                    sources: response.sources,
                },
            ]);
        } catch (err) {
            const detail =
                err instanceof ApiError ? err.detail : "Couldn't reach RepoLens. Check that the backend is running.";
            setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "error", content: detail }]);
        } finally {
            setIsSending(false);
        }
    }

    return (
        <div className="flex h-screen flex-col bg-rl-bg text-rl-text">
            <AppHeader />
            <div className="flex items-center gap-2 border-b border-rl-border px-6 py-2.5">
                <Link
                    href={`/repo/${repositoryId}`}
                    className="flex items-center gap-1 font-mono text-xs text-rl-text-dim hover:text-rl-trace"
                >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    {repo?.name ?? "repository"}
                </Link>
                <span className="font-mono text-xs text-rl-text-dim">/ chat</span>
            </div>

            <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col overflow-hidden px-6">
                <div className="flex-1 overflow-y-auto py-6">
                    {messages.length === 0 ? (
                        <EmptyState repoName={repo?.name} />
                    ) : (
                        <div className="space-y-4">
                            {messages.map((m) => (
                                <MessageBubble key={m.id} message={m} repositoryId={repositoryId} />
                            ))}
                            {isSending && (
                                <div className="flex items-center gap-2 font-mono text-xs text-rl-text-dim">
                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                    retrieving context and generating an answer…
                                </div>
                            )}
                        </div>
                    )}
                    <div ref={bottomRef} />
                </div>

                <form onSubmit={handleSubmit} className="shrink-0 border-t border-rl-border py-4">
                    <div className="flex items-center gap-2 rounded-lg border border-rl-border bg-rl-surface p-1.5">
                        <input
                            type="text"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            placeholder="Ask a question about this repository…"
                            disabled={isSending}
                            className="flex-1 bg-transparent px-2 py-1.5 text-sm text-rl-text placeholder:text-rl-text-dim outline-none disabled:opacity-60"
                            autoComplete="off"
                        />
                        <button
                            type="submit"
                            disabled={isSending || !input.trim()}
                            suppressHydrationWarning
                            aria-label="Send"
                            className="shrink-0 rounded-md bg-rl-signal p-2 text-rl-bg transition-opacity hover:opacity-90 disabled:opacity-50"
                        >
                            <Send className="h-3.5 w-3.5" />
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}

function EmptyState({ repoName }: { repoName?: string }) {
    return (
        <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
            <MessageSquare className="h-6 w-6 text-rl-text-dim" />
            <p className="font-[family-name:var(--font-display)] text-lg text-rl-text">
                Ask anything about {repoName ?? "this repository"}
            </p>
            <p className="max-w-sm font-mono text-xs text-rl-text-dim">
                Answers are grounded in retrieved code — every response cites the files it drew from.
            </p>
        </div>
    );
}

function MessageBubble({
    message,
    repositoryId,
}: {
    message: ChatMessage;
    repositoryId: string;
}) {
    if (message.role === "user") {
        return (
            <div className="flex justify-end">
                <div className="max-w-[85%] rounded-lg rounded-br-sm bg-rl-signal px-4 py-2.5 text-sm text-rl-bg">
                    {message.content}
                </div>
            </div>
        );
    }

    if (message.role === "error") {
        return (
            <div className="flex justify-start">
                <div className="max-w-[85%] rounded-lg rounded-bl-sm border border-rl-danger/30 bg-rl-danger-bg px-4 py-2.5 text-sm text-rl-danger">
                    {message.content}
                </div>
            </div>
        );
    }

    return (
        <div className="flex justify-start">
            <div className="max-w-[85%] rounded-lg rounded-bl-sm border border-rl-border bg-rl-surface px-4 py-2.5">
                <MarkdownContent content={message.content} />
                {message.sources && message.sources.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5 border-t border-rl-border pt-2.5">
                        {message.sources.map((s, i) => (
                            <Link
                                key={`${s.path}:${s.start_line}:${i}`}
                                href={`/repo/${repositoryId}/explorer?file=${encodeURIComponent(s.path)}`}
                                className="rounded border border-rl-trace/40 px-1.5 py-0.5 font-mono text-[10px] text-rl-trace hover:bg-rl-trace/10"
                            >
                                {s.path}:{s.start_line}-{s.end_line}
                            </Link>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}