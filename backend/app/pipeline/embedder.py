"""
pipeline/embedder.py
────────────────────
Gera embeddings via Ollama (nomic-embed-text).
Retorna vetores de dimensão 768 prontos para pgvector.
"""

from __future__ import annotations

import time
from typing import Generator

import os
import ollama

from app.logs.config import logger

EMBED_MODEL  = "nomic-embed-text"
BATCH_SIZE   = 32
_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
_client      = ollama.Client(host=_OLLAMA_HOST)


def embed_text(text: str) -> list[float]:
    """Gera embedding para um único texto."""
    resp = _client.embeddings(model=EMBED_MODEL, prompt=text)
    return resp["embedding"]


def embed_texts_batch(texts: list[str]) -> list[list[float]]:
    """
    Gera embeddings em lote com retry simples.
    Retorna lista de vetores na mesma ordem dos textos.
    """
    embeddings: list[list[float]] = []

    for batch in _batched(texts, BATCH_SIZE):
        for attempt in range(3):
            try:
                batch_embs = [
                    ollama.embeddings(model=EMBED_MODEL, prompt=t)["embedding"]
                    for t in batch
                ]
                embeddings.extend(batch_embs)
                break
            except Exception as e:
                if attempt == 2:
                    logger.error(f"[Embedder] Falha após 3 tentativas: {e}")
                    raise
                wait = 2 ** attempt
                logger.warning(f"[Embedder] Erro (tentativa {attempt+1}), aguardando {wait}s: {e}")
                time.sleep(wait)

    logger.info(f"[Embedder] {len(texts)} textos → {len(embeddings)} embeddings gerados")
    return embeddings


# ──────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────

def _batched(items: list, size: int) -> Generator[list, None, None]:
    for i in range(0, len(items), size):
        yield items[i : i + size]