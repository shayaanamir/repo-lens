"use client";

import Link, { useLinkStatus } from "next/link";
import { usePathname } from "next/navigation";
import {
    LayoutGrid,
    FolderTree,
    Network,
    Search,
    MessageSquare,
    Mic,
    Loader2,
    type LucideIcon,
} from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
    { key: "overview", label: "Overview", icon: LayoutGrid, href: (id: string) => `/repo/${id}` },
    { key: "files", label: "Files", icon: FolderTree, href: (id: string) => `/repo/${id}/explorer` },
    { key: "graph", label: "Graph", icon: Network, href: (id: string) => `/repo/${id}/graph` },
    { key: "search", label: "Search", icon: Search, href: (id: string) => `/repo/${id}/search` },
    { key: "chat", label: "Chat", icon: MessageSquare, href: (id: string) => `/repo/${id}/chat` },
];

const PREP_ITEM = { key: "prep", label: "Prep", icon: Mic, href: (id: string) => `/repo/${id}/interview` };

/** Must render inside a <Link>: useLinkStatus reports whether *that*
 * link's navigation is still in flight. */
function NavItemContent({
    icon: Icon,
    label,
    active,
}: {
    icon: LucideIcon;
    label: string;
    active: boolean;
}) {
    const { pending } = useLinkStatus();
    const highlighted = active || pending;

    return (
        <span
            className={cn(
                "flex w-16 flex-col items-center gap-1 rounded-md border py-2.5 font-mono text-[9px] uppercase tracking-widest transition-colors",
                highlighted
                    ? "border-rl-signal/50 bg-rl-signal/10 text-rl-signal"
                    : "border-transparent text-rl-text-dim hover:text-rl-text"
            )}
        >
            {/* Same size either way, so nothing shifts when it swaps. */}
            {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Icon className="h-4 w-4" />}
            {label}
        </span>
    );
}

export function AppSidebar({ repositoryId }: { repositoryId: string }) {
    const pathname = usePathname();

    function isActive(href: string) {
        if (href === `/repo/${repositoryId}`) return pathname === href;
        return pathname?.startsWith(href) ?? false;
    }

    return (
        <aside className="flex h-screen w-20 shrink-0 flex-col items-center justify-between border-r border-rl-border bg-rl-surface py-4">
            <div className="flex flex-col items-center gap-2">
                <Link
                    href="/"
                    className="mb-3 font-mono text-[9px] font-medium tracking-widest text-rl-text-dim hover:text-rl-trace"
                >
                    RL
                </Link>
                {NAV_ITEMS.map((item) => {
                    const href = item.href(repositoryId);
                    const active = isActive(href);
                    return (
                        <Link
                            key={item.key}
                            href={href}
                            className="block"
                            aria-current={active ? "page" : undefined}
                        >
                            <NavItemContent icon={item.icon} label={item.label} active={active} />
                        </Link>
                    );
                })}
            </div>

            <div className="flex flex-col items-center gap-3">
                {(() => {
                    const href = PREP_ITEM.href(repositoryId);
                    const active = isActive(href);
                    return (
                        <Link href={href} className="block" aria-current={active ? "page" : undefined}>
                            <NavItemContent icon={PREP_ITEM.icon} label={PREP_ITEM.label} active={active} />
                        </Link>
                    );
                })()}
                <ThemeToggle />
            </div>
        </aside>
    );
}