from __future__ import annotations

from types import SimpleNamespace

from app.services.analysis_normalizer import normalize_analysis_result
from app.services.match_item_export import build_match_item_export, match_item_filename


def _document(**overrides):
    values = {
        "id": 12,
        "business_key": "PE-16-2026",
        "source_name": "Termo_de_Referencia.pdf",
        "source_path": "/editais/Termo_de_Referencia.pdf",
        "result": {
            "n_interno": "PE-16-2026",
            "edital": {
                "numero_pregao": "16/2026",
                "tipo_licitacao": "Pregao Eletronico",
                "orgao": "Fundacao X",
                "uasg": "123456",
                "local": "Compras.gov.br",
                "data_disputa": "20/09/2026",
            },
            "documentacao": [{"documento": "Datasheet do fabricante"}],
        },
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _item(**overrides):
    values = {
        "id": 99,
        "item_number": "67",
        "categoria": "Switch",
        "lote_grupo": "1",
        "quantity": 10.0,
        "unit": "unidade",
        "description": "SWITCH 24 PORTAS GERENCIAVEL",
        "unit_value": 1500.0,
        "total_value": 15000.0,
        "garantia": "12 meses",
        "prazo_entrega": "5 dias uteis apos a requisicao",
        "exclusividade_me_epp_item": "Sim",
        "brand": None,
        "model": None,
        "has_direcionamento_marca": False,
        "direcionamento_marca_tipo": None,
        "direcionamento_marca_justificativa": None,
        "caracteristicas_tecnicas": "Suporte a VLAN e STP/RSTP",
        "caracteristicas_bi": {
            "quantidade_portas": "24 Portas",
            "portas_acesso": "Gigabit (10/100/1000)",
            "gerenciamento": "Gerenciavel",
            "alimentacao_poe": "Nao PoE",
            "uplinks": "N/C",
            "camada": "L2",
        },
        "raw_payload": {
            "numero_item_edital": "67",
            "descricao_original": "SWITCH 24 PORTAS GERENCIAVEL",
            "caracteristicas_tecnicas": "Suporte a VLAN e STP/RSTP",
            "direcionamento_marca": {"existe": False},
            "pagina": 15,
        },
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_build_match_export_preserves_raw_and_builds_normalized_contract() -> None:
    payload = build_match_item_export(_document(), _item())

    assert payload["metadados_exportacao"]["schema"] == "tor.match-item"
    assert payload["processo"]["processo_id"] == "PE-16-2026"
    assert payload["item"]["numero"] == "67"
    assert payload["raw"]["payload_original"]["pagina"] == 15
    assert payload["normalized"]["categoria_especifica"]["portas_acesso_qtd"] == 24
    assert payload["normalized"]["categoria_especifica"]["gerenciavel"] is True
    assert payload["normalized"]["categoria_especifica"]["poe"] is False
    assert "uplinks" not in payload["normalized"]["caracteristicas_bi"]
    assert payload["obrigacoes_gerais"]["prazo_entrega_dias"] == 5
    assert payload["obrigacoes_gerais"]["prazo_entrega_tipo"] == "uteis"
    assert payload["obrigacoes_gerais"]["garantia_meses"] == 12
    assert payload["obrigacoes_gerais"]["documentos_exigidos"] == ["Datasheet do fabricante"]
    assert any(req["campo_normalizado"] == "quantidade_portas" for req in payload["requisitos_atomicos"])


def test_build_match_export_keeps_supplied_atomic_requirements_and_provenance() -> None:
    item = _item()
    item.raw_payload["requisitos_atomicos"] = [
        {
            "id": "R67.01",
            "texto_original": "24 PORTAS RJ45",
            "campo_normalizado": "portas_acesso_qtd",
            "operador": ">=",
            "valor": 24,
            "unidade": "portas",
            "fonte": {"documento_id": "TR_v2", "pagina": 37},
        }
    ]

    requirement = build_match_item_export(_document(), item)["requisitos_atomicos"][0]

    assert requirement["id"] == "R67.01"
    assert requirement["operador"] == ">="
    assert requirement["origem"]["documento_id"] == "TR_v2"
    assert requirement["origem"]["pagina"] == 37


def test_build_match_export_reports_management_conflicts() -> None:
    item = _item()
    item.raw_payload["gerenciamento"] = "Nao Gerenciavel"

    divergences = build_match_item_export(_document(), item)["divergencias_documentais"]

    assert divergences[0]["tipo"] == "CONFLITO_ENTRE_CAMPOS"
    assert divergences[0]["campo"] == "gerenciamento"
    assert divergences[0]["status"] == "NAO_RESOLVIDO"


def test_match_filename_is_safe_and_identifies_process_and_item() -> None:
    assert match_item_filename(_document(), _item()) == "match_pe-16-2026_item_67.json"


def test_normalizer_preserves_first_raw_item_without_recursive_snapshots() -> None:
    source = {
        "schema_version": "7.4",
        "itens_elegiveis": [
            {
                "numero_item_edital": "67",
                "categoria": "switch",
                "descricao_original": "Texto EXATO do edital",
                "caracteristicas_bi": {"gerenciamento": "gerenciável"},
            }
        ],
    }

    first = normalize_analysis_result(source)
    second = normalize_analysis_result(first)
    raw = second["itens_elegiveis"][0]["_raw_input"]

    assert raw["categoria"] == "switch"
    assert raw["descricao_original"] == "Texto EXATO do edital"
    assert raw["caracteristicas_bi"]["gerenciamento"] == "gerenciável"
    assert "_raw_input" not in raw
