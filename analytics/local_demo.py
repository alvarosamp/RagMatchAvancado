"""Seed fictitious CRM data only in the isolated market_local_test database."""

import bcrypt
from app.auth.models import Tenant, User
from app.crm.models import CrmCatalogProduct, CrmNotice, CrmNoticeProduct
from app.db.session import SessionLocal, set_tenant_context
from app.market_intelligence import (
    crm_source,  # noqa: F401 -- register operational models
)
from sqlalchemy import text

DEMO_PASSWORD = "DockerTeste@2026"


def main():
    with SessionLocal() as db:
        assert db.scalar(text("select current_database()")) == "market_local_test", (
            "Demo is restricted to the isolated Docker test database."
        )
        tenants = db.query(Tenant).all()
        assert all(t.slug in {"demo-market-1", "demo-market-2"} for t in tenants), (
            "Refusing to seed a database containing other tenants."
        )
    for tenant_id in (1, 2):
        with SessionLocal() as db:
            set_tenant_context(db, tenant_id)
            if db.get(Tenant, tenant_id):
                continue
            db.add(
                Tenant(
                    id=tenant_id,
                    slug=f"demo-market-{tenant_id}",
                    name=f"Empresa de demonstração {tenant_id}",
                )
            )
            db.flush()
            db.add(
                User(
                    tenant_id=tenant_id,
                    email=f"demo{tenant_id}@example.com",
                    hashed_password=bcrypt.hashpw(
                        DEMO_PASSWORD.encode(), bcrypt.gensalt()
                    ).decode(),
                    full_name=f"Administrador de teste {tenant_id}",
                    cpf="52998224725" if tenant_id == 1 else "11144477735",
                    phone="11999999999",
                    role="admin",
                    is_active=True,
                )
            )
            product = CrmCatalogProduct(
                id=f"demo-p{tenant_id}",
                tenant_id=tenant_id,
                name=f"Switch de demonstração {tenant_id}",
                brand="DEMO",
                sku=f"DEMO-{tenant_id}",
                cost=300,
                min_price=450,
                supplier_name=f"Fornecedor fictício {tenant_id}",
            )
            notice = CrmNotice(
                id=f"demo-n{tenant_id}",
                tenant_id=tenant_id,
                number=f"DEMO-{tenant_id}/2026",
                state="SP",
            )
            db.add_all([product, notice])
            db.flush()
            db.add(
                CrmNoticeProduct(
                    id=f"demo-i{tenant_id}",
                    tenant_id=tenant_id,
                    notice_id=notice.id,
                    item_number=1,
                    description=f"Switch de demonstração {tenant_id}",
                    category="Switch",
                    quantity=10,
                    reference_price=650 * tenant_id,
                    catalog_product_id=product.id,
                    match_review_verdict="ATENDE",
                    unit="UN",
                    cost=300,
                )
            )
            db.commit()
    print("Fictitious demo CRM seeded for two isolated tenants.")


if __name__ == "__main__":
    main()
