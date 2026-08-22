import pytest

from app.search.embeddings import EmbeddingTaskType, OUTPUT_DIMENSIONALITY, embed_texts


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _magnitude(v: list[float]) -> float:
    return sum(x * x for x in v) ** 0.5


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    return _dot(a, b) / (_magnitude(a) * _magnitude(b))


# Marked integration since it loads the real sentence-transformers model
# (a few seconds on first call, cached after) rather than mocking it —
# mirrors test_git_service.py's pattern of hitting the real dependency
# for a true sanity check, not just exercising the code path.
pytestmark = pytest.mark.integration


@pytest.mark.anyio
async def test_embed_texts_returns_correct_shape_and_normalization():
    texts = [
        "def add(a, b):\n    return a + b",
        "def sum_values(x, y):\n    return x + y",
    ]

    embeddings = await embed_texts(texts, EmbeddingTaskType.DOCUMENT)

    assert len(embeddings) == len(texts)
    for vec in embeddings:
        assert len(vec) == OUTPUT_DIMENSIONALITY
        # normalize_embeddings=True should give unit vectors
        assert abs(_magnitude(vec) - 1.0) < 1e-4


@pytest.mark.anyio
async def test_empty_input_returns_empty_list():
    assert await embed_texts([], EmbeddingTaskType.DOCUMENT) == []


@pytest.mark.anyio
async def test_similar_code_embeds_closer_than_unrelated_code():
    """
    Sanity check mirroring TASKS.md Phase 4's 'query relevance sanity
    checks': two functions doing the same thing (adding two numbers)
    should land closer together than either does to an unrelated class,
    regardless of which embedding provider is behind embed_texts().
    """
    texts = [
        "def add(a, b):\n    return a + b",                                    # 0: adds two numbers
        "def sum_values(x, y):\n    return x + y",                              # 1: also adds two numbers
        "class UserRepository:\n    def find_by_id(self, id):\n        pass",   # 2: unrelated (DB lookup)
    ]

    embeddings = await embed_texts(texts, EmbeddingTaskType.DOCUMENT)

    sim_similar = _cosine_similarity(embeddings[0], embeddings[1])
    sim_different = _cosine_similarity(embeddings[0], embeddings[2])

    assert sim_similar > sim_different


@pytest.mark.anyio
async def test_query_embedding_ranks_matching_code_higher():
    """Natural-language query should score closer to the function it
    actually describes than to an unrelated one — the exact mechanic
    the /search endpoint depends on."""
    add_fn = "def add(a, b):\n    return a + b"
    unrelated = "class UserRepository:\n    def find_by_id(self, id):\n        pass"

    doc_embeddings = await embed_texts([add_fn, unrelated], EmbeddingTaskType.DOCUMENT)
    query_embedding = (
        await embed_texts(["function that adds two numbers"], EmbeddingTaskType.CODE_QUERY)
    )[0]

    sim_to_add_fn = _cosine_similarity(query_embedding, doc_embeddings[0])
    sim_to_unrelated = _cosine_similarity(query_embedding, doc_embeddings[1])

    assert sim_to_add_fn > sim_to_unrelated