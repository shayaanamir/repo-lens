"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

export function MarkdownContent({
    content,
    className,
}: {
    content: string;
    className?: string;
}) {
    return (
        <div className={cn("text-sm leading-relaxed text-rl-text", className)}>
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                    h1: ({ children }) => (
                        <h1 className="mb-3 mt-5 font-[family-name:var(--font-display)] text-xl text-rl-text first:mt-0">
                            {children}
                        </h1>
                    ),
                    h2: ({ children }) => (
                        <h2 className="mb-2 mt-5 font-[family-name:var(--font-display)] text-lg text-rl-text first:mt-0">
                            {children}
                        </h2>
                    ),
                    h3: ({ children }) => (
                        <h3 className="mb-2 mt-4 font-[family-name:var(--font-display)] text-base text-rl-text first:mt-0">
                            {children}
                        </h3>
                    ),
                    p: ({ children }) => (
                        <p className="mb-3 last:mb-0">{children}</p>
                    ),
                    ul: ({ children }) => (
                        <ul className="mb-3 ml-5 list-disc space-y-1 last:mb-0">{children}</ul>
                    ),
                    ol: ({ children }) => (
                        <ol className="mb-3 ml-5 list-decimal space-y-1 last:mb-0">{children}</ol>
                    ),
                    li: ({ children }) => <li className="pl-1">{children}</li>,
                    strong: ({ children }) => (
                        <strong className="font-semibold text-rl-text">{children}</strong>
                    ),
                    em: ({ children }) => <em className="italic">{children}</em>,
                    a: ({ children, href }) => (
                        <a
                            href={href}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-rl-trace underline underline-offset-2 hover:opacity-80"
                        >
                            {children}
                        </a>
                    ),
                    blockquote: ({ children }) => (
                        <blockquote className="mb-3 border-l-2 border-rl-border pl-3 text-rl-text-dim last:mb-0">
                            {children}
                        </blockquote>
                    ),
                    code: ({ className, children, ...props }) => {
                        const isBlock = /language-/.test(className ?? "");
                        if (isBlock) {
                            return (
                                <code className={cn("font-mono text-xs", className)} {...props}>
                                    {children}
                                </code>
                            );
                        }
                        return (
                            <code className="rounded border border-rl-border bg-rl-bg px-1 py-0.5 font-mono text-[0.85em] text-rl-signal">
                                {children}
                            </code>
                        );
                    },
                    pre: ({ children }) => (
                        <pre className="mb-3 overflow-x-auto rounded-md border border-rl-border bg-rl-bg p-3 last:mb-0">
                            {children}
                        </pre>
                    ),
                    hr: () => <hr className="my-4 border-rl-border" />,
                }}
            >
                {content}
            </ReactMarkdown>
        </div>
    );
}