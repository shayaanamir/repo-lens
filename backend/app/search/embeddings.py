import asyncio
import logging
import os
import threading

import numpy as np
from qdrant_client import models

from app.core.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
# Name exactly as shown in the Qdrant Cloud Inference tab.
CLOUD_INFERENCE_MODEL_NAME = "sentence-transformers/all-minilm-l6-v2"

# Must match qdrant_client.py's VECTOR_SIZE.
OUTPUT_DIMENSIONALITY = 384

EMBED_BATCH_SIZE = 32

# The cloud model's context window is 256 tokens (~1000 chars of code).
# The local model silently truncates at the same limit, so truncating
# the text we send keeps the two providers behaving alike. The full
# chunk is still stored in the payload.
CLOUD_MAX_INPUT_CHARS = 1500

MODEL_CACHE_DIR = os.environ.get("FASTEMBED_CACHE_PATH", "/opt/fastembed_cache")

_model = None
_model_lock = threading.Lock()


class EmbeddingError(Exception):
    """Raised when local embedding generation fails unexpectedly."""
    pass


class EmbeddingTaskType:
    """Kept for interface compatibility with callers. all-MiniLM-L6-v2
    is symmetric (no distinct query/document mode)."""
    DOCUMENT = "document"
    CODE_QUERY = "query"


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                # Imported lazily so the qdrant_cloud provider never
                # pays the onnxruntime import cost in RAM.
                from fastembed import TextEmbedding

                logger.info("Loading embedding model %s...", EMBEDDING_MODEL_NAME)
                _model = TextEmbedding(
                    model_name=EMBEDDING_MODEL_NAME, cache_dir=MODEL_CACHE_DIR
                )
                logger.info("Embedding model loaded")
    return _model


def _encode(model, texts: list[str]) -> list[list[float]]:
    vectors = np.array(
        list(model.embed(texts, batch_size=EMBED_BATCH_SIZE)), dtype=np.float32
    )
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (vectors / norms).tolist()


async def embed_texts(texts: list[str], task_type: str) -> list:
    """
    Returns one embedding per input text.

    - provider "local": a list of float vectors, computed on this machine.
    - provider "qdrant_cloud": a list of qdrant `Document` objects. No
      network call happens here; Qdrant Cloud generates the vectors when
      the Document is upserted or used as a query, so callers can pass
      the result straight to upsert/query_points unchanged.
    """
    if not texts:
        return []

    if settings.embedding_provider == "qdrant_cloud":
        return [
            models.Document(
                text=text[:CLOUD_MAX_INPUT_CHARS], model=CLOUD_INFERENCE_MODEL_NAME
            )
            for text in texts
        ]

    model = await asyncio.to_thread(_get_model)
    return await asyncio.to_thread(_encode, model, texts)