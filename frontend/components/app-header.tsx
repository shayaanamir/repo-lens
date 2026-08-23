"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { ThemeToggle } from "@/components/theme-toggle";

export function AppHeader({ children }: { children?: ReactNode }) {
    return (
        <header className="sticky top-0 z-10 border-b border-rl-border bg-rl-bg/95 backdrop-blur">
            <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
                <Link
                    href="/"
                    className="font-mono text-sm font-medium tracking-[0.2em] text-rl-text"
                >
                    REPOLENS
                </Link>
                <div className="flex items-center gap-4">
                    {children}
                    <ThemeToggle />
                </div>
            </div>
        </header>
    );
}