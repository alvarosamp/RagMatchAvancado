from types import SimpleNamespace

from docx import Document

from app.services.proposal_generator import build_notice_proposal_docx


def _enum_value(value: str):
    return SimpleNamespace(value=value)


def test_build_notice_proposal_includes_all_won_items(tmp_path):
    products = [
        SimpleNamespace(
            id="item-1",
            item_number="1",
            description="Switch gerenciavel 24 portas",
            unit="UN",
            quantity=2,
            unit_price=None,
            reference_price=500,
            catalog_product=SimpleNamespace(
                name="Switch 24 portas",
                brand="TP-Link",
                model="SG2428",
                unit="UN",
            ),
        ),
        SimpleNamespace(
            id="item-2",
            item_number="2",
            description="Roteador corporativo",
            unit="UN",
            quantity=1,
            unit_price=None,
            reference_price=900,
            catalog_product=SimpleNamespace(
                name="Roteador",
                brand="MikroTik",
                model="RB4011",
                unit="UN",
            ),
        ),
        SimpleNamespace(
            id="item-3",
            item_number="3",
            description="Item perdido",
            unit="UN",
            quantity=1,
            unit_price=None,
            reference_price=100,
            catalog_product=None,
        ),
    ]
    notice = SimpleNamespace(
        id="notice-1",
        number="123/2026",
        tor_id="TOR-001",
        modality="Pregao Eletronico 001/2026",
        organ=SimpleNamespace(name="Municipio de Teste"),
        portal=SimpleNamespace(name="Portal Teste"),
        notice_products=products,
        notice_item_results=[
            SimpleNamespace(
                notice_product_id="item-1",
                notice_product=products[0],
                winner_type=_enum_value("us"),
                winning_quantity=2,
                winning_price=450,
                winner_brand="TP-Link",
                winner_model="SG2428",
            ),
            SimpleNamespace(
                notice_product_id="item-2",
                notice_product=products[1],
                winner_type="us",
                winning_quantity=1,
                winning_price=850,
                winner_brand="MikroTik",
                winner_model="RB4011",
            ),
            SimpleNamespace(
                notice_product_id="item-3",
                notice_product=products[2],
                winner_type="competitor",
                winning_quantity=1,
                winning_price=90,
                winner_brand=None,
                winner_model=None,
            ),
        ],
    )

    content = build_notice_proposal_docx(notice)
    path = tmp_path / "proposta.docx"
    path.write_bytes(content)

    document = Document(str(path))
    item_table_text = "\n".join(
        cell.text for row in document.tables[1].rows for cell in row.cells
    )

    assert "Switch gerenciavel 24 portas" in item_table_text
    assert "Roteador corporativo" in item_table_text
    assert "Item perdido" not in item_table_text
    assert "R$ 900,00" in item_table_text
    assert "R$ 850,00" in item_table_text
    assert "R$ 1.750,00" in item_table_text
    assert "mil setecentos e cinquenta reais" in item_table_text
