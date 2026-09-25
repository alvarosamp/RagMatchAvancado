from __future__ import annotations

import pytest
from app.integrations.bling.schemas import BlingInvoicePayload, BlingSalesOrderPayload
from pydantic import ValidationError


def test_sales_order_accepts_and_preserves_bling_extra_fields():
    payload = BlingSalesOrderPayload.model_validate(
        {
            "data": "2026-09-24",
            "dataSaida": "2026-09-24",
            "dataPrevista": "2026-09-25",
            "contato": {"id": 10},
            "itens": [{"produto": {"id": 20}, "quantidade": 2, "valor": 5}],
            "parcelas": [],
            "observacoes": "pedido do CRM",
        }
    )

    body = payload.model_dump(mode="json")
    assert body["data"] == "2026-09-24"
    assert body["observacoes"] == "pedido do CRM"


def test_sales_order_rejects_item_without_product_reference():
    with pytest.raises(ValidationError, match="produto.id"):
        BlingSalesOrderPayload.model_validate(
            {
                "data": "2026-09-24",
                "dataSaida": "2026-09-24",
                "dataPrevista": "2026-09-25",
                "contato": {"id": 10},
                "itens": [{"quantidade": 1}],
                "parcelas": [],
            }
        )


def test_invoice_requires_fiscal_contact_and_operation_nature():
    with pytest.raises(ValidationError, match="naturezaOperacao.id"):
        BlingInvoicePayload.model_validate(
            {
                "tipo": 1,
                "numero": "123",
                "dataOperacao": "2026-09-24 10:00:00",
                "contato": {
                    "nome": "Cliente",
                    "tipoPessoa": "J",
                    "numeroDocumento": "12345678000190",
                    "contribuinte": 9,
                },
                "naturezaOperacao": {},
                "itens": [{"codigo": "SKU-1"}],
            }
        )
