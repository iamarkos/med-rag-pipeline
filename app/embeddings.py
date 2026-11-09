"""One embedding function, shared by the worker and the API.

Documents (in the worker) and search questions (in the API) must be turned into
vectors by the same model, otherwise their distances mean nothing. Keeping the
model name and the function in one place guarantees that.
"""

from functools import lru_cache

from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """Load the model the first time it is needed, then reuse it."""
    return SentenceTransformer(EMBEDDING_MODEL_NAME)


def embed_text(text: str) -> list[float]:
    """Turn text into a vector of 384 floating-point numbers."""
    vector: list[float] = get_embedding_model().encode(text).tolist()
    return vector
