# backend/scripts/test_cloud_inference.py
"""
Smoke-tests Qdrant Cloud Inference end to end against a real cluster,
using a throwaway collection that is deleted at the end.

Run with the cloud settings passed as environment variables (never
commit them):
    docker compose exec -e QDRANT_URL=... -e QDRANT_API_KEY=... ^
        -e EMBEDDING_PROVIDER=qdrant_cloud ^
        -e QDRANT_COLLECTION_NAME=repolens_smoketest ^
        backend python -m scripts.test_cloud_inference
"""
import asyncio
import uuid

from app.core.config import settings
from app.search.embeddings import EmbeddingTaskType, embed_texts
from app.search.qdrant_client import (
    ensure_collection,
    get_qdrant_client,
    search_chunks,
    upsert_chunk_vectors,
)

SAMPLES = [
    ("add.py", "def add(a, b):\n    return a + b"),
    ("users.py", "class UserRepository:\n    def find_by_id(self, id):\n        pass"),
    ("retry.py", "def retry(fn, attempts=3):\n    for _ in range(attempts):\n        try:\n            return fn()\n        except Exception:\n            pass"),
]


async def main():
    assert settings.embedding_provider == "qdrant_cloud", "set EMBEDDING_PROVIDER=qdrant_cloud"
    assert settings.qdrant_collection_name != "code_chunks", "use a throwaway collection name"

    repo_id = uuid.uuid4()
    await ensure_collection()
    try:
        docs = await embed_texts([s[1] for s in SAMPLES], EmbeddingTaskType.DOCUMENT)
        points = [
            (uuid.uuid4(), doc, {
                "repository_id": str(repo_id), "file_id": str(uuid.uuid4()),
                "path": path, "start_line": 1, "end_line": 3,
                "symbol_name": None, "symbol_kind": None, "content": content,
            })
            for (path, content), doc in zip(SAMPLES, docs)
        ]
        await upsert_chunk_vectors(repo_id, points)
        print(f"Upserted {len(points)} points")

        query = (await embed_texts(["function that adds two numbers"], EmbeddingTaskType.CODE_QUERY))[0]
        results = await search_chunks(repo_id, query, limit=3)
        for r in results:
            print(f"{r.score:.3f}  {r.payload['path']}")

        assert results and results[0].payload["path"] == "add.py", "unexpected top result"
        print("OK: cloud inference works end to end")
    finally:
        client = get_qdrant_client()
        await client.delete_collection(settings.qdrant_collection_name)
        print(f"Deleted throwaway collection '{settings.qdrant_collection_name}'")


if __name__ == "__main__":
    asyncio.run(main())