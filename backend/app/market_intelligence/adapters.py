"""Convert source payloads to the typed ledger without inferring missing events."""

from .domain import normalize, number, timestamp, unit, valid_cnpj
from .models import Fact, Identity, ProductSupplier
from .repository import canonical_brand, fact, now, resolve, scoped, upsert


def entity_id(db, tenant_id, source, kind, source_id):
    if source_id is None:
        return None
    link = (
        scoped(db, Identity, tenant_id)
        .filter_by(source=source, kind=kind, source_id=str(source_id))
        .one_or_none()
    )
    return link.entity_id if link else None


def normalized_record(db, tenant_id, source, kind, data):
    """Contract for manual reconciliation, CNPJ files and source-specific adapters."""
    source_id = str(data["id"])
    if kind in {"product", "supplier", "brand", "category"}:
        if (
            kind == "supplier"
            and source == "cnpj"
            and not valid_cnpj(data.get("tax_id"))
        ):
            raise ValueError("Cadastro CNPJ com identificador inválido.")
        return resolve(db, tenant_id, source, kind, source_id, data)
    if kind == "product_supplier":
        product_id = entity_id(db, tenant_id, source, "product", data.get("product_id"))
        supplier_id = entity_id(
            db, tenant_id, source, "supplier", data.get("supplier_id")
        )
        if not product_id or not supplier_id:
            raise ValueError(
                "Relação sem produto/fornecedor resolvido; carregar dimensões primeiro."
            )
        return upsert(
            db,
            ProductSupplier,
            tenant_id,
            {"product_id": product_id, "supplier_id": supplier_id, "source": source},
            {
                "cost": number(data.get("cost"), positive=True),
                "supplier_sku": data.get("supplier_sku"),
                "lead_time_days": data.get("lead_time_days"),
                "minimum_quantity": number(data.get("minimum_quantity")),
                "active": data.get("active", True),
            },
        )
    if kind not in {
        "demand",
        "match",
        "offer",
        "purchase",
        "sale",
        "award",
        "price",
        "inventory",
        "index",
    }:
        raise ValueError("Tipo de registro não suportado.")
    values = {
        key: data.get(key)
        for key in (
            "notice_id",
            "item_id",
            "category",
            "brand",
            "state",
            "description",
            "outcome",
            "coverage",
            "price_type",
        )
    }
    values["product_id"] = entity_id(
        db, tenant_id, source, "product", data.get("product_id")
    )
    values["supplier_id"] = entity_id(
        db, tenant_id, source, "supplier", data.get("supplier_id")
    )
    for field in (
        "quantity",
        "unit_price",
        "total_value",
        "reference_price",
        "cost",
        "offered_price",
        "winning_price",
    ):
        values[field] = number(
            data.get(field), positive=field not in {"quantity", "total_value"}
        )
    values["unit"], values["currency"] = (
        unit(data.get("unit")),
        data.get("currency", "BRL"),
    )
    values["brand"] = canonical_brand(db, tenant_id, values["brand"])
    values["event_at"] = timestamp(data.get("event_at"), now())
    values["available_at"] = now()  # Clients cannot backdate feature availability.
    values["active"] = bool(data.get("active", True))
    values["attributes"] = {
        **data.get("attributes", {}),
        "source_product_id": str(data.get("product_id"))
        if data.get("product_id") is not None
        else None,
        "source_supplier_id": str(data.get("supplier_id"))
        if data.get("supplier_id") is not None
        else None,
    }
    if values["state"]:
        values["state"] = str(values["state"]).upper()[:2]
    if (
        values["total_value"] is None
        and values["quantity"] is not None
        and values["unit_price"] is not None
    ):
        values["total_value"] = values["quantity"] * values["unit_price"]
    return fact(db, tenant_id, source, kind, source_id, **values)


def bling_record(db, tenant_id, kind, data):
    if kind == "product":
        return normalized_record(
            db,
            tenant_id,
            "bling",
            kind,
            {
                "id": data["id"],
                "name": data.get("nome") or str(data["id"]),
                "sku": data.get("codigo"),
                "gtin": data.get("gtin"),
                "brand": data.get("marca"),
                "mpn": data.get("codigoFabricante"),
                "category": str((data.get("categoria") or {}).get("id") or "") or None,
                "unit": data.get("unidade"),
                "active": data.get("situacao") != "I",
                "source_payload": data,
            },
        )
    if kind == "supplier":
        roles = data.get("tiposContato") or []
        verified = isinstance(roles, list) and any(
            isinstance(role, dict) and normalize(role.get("descricao")) == "fornecedor"
            for role in roles
        )
        return normalized_record(
            db,
            tenant_id,
            "bling",
            kind,
            {
                "id": data["id"],
                "name": data.get("nome") or data.get("fantasia") or str(data["id"]),
                "tax_id": data.get("numeroDocumento"),
                "supplier_role_verified": verified,
                "source_payload": data,
            },
        )
    if kind == "product_supplier":
        return normalized_record(
            db,
            tenant_id,
            "bling",
            kind,
            {
                "id": data["id"],
                "product_id": (data.get("produto") or {}).get("id"),
                "supplier_id": (data.get("fornecedor") or {}).get("id"),
                "cost": data.get("precoCompra"),
                "supplier_sku": data.get("codigo"),
                "lead_time_days": data.get("prazoEntrega"),
            },
        )
    if kind in {"purchase", "sale", "proposal"}:
        # Updating an order can remove or reorder lines. Reconcile its complete
        # scope before inserting the current payload, in the same transaction.
        ledger_kind = "offer" if kind == "proposal" else kind
        scoped(db, Fact, tenant_id).filter(
            Fact.source == "bling",
            Fact.kind == ledger_kind,
            Fact.source_id.startswith(f"{data['id']}:", autoescape=True),
        ).update({Fact.active: False}, synchronize_session=False)
        if kind in {"purchase", "sale"}:
            scoped(db, Fact, tenant_id).filter(
                Fact.source == "bling",
                Fact.kind == "price",
                Fact.source_id.startswith(f"{kind}:{data['id']}:", autoescape=True),
            ).update({Fact.active: False}, synchronize_session=False)
        contact_id = (data.get("fornecedor") or data.get("contato") or {}).get("id")
        event_date = data.get("data") or data.get("dataEmissao")
        for index, line in enumerate(data.get("itens", [])):
            line_id = line.get("id")
            if line_id is None:
                # Positional identity is stable only within this version of an order.
                line_id = index
            product_id = (line.get("produto") or {}).get("id")
            attributes = {
                "source_status": data.get("situacao"),
                "promised_at": data.get("dataPrevistaRecebimento"),
                "received_at": data.get("dataRecebimento"),
                "quantity_received": line.get("quantidadeRecebida"),
                "source_order_id": str(data["id"]),
            }
            normalized = {
                "id": f"{data['id']}:{line_id}",
                "product_id": product_id,
                "supplier_id": contact_id if kind == "purchase" else None,
                "quantity": line.get("quantidade"),
                "unit_price": line.get("valor"),
                "unit": line.get("unidade"),
                "description": line.get("descricao"),
                "event_at": event_date,
                "attributes": attributes,
                "outcome": "quoted" if kind == "proposal" else "ordered",
            }
            if kind == "purchase":
                normalized["cost"] = line.get("valor")
            if kind == "proposal":
                normalized["offered_price"] = line.get("valor")
            normalized_record(
                db,
                tenant_id,
                "bling",
                "offer" if kind == "proposal" else kind,
                normalized,
            )
            if kind in {"purchase", "sale"}:
                normalized_record(
                    db,
                    tenant_id,
                    "bling",
                    "price",
                    {
                        **normalized,
                        "id": f"{kind}:{normalized['id']}",
                        "price_type": "supplier_cost"
                        if kind == "purchase"
                        else "sales_price",
                    },
                )
        return
    if kind == "inventory":
        product_id = (data.get("produto") or {}).get("id")
        return normalized_record(
            db,
            tenant_id,
            "bling",
            kind,
            {
                "id": f"{product_id}:{now().date().isoformat()}",
                "product_id": product_id,
                "quantity": data.get("saldoFisicoTotal"),
                "event_at": now().isoformat(),
                "attributes": {
                    "virtual_balance": data.get("saldoVirtualTotal"),
                    "source_payload": data,
                },
            },
        )
    raise ValueError("Recurso Bling não suportado.")


def pncp_record(db, tenant_id, kind, source_id, data):
    if kind not in {"demand", "award"}:
        return  # Notices/contracts remain raw evidence; no fabricated item measures.
    notice, item = data["notice"], data["item"]
    org = notice.get("unidadeOrgao") or {}
    key = f"{notice['numeroControlePNCP']}:{item['numeroItem']}"
    event_date = notice.get("dataPublicacaoPncp") or notice.get("dataInclusao")
    values = {
        "id": source_id,
        "notice_id": notice["numeroControlePNCP"],
        "item_id": key,
        "description": item.get("descricao"),
        "category": str(item.get("categoriaItemCatalogo"))
        if item.get("categoriaItemCatalogo") is not None
        else None,
        "state": org.get("ufSigla"),
        "unit": item.get("unidadeMedida"),
        "quantity": item.get("quantidade"),
        "event_at": event_date,
        "reference_price": item.get("valorUnitarioEstimado"),
        "total_value": item.get("valorTotalEstimado") or item.get("valorTotal"),
        "coverage": "unassessed",
        "attributes": {
            "buyer_cnpj": (notice.get("orgaoEntidade") or {}).get("cnpj"),
            "buyer_name": (notice.get("orgaoEntidade") or {}).get("razaoSocial"),
            "origin": "pncp",
            "taxonomy": "pncp_categoria_item_catalogo",
        },
    }
    if kind == "award":
        result = data["result"]
        supplier_id = result.get("niFornecedor")
        if supplier_id:
            resolve(
                db,
                tenant_id,
                "pncp",
                "supplier",
                supplier_id,
                {
                    "name": result.get("nomeRazaoSocialFornecedor") or str(supplier_id),
                    "tax_id": supplier_id,
                },
            )
        values.update(
            supplier_id=supplier_id,
            winning_price=result.get("valorUnitarioHomologado"),
            quantity=result.get("quantidadeHomologada"),
            total_value=result.get("valorTotalHomologado"),
            brand=result.get("marca"),
            event_at=result.get("dataResultado") or event_date,
            active=result.get("situacaoCompraItemResultadoId") == 1,
            outcome="awarded"
            if result.get("situacaoCompraItemResultadoId") == 1
            else "cancelled",
        )
        normalized_record(
            db,
            tenant_id,
            "pncp",
            "price",
            {
                **values,
                "id": source_id,
                "unit_price": result.get("valorUnitarioHomologado"),
                "price_type": "winning_price",
            },
        )
    return normalized_record(db, tenant_id, "pncp", kind, values)
