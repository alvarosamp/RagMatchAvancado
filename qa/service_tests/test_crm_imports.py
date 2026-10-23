from copy import deepcopy

from openpyxl import Workbook
import pytest

from app.crm import json_analysis_importer as importer, sales_process_importer as sales
from app.crm.models import CrmNotice, CrmNoticeDocument, CrmNoticeProduct, CrmNoticeSession


@pytest.fixture
def analysis(unique):
    return {"n_interno": f"QA-IMPORT-{unique}", "particularities": "Criterio: menor preço\nIntervalo: R$ 10,00\nExclusividade: sim",
        "edital": {"numero_pregao": f"PE-{unique}", "orgao": "Prefeitura importação QA", "cidade": "São Paulo", "uf": "SP",
            "local": "Portal importação QA", "objeto": "Aquisição de switches", "data_disputa": "2026-12-31", "hora_disputa": "10:00",
            "valor_total_edital": "600,00", "validade_proposta": "60 dias", "exclusividade_me_epp": "sim"},
        "auditoria": {"modo_analise": "completo", "confianca_geral": "alta"},
        "riscos": {"risco_identificado": "Prazo curto", "risco_operacional": ["Entrega", "Amostra"], "risco_documental": {"tipo": "Atestado"}},
        "itens_elegiveis": [{"numero_item_edital": "1", "descricao_original": "Switch QA 48 portas", "categoria": "switch", "quantidade": 3,
            "preco_unitario": 100, "unidade": "UN", "garantia": "36 meses", "prazo_entrega": "10 dias",
            "caracteristicas_bi": {"quantidade_portas": "48", "poe": {"alimentacao_poe": "370 W"}},
            "direcionamento_marca": {"existe": True, "marca_modelo": "QA-SW48", "tipo": "referência", "justificativa": "Compatibilidade"}}],
        "documentacao": [{"documento": "Atestado QA", "categoria": "Habilitação"}],
        "declaracoes": [{"declaracao": "Declaração QA"}]}


def test_json_import_persists_relationships_items_and_checklists_then_reimports_idempotently(db, context, analysis):
    first = importer.sync_analysis_json_to_crm(db, context, analysis, notify=False)
    db.flush()
    notice = db.get(CrmNotice, first["notice_id"])
    assert first["created"] and first["products"] == 1
    product = db.query(CrmNoticeProduct).filter_by(notice_id=notice.id).one()
    assert product.quantity == 3 and product.reference_total_price == 300
    assert product.bi_feature_quantidade_portas == "48"
    assert notice.organ_id and notice.portal_id
    assert db.query(CrmNoticeSession).filter_by(notice_id=notice.id).count() == 1
    assert db.query(CrmNoticeDocument).filter_by(notice_id=notice.id, name="Atestado QA").count() == 1
    notice.stage = "proposal"
    product.notes = "Cotação negociada QA"
    db.flush()
    second = importer.sync_analysis_json_to_crm(db, context, analysis, notify=False)
    db.flush()
    assert not second["created"] and second["notice_id"] == first["notice_id"]
    assert notice.stage == "proposal" and product.notes == "Cotação negociada QA"
    assert db.query(CrmNoticeProduct).filter_by(notice_id=notice.id).count() == 1


def test_partial_json_import_preserves_prices_quantity_and_other_items(db, context, analysis):
    analysis["itens_elegiveis"].append({"numero_item_edital": "2", "descricao_original": "Cabo QA", "quantidade": 10, "valor_total_item": 200})
    first = importer.sync_analysis_json_to_crm(db, context, analysis, notify=False)
    partial = deepcopy(analysis)
    partial["itens_elegiveis"] = [{"numero_item_edital": "1", "preco_unitario": 200}]
    importer.sync_analysis_json_to_crm(db, context, partial, notify=False)
    db.flush()
    rows = db.query(CrmNoticeProduct).filter_by(notice_id=first["notice_id"]).order_by(CrmNoticeProduct.item_number).all()
    assert len(rows) == 2
    assert rows[0].quantity == 3 and rows[0].reference_total_price == 600
    assert rows[1].reference_price == 20


@pytest.mark.parametrize("sheet", ["Processos ganhos", "Monitoramento"])
def test_sales_spreadsheet_import_preserves_numbers_and_is_idempotent(db, context, unique, sheet):
    rows = [{"orgao": "Prefeitura vendas QA", "portal": "Portal vendas QA", "data_da_sessao": "31/12/2026",
             "endereco": "São Paulo", "uf": "SP", "item": 1, "lote": "A", "descricao": "Switch QA", "descricao_do_produto": "Switch QA",
             "quantidade": "3", "custo_unitario_c_ipi": "80,00", "custo": "80,00", "preco_minimo_unitario": "100,00", "preco": "100,00",
             "codigo_do_produto": "QA-SW", "part_number_do_produto": "QA-SW", "exclusivo_epp": "sim", "status": "QA negociação"}]
    key = f"qa-sales-{unique}"
    notice = sales.upsert_notice_from_group(db, context, key, rows, sheet)
    assert sales.upsert_group_products(db, context, notice, rows, sheet) == 1
    assert sales.upsert_notice_from_group(db, context, key, rows, sheet).id == notice.id
    sales.upsert_group_products(db, context, notice, rows, sheet)
    db.flush()
    product = db.query(CrmNoticeProduct).filter_by(notice_id=notice.id).one()
    assert product.quantity == 3 and product.cost == 80 and product.reference_price == 100
    assert notice.outcome == ("won" if sheet == "Processos ganhos" else "pending")


def test_analyzed_spreadsheet_rows_create_notice_products_and_documentation(db, context, unique, tmp_path):
    row = {"n_interno": f"QA-SHEET-{unique}", "orgao": "Prefeitura planilha QA", "portal": "Portal planilha QA", "uf": "SP",
           "data_disputa": "31/12/2026", "hora_disputa": "10:00", "item_1": "Switch QA 48 portas", "quantidade_1": 3,
           "habilitacao_juridica": "Contrato social QA", "qualificacao_tecnica": "Atestado QA"}
    workbook = Workbook()
    workbook.active.title = "Analisados QA"
    workbook.active.append(list(row))
    workbook.active.append(list(row.values()))
    workbook.active.append([None] * len(row))
    path = tmp_path / "analysis.xlsx"
    workbook.save(path)
    name, parsed = sales.detect_analyzed_sheet_rows(path)
    assert name == "Analisados QA" and len(parsed) == 1
    notice = sales.upsert_notice_from_analyzed_row(db, context, parsed[0], 1)
    assert sales.upsert_analyzed_documents(db, context, notice, parsed[0]) == 2
    assert sales.upsert_notice_from_analyzed_row(db, context, parsed[0], 1).id == notice.id
    assert notice.number == row["n_interno"]
    assert sales.group_sheet_rows("Monitoramento", [{"orgao": "QA"}, {"orgao": "QA"}])
