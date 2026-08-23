// Typed fetch wrapper for the RepoLens backend API.
// Base URL comes from NEXT_PUBLIC_API_URL so it works both in the
// browser (localhost:8000) and, if ever needed, server-side.

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
    status: number;
    detail: string;

    constructor(status: number, detail: string) {
        super(detail);
        this.status = status;
        this.detail = detail;
        this.name = "ApiError";
    }
}

async function request<T>(
    path: string,
    options: RequestInit = {}
): Promise<T> {
    const res = await fetch(`${API_BASE_URL}${path}`, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...options.headers,
        },
    });

    if (!res.ok) {
        let detail = res.statusText;
        try {
            const body = await res.json();
            detail = body.detail || detail;
        } catch {
            // response body wasn't JSON — fall back to statusText
        }
        throw new ApiError(res.status, detail);
    }

    // 204 No Content etc. — nothing to parse
    if (res.status === 204) {
        return undefined as T;
    }

    return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------
// Types (mirror backend/app/*/schemas.py)
// ---------------------------------------------------------------------

export interface Repository {
    id: string;
    github_url: string;
    name: string;
    default_branch: string;
    status: string; // "pending" | "indexing" | "ready" | "failed"
    primary_language: string | null;
    readme_content: string | null;
    summary: string | null;
    imported_at: string;
}

export interface FileEntry {
    id: string;
    path: string;
    language: string | null;
    size: number;
}

export interface FileContent {
    path: string;
    content: string;
}

export type JobStage = "clone" | "parse" | "embed" | "summarize";
export type JobStatus = "pending" | "running" | "completed" | "failed";

export interface Job {
    id: string;
    stage: JobStage;
    status: JobStatus;
    error: string | null;
    created_at: string;
    started_at: string | null;
    completed_at: string | null;
}

export interface JobListResponse {
    repository_id: string;
    jobs: Job[];
}

export interface GraphNode {
    id: string;
    label: string;
    language: string | null;
}

export interface GraphEdge {
    id: string;
    source: string;
    target: string;
}

export interface DependencyGraph {
    nodes: GraphNode[];
    edges: GraphEdge[];
}

export interface SearchResult {
    file_id: string;
    path: string;
    start_line: number;
    end_line: number;
    symbol_name: string | null;
    symbol_kind: string | null;
    score: number;
}

export interface SearchResponse {
    query: string;
    results: SearchResult[];
}

export interface SourceRef {
    path: string;
    start_line: number;
    end_line: number;
}

export interface ChatResponse {
    answer: string;
    sources: SourceRef[];
}

export interface ExplainResponse {
    explanation: string;
    sources: SourceRef[];
}

// ---------------------------------------------------------------------
// Repo Module
// ---------------------------------------------------------------------

export function createRepository(githubUrl: string): Promise<Repository> {
    return request<Repository>("/repositories", {
        method: "POST",
        body: JSON.stringify({ github_url: githubUrl }),
    });
}

export function getRepository(id: string): Promise<Repository> {
    return request<Repository>(`/repositories/${id}`);
}

export function listFiles(id: string): Promise<FileEntry[]> {
    return request<FileEntry[]>(`/repositories/${id}/files`);
}

export function getFileContent(id: string, path: string): Promise<FileContent> {
    // Path segments (slashes) are preserved by the backend's {file_path:path}
    // route — encode each segment individually so slashes survive.
    const encodedPath = path.split("/").map(encodeURIComponent).join("/");
    return request<FileContent>(`/repositories/${id}/files/${encodedPath}`);
}

// ---------------------------------------------------------------------
// Jobs Module
// ---------------------------------------------------------------------

export function getJobs(id: string): Promise<JobListResponse> {
    return request<JobListResponse>(`/repositories/${id}/jobs`);
}

// ---------------------------------------------------------------------
// Analysis Module
// ---------------------------------------------------------------------

export function getDependencyGraph(id: string): Promise<DependencyGraph> {
    return request<DependencyGraph>(`/repositories/${id}/graph`);
}

// ---------------------------------------------------------------------
// Search Module
// ---------------------------------------------------------------------

export function searchRepository(id: string, query: string, limit = 10): Promise<SearchResponse> {
    const params = new URLSearchParams({ q: query, limit: String(limit) });
    return request<SearchResponse>(`/repositories/${id}/search?${params}`);
}

// ---------------------------------------------------------------------
// AI Module
// ---------------------------------------------------------------------

export function chatWithRepository(id: string, question: string): Promise<ChatResponse> {
    return request<ChatResponse>(`/repositories/${id}/chat`, {
        method: "POST",
        body: JSON.stringify({ question }),
    });
}

export function explainFile(id: string, path: string): Promise<ExplainResponse> {
    const encodedPath = path.split("/").map(encodeURIComponent).join("/");
    return request<ExplainResponse>(`/repositories/${id}/files/${encodedPath}/explain`, {
        method: "POST",
    });
}