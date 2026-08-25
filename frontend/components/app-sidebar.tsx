"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutGrid, FolderTree, Network, Search, MessageSquare } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
    { key: "overview", label: "Overview", icon: LayoutGrid, href: (id: string) => `/repo/${id}` },
    { key: "files", label: "Files", icon: FolderTree, href: (id: string) => `/repo/${id}/explorer` },
    { key: "graph", label: "Graph", icon: Network, href: (id: string) => `/repo/${id}/graph` },
    { key: "search", label: "Search", icon: Search, href: (id: string) => `/repo/${id}/search` },
    { key: "chat", label: "Chat", icon: MessageSquare, href: (id: string) => `/repo/${id}/chat` },
];

export function AppSidebar({ repositoryId }: { repositoryId: string }) {
    const pathname = usePathname();

    function isActive(href: string) {
        if (href === `/repo/${repositoryId}`) return pathname === href;
        return pathname?.startsWith(href);
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
                    const Icon = item.icon;
                    return (
                        <Link
                            key={item.key}
                            href={href}
                            className={cn(
                                "flex w-16 flex-col items-center gap-1 rounded-md border py-2.5 font-mono text-[9px] uppercase tracking-widest transition-colors",
                                active
                                    ? "border-rl-signal/50 bg-rl-signal/10 text-rl-signal"
                                    : "border-transparent text-rl-text-dim hover:text-rl-text"
                            )}
                        >
                            <Icon className="h-4 w-4" />
                            {item.label}
                        </Link>
                    );
                })}
            </div>
            <ThemeToggle />
        </aside>
    );
}