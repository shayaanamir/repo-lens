import type { FileEntry } from "@/lib/api-client";

export interface FileTreeNode {
    name: string;
    path: string;
    type: "file" | "dir";
    file?: FileEntry; // only set when type === "file"
    children?: FileTreeNode[]; // only set when type === "dir"
}

/** Turns a flat list of repo-relative file paths into a nested tree,
 * directories first then files, both alphabetical. */
export function buildFileTree(files: FileEntry[]): FileTreeNode[] {
    interface MutableNode {
        name: string;
        path: string;
        type: "file" | "dir";
        file?: FileEntry;
        children?: Record<string, MutableNode>;
    }

    const root: Record<string, MutableNode> = {};

    for (const file of files) {
        const parts = file.path.split("/").filter(Boolean);
        let cursor = root;

        parts.forEach((part, i) => {
            const isFile = i === parts.length - 1;
            const path = parts.slice(0, i + 1).join("/");

            if (!cursor[part]) {
                cursor[part] = isFile
                    ? { name: part, path, type: "file", file }
                    : { name: part, path, type: "dir", children: {} };
            }

            if (!isFile) {
                cursor = cursor[part].children!;
            }
        });
    }

    return sortTree(root);
}

function sortTree(map: Record<string, any>): FileTreeNode[] {
    const nodes = Object.values(map) as any[];
    nodes.sort((a, b) => {
        if (a.type !== b.type) return a.type === "dir" ? -1 : 1;
        return a.name.localeCompare(b.name);
    });

    return nodes.map((node) =>
        node.type === "dir"
            ? { ...node, children: sortTree(node.children) }
            : { name: node.name, path: node.path, type: "file", file: node.file }
    );
}