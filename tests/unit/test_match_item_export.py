from __future__ import annotations

from types import SimpleNamespace

from app.services.analysis_normalizer import normalize_analysis_result
from app.services.match_item_export import (
    build_crm_notice_match_export,
    build_crm_match_item_export,
    build_match_item_export,
    match_item_filename,
    match_notice_filename,
)


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


def test_build_match_export_consumes_v8_nested_features_and_requirements() -> None:
    raw = {
        "categoria": "Transceiver",
        "direcionamento_marca": "Não identificado",
        "requisitos_tecnicos": [
            {
                "campo": "alcance_m",
                "operador": ">=",
                "valor": "10000",
                "unidade": "m",
                "condicao": "fibra monomodo",
                "texto_original": "alcance minimo de 10 km",
            }
        ],
        "evidencias": {
            "fibra_conector.alcance_m": [
                {"arquivo": "termo.pdf", "pagina": "12"}
            ]
        },
    }
    bi = {
        "transceiver": {
            "identificacao": {
                "form_factor": "SFP+",
                "velocidade_nominal_gbps": "10",
            },
            "fibra_conector": {"tipo_fibra": "Monomodo", "alcance_m": "10000"},
        }
    }
    item = _item(
        categoria="Transceiver",
        caracteristicas_bi=bi,
        raw_payload={"_raw_input": raw, "caracteristicas_bi": bi},
    )

    payload = build_match_item_export(_document(), item)
    category = payload["normalized"]["categoria_especifica"]
    requirement = payload["requisitos_atomicos"][0]

    assert category["form_factor"] == "SFP+"
    assert category["speed"] == "10"
    assert category["media_type"] == "Monomodo"
    assert category["distance"] == "10000"
    assert requirement["campo_normalizado"] == "alcance_m"
    assert requirement["escopo"] == "fibra monomodo"
    assert requirement["origem"]["arquivo"] == "termo.pdf"
    assert requirement["origem"]["pagina"] == "12"
    assert payload["raw"]["direcionamento_original"]["texto_original"] == "Não identificado"


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


def test_build_crm_match_export_uses_notice_and_product_metadata() -> None:
    notice = SimpleNamespace(
        id="notice-1",
        analysis_document_id=12,
        tor_id="2026_09_10_2",
        number="2026_09_10_2",
        bid_number="11/2026",
        modality="Pregao Eletronico",
        uasg=None,
        auction_date="2026-09-17T09:00:00",
        organ=SimpleNamespace(name="Camara Municipal de Marialva"),
        portal=SimpleNamespace(name="BNC", url="https://bnc.org.br"),
    )
    product = SimpleNamespace(
        id="product-1",
        item_number="1",
        category="Switch",
        lot="1",
        quantity=24,
        unit="UN",
        description="Switch 24 portas gerenciavel",
        reference_price=209.99,
        reference_total_price=5037.96,
        warranty="12 meses",
        delivery_deadline="10 dias uteis",
        exclusive_epp_label="Sim",
        is_exclusive_epp=True,
        brand_direction_model=None,
        brand_direction_exists=False,
        brand_direction_type=None,
        brand_direction_justification=None,
        technical_characteristics="VLAN e STP",
        bi_features={"quantidade_portas": "24 Portas", "gerenciamento": "Gerenciavel"},
        raw_payload={"descricao_original": "Switch 24 portas gerenciavel", "pagina": 8},
    )

    payload = build_crm_match_item_export(notice, product)

    assert payload["processo"]["processo_id"] == "2026_09_10_2"
    assert payload["processo"]["orgao"] == "Camara Municipal de Marialva"
    assert payload["processo"]["portal"] == "BNC"
    assert payload["item"]["numero"] == "1"
    assert payload["raw"]["payload_original"]["pagina"] == 8
    assert payload["normalized"]["categoria_especifica"]["portas_acesso_qtd"] == 24


def test_build_crm_notice_export_contains_all_edital_items_in_one_json() -> None:
    notice = SimpleNamespace(
        id="notice-1",
        analysis_document_id=12,
        tor_id="2026_09_10_2",
        number="2026_09_10_2",
        bid_number="11/2026",
        modality="Pregao Eletronico",
        uasg=None,
        auction_date="2026-09-17T09:00:00",
        organ=SimpleNamespace(name="Camara Municipal de Marialva"),
        portal=SimpleNamespace(name="BNC", url="https://bnc.org.br"),
    )

    def product(product_id: str, item_number: str, **overrides):
        values = {
            "id": product_id,
            "item_number": item_number,
            "category": "Switch",
            "lot": "1",
            "quantity": 2,
            "unit": "UN",
            "description": f"Switch item {item_number}",
            "reference_price": 100.0,
            "reference_total_price": 200.0,
            "warranty": "12 meses",
            "delivery_deadline": "10 dias uteis",
            "exclusive_epp_label": None,
            "is_exclusive_epp": False,
            "brand_direction_model": None,
            "brand_direction_exists": False,
            "brand_direction_type": None,
            "brand_direction_justification": None,
            "technical_characteristics": "VLAN",
            "bi_features": {"quantidade_portas": "24 Portas"},
            "raw_payload": {"descricao_original": f"Switch item {item_number}"},
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    payload = build_crm_notice_match_export(
        notice,
        [
            product("product-1", "1"),
            product("product-2", "2", quantity=3),
            product("kit-1", "2.1", raw_payload={"kit_component": True}),
        ],
    )

    assert payload["metadados_exportacao"]["schema"] == "tor.match-edital"
    assert payload["processo"]["processo_id"] == "2026_09_10_2"
    assert payload["resumo"] == {"quantidade_itens": 2, "quantidade_total": 5.0}
    assert [entry["item"]["numero"] for entry in payload["itens"]] == ["1", "2"]
    assert all("processo" not in entry for entry in payload["itens"])
    assert match_notice_filename(payload) == "match_edital_2026_09_10_2.json"
