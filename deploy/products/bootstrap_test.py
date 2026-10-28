"""Create the test login without resetting existing users or enabling signup."""

import os


def demo_payload(sequence):
    switch = {"numero_item_edital": "1", "categoria": "Switch", "descricao_original": "DEMONSTRAÇÃO FICTÍCIA: Switch DEMO-SW24 de 24 portas Gigabit, PoE+, uplinks 4 SFP+ 10G.",
              "quantidade": 10 * sequence, "unidade": "UN", "preco_unitario": "R$ 1.000,00",
              "direcionamento_marca": {"existe": True, "marca_modelo": "Marca Demo DEMO-SW24", "tipo": "Referência fictícia", "justificativa": "Dados artificiais para testar a interface"},
              "caracteristicas_bi": {"quantidade_portas": "24 Portas", "portas_acesso": "Gigabit (10/100/1000)", "gerenciamento": "Gerenciavel", "alimentacao_poe": "PoE+", "uplinks": "4 SFP+ 10G"}}
    return {"schema_version": "7.4.4", "n_interno": f"DEMO-PRODUTOS-{sequence:03}",
            "edital": {"orgao": "DEMONSTRAÇÃO — órgão fictício", "numero_pregao": f"DEMO-{sequence}", "uf": "SP", "cidade": "Demonstração", "status": "🟢", "resumo_itens": "DADOS FICTÍCIOS PARA TESTE"},
            "itens_elegiveis": [switch]}


def main():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    import app.main  # noqa: F401 -- register all ORM relationships
    from app.auth.models import Tenant, User
    from app.auth.password_policy import assert_valid_password
    from app.auth.security import hash_password
    from app.crm.models import CrmCatalogProduct, CrmNotice
    from app.crm.json_analysis_importer import sync_analysis_json_to_crm
    from app.crm.sales_process_importer import build_import_context_for_user

    url = os.environ["DATABASE_URL"]
    if url.rsplit("/", 1)[-1] != "ragmatch_products_test":
        raise RuntimeError("Este inicializador só aceita o banco ragmatch_products_test.")
    email = os.environ["ADMIN_EMAIL"].strip().lower()
    password = os.environ["ADMIN_PASSWORD"]
    assert_valid_password(password)
    with Session(create_engine(url)) as db:
        tenant = db.query(Tenant).filter_by(slug="ragmatch-produtos-teste").first()
        if tenant is None:
            tenant = Tenant(slug="ragmatch-produtos-teste", name="RagMatch — teste de produtos")
            db.add(tenant)
            db.flush()
        user = db.query(User).filter_by(email=email).first()
        if user is not None and (user.tenant_id != tenant.id or user.role != "admin"):
            raise RuntimeError("O email já pertence a outra conta. Nenhum acesso foi alterado.")
        if user is None:
            user = User(email=email, full_name="Administrador de teste", tenant_id=tenant.id, role="admin", hashed_password=hash_password(password))
            db.add(user)
            db.flush()
        if os.getenv("SEED_DEMO", "0") == "1":
            if not db.query(CrmCatalogProduct).filter_by(tenant_id=tenant.id, sku="DEMO-SW24").first():
                db.add(CrmCatalogProduct(tenant_id=tenant.id, name="DEMONSTRAÇÃO — switch fictício", sku="DEMO-SW24", brand="Marca Demo", model="DEMO-SW24", category="Switch", specification="Produto fictício de demonstração"))
                db.flush()
            context = build_import_context_for_user(user)
            for sequence in (1, 2):
                payload = demo_payload(sequence)
                if not db.query(CrmNotice).filter_by(tenant_id=tenant.id, tor_id=payload["n_interno"]).first():
                    sync_analysis_json_to_crm(db, context, payload, source_name="DEMONSTRACAO-FICTICIA.json", notify=False)
        db.commit()
    print("Ambiente de teste inicializado; contas existentes e senhas preservadas.")


if __name__ == "__main__":
    main()
