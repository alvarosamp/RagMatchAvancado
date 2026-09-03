from types import SimpleNamespace

import pytest

from app.ai.embedding_provider import EmbeddingIdentity
from app.services import catalog_embeddings


class FakeSession:
    def __init__(self):
        self.flush_count = 0
        self.commit_count = 0

    def flush(self):
        self.flush_count += 1

    def commit(self):
        self.commit_count += 1


class FakeQuery:
    def __init__(self, products):
        self._products = products

    def all(self):
        return list(self._products)


def _product(**overrides):
    values = {
        "id": "product-1",
        "name": "Notebook corporativo",
        "brand": "Marca A",
        "model": "N14",
        "manufacturer_part_number": "PN-1",
        "sku": "SKU-1",
        "category": "informatica",
        "specification": "16 GB RAM SSD 512 GB",
        "description": None,
        "keywords": None,
        "equivalent_skus": None,
        "notes": None,
        "embedding": None,
        "embedding_model": None,
        "embedding_provider": None,
        "embedding_dimensions": None,
        "embedding_source_hash": None,
        "embedding_updated_at": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_embedding_hash_changes_only_when_searchable_content_changes():
    product = _product()
    original = catalog_embeddings.catalog_embedding_source_hash(product)
    product.cost = 999.0
    assert catalog_embeddings.catalog_embedding_source_hash(product) == original
    product.specification = "32 GB RAM SSD 1 TB"
    assert catalog_embeddings.catalog_embedding_source_hash(product) != original


def test_ensure_catalog_embeddings_updates_stale_and_reuses_current(monkeypatch):
    identity = EmbeddingIdentity("test", "embed-v2", 3)
    current = _product(
        embedding=[1.0, 0.0, 0.0],
        embedding_model=identity.model,
        embedding_provider=identity.provider,
        embedding_dimensions=identity.dimensions,
    )
    current.embedding_source_hash = catalog_embeddings.catalog_embedding_source_hash(current)
    stale = _product(sku="SKU-2", name="Mouse", embedding=[0.0, 1.0, 0.0])
    embedded_texts = []

    monkeypatch.setattr(catalog_embeddings, "get_embedding_identity", lambda: identity)
    monkeypatch.setattr(
        catalog_embeddings,
        "embed_texts_batch",
        lambda texts: embedded_texts.extend(texts) or [[0.1, 0.2, 0.3] for _ in texts],
    )
    session = FakeSession()

    stats = catalog_embeddings.ensure_catalog_embeddings(session, [current, stale])

    assert stats == {
        "total": 2,
        "updated": 1,
        "reused": 1,
        "embedding_version": "test:embed-v2:3",
    }
    assert len(embedded_texts) == 1
    assert current.embedding == [1.0, 0.0, 0.0]
    assert stale.embedding == [0.1, 0.2, 0.3]
    assert stale.embedding_source_hash == catalog_embeddings.catalog_embedding_source_hash(stale)
    # A persistencia participa da mesma transacao do match; o servico nao
    # confirma nem faz flush parcial antes de o ranking terminar.
    assert session.flush_count == 0


def test_ensure_catalog_embeddings_rejects_wrong_dimensions_without_mutating(monkeypatch):
    product = _product()
    monkeypatch.setattr(
        catalog_embeddings,
        "get_embedding_identity",
        lambda: EmbeddingIdentity("test", "broken", 3),
    )
    monkeypatch.setattr(catalog_embeddings, "embed_texts_batch", lambda texts: [[0.1, 0.2]])

    with pytest.raises(ValueError, match="dimensao"):
        catalog_embeddings.ensure_catalog_embeddings(FakeSession(), [product])
    assert product.embedding is None


def test_catalog_embedding_status_reports_stale_reasons(monkeypatch):
    identity = EmbeddingIdentity("test", "embed-v2", 3)
    current = _product(
        embedding=[1.0, 0.0, 0.0],
        embedding_model=identity.model,
        embedding_provider=identity.provider,
        embedding_dimensions=identity.dimensions,
    )
    current.embedding_source_hash = catalog_embeddings.catalog_embedding_source_hash(current)
    stale = _product(sku="SKU-2", name="Mouse")

    monkeypatch.setattr(catalog_embeddings, "get_embedding_identity", lambda: identity)
    monkeypatch.setattr(catalog_embeddings, "_catalog_query", lambda db, tenant_id, active_only: FakeQuery([current, stale]))

    status = catalog_embeddings.catalog_embedding_status(FakeSession(), 10)

    assert status["total"] == 2
    assert status["current"] == 1
    assert status["stale"] == 1
    assert status["coverage"] == 0.5
    assert status["reason_counts"]["missing_vector"] == 1
    assert status["examples"][0]["id"] == stale.id


def test_backfill_catalog_embeddings_processes_only_stale_products(monkeypatch):
    identity = EmbeddingIdentity("test", "embed-v2", 3)
    current = _product(
        id="current",
        embedding=[1.0, 0.0, 0.0],
        embedding_model=identity.model,
        embedding_provider=identity.provider,
        embedding_dimensions=identity.dimensions,
    )
    current.embedding_source_hash = catalog_embeddings.catalog_embedding_source_hash(current)
    stale = _product(id="stale", sku="SKU-2", name="Mouse")

    monkeypatch.setattr(catalog_embeddings, "get_embedding_identity", lambda: identity)
    monkeypatch.setattr(catalog_embeddings, "_catalog_query", lambda db, tenant_id, active_only: FakeQuery([current, stale]))
    monkeypatch.setattr(catalog_embeddings, "embed_texts_batch", lambda texts: [[0.1, 0.2, 0.3] for _ in texts])
    session = FakeSession()

    result = catalog_embeddings.backfill_catalog_embeddings(session, 10, limit=10)

    assert result["processed"] == 1
    assert result["embedding"]["updated"] == 1
    assert result["status"]["stale"] == 0
    assert result["has_more"] is False
    assert session.commit_count == 1
