from datetime import datetime, timezone
from decimal import Decimal

from app.market_intelligence.adapters import normalized_record
from app.market_intelligence.relationships import relationship_report
from app.market_intelligence.service import report


def test_relations_keep_units_sources_and_unknown_coverage_separate():
    entities = [
        {"id": "p", "kind": "product", "name": "Switch", "active": True},
        {"id": "empty", "kind": "product", "name": "Sem demanda", "active": True},
        {"id": "s", "kind": "supplier", "name": "Fornecedor"},
    ]
    records = [
        {
            "kind": "demand",
            "source": "crm",
            "product_id": "p",
            "quantity": Decimal(2),
            "unit": "UN",
            "total_value": Decimal(100),
            "coverage": "covered",
        },
        {
            "kind": "demand",
            "source": "crm",
            "product_id": "p",
            "quantity": Decimal(1),
            "unit": "KIT",
            "total_value": None,
            "coverage": "pending_review",
        },
        {
            "kind": "demand",
            "source": "pncp",
            "product_id": "p",
            "quantity": Decimal(5),
            "unit": "UN",
            "total_value": Decimal(500),
        },
        {"kind": "demand", "source": "crm", "product_id": None, "total_value": None},
    ]
    result = relationship_report(
        records,
        entities,
        [
            {
                "id": "r",
                "source": "crm",
                "product_id": "p",
                "supplier_id": "s",
                "cost": Decimal(10),
                "active": True,
            }
        ],
    )
    selected = next(row for row in result["product_demand"] if row["id"] == "crm:p")
    assert selected["items"] == 2 and selected["covered_items"] == 1
    assert selected["value"] == 100 and selected["value_sample"] == 1
    assert selected["quantity"] is None
    assert (
        next(row for row in result["product_demand"] if row["product_id"] == "empty")[
            "value"
        ]
        is None
    )
    assert result["supplier_products"][0]["supplier"] == "Fornecedor"
    assert len(result["product_demand"]) == 4


def test_report_relationships_and_freshness_are_tenant_scoped(db):
    from app.market_intelligence.models import SyncRun

    for tenant in (1, 2):
        normalized_record(
            db, tenant, "manual", "product", {"id": "p", "name": f"Product {tenant}"}
        )
        normalized_record(
            db, tenant, "manual", "supplier", {"id": "s", "name": f"Supplier {tenant}"}
        )
        normalized_record(
            db,
            tenant,
            "manual",
            "product_supplier",
            {"id": "r", "product_id": "p", "supplier_id": "s"},
        )
        for _ in range(3):
            db.add(
                SyncRun(
                    tenant_id=tenant,
                    source="crm",
                    status="completed",
                    finished_at=datetime.now(timezone.utc),
                )
            )
    db.flush()
    result = report(db, 1)
    assert {row["product"] for row in result["product_demand"]} == {"Product 1"}
    assert {row["supplier"] for row in result["supplier_products"]} == {"SUPPLIER 1"}
    assert len(result["quality"]["freshness"]) == 1
