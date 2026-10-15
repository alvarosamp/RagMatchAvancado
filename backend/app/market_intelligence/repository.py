import json
from datetime import datetime, timezone
from difflib import SequenceMatcher

from sqlalchemy import text

from .domain import gtin, json_value, normalize, payload_hash, tax_id, valid_cnpj
from .models import BrandAlias, Entity, Fact, Identity, RawRecord, Review


def now():
    return datetime.now(timezone.utc)


def scoped(db, model, tenant_id):
    return db.query(model).filter(model.tenant_id == tenant_id)


def upsert(db, model, tenant_id, keys, values):
    row = scoped(db, model, tenant_id).filter_by(**keys).one_or_none()
    if row is None:
        row = model(tenant_id=tenant_id, **keys)
        db.add(row)
    for key, value in values.items():
        setattr(row, key, value)
    db.flush()
    return row


def store_raw(
    db, tenant_id, run_id, source, entity, source_id, payload, source_updated_at=None
):
    payload = json.loads(json.dumps(payload, default=json_value, ensure_ascii=False))
    digest = payload_hash(payload)
    latest = (
        scoped(db, RawRecord, tenant_id)
        .filter_by(source=source, entity=entity, source_id=str(source_id))
        .order_by(RawRecord.revision_number.desc())
        .first()
    )
    if latest is not None and latest.payload_hash == digest:
        return False
    upsert(
        db,
        RawRecord,
        tenant_id,
        {
            "source": source,
            "entity": entity,
            "source_id": str(source_id),
            "revision_number": latest.revision_number + 1 if latest else 1,
        },
        {
            "payload_hash": digest,
            "batch_id": run_id,
            "payload": payload,
            "source_updated_at": source_updated_at,
            "ingested_at": now(),
        },
    )
    return True


def canonical_brand(db, tenant_id, value):
    if not value:
        return None
    alias = (
        scoped(db, BrandAlias, tenant_id)
        .filter_by(alias=normalize(value))
        .one_or_none()
    )
    return alias.canonical if alias else str(value).strip()


def resolve(db, tenant_id, source, kind, source_id, attributes):
    """Exact identifiers auto-link; similar names create review suggestions only."""
    source_id = str(source_id)
    attrs = dict(attributes)
    name = str(attrs.get("name") or source_id).strip()
    original_name = name
    if kind == "supplier":
        from .suppliers import comparison_key, display_name, name_key

        name = display_name(name)
    cnpj = tax_id(attrs.get("tax_id"))
    cnpj = cnpj if valid_cnpj(cnpj) else None
    barcode = gtin(attrs.get("gtin"))
    brand = canonical_brand(db, tenant_id, attrs.get("brand"))
    mpn = normalize(attrs.get("mpn")) or None
    key, method = f"source:{source}:{source_id}", "source_identity"
    if kind == "supplier" and cnpj:
        key, method = f"cnpj:{cnpj}", "cnpj_exact"
    elif kind == "product" and barcode:
        key, method = f"gtin:{barcode}", "gtin_exact"
    elif kind == "product" and brand and mpn:
        key, method = f"brand_mpn:{normalize(brand)}:{mpn}", "brand_mpn_exact"
    elif kind in {"brand", "category"}:
        key, method = f"name:{normalize(name)}", "normalized_name"
    link = (
        scoped(db, Identity, tenant_id)
        .filter_by(source=source, kind=kind, source_id=source_id)
        .one_or_none()
    )
    candidate = (
        scoped(db, Entity, tenant_id)
        .filter_by(kind=kind, identity_key=key)
        .one_or_none()
    )
    if (
        kind == "supplier"
        and not candidate
        and not cnpj
        and attrs.get("name")
        and len(name_key(name)) >= 4
        and name_key(name)
        not in {"nao informado", "desconhecido", "fornecedor", "unknown"}
    ):
        # Formatting variants, not fuzzy names. Multiple known CNPJs remain ambiguous.
        matches = (
            scoped(db, Entity, tenant_id)
            .filter_by(kind="supplier", normalized_name=name_key(name), active=True)
            .limit(2)
            .all()
        )
        if len(matches) == 1:
            candidate = matches[0]
            method = "supplier_name_format_exact"
    current = (
        scoped(db, Entity, tenant_id).filter_by(id=link.entity_id).one()
        if link
        else None
    )
    if (
        kind == "supplier"
        and candidate
        and (candidate.attributes or {}).get("superseded_by")
    ):
        from .suppliers import canonical_id

        candidate = (
            scoped(db, Entity, tenant_id)
            .filter_by(id=canonical_id(db, tenant_id, candidate.id))
            .one()
        )
    contradiction = current and (
        (cnpj and current.tax_id and cnpj != current.tax_id)
        or (barcode and current.gtin and barcode != current.gtin)
    )
    if contradiction:
        if not candidate:
            candidate = Entity(
                tenant_id=tenant_id,
                kind=kind,
                identity_key=key,
                name=name,
                normalized_name=normalize(name),
                tax_id=cnpj,
                gtin=barcode,
                attributes=attrs,
            )
            db.add(candidate)
            db.flush()
        review = (
            scoped(db, Review, tenant_id)
            .filter_by(
                source=source, kind=kind, source_id=source_id, candidate_id=candidate.id
            )
            .one_or_none()
        )
        if not review:
            db.add(
                Review(
                    tenant_id=tenant_id,
                    source=source,
                    kind=kind,
                    source_id=source_id,
                    candidate_id=candidate.id,
                    current_id=current.id,
                    reason="conflicting_identifier",
                    evidence=attrs,
                )
            )
        return None
    target = current if link and link.method == "human_review" else candidate or current
    if not target:
        target = Entity(
            tenant_id=tenant_id,
            kind=kind,
            identity_key=key,
            name=name,
            normalized_name=normalize(name),
        )
        db.add(target)
        db.flush()
        # Blocking limits suggestions; a different known identifier forbids a merge.
        if method == "source_identity":
            candidates = scoped(db, Entity, tenant_id).filter(
                Entity.kind == kind, Entity.id != target.id, Entity.active.is_(True)
            )
            if kind == "product":
                candidates = candidates.filter(
                    Entity.brand == brand, Entity.category == attrs.get("category")
                )
            for other in candidates.limit(100).all():
                if cnpj and other.tax_id and cnpj != other.tax_id:
                    continue
                score = SequenceMatcher(
                    None,
                    comparison_key(name) if kind == "supplier" else normalize(name),
                    comparison_key(other.name)
                    if kind == "supplier"
                    else other.normalized_name,
                ).ratio()
                if score >= 0.85:
                    db.add(
                        Review(
                            tenant_id=tenant_id,
                            source=source,
                            kind=kind,
                            source_id=source_id,
                            candidate_id=other.id,
                            current_id=target.id,
                            reason="similar_name",
                            evidence={
                                "score": score,
                                "incoming": attrs,
                                "method": "blocked_name_v1",
                            },
                        )
                    )
    for field, value in {
        "name": display_name(target.name) if kind == "supplier" else name,
        "normalized_name": name_key(target.name)
        if kind == "supplier"
        else normalize(name),
        "tax_id": cnpj,
        "gtin": barcode,
        "brand": brand,
        "mpn": mpn,
        "sku": attrs.get("sku"),
        "category": attrs.get("category"),
        "crm_product_id": attrs.get("crm_product_id"),
    }.items():
        if value is not None:
            setattr(target, field, value)
    target.attributes = {**(target.attributes or {}), **attrs}
    if kind == "supplier":
        aliases = set(target.attributes.get("name_aliases", []))
        aliases.add(original_name)
        target.attributes = {
            **target.attributes,
            "name_aliases": sorted(aliases),
            "supplier_name_version": "supplier-name-v1",
        }
    target.active = attrs.get("active", True)
    target.updated_at = now()
    if not link:
        db.add(
            Identity(
                tenant_id=tenant_id,
                source=source,
                kind=kind,
                source_id=source_id,
                entity_id=target.id,
                method=method,
                confidence=1,
                evidence={
                    "identity_key": key,
                    "version": "identity-v1",
                    "source_name": original_name,
                },
            )
        )
    elif link.method != "human_review":
        link.entity_id, link.method, link.evidence = (
            target.id,
            method,
            {
                "identity_key": key,
                "version": "identity-v1",
                "source_name": original_name,
            },
        )
    db.flush()
    return target


def fact(db, tenant_id, source, kind, source_id, **values):
    values["updated_at"] = now()
    values.setdefault("active", True)
    values.setdefault("available_at", now())
    values.setdefault("event_at", now())
    return upsert(
        db,
        Fact,
        tenant_id,
        {"source": source, "kind": kind, "source_id": str(source_id)},
        values,
    )


def acquire_source_lock(db, tenant_id, source):
    if db.get_bind().dialect.name != "postgresql":
        return True
    key = int(payload_hash({"tenant": tenant_id, "source": source})[:15], 16)
    return bool(
        db.execute(
            text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": key}
        ).scalar()
    )


def review_identity(db, tenant_id, review_id, decision, user_id):
    row = (
        scoped(db, Review, tenant_id)
        .filter_by(id=review_id)
        .with_for_update()
        .one_or_none()
    )
    if row is None:
        raise LookupError("Revisão não encontrada.")
    if row.status != "pending":
        raise ValueError("Esta revisão já foi concluída.")
    if decision == "accepted":
        if row.reason == "conflicting_identifier":
            raise ValueError(
                "Identificadores contraditórios exigem corrigir a origem; a fusão foi bloqueada."
            )
        candidate = (
            scoped(db, Entity, tenant_id)
            .filter_by(id=row.candidate_id, kind=row.kind)
            .one()
        )
        current = (
            scoped(db, Entity, tenant_id).filter_by(id=row.current_id).one_or_none()
        )
        if current and (
            (current.tax_id and candidate.tax_id and current.tax_id != candidate.tax_id)
            or (current.gtin and candidate.gtin and current.gtin != candidate.gtin)
        ):
            raise ValueError("Identificadores incompatíveis.")
        link = (
            scoped(db, Identity, tenant_id)
            .filter_by(source=row.source, kind=row.kind, source_id=row.source_id)
            .one()
        )
        link.entity_id, link.method, link.reviewed_by, link.reviewed_at = (
            candidate.id,
            "human_review",
            user_id,
            now(),
        )
        # Only this source identity is remapped. Other identities of current stay intact.
        field = Fact.product_id if row.kind == "product" else Fact.supplier_id
        origin_key = (
            "source_product_id" if row.kind == "product" else "source_supplier_id"
        )
        for record in (
            scoped(db, Fact, tenant_id)
            .filter(Fact.source == row.source, field == row.current_id)
            .yield_per(500)
        ):
            if str((record.attributes or {}).get(origin_key)) == row.source_id:
                setattr(
                    record,
                    "product_id" if row.kind == "product" else "supplier_id",
                    candidate.id,
                )
        if (
            row.kind == "supplier"
            and current
            and scoped(db, Identity, tenant_id)
            .filter_by(kind="supplier", entity_id=current.id)
            .count()
            == 0
        ):
            from .suppliers import merge_supplier

            row.evidence = {
                **(row.evidence or {}),
                "consolidation": merge_supplier(db, tenant_id, current, candidate),
            }
    row.status, row.reviewed_by, row.reviewed_at = decision, user_id, now()
    db.flush()
    return row
