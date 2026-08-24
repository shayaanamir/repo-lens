"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
    ReactFlow,
    ReactFlowProvider,
    Background,
    BackgroundVariant,
    useReactFlow,
    type Node,
    type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { ArrowLeft, Loader2, Minus, Plus, RotateCcw } from "lucide-react";

import { AppHeader } from "@/components/app-header";
import { FileNode, type FileNodeData } from "@/components/dependency-graph/file-node";
import {
    categorizeNodes,
    computeLayeredPositions,
    CATEGORY_META,
    type FileCategory,
} from "@/lib/graph-layout";
import {
    getDependencyGraph,
    getRepository,
    ApiError,
    type DependencyGraph,
    type Repository,
} from "@/lib/api-client";

const nodeTypes = { file: FileNode };
const ALL_CATEGORIES: FileCategory[] = ["entry", "core", "utility", "types", "test"];

export default function DependencyGraphPage() {
    const params = useParams<{ id: string }>();
    const repositoryId = params.id;

    const [repo, setRepo] = useState<Repository | null>(null);
    const [graph, setGraph] = useState<DependencyGraph | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!repositoryId) return;
        let cancelled = false;
        (async () => {
            try {
                const [repoData, graphData] = await Promise.all([
                    getRepository(repositoryId),
                    getDependencyGraph(repositoryId),
                ]);
                if (cancelled) return;
                setRepo(repoData);
                setGraph(graphData);
            } catch (err) {
                if (cancelled) return;
                setError(err instanceof ApiError ? err.detail : "Couldn't load the dependency graph.");
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [repositoryId]);

    if (error) {
        return (
            <div className="min-h-screen bg-rl-bg text-rl-text">
                <AppHeader />
                <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 px-6 text-center">
                    <p className="font-[family-name:var(--font-display)] text-lg">Couldn't load graph</p>
                    <p className="font-mono text-xs text-rl-text-dim">{error}</p>
                    <Link href="/" className="mt-2 font-mono text-xs text-rl-trace underline underline-offset-4">
                        ← back home
                    </Link>
                </div>
            </div>
        );
    }

    return (
        <div className="flex h-screen flex-col bg-rl-bg text-rl-text">
            <AppHeader />
            <div className="flex items-center gap-2 border-b border-rl-border px-6 py-2.5">
                <Link
                    href={`/repo/${repositoryId}`}
                    className="flex items-center gap-1 font-mono text-xs text-rl-text-dim hover:text-rl-trace"
                >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    {repo?.name ?? "repository"}
                </Link>
                <span className="font-mono text-xs text-rl-text-dim">/ dependency graph</span>
            </div>

            {!graph ? (
                <div className="flex flex-1 items-center justify-center">
                    <Loader2 className="h-5 w-5 animate-spin text-rl-text-dim" />
                </div>
            ) : graph.nodes.length === 0 ? (
                <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 text-center">
                    <p className="font-mono text-sm text-rl-text-dim">
            // no resolvable import relationships found yet
                    </p>
                    <p className="max-w-sm text-xs text-rl-text-dim">
                        Files with no detected imports aren&apos;t shown here — this repository may still be
                        indexing, or may not have cross-file imports RepoLens can resolve.
                    </p>
                </div>
            ) : (
                <ReactFlowProvider>
                    <GraphCanvas graph={graph} repositoryId={repositoryId} />
                </ReactFlowProvider>
            )}
        </div>
    );
}

function GraphCanvas({ graph, repositoryId }: { graph: DependencyGraph; repositoryId: string }) {
    const { zoomIn, zoomOut, fitView, getZoom } = useReactFlow();
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [visibleCategories, setVisibleCategories] = useState<Set<FileCategory>>(
        new Set(ALL_CATEGORIES)
    );
    const [zoomPct, setZoomPct] = useState(100);

    const categorized = useMemo(() => categorizeNodes(graph.nodes, graph.edges), [graph]);
    const positions = useMemo(
        () => computeLayeredPositions(categorized, graph.edges),
        [categorized, graph.edges]
    );

    const connectedIds = useMemo(() => {
        if (!selectedId) return null;
        const ids = new Set<string>([selectedId]);
        for (const e of graph.edges) {
            if (e.source === selectedId) ids.add(e.target);
            if (e.target === selectedId) ids.add(e.source);
        }
        return ids;
    }, [selectedId, graph.edges]);

    const visibleNodeIds = useMemo(
        () => new Set(categorized.filter((n) => visibleCategories.has(n.category)).map((n) => n.id)),
        [categorized, visibleCategories]
    );

    const flowNodes: Node<FileNodeData>[] = useMemo(
        () =>
            categorized
                .filter((n) => visibleNodeIds.has(n.id))
                .map((n) => ({
                    id: n.id,
                    type: "file",
                    position: positions.get(n.id) ?? { x: 0, y: 0 },
                    data: {
                        label: n.label.split("/").pop() ?? n.label,
                        fullPath: n.label,
                        category: n.category,
                        dimmed: connectedIds ? !connectedIds.has(n.id) : false,
                    },
                    selected: n.id === selectedId,
                    draggable: false,
                })),
        [categorized, positions, visibleNodeIds, connectedIds, selectedId]
    );

    const flowEdges: Edge[] = useMemo(
        () =>
            graph.edges
                .filter((e) => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target))
                .map((e) => {
                    const isConnectedToSelection =
                        !!connectedIds && (e.source === selectedId || e.target === selectedId);
                    return {
                        id: e.id,
                        source: e.source,
                        target: e.target,
                        type: "bezier",
                        style: {
                            stroke: isConnectedToSelection ? "var(--rl-trace)" : "var(--rl-border)",
                            strokeWidth: isConnectedToSelection ? 1.5 : 1,
                            opacity: connectedIds ? (isConnectedToSelection ? 1 : 0.12) : 0.5,
                        },
                    };
                }),
        [graph.edges, visibleNodeIds, connectedIds, selectedId]
    );

    const selectedNode = categorized.find((n) => n.id === selectedId) ?? null;
    const imports = selectedNode
        ? graph.edges
            .filter((e) => e.source === selectedNode.id)
            .map((e) => categorized.find((n) => n.id === e.target)?.label ?? e.target)
        : [];
    const importedBy = selectedNode
        ? graph.edges
            .filter((e) => e.target === selectedNode.id)
            .map((e) => categorized.find((n) => n.id === e.source)?.label ?? e.source)
        : [];

    function toggleCategory(cat: FileCategory) {
        setVisibleCategories((prev) => {
            const next = new Set(prev);
            if (next.has(cat)) next.delete(cat);
            else next.add(cat);
            return next;
        });
    }

    function syncZoom() {
        setZoomPct(Math.round(getZoom() * 100));
    }

    return (
        <div className="flex flex-1 overflow-hidden">
            <div className="relative flex-1">
                <div className="absolute left-4 top-4 z-10 flex flex-wrap items-center gap-3 rounded-md border border-rl-border bg-rl-surface/95 px-3 py-2 backdrop-blur">
                    {ALL_CATEGORIES.map((cat) => {
                        const meta = CATEGORY_META[cat];
                        const checked = visibleCategories.has(cat);
                        return (
                            <label
                                key={cat}
                                className="flex cursor-pointer items-center gap-1.5 font-mono text-[11px] uppercase tracking-wide text-rl-text-dim"
                            >
                                <input
                                    type="checkbox"
                                    checked={checked}
                                    onChange={() => toggleCategory(cat)}
                                    className="h-3 w-3"
                                />
                                <span style={{ color: checked ? `var(${meta.cssVar})` : undefined }}>
                                    {meta.label}
                                </span>
                            </label>
                        );
                    })}
                </div>

                <div className="absolute right-4 top-4 z-10 flex items-center gap-1 rounded-md border border-rl-border bg-rl-surface/95 px-2 py-1.5 backdrop-blur">
                    <button
                        onClick={() => { zoomOut(); syncZoom(); }}
                        className="rounded p-1 text-rl-text-dim hover:bg-rl-border/50 hover:text-rl-text"
                        aria-label="Zoom out"
                    >
                        <Minus className="h-3.5 w-3.5" />
                    </button>
                    <span className="w-10 text-center font-mono text-[11px] text-rl-text-dim">{zoomPct}%</span>
                    <button
                        onClick={() => { zoomIn(); syncZoom(); }}
                        className="rounded p-1 text-rl-text-dim hover:bg-rl-border/50 hover:text-rl-text"
                        aria-label="Zoom in"
                    >
                        <Plus className="h-3.5 w-3.5" />
                    </button>
                    <button
                        onClick={() => { fitView({ padding: 0.2 }); syncZoom(); }}
                        className="ml-1 rounded p-1 text-rl-text-dim hover:bg-rl-border/50 hover:text-rl-text"
                        aria-label="Reset view"
                    >
                        <RotateCcw className="h-3.5 w-3.5" />
                    </button>
                </div>

                <ReactFlow
                    nodes={flowNodes}
                    edges={flowEdges}
                    nodeTypes={nodeTypes}
                    onNodeClick={(_, node) => setSelectedId(node.id === selectedId ? null : node.id)}
                    onPaneClick={() => setSelectedId(null)}
                    onMoveEnd={syncZoom}
                    fitView
                    nodesDraggable={false}
                    nodesConnectable={false}
                    proOptions={{ hideAttribution: true }}
                >
                    <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="var(--rl-border)" />
                </ReactFlow>
            </div>

            <aside className="w-72 shrink-0 overflow-y-auto border-l border-rl-border bg-rl-surface px-5 py-5">
                {!selectedNode ? (
                    <p className="font-mono text-xs text-rl-text-dim">
            // select a node to inspect its dependencies
                    </p>
                ) : (
                    <div>
                        <p
                            className="font-mono text-[11px] uppercase tracking-widest"
                            style={{ color: `var(${CATEGORY_META[selectedNode.category].cssVar})` }}
                        >
                            {CATEGORY_META[selectedNode.category].label}
                        </p>
                        <h2 className="mt-2 break-all font-mono text-sm text-rl-text">{selectedNode.label}</h2>
                        <p className="mt-1 font-mono text-[11px] text-rl-text-dim">
                            {selectedNode.language ?? "plaintext"} · {selectedNode.inDegree} in ·{" "}
                            {selectedNode.outDegree} out
                        </p>

                        <Link
                            href={`/repo/${repositoryId}/explorer?file=${encodeURIComponent(selectedNode.label)}`}
                            className="mt-4 block rounded border border-rl-border px-3 py-1.5 text-center font-mono text-[11px] uppercase tracking-wide text-rl-text-dim hover:border-rl-trace hover:text-rl-trace"
                        >
                            Open in Explorer
                        </Link>

                        <div className="mt-6">
                            <p className="font-mono text-[11px] uppercase tracking-widest text-rl-text-dim">
                                Imports
                            </p>
                            {imports.length === 0 ? (
                                <p className="mt-1.5 font-mono text-xs text-rl-text-dim">None</p>
                            ) : (
                                <ul className="mt-1.5 space-y-1">
                                    {imports.map((path) => (
                                        <li key={path} className="truncate font-mono text-xs text-rl-text">
                                            {path}
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </div>

                        <div className="mt-6">
                            <p className="font-mono text-[11px] uppercase tracking-widest text-rl-text-dim">
                                Imported by
                            </p>
                            {importedBy.length === 0 ? (
                                <p className="mt-1.5 font-mono text-xs text-rl-text-dim">None — entry point</p>
                            ) : (
                                <ul className="mt-1.5 space-y-1">
                                    {importedBy.map((path) => (
                                        <li key={path} className="truncate font-mono text-xs text-rl-text">
                                            {path}
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </div>
                    </div>
                )}
            </aside>
        </div>
    );
}