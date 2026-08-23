"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, File as FileIcon, Folder, FolderOpen } from "lucide-react";
import { cn } from "@/lib/utils";
import type { FileTreeNode } from "@/lib/file-tree";

export function FileTreeView({
    nodes,
    selectedPath,
    onSelect,
}: {
    nodes: FileTreeNode[];
    selectedPath: string | null;
    onSelect: (node: FileTreeNode) => void;
}) {
    return (
        <div className="py-2">
            {nodes.map((node) => (
                <TreeNode key={node.path} node={node} depth={0} selectedPath={selectedPath} onSelect={onSelect} />
            ))}
        </div>
    );
}

function TreeNode({
    node,
    depth,
    selectedPath,
    onSelect,
}: {
    node: FileTreeNode;
    depth: number;
    selectedPath: string | null;
    onSelect: (node: FileTreeNode) => void;
}) {
    const [expanded, setExpanded] = useState(depth === 0);
    const indent = { paddingLeft: `${depth * 14 + 10}px` };

    if (node.type === "file") {
        const isSelected = node.path === selectedPath;
        return (
            <button
                type="button"
                onClick={() => onSelect(node)}
                style={indent}
                className={cn(
                    "flex w-full items-center gap-1.5 py-1 pr-2 text-left font-mono text-xs transition-colors",
                    isSelected
                        ? "bg-rl-trace/10 text-rl-trace"
                        : "text-rl-text-dim hover:bg-rl-border/40 hover:text-rl-text"
                )}
            >
                <FileIcon className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{node.name}</span>
            </button>
        );
    }

    return (
        <div>
            <button
                type="button"
                onClick={() => setExpanded((v) => !v)}
                style={indent}
                className="flex w-full items-center gap-1 py-1 pr-2 text-left font-mono text-xs text-rl-text hover:bg-rl-border/40"
            >
                {expanded ? (
                    <ChevronDown className="h-3 w-3 shrink-0 text-rl-text-dim" />
                ) : (
                    <ChevronRight className="h-3 w-3 shrink-0 text-rl-text-dim" />
                )}
                {expanded ? (
                    <FolderOpen className="h-3.5 w-3.5 shrink-0 text-rl-signal" />
                ) : (
                    <Folder className="h-3.5 w-3.5 shrink-0 text-rl-signal" />
                )}
                <span className="truncate">{node.name}</span>
            </button>
            {expanded &&
                node.children?.map((child) => (
                    <TreeNode key={child.path} node={child} depth={depth + 1} selectedPath={selectedPath} onSelect={onSelect} />
                ))}
        </div>
    );
}