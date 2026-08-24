import type { GraphEdge, GraphNode } from "@/lib/api-client";

export type FileCategory = "entry" | "core" | "utility" | "types" | "test";

export interface CategorizedNode extends GraphNode {
    category: FileCategory;
    inDegree: number;
    outDegree: number;
}

export const CATEGORY_META: Record<FileCategory, { label: string; cssVar: string }> = {
    entry: { label: "Entry Point", cssVar: "--rl-signal" },
    core: { label: "Core Module", cssVar: "--rl-text-dim" },
    utility: { label: "Utility", cssVar: "--rl-utility" },
    types: { label: "Types", cssVar: "--rl-trace" },
    test: { label: "Test", cssVar: "--rl-test" },
};

const TEST_PATTERN = /(^|\/)(tests?|__tests__)(\/|$)|\.test\.|\.spec\.|_test\.|test_/i;
const TYPES_PATTERN = /(^|\/)(types?|schemas?)(\/|\.)/i;
const UTILITY_PATTERN = /(^|\/)(utils?|helpers?|lib)(\/|\.)/i;

/** Categorizes nodes using signals we actually have: in-degree (from
 * the real edge list) for "entry point", and path patterns for the
 * rest. Not as precise as a real module classifier, but honest about
 * what the backend can tell us. */
export function categorizeNodes(nodes: GraphNode[], edges: GraphEdge[]): CategorizedNode[] {
    const inDegree = new Map<string, number>();
    const outDegree = new Map<string, number>();
    for (const n of nodes) {
        inDegree.set(n.id, 0);
        outDegree.set(n.id, 0);
    }
    for (const e of edges) {
        outDegree.set(e.source, (outDegree.get(e.source) ?? 0) + 1);
        inDegree.set(e.target, (inDegree.get(e.target) ?? 0) + 1);
    }

    return nodes.map((n) => {
        const inD = inDegree.get(n.id) ?? 0;
        const outD = outDegree.get(n.id) ?? 0;
        let category: FileCategory;
        if (inD === 0 && outD > 0) category = "entry";
        else if (TEST_PATTERN.test(n.label)) category = "test";
        else if (TYPES_PATTERN.test(n.label)) category = "types";
        else if (UTILITY_PATTERN.test(n.label)) category = "utility";
        else category = "core";
        return { ...n, category, inDegree: inD, outDegree: outD };
    });
}

export interface LayoutPosition {
    x: number;
    y: number;
}

const COL_WIDTH = 260;
const ROW_HEIGHT = 64;

/** Left-to-right layered layout: level = longest path from any
 * zero-indegree node, via Kahn's algorithm. Nodes stuck in an import
 * cycle (never resolved) are dumped one column past the deepest
 * resolved node rather than looping forever. */
export function computeLayeredPositions(
    nodes: CategorizedNode[],
    edges: GraphEdge[]
): Map<string, LayoutPosition> {
    const nodeIds = new Set(nodes.map((n) => n.id));
    const adjacency = new Map<string, string[]>();
    const inDegree = new Map<string, number>();
    for (const n of nodes) {
        adjacency.set(n.id, []);
        inDegree.set(n.id, 0);
    }
    for (const e of edges) {
        if (!nodeIds.has(e.source) || !nodeIds.has(e.target)) continue;
        adjacency.get(e.source)!.push(e.target);
        inDegree.set(e.target, (inDegree.get(e.target) ?? 0) + 1);
    }

    const level = new Map<string, number>();
    const remainingIn = new Map(inDegree);
    const queue: string[] = [];
    for (const n of nodes) {
        if ((inDegree.get(n.id) ?? 0) === 0) {
            level.set(n.id, 0);
            queue.push(n.id);
        }
    }

    while (queue.length) {
        const id = queue.shift()!;
        const myLevel = level.get(id) ?? 0;
        for (const next of adjacency.get(id) ?? []) {
            level.set(next, Math.max(level.get(next) ?? 0, myLevel + 1));
            remainingIn.set(next, (remainingIn.get(next) ?? 0) - 1);
            if ((remainingIn.get(next) ?? 0) <= 0 && !queue.includes(next)) {
                queue.push(next);
            }
        }
    }

    const maxResolvedLevel = Math.max(0, ...Array.from(level.values()));
    for (const n of nodes) {
        if (!level.has(n.id)) level.set(n.id, maxResolvedLevel + 1);
    }

    const byLevel = new Map<number, string[]>();
    for (const n of nodes) {
        const lvl = level.get(n.id) ?? 0;
        if (!byLevel.has(lvl)) byLevel.set(lvl, []);
        byLevel.get(lvl)!.push(n.id);
    }

    const idToLabel = new Map(nodes.map((n) => [n.id, n.label]));
    const positions = new Map<string, LayoutPosition>();
    for (const [lvl, ids] of byLevel) {
        ids.sort((a, b) => (idToLabel.get(a) ?? "").localeCompare(idToLabel.get(b) ?? ""));
        const count = ids.length;
        ids.forEach((id, i) => {
            positions.set(id, {
                x: lvl * COL_WIDTH,
                y: i * ROW_HEIGHT - ((count - 1) * ROW_HEIGHT) / 2,
            });
        });
    }

    return positions;
}