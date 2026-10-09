"""Supplier spelling normalization and auditable consolidation within one tenant."""

import re
import unicodedata
from collections import defaultdict

from .domain import normalize, valid_cnpj
from .models import Entity, Fact, Identity, ProductSupplier, Review, SupplierQuote
from .repository import now, scoped

VERSION = "supplier-name-v1"


def display_name(value):
    return (
        re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(value or "")))
        .strip()
        .upper()
    )


def name_key(value):
    return normalize(str(value or "").replace("&", " e "))


def comparison_key(value):
    # Legal suffixes improve review suggestions; they do not authorize a merge.
    key = name_key(value)
    while True:
        shorter = re.sub(r"\s+(ltda|limitada|eireli|me|epp|s a|sa)$", "", key)
        if shorter == key:
            return key
        key = shorter


def canonical_id(db, tenant_id, identity):
    seen = set()
    while identity and identity not in seen:
        seen.add(identity)
        row = (
            scoped(db, Entity, tenant_id)
            .filter_by(id=identity, kind="supplier")
            .one_or_none()
        )
        replacement = (row.attributes or {}).get("superseded_by") if row else None
        if not replacement:
            return identity if row else None
        identity = replacement
    raise ValueError("Ciclo inválido nos aliases de fornecedor.")


def merge_supplier(db, tenant_id, current, target):
    if current.id == target.id:
        return {}
    if current.tax_id and target.tax_id and current.tax_id != target.tax_id:
        raise ValueError(
            "CNPJs diferentes: empresas/filiais não podem ser unidas pelo nome."
        )
    relations = []
    for link in (
        scoped(db, ProductSupplier, tenant_id).filter_by(supplier_id=current.id).all()
    ):
        existing = (
            scoped(db, ProductSupplier, tenant_id)
            .filter_by(
                supplier_id=target.id, product_id=link.product_id, source=link.source
            )
            .one_or_none()
        )
        if existing:
            relations.append(
                {
                    "id": link.id,
                    "product_id": link.product_id,
                    "source": link.source,
                    "cost": str(link.cost) if link.cost is not None else None,
                    "lead_time_days": link.lead_time_days,
                    "supplier_sku": link.supplier_sku,
                    "minimum_quantity": str(link.minimum_quantity)
                    if link.minimum_quantity is not None
                    else None,
                    "active": link.active,
                }
            )
            for field in ("cost", "lead_time_days", "supplier_sku", "minimum_quantity"):
                if getattr(existing, field) is None:
                    setattr(existing, field, getattr(link, field))
            existing.active = existing.active or link.active
            db.delete(link)
        else:
            link.supplier_id = target.id
    scoped(db, Fact, tenant_id).filter_by(supplier_id=current.id).update(
        {Fact.supplier_id: target.id}, synchronize_session="fetch"
    )
    scoped(db, SupplierQuote, tenant_id).filter_by(supplier_id=current.id).update(
        {SupplierQuote.supplier_id: target.id}, synchronize_session="fetch"
    )
    for link in scoped(db, Identity, tenant_id).filter_by(
        kind="supplier", entity_id=current.id
    ):
        link.entity_id = target.id
        link.evidence = {
            **(link.evidence or {}),
            "supplier_normalization": VERSION,
            "previous_entity_id": current.id,
        }
    aliases = set((target.attributes or {}).get("name_aliases", []))
    aliases.update((current.attributes or {}).get("name_aliases", []))
    aliases.update([current.name, target.name])
    target.attributes = {
        **(target.attributes or {}),
        "name_aliases": sorted(aliases),
        "supplier_name_version": VERSION,
    }
    if not target.tax_id and current.tax_id:
        target.tax_id = current.tax_id
    current.attributes = {
        **(current.attributes or {}),
        "superseded_by": target.id,
        "supplier_name_version": VERSION,
    }
    current.active = False
    for review in scoped(db, Review, tenant_id).filter_by(
        kind="supplier", status="pending"
    ):
        if {review.current_id, review.candidate_id} == {current.id, target.id}:
            review.status = "superseded"
            review.evidence = {**(review.evidence or {}), "resolved_by": VERSION}
    db.flush()
    return {
        "previous_name": current.name,
        "canonical_name": target.name,
        "collapsed_relations": relations,
        "version": VERSION,
    }


def normalize_suppliers(db, tenant_id, user_id=None):
    rows = (
        scoped(db, Entity, tenant_id)
        .filter_by(kind="supplier", active=True)
        .order_by(Entity.created_at, Entity.id)
        .limit(10001)
        .all()
    )
    if len(rows) > 10000:
        raise ValueError("Normalização limitada a 10.000 fornecedores por execução.")
    groups = defaultdict(list)
    for row in rows:
        aliases = set((row.attributes or {}).get("name_aliases", []))
        aliases.add(row.name)
        row.name = display_name(row.name)
        row.normalized_name = name_key(row.name)
        row.attributes = {
            **(row.attributes or {}),
            "name_aliases": sorted(aliases),
            "supplier_name_version": VERSION,
        }
        if valid_cnpj(row.tax_id):
            groups[("cnpj", row.tax_id)].append(row)
    merged = 0
    # Full CNPJ identifies the establishment. Never use the CNPJ root here.
    for group in groups.values():
        target = group[0]
        for current in group[1:]:
            evidence = merge_supplier(db, tenant_id, current, target)
            db.add(
                Review(
                    tenant_id=tenant_id,
                    source="normalization",
                    kind="supplier",
                    source_id=current.id,
                    current_id=current.id,
                    candidate_id=target.id,
                    reason="supplier_normalization",
                    status="accepted",
                    reviewed_by=user_id,
                    reviewed_at=now(),
                    evidence=evidence,
                )
            )
            merged += 1
    spelling = defaultdict(list)
    for row in rows:
        if (
            row.active
            and len(row.normalized_name) >= 4
            and row.normalized_name
            not in {"nao informado", "desconhecido", "fornecedor", "unknown"}
        ):
            spelling[row.normalized_name].append(row)
    for group in spelling.values():
        if len({row.tax_id for row in group if row.tax_id}) > 1:
            continue
        target = next((row for row in group if row.tax_id), group[0])
        for current in group:
            if current.id == target.id:
                continue
            rejected = (
                scoped(db, Review, tenant_id)
                .filter_by(kind="supplier", status="rejected")
                .filter(
                    Review.current_id.in_([current.id, target.id]),
                    Review.candidate_id.in_([current.id, target.id]),
                )
                .first()
            )
            if rejected:
                continue
            evidence = merge_supplier(db, tenant_id, current, target)
            db.add(
                Review(
                    tenant_id=tenant_id,
                    source="normalization",
                    kind="supplier",
                    source_id=current.id,
                    current_id=current.id,
                    candidate_id=target.id,
                    reason="supplier_normalization",
                    status="accepted",
                    reviewed_by=user_id,
                    reviewed_at=now(),
                    evidence=evidence,
                )
            )
            merged += 1
    db.flush()
    return {"suppliers_examined": len(rows), "merged": merged, "version": VERSION}
