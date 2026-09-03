"""Generate versioned embeddings through the configured provider."""

from __future__ import annotations

import os

import ollama

from app.ai.embedding_provider import EmbeddingIdentity, EmbeddingProvider
from app.ai.ollama_provider import OllamaEmbeddingProvider
from app.core.ml_config import get_ml_config
from app.logs.config import logger

EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
BATCH_SIZE = 32
_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
_client = ollama.Client(host=_OLLAMA_HOST)
_provider: EmbeddingProvider = OllamaEmbeddingProvider(
    client=_client,
    model=EMBED_MODEL,
    dimensions=get_ml_config().embed_dims,
    batch_size=BATCH_SIZE,
)


def embed_text(text: str) -> list[float]:
    """Generate one embedding."""
    return _provider.embed([text])[0]


def embed_texts_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings in input order with provider-level validation."""
    embeddings = _provider.embed(texts)
    logger.info("[Embedder] %s textos -> %s embeddings gerados", len(texts), len(embeddings))
    return embeddings


def get_embedding_identity() -> EmbeddingIdentity:
    """Return the provider/model/schema identity stored with each vector."""
    return _provider.identity
