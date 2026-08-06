from fastapi import FastAPI

app = FastAPI(title="RepoLens")

@app.get("/health")
def health():
    return {"status": "ok"}