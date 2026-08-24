"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { CATEGORY_META, type FileCategory } from "@/lib/graph-layout";

export interface FileNodeData {
    label: string;
    fullPath: string;
    category: FileCategory;
    dimmed: boolean;
    [key: string]: unknown;
}

export function FileNode({ data, selected }: NodeProps) {
    const d = data as FileNodeData;
    const meta = CATEGORY_META[d.category];
    const isEntry = d.category === "entry";
    const highlighted = isEntry || selected;

    return (
        <div
            title={d.fullPath}
            className="rounded-md border bg-rl-surface px-3 py-2 font-mono text-xs transition-opacity"
            style={{
                borderColor: highlighted ? `var(${meta.cssVar})` : "var(--rl-border)",
                color: highlighted ? `var(${meta.cssVar})` : "var(--rl-text)",
                opacity: d.dimmed ? 0.25 : 1,
                boxShadow: selected ? `0 0 0 1px var(${meta.cssVar})` : "none",
                minWidth: 140,
            }}
        >
            <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
            <span className="block max-w-[180px] truncate">{d.label}</span>
            <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
        </div>
    );
}