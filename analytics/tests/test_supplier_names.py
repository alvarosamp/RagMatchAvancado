from app.market_intelligence.models import (
    Entity,
    Fact,
    Feedback,
    Identity,
    ProductSupplier,
    Review,
)
from app.market_intelligence.repository import fact, resolve, review_identity, scoped
from app.market_intelligence.suppliers import canonical_id, normalize_suppliers


def test_formatting_variants_share_a_stable_name_and_preserve_originals(db):
    first = resolve(db, 1, "manual", "supplier", "a", {"name": "Ácme Tecnologia Ltda"})
    second = resolve(
        db, 1, "crm", "supplier", "b", {"name": "  ACME  TECNOLOGIA, LTDA. "}
    )
    assert first.id == second.id
    assert first.name == "ÁCME TECNOLOGIA LTDA"
    assert len(first.attributes["name_aliases"]) == 2
    assert (
        scoped(db, Identity, 1).filter_by(source="crm").one().evidence["source_name"]
        == "ACME  TECNOLOGIA, LTDA."
    )
    assert scoped(db, Review, 1).count() == 0


def test_same_name_with_different_full_cnpjs_remains_separate(db):
    a = resolve(
        db,
        1,
        "manual",
        "supplier",
        "a",
        {"name": "ACME", "tax_id": "00.000.000/E08G-12"},
    )
    b = resolve(
        db,
        1,
        "manual",
        "supplier",
        "b",
        {"name": "ACME", "tax_id": "00.000.000/0001-91"},
    )
    unknown = resolve(db, 1, "crm", "supplier", "c", {"name": "ACME"})
    normalize_suppliers(db, 1)
    assert len({a.id, b.id, unknown.id}) == 3
    assert a.active and b.active and unknown.active


def test_legal_suffix_without_cnpj_requires_review_and_consolidates_relations(db):
    target = resolve(db, 1, "crm", "supplier", "a", {"name": "ACME"})
    current = resolve(db, 1, "manual", "supplier", "b", {"name": "ACME Ltda"})
    product = resolve(db, 1, "manual", "product", "p", {"name": "Switch"})
    db.add(
        ProductSupplier(
            tenant_id=1,
            product_id=product.id,
            supplier_id=current.id,
            source="manual",
            cost=20,
        )
    )
    fact(
        db,
        1,
        "manual",
        "purchase",
        "purchase",
        supplier_id=current.id,
        attributes={"source_supplier_id": "b"},
    )
    db.flush()
    assert current.id != target.id
    pending = scoped(db, Review, 1).one()
    review_identity(db, 1, pending.id, "accepted", 100)
    assert not current.active
    assert scoped(db, ProductSupplier, 1).one().supplier_id == target.id
    assert scoped(db, Fact, 1).one().supplier_id == target.id
    assert canonical_id(db, 1, current.id) == target.id
    normalize_suppliers(db, 1)
    assert scoped(db, Entity, 1).filter_by(kind="supplier", active=True).count() == 1


def test_existing_duplicates_merge_history_and_links_without_crossing_tenants(db):
    product = resolve(db, 1, "manual", "product", "p", {"name": "Switch"})
    old = Entity(
        id="old",
        tenant_id=1,
        kind="supplier",
        identity_key="source:old",
        name="ACME Ltda",
        normalized_name="acme ltda",
        tax_id="00000000E08G12",
    )
    new = Entity(
        id="new",
        tenant_id=1,
        kind="supplier",
        identity_key="source:new",
        name="Acme Tecnologia",
        normalized_name="acme tecnologia",
        tax_id="00000000E08G12",
    )
    foreign = Entity(
        id="foreign",
        tenant_id=2,
        kind="supplier",
        identity_key="source:foreign",
        name="Acme",
        normalized_name="acme",
        tax_id="00000000E08G12",
    )
    db.add_all([old, new, foreign])
    db.flush()
    for supplier, source in ((old, "crm"), (new, "manual")):
        db.add(
            Identity(
                tenant_id=1,
                source=source,
                kind="supplier",
                source_id="s",
                entity_id=supplier.id,
                method="source_identity",
                confidence=1,
            )
        )
        db.add(
            ProductSupplier(
                tenant_id=1,
                source="manual",
                product_id=product.id,
                supplier_id=supplier.id,
                cost=10 if supplier is old else 20,
            )
        )
        fact(
            db,
            1,
            source,
            "purchase",
            "p",
            supplier_id=supplier.id,
            total_value=100,
            active=False,
        )
    feedback = Feedback(
        tenant_id=1,
        item_id="i",
        action="supplier_selected",
        user_id=100,
        payload={"supplier_id": "old"},
    )
    db.add(feedback)
    db.flush()
    result = normalize_suppliers(db, 1, 100)
    assert result["merged"] == 1
    target = scoped(db, Entity, 1).filter_by(kind="supplier", active=True).one()
    assert {row.supplier_id for row in scoped(db, Fact, 1)} == {target.id}
    assert scoped(db, ProductSupplier, 1).count() == 1
    assert foreign.active and foreign.name == "Acme"
    assert canonical_id(db, 1, feedback.payload["supplier_id"]) == target.id
    assert feedback.payload == {"supplier_id": "old"}
    audit = scoped(db, Review, 1).filter_by(reason="supplier_normalization").one()
    assert audit.reviewed_by == 100 and audit.evidence["collapsed_relations"]
    assert normalize_suppliers(db, 1)["merged"] == 0


def test_reimport_cannot_resurrect_a_consolidated_source_entity(db):
    for identity, source in (("a", "crm"), ("b", "manual")):
        db.add(
            Entity(
                id=identity,
                tenant_id=1,
                kind="supplier",
                identity_key=f"source:{source}:s",
                name="ACME Tecnologia",
                normalized_name="acme tecnologia",
            )
        )
        db.flush()
        db.add(
            Identity(
                tenant_id=1,
                source=source,
                kind="supplier",
                source_id="s",
                entity_id=identity,
                method="source_identity",
                confidence=1,
            )
        )
    db.flush()
    normalize_suppliers(db, 1)
    target = scoped(db, Entity, 1).filter_by(kind="supplier", active=True).one()
    for source in ("crm", "manual"):
        assert (
            resolve(db, 1, source, "supplier", "s", {"name": "acme tecnologia"}).id
            == target.id
        )
    assert scoped(db, Entity, 1).filter_by(kind="supplier", active=True).count() == 1


def test_missing_supplier_names_do_not_merge_by_generic_label(db):
    a = resolve(db, 1, "crm", "supplier", "a", {"name": "Não informado"})
    b = resolve(db, 1, "manual", "supplier", "b", {"name": "Não informado"})
    normalize_suppliers(db, 1)
    assert a.id != b.id and a.active and b.active
