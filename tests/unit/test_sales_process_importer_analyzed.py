from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from app.crm.sales_process_importer import (
    detect_analyzed_sheet_rows,
    get_analyzed_portal_value,
    get_value,
    iter_analyzed_items,
    parse_datetime_pair,
    parse_float,
    should_import_analyzed_row,
)


def _build_analyzed_workbook(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Pagina1"
    ws.append(
        [
            "Selecionado",
            "N Interno",
            "Status",
            "Data Disputa",
            "Hora Disputa",
            "Orgao",
            "Local",
            "Portal",
            "Nº Pregao",
            "Cidade",
            "UF",
            "Lote item 1",
            "Numero item edital 1",
            "Item 1",
            "Preco item 1",
            "Quantidade item 1",
            "Exclusividade ME/EPP item 1",
        ]
    )
    ws.append(
        [
            None,
            "2026_05_29_1",
            "verde",
            "2026-06-03 00:00:00",
            "14:00:00",
            "Prefeitura Teste",
            "Compras.gov.br",
            "Portal Nacional",
            "90031/2026",
            "Curitiba",
            "PR",
            "Grupo 1",
            6,
            "Switch gerenciavel 24 portas",
            "R$ 49.450,00",
            2,
            "Nao",
        ]
    )
    wb.save(path)


def test_detect_analyzed_sheet_and_expand_items(tmp_path: Path) -> None:
    path = tmp_path / "planilha_analisada.xlsx"
    _build_analyzed_workbook(path)

    detected = detect_analyzed_sheet_rows(path)

    assert detected is not None
    sheet_name, rows = detected
    assert sheet_name == "Pagina1"
    assert len(rows) == 1
    assert get_value(rows[0], "n interno") == "2026_05_29_1"
    assert get_analyzed_portal_value(rows[0]) == "Portal Nacional"

    items = iter_analyzed_items(rows[0])
    assert items == [
        {
            "item_number": "6",
            "lot": "Grupo 1",
            "description": "Switch gerenciavel 24 portas",
            "quantity": 2.0,
            "reference_price": 49450.0,
            "reference_total": 98900.0,
            "exclusive_epp": False,
            "sort_order": 0,
        }
    ]


def test_parse_values_from_analyzed_sheet() -> None:
    assert parse_float("R$ 846,99") == 846.99
    assert parse_float("Sigiloso") is None
    assert parse_datetime_pair("2026-06-03 00:00:00", "14:00:00").isoformat() == (
        "2026-06-03T14:00:00"
    )


def test_selected_no_is_skipped() -> None:
    assert should_import_analyzed_row({"selecionado": "nao"}) is False
    assert should_import_analyzed_row({"selecionado": None}) is True


def test_portal_falls_back_to_local_when_portal_is_blank() -> None:
    assert get_analyzed_portal_value({"portal": None, "local": "Compras.gov.br"}) == (
        "Compras.gov.br"
    )
