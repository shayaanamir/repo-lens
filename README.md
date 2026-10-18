# RepoLens

> Read the blueprint before you read the code.

RepoLens helps developers understand an unfamiliar GitHub repository in minutes instead of hours. Paste a public repository URL and RepoLens clones it, parses it with Tree-sitter, maps how its files depend on each other, indexes it for semantic search, and answers questions grounded in the code it actually found, with file and line citations.

**Live demo:** https://repo-lens-indol.vercel.app/
**API docs:** https://repo-lens-0n6p.onrender.com/docs

> The demo runs entirely on free hosting tiers. After a period of inactivity the backend sleeps, so the first request can take about a minute to wake it.


![Dashboard](docs/dashboard.png)
![Dependency graph](docs/graph.png)
![Chat with citations](docs/chat.png)


---

## Why RepoLens is different

Most AI code tools put a chatbot in front of a pile of files. RepoLens builds a structured understanding of the repository first and only then brings in AI.

- **Deterministic before AI.** Static analysis (symbols, imports, dependency edges) always runs first. The AI layer only explains what parsing already found.
- **Every answer is sourced.** Chat and file explanations return the files and line ranges they were grounded in, and the UI links straight to them.
- **Useful without AI.** Browsing, search and the dependency graph never depend on a language model being available. If Gemini is rate-limited or down, only chat and explanations are affected, and they fail with a clear message instead of a crash.
- **Indexing never blocks the UI.** Import returns immediately and a background pipeline does the heavy work while the UI polls its progress.

---

## Features

- **Import any public GitHub repository** by URL or `owner/repo` shorthand.
- **Dashboard** with an AI-generated summary, extracted facts (files, symbols, import edges, chunks), pipeline status, language breakdown, a "start here" list and the most-referenced modules.
- **File explorer** with a file tree and a syntax-highlighted Monaco viewer.
- **AI file explanations** that use the file's parsed symbols as context and cite the lines they relied on.
- **Dependency graph** of file-level imports, laid out in layers, with entry points, core modules, utilities, types and tests filterable and colour-coded. Click a node to see what it imports and what imports it.
- **Semantic search.** Describe behaviour in plain language ("retries a failed network request") and get matching code with file and line references.
- **AI chat** that retrieves relevant code chunks and answers from them, with clickable source citations.
- **Interview prep.** Generates an elevator pitch, an architecture walkthrough and likely interview questions for a repository, optionally woven around a hard problem you describe.
- **Per-browser repository lists.** No accounts needed: each visitor sees only the repositories they added, while indexed data is shared underneath so importing an already-indexed repo is instant.
- Light and dark themes.

---

## How it works

Importing a repository creates four background jobs that run in order. The dashboard shows live progress for each.

| Stage | What happens |
|---|---|
| **1. Clone** | Validates the URL against a host allowlist, then does an isolated, size- and time-limited shallow `git clone` (120 s, 500 MB). Extracts the README and primary language. |
| **2. Parse** | Scans files and stores text content in PostgreSQL. Tree-sitter extracts functions, classes and methods; import statements are resolved to in-repo files to build dependency edges. |
| **3. Embed** | Chunks code by symbol (falling back to overlapping line windows for files with no symbols), embeds each chunk with `all-MiniLM-L6-v2`, and stores vectors with file and line metadata in Qdrant. |
| **4. Summarize** | One Gemini call writes a short repository summary from the README, language and a sample of top-level symbols. A failure here never blocks the repository from becoming usable. |

Chat and file explanations use a **retrieve-then-generate** flow: the question is embedded, the top matching chunks are fetched from Qdrant (scoped to that repository), and only those excerpts go into the prompt.

---

## Architecture

RepoLens is a **modular monolith**: one FastAPI service organised into modules with clear boundaries, two purpose-built data stores, and a Next.js frontend.

```
┌──────────────────────────────────────────────────────────────┐
│                      Frontend (Next.js)                       │
│  Landing → Dashboard → Explorer → Graph → Search → Chat       │
└───────────────────────────────┬──────────────────────────────┘
                                │ REST / JSON
┌───────────────────────────────▼──────────────────────────────┐
│                       Backend (FastAPI)                       │
│  ┌────────┐ ┌──────────┐ ┌────────┐ ┌────────┐ ┌──────────┐  │
│  │  repo  │ │ analysis │ │ search │ │   ai   │ │   jobs   │  │
│  │ import │ │Tree-sitter│ │ chunks │ │ chat / │ │  queue + │  │
│  │ browse │ │  graph   │ │ vectors│ │ explain│ │  worker  │  │
│  └────────┘ └──────────┘ └────────┘ └────────┘ └──────────┘  │
└───────┬──────────────────────┬──────────────────────┬────────┘
        │                      │                      │
  ┌─────▼──────┐        ┌──────▼──────┐        ┌──────▼──────┐
  │ PostgreSQL │        │   Qdrant    │        │ Gemini API  │
  │ repos,files│        │  code chunk │        │ chat, explain│
  │ symbols,   │        │  embeddings │        │ summaries   │
  │ edges, jobs│        │             │        │             │
  └────────────┘        └─────────────┘        └─────────────┘
```

| Module | Responsibility |
|---|---|
| `repo` | URL validation, shallow cloning, metadata extraction, file browsing, per-visitor repository lists |
| `analysis` | Tree-sitter parsing, symbol and import extraction, import resolution, dependency graph |
| `search` | Chunking, embeddings, Qdrant storage and nearest-neighbour search |
| `ai` | Gemini client, prompt building, chat, file explanations, summaries, interview prep |
| `jobs` | Database-backed job queue, background worker, retries, recovery after restarts |
| `core` | Config, database session, rate limiting, admin auth, visitor identity |

The job queue is a plain `job` table plus a polling worker running inside the API process. That is enough for this scale and avoids running Redis or Celery.

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js (App Router), React, TypeScript, Tailwind CSS, shadcn/ui, `@xyflow/react` (React Flow), Monaco Editor, react-markdown |
| Backend | Python, FastAPI, SQLAlchemy (async), Alembic, Pydantic v2 |
| Code analysis | Tree-sitter (Python, JavaScript, TypeScript, TSX grammars) |
| Databases | PostgreSQL, Qdrant |
| Embeddings | `all-MiniLM-L6-v2` (384 dimensions): FastEmbed locally, Qdrant Cloud Inference in production |
| AI | Gemini API |
| Infrastructure | Docker, Docker Compose |

---

## Getting started (local)

### Prerequisites

- Docker and Docker Compose
- A [Gemini API key](https://aistudio.google.com/) (free tier is enough). Browsing, search and the graph work without one; chat, explanations and summaries need it.

### Run it

```bash
git clone https://github.com/shayaanamir/repo-lens.git
cd repo-lens
```

Create `backend/.env`:

```env
GEMINI_API_KEY=your-key-here
RATE_LIMITING_ENABLED=false
```

`DATABASE_URL` and `QDRANT_URL` are supplied by `docker-compose.yml`. Then start everything and apply the database migrations:

```bash
docker compose up --build
docker compose exec backend alembic upgrade head
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API docs (Swagger) | http://localhost:8000/docs |
| Qdrant dashboard | http://localhost:6333/dashboard |

Open the frontend, paste a repository such as `pallets/flask`, and watch the four pipeline stages complete.

The embedding model is downloaded into the backend image at build time, so the first build takes a little longer.

### Useful scripts

Run these inside the backend container:

```bash
docker compose exec backend python -m scripts.check_jobs                       # list job statuses
docker compose exec backend python -m scripts.retry_job <repo_id> <stage>      # re-run a failed stage
docker compose exec backend python -m scripts.reset_repos                      # delete all repositories, vectors and clones
docker compose exec backend python -m scripts.test_ai_module <repo_id>         # smoke-test chat and explain
```

---

## Configuration

### Backend

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | required | PostgreSQL URL, e.g. `postgresql+asyncpg://user:pass@host/db`. `sslmode` and `channel_binding` query parameters are translated automatically for asyncpg. |
| `QDRANT_URL` | required | Qdrant endpoint |
| `QDRANT_API_KEY` | empty | Needed for Qdrant Cloud |
| `QDRANT_COLLECTION_NAME` | `code_chunks` | Shared collection, filtered by `repository_id` |
| `EMBEDDING_PROVIDER` | `local` | `local` (FastEmbed on the backend) or `qdrant_cloud` (Qdrant Cloud Inference) |
| `GEMINI_API_KEY` | empty | Enables chat, explanations, summaries and interview prep |
| `GEMINI_MODEL` | see `config.py` | Gemini model name |
| `REPO_STORAGE_DIR` | `data/repos` | Where clones live while indexing |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed frontend origins |
| `RATE_LIMITING_ENABLED` | `true` | Per-IP and global rate limits |
| `MAX_REPOSITORIES` | `0` (unlimited) | Cap on total indexed repositories |
| `MAX_REPOSITORIES_PER_VISITOR` | `0` (unlimited) | Cap on each visitor's list |
| `AI_GLOBAL_HOURLY_LIMIT` | `0` (unlimited) | Shared hourly budget for Gemini calls |
| `ADMIN_TOKEN` | empty | When set, hard-deleting a repository requires `Authorization: Bearer <token>` |

### Frontend

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_URL` | Backend base URL (default `http://localhost:8000`). Baked in at build time. |

---

## API overview

The full, interactive reference is at `/docs`. Endpoints that read or change a visitor's list expect an `X-Visitor-Id` header, which the frontend generates and stores in the browser.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/repositories` | Add a repository to your list; indexes it if it's new |
| `GET` | `/repositories` | Your repositories |
| `GET` | `/repositories/{id}` | Metadata and status |
| `GET` | `/repositories/{id}/jobs` | Per-stage indexing status |
| `GET` | `/repositories/{id}/stats` | Dashboard statistics |
| `GET` | `/repositories/{id}/files` | File list |
| `GET` | `/repositories/{id}/files/{path}` | File contents |
| `GET` | `/repositories/{id}/graph` | Dependency graph (nodes and edges) |
| `GET` | `/repositories/{id}/search?q=` | Semantic code search |
| `POST` | `/repositories/{id}/chat` | Ask a question; returns an answer and `sources[]` |
| `POST` | `/repositories/{id}/files/{path}/explain` | AI explanation of a file, with `sources[]` |
| `POST` | `/repositories/{id}/interview-prep` | Pitch, walkthrough and likely questions |
| `DELETE` | `/repositories/{id}/membership` | Remove a repository from your list |
| `DELETE` | `/repositories/{id}` | Admin hard delete (requires `ADMIN_TOKEN`) |
| `GET` | `/health` | Liveness check |

---

## Testing

```bash
docker compose exec backend python -m pytest app -q                     # everything
docker compose exec backend python -m pytest app -q -m "not integration"   # skip tests that need the network
```

The backend has 160+ tests covering URL validation, cloning, metadata extraction, symbol and import extraction, import resolution, chunking, embeddings, the job worker and recovery, prompt building, the AI services, rate limiting, per-visitor lists and the API routers. Tests marked `integration` clone real repositories and load the real embedding model.

---

## Deployment

The public demo runs at zero cost:

| Component | Service |
|---|---|
| Frontend | Vercel |
| Backend (Docker) | Render, free web service |
| PostgreSQL | Neon, free tier |
| Vector store and embeddings | Qdrant Cloud, free cluster with Cloud Inference |
| LLM | Gemini API, free tier |

Running on small free instances shaped several design choices (see below). To deploy your own copy:

1. Create a Neon database and apply migrations with `alembic upgrade head`, using the **direct** (non-pooled) connection string.
2. Create a Qdrant Cloud cluster and note its URL and API key.
3. Create a Render web service from `backend/` (Docker runtime, health check path `/health`) with the environment variables above, including `EMBEDDING_PROVIDER=qdrant_cloud`.
4. Create a Vercel project from `frontend/` with `NEXT_PUBLIC_API_URL` set to the Render URL.
5. Set `CORS_ORIGINS` on Render to the Vercel URL.

---

## Design decisions and trade-offs

- **Swappable embeddings.** Embedding with the Gemini API hit the free-tier daily quota on a single mid-sized repository. The provider sits behind one `embed_texts()` function, so it was replaced with a local model, and later with Qdrant Cloud Inference for production, without touching chunking, storage or search. The same model and 384 dimensions were kept throughout, so existing vectors stayed valid.
- **Small backend footprint.** Loading a local embedding model needed far more memory and CPU than a 512 MB free instance provides, so production offloads embedding to Qdrant Cloud and the backend does no heavy compute.
- **Ephemeral disk.** Free hosting wipes the disk on restart, so file contents are stored in PostgreSQL (with per-file and per-repository size caps) and the explorer and explanations read from the database. On startup the worker detects interrupted pipelines and restarts them from the right stage.
- **Idempotent, ordered stages.** Re-running a stage deletes its previous output before writing new rows, and deletes commit in Postgres before cleaning Qdrant and disk, so retries never produce duplicates or half-deleted repositories.
- **Untrusted input.** Cloned repositories are never executed. URLs are validated against a host allowlist with strict path rules, file reads are guarded against path traversal, and clones are shallow, time-limited and size-limited.
- **Abuse protection without accounts.** Per-IP and global rate limits, a cap on total repositories, a shared hourly AI budget, and an admin-token-protected hard delete keep a public, unauthenticated demo within free-tier limits.
- **Shared index, private lists.** Repositories are indexed once and linked to visitors through a link table, so a repo someone already indexed appears instantly for the next visitor, and its data is purged automatically when nobody has it any more.

---

## Known limitations

- Symbol extraction and the dependency graph cover **Python, JavaScript, TypeScript and TSX**. Other languages can still be browsed and searched, but have no symbols or graph edges.
- Import resolution handles relative imports and Python package imports. Path aliases such as `@/components/...` in `tsconfig.json` are not resolved, so those edges are missing.
- The embedding model is general-purpose with a 256-token window, not code-specialised, so semantic search relevance is decent but not perfect.
- Only public repositories are supported. There are no user accounts; a visitor's list lives in their browser, so clearing site data loses it.
- On the free demo, the backend sleeps when idle, in-memory rate-limit counters reset on restart, and the number of repositories is capped.

---

## Roadmap

Ideas deliberately left out of the MVP:

- Private repositories and GitHub OAuth
- Pull request analysis
- Technical debt and security insights
- Architecture evolution timeline
- A code-specialised embedding model
- Team workspaces and multi-LLM support

---

## Project structure

```
repo-lens/
├── backend/
│   ├── app/
│   │   ├── core/        # config, db, rate limiting, auth, migrations
│   │   ├── repo/        # import, cloning, metadata, file browsing
│   │   ├── analysis/    # Tree-sitter parsing, symbols, imports, graph
│   │   ├── search/      # chunker, embeddings, Qdrant client
│   │   ├── ai/          # Gemini client, prompts, chat, explain, summary
│   │   ├── jobs/        # queue, worker, recovery
│   │   └── main.py
│   ├── scripts/         # maintenance and smoke-test scripts
│   └── Dockerfile
├── frontend/
│   ├── app/             # landing page and /repo/[id]/* routes
│   ├── components/
│   ├── hooks/
│   └── lib/             # API client, graph layout, file tree
├── docker-compose.yml
├── PROJECT.md           # vision, scope and requirements
├── ARCHITECTURE.md      # detailed design
└── TASKS.md             # phased build plan
```

---

## Author

Built by **Shayaan Amir** · [GitHub](https://github.com/shayaanamir) · [LinkedIn](https://linkedin.com/in/shayaan-amir)
