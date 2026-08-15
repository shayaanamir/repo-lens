import asyncio
from math import sqrt

from app.search.embeddings import embed_texts, EmbeddingTaskType, OUTPUT_DIMENSIONALITY


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _magnitude(v: list[float]) -> float:
    return sqrt(sum(x * x for x in v))


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    return _dot(a, b) / (_magnitude(a) * _magnitude(b))


async def main():
    texts = [
        "def add(a, b):\n    return a + b",          # 0: adds two numbers
        "def sum_values(x, y):\n    return x + y",     # 1: also adds two numbers (should be close to 0)
        "class UserRepository:\n    def find_by_id(self, id):\n        pass",  # 2: unrelated (DB lookup)
    ]

    print(f"Requesting embeddings for {len(texts)} texts (task=RETRIEVAL_DOCUMENT)...")
    embeddings = await embed_texts(texts, EmbeddingTaskType.DOCUMENT)

    assert len(embeddings) == len(texts), "Got back a different number of embeddings than inputs"
    for i, vec in enumerate(embeddings):
        assert len(vec) == OUTPUT_DIMENSIONALITY, f"Vector {i} has wrong dimensionality: {len(vec)}"
        mag = _magnitude(vec)
        print(f"  [{i}] dims={len(vec)} magnitude={mag:.4f} (should be ~1.0 after normalization)")

    sim_similar = _cosine_similarity(embeddings[0], embeddings[1])
    sim_different = _cosine_similarity(embeddings[0], embeddings[2])

    print(f"\ncosine(add_fn, sum_fn)        = {sim_similar:.4f}  (expect high, similar logic)")
    print(f"cosine(add_fn, UserRepository) = {sim_different:.4f}  (expect lower, unrelated)")

    if sim_similar > sim_different:
        print("\n✅ Sanity check passed: semantically similar code embedded closer together.")
    else:
        print("\n⚠️  Unexpected: similar code did not embed closer than unrelated code.")

    print("\nNow testing a query-side embedding (task=CODE_RETRIEVAL_QUERY)...")
    query_vec = (await embed_texts(["function that adds two numbers"], EmbeddingTaskType.CODE_QUERY))[0]
    print(f"  query dims={len(query_vec)} magnitude={_magnitude(query_vec):.4f}")
    print(f"  cosine(query, add_fn) = {_cosine_similarity(query_vec, embeddings[0]):.4f}  (expect high)")
    print(f"  cosine(query, UserRepository) = {_cosine_similarity(query_vec, embeddings[2]):.4f}  (expect lower)")


if __name__ == "__main__":
    asyncio.run(main())