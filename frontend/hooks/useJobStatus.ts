"use client";

import { useEffect, useRef, useState } from "react";
import { getJobs, type Job, type JobListResponse } from "@/lib/api-client";

const POLL_INTERVAL_MS = 3000;

export type PipelinePhase = "indexing" | "ready" | "failed";

interface UseJobStatusResult {
    jobs: Job[];
    phase: PipelinePhase;
    currentStage: Job | null; // the first non-completed job, i.e. what's running now
    error: string | null; // populated if any stage failed
    isLoading: boolean;
}

/**
 * Polls GET /repositories/{id}/jobs every few seconds until every stage
 * is completed (or one fails). Stops polling once the pipeline reaches
 * a terminal state, so we don't keep hitting the backend forever.
 */
export function useJobStatus(repositoryId: string | null): UseJobStatusResult {
    const [jobs, setJobs] = useState<Job[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

    useEffect(() => {
        if (!repositoryId) {
            setIsLoading(false);
            return;
        }

        let cancelled = false;

        const poll = async () => {
            try {
                const data: JobListResponse = await getJobs(repositoryId);
                if (cancelled) return;

                setJobs(data.jobs);
                setIsLoading(false);

                const terminal =
                    data.jobs.every((j) => j.status === "completed") ||
                    data.jobs.some((j) => j.status === "failed");

                if (terminal && intervalRef.current) {
                    clearInterval(intervalRef.current);
                    intervalRef.current = null;
                }
            } catch {
                // Transient network/API hiccup — keep polling, don't surface
                // a hard error just because one poll failed.
                if (!cancelled) setIsLoading(false);
            }
        };

        poll(); // fire immediately, don't wait for the first interval tick
        intervalRef.current = setInterval(poll, POLL_INTERVAL_MS);

        return () => {
            cancelled = true;
            if (intervalRef.current) clearInterval(intervalRef.current);
        };
    }, [repositoryId]);

    const failedJob = jobs.find((j) => j.status === "failed") ?? null;
    const phase: PipelinePhase = failedJob
        ? "failed"
        : jobs.length > 0 && jobs.every((j) => j.status === "completed")
            ? "ready"
            : "indexing";

    const currentStage = jobs.find((j) => j.status !== "completed") ?? null;

    return {
        jobs,
        phase,
        currentStage,
        error: failedJob?.error ?? null,
        isLoading,
    };
}