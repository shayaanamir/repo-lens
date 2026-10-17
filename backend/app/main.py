from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.repo.router import router as repo_router
from app.jobs.worker import run_worker_loop
from app.jobs.router import router as jobs_router
from app.analysis.router import router as analysis_router
from app.search.qdrant_client import ensure_collection
from app.search.router import router as search_router
from app.ai.router import router as ai_router
from app.core.config import settings

import logging
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_collection()
    worker_task = asyncio.create_task(run_worker_loop())
    yield
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="RepoLens", lifespan=lifespan)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(repo_router)
app.include_router(jobs_router)
app.include_router(analysis_router)
app.include_router(search_router)
app.include_router(ai_router)

@app.get("/health")
def health():
    return {"status": "ok"}