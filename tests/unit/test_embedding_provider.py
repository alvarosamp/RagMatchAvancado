import pytest

from app.ai.ollama_provider import OllamaEmbeddingProvider


class FakeClient:
    def __init__(self, vectors):
        self.vectors = iter(vectors)

    def embeddings(self, *, model, prompt):
        return {"embedding": next(self.vectors)}


def test_ollama_provider_exposes_version_and_preserves_order():
    provider = OllamaEmbeddingProvider(
        client=FakeClient([[1.0, 0.0], [0.0, 1.0]]),
        model="embed-test",
        dimensions=2,
        batch_size=1,
        max_attempts=1,
    )

    assert provider.identity.version == "ollama:embed-test:2"
    assert provider.embed(["primeiro", "segundo"]) == [[1.0, 0.0], [0.0, 1.0]]


def test_ollama_provider_rejects_incompatible_dimension():
    provider = OllamaEmbeddingProvider(
        client=FakeClient([[1.0]]),
        model="embed-test",
        dimensions=2,
        max_attempts=1,
    )

    with pytest.raises(ValueError, match="esperado 2"):
        provider.embed(["texto"])
