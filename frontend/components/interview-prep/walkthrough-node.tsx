"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";

export interface WalkthroughNodeData {
    index: number;
    filePath: string | null;
    preview: string;
    selected: boolean;
    [key: string]: unknown;
}

export function WalkthroughNode({ data }: NodeProps) {
    const d = data as WalkthroughNodeData;

    return (
        <div
            className="w-64 rounded-md border bg-rl-surface px-3 py-2.5 transition-colors"
            style={{
                borderColor: d.selected ? "var(--rl-signal)" : "var(--rl-border)",
                boxShadow: d.selected ? "0 0 0 1px var(--rl-signal)" : "none",
            }}
        >
            <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
            <span className="mb-1 inline-block rounded-full border border-rl-signal/50 px-1.5 py-0.5 font-mono text-[10px] text-rl-signal">
                {String(d.index).padStart(2, "0")}
            </span>
            {d.filePath ? (
                <p className="truncate font-mono text-xs text-rl-text" title={d.filePath}>
                    {d.filePath}
                </p>
            ) : (
                <p className="truncate text-xs italic text-rl-text-dim" title={d.preview}>
                    {d.preview}
                </p>
            )}
            <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
        </div>
    );
}