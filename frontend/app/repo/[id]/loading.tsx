import { Loader2 } from "lucide-react";

/** Shown instantly while a tab under /repo/[id] loads. Next.js prefetches
 * this fallback, so switching tabs responds immediately, and the sidebar
 * (rendered by layout.tsx) stays in place and interactive. */
export default function RepoTabLoading() {
    return (
        <div className="flex flex-1 flex-col overflow-hidden" role="status" aria-live="polite">
            <div className="flex items-center gap-2 border-b border-rl-border px-6 py-2.5">
                <div className="h-3 w-28 animate-pulse rounded bg-rl-border" />
            </div>
            <div className="flex flex-1 flex-col items-center justify-center gap-3">
                <Loader2 className="h-5 w-5 animate-spin text-rl-text-dim" />
                <p className="font-mono text-xs text-rl-text-dim">loading…</p>
            </div>
            <span className="sr-only">Loading</span>
        </div>
    );
}