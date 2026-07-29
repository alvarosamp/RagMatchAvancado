import pytest
from fastapi import HTTPException

from app.services.document_platform import (
    build_document_business_key,
    normalize_document_payload,
    resolve_document_schema,
    validate_document_payload,
)


def test_edital_usa_schema_padrao_e_preserva_outro():
    payload = {
        "n_interno": "PE-12-2026",
        "edital": {"numero_pregao": "12/2026", "orgao": "Prefeitura X"},
        "itens_elegiveis": [
            {
                "numero_item_edital": "10",
                "categoria": "Outro",
                "descricao_original": "Equipamento especial",
            }
        ],
    }

    schema = resolve_document_schema("edital")
    normalized = normalize_document_payload("edital", payload)

    assert schema.name == "edital"
    assert schema.version == "7.4"
    assert normalized["itens_elegiveis"][0]["categoria"] == "Outro"


def test_edital_sem_identificacao_nao_avanca():
    schema = resolve_document_schema("edital")

    with pytest.raises(HTTPException) as exc:
        validate_document_payload("edital", {"edital": {}, "itens_elegiveis": []}, schema)

    assert exc.value.status_code == 422


def test_datasheet_tor_gera_business_key_estavel():
    schema = resolve_document_schema("datasheet_tor")
    payload = {
        "produto": {
            "fabricante": "TP-Link",
            "modelo": "TL-SG3210",
            "part_number": "SG3210",
        }
    }

    first = build_document_business_key("datasheet_tor", payload, schema)
    second = build_document_business_key("datasheet_tor", dict(payload), schema)

    assert first == second
    assert first.startswith("datasheet_tor|meta|")
