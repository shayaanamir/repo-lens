from fastapi import FastAPI

from app.repo.router import router as repo_router

app = FastAPI(title="RepoLens")

app.include_router(repo_router)

@app.get("/health")
def health():
    return {"status": "ok"}