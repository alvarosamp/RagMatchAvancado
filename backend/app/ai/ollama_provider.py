from __future__ import annotations

import time
from typing import Any

from app.ai.embedding_provider import EmbeddingIdentity
from app.logs.config import logger


class OllamaEmbeddingProvider:
    def __init__(
        self,
        *,
        client: Any,
        model: str,
        dimensions: int,
        batch_size: int = 32,
        max_attempts: int = 3,
    ) -> None:
        self.client = client
        self.model = model
        self.dimensions = dimensions
        self.batch_size = batch_size
        self.max_attempts = max_attempts

    @property
    def identity(self) -> EmbeddingIdentity:
        return EmbeddingIdentity(provider="ollama", model=self.model, dimensions=self.dimensions)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            for attempt in range(self.max_attempts):
                try:
                    batch_vectors = [
                        list(self.client.embeddings(model=self.model, prompt=text)["embedding"])
                        for text in batch
                    ]
                    self._validate(batch_vectors)
                    vectors.extend(batch_vectors)
                    break
                except Exception as exc:
                    if attempt + 1 >= self.max_attempts:
                        logger.error("[EmbeddingProvider] Falha apos %s tentativas: %s", self.max_attempts, exc)
                        raise
                    wait_seconds = 2**attempt
                    logger.warning(
                        "[EmbeddingProvider] Tentativa %s falhou; novo envio em %ss: %s",
                        attempt + 1,
                        wait_seconds,
                        exc,
                    )
                    time.sleep(wait_seconds)
        return vectors

    def _validate(self, vectors: list[list[float]]) -> None:
        for vector in vectors:
            if len(vector) != self.dimensions:
                raise ValueError(
                    f"Embedding {self.model} retornou {len(vector)} dimensoes; esperado {self.dimensions}."
                )
