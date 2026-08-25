"use client";

import { useParams } from "next/navigation";
import { AppSidebar } from "@/components/app-sidebar";

export default function RepoLayout({ children }: { children: React.ReactNode }) {
    const params = useParams<{ id: string }>();
    const repositoryId = params.id;

    return (
        <div className="flex h-screen overflow-hidden bg-rl-bg text-rl-text">
            <AppSidebar repositoryId={repositoryId} />
            <div className="flex min-w-0 flex-1 flex-col overflow-hidden">{children}</div>
        </div>
    );
}