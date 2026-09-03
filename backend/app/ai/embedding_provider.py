from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EmbeddingIdentity:
    provider: str
    model: str
    dimensions: int

    @property
    def version(self) -> str:
        return f"{self.provider}:{self.model}:{self.dimensions}"


class EmbeddingProvider(Protocol):
    @property
    def identity(self) -> EmbeddingIdentity:
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        ...

