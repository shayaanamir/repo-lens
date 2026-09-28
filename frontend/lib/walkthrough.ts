// Pulls a file-path-looking token out of a talking point, so flowchart
// nodes can show "app/routing.py" instead of a full sentence. Prefers
// backtick-quoted spans (the AI tends to format file refs that way),
// falls back to a bare path/filename pattern with an extension.
const FILE_TOKEN_PATTERN = /`([^`]+)`|(\b[\w.-]+(?:\/[\w.-]+)*\.\w{1,10}\b)/g;

export function extractFileReference(text: string): string | null {
    const matches = Array.from(text.matchAll(FILE_TOKEN_PATTERN));
    for (const m of matches) {
        const candidate = (m[1] ?? m[2] ?? "").trim();
        if (candidate && !candidate.includes(" ") && /\.\w{1,10}$/.test(candidate)) {
            return candidate;
        }
    }
    return null;
}