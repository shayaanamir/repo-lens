"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
    ReactFlow,
    ReactFlowProvider,
    Background,
    BackgroundVariant,
    MarkerType,
    type Node,
    type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { ExternalLink } from "lucide-react";
import { WalkthroughNode, type WalkthroughNodeData } from "./walkthrough-node";
import { extractFileReference } from "@/lib/walkthrough";

const nodeTypes = { step: WalkthroughNode };

const NODE_HEIGHT = 96;

export function WalkthroughFlow({
    points,
    repositoryId,
}: {
    points: string[];
    repositoryId: string;
}) {
    const [selectedId, setSelectedId] = useState<string | null>(null);

    const steps = useMemo(
        () =>
            points.map((text, i) => ({
                id: String(i),
                text,
                filePath: extractFileReference(text),
            })),
        [points]
    );

    // Single top-to-bottom column — every edge points the same direction
    // (bottom handle -> top handle), so nothing ever has to loop back on
    // itself the way it did in the earlier left-right/right-left snake.
    const nodes: Node<WalkthroughNodeData>[] = useMemo(
        () =>
            steps.map((step, i) => ({
                id: step.id,
                type: "step",
                position: { x: 0, y: i * NODE_HEIGHT },
                data: {
                    index: i + 1,
                    filePath: step.filePath,
                    preview: step.text.length > 40 ? `${step.text.slice(0, 40)}…` : step.text,
                    selected: step.id === selectedId,
                },
                draggable: false,
            })),
        [steps, selectedId]
    );

    const edges: Edge[] = useMemo(
        () =>
            steps.slice(1).map((_, i) => {
                const isAdjacentToSelection =
                    selectedId !== null && (String(i) === selectedId || String(i + 1) === selectedId);
                return {
                    id: `${i}-${i + 1}`,
                    source: String(i),
                    target: String(i + 1),
                    type: "smoothstep",
                    markerEnd: {
                        type: MarkerType.ArrowClosed,
                        color: isAdjacentToSelection ? "var(--rl-signal)" : "var(--rl-border)",
                        width: 16,
                        height: 16,
                    },
                    style: {
                        stroke: isAdjacentToSelection ? "var(--rl-signal)" : "var(--rl-border)",
                        strokeWidth: isAdjacentToSelection ? 1.5 : 1.25,
                        opacity: selectedId ? (isAdjacentToSelection ? 1 : 0.4) : 0.7,
                    },
                };
            }),
        [steps, selectedId]
    );

    const selectedStep = steps.find((s) => s.id === selectedId) ?? null;

    return (
        <div className="flex h-[calc(100vh-260px)] min-h-[480px] w-full overflow-hidden rounded-lg border border-rl-border">
            <div className="min-w-0 flex-1 bg-rl-bg">
                <ReactFlowProvider>
                    <ReactFlow
                        nodes={nodes}
                        edges={edges}
                        nodeTypes={nodeTypes}
                        onNodeClick={(_, node) => setSelectedId(node.id === selectedId ? null : node.id)}
                        onPaneClick={() => setSelectedId(null)}
                        fitView
                        fitViewOptions={{ padding: 0.25, maxZoom: 1.25 }}
                        nodesDraggable={false}
                        nodesConnectable={false}
                        proOptions={{ hideAttribution: true }}
                    >
                        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="var(--rl-border)" />
                    </ReactFlow>
                </ReactFlowProvider>
            </div>

            <aside className="w-72 shrink-0 overflow-y-auto border-l border-rl-border bg-rl-surface px-5 py-5">
                {!selectedStep ? (
                    <p className="font-mono text-xs text-rl-text-dim">
                        select a step to read its explanation
                    </p>
                ) : (
                    <div>
                        <p className="font-mono text-[11px] uppercase tracking-widest text-rl-signal">
                            Step {String(steps.indexOf(selectedStep) + 1).padStart(2, "0")}
                        </p>

                        {selectedStep.filePath && (
                            <p className="mt-2 break-all font-mono text-xs text-rl-text">{selectedStep.filePath}</p>
                        )}

                        <p className="mt-3 text-sm leading-relaxed text-rl-text">{selectedStep.text}</p>

                        {selectedStep.filePath && (
                            <Link
                                href={`/repo/${repositoryId}/explorer?file=${encodeURIComponent(selectedStep.filePath)}`}
                                className="mt-4 inline-flex items-center gap-1 rounded border border-rl-border px-2.5 py-1.5 font-mono text-[11px] uppercase tracking-wide text-rl-text-dim hover:border-rl-trace hover:text-rl-trace"
                            >
                                Open in Explorer
                                <ExternalLink className="h-3 w-3" />
                            </Link>
                        )}
                    </div>
                )}
            </aside>
        </div>
    );
}