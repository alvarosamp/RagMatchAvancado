from app.services.analysis_normalizer import (
    normalize_analysis_result,
    normalize_brand_direction,
)


def test_legacy_spreadsheet_headers_and_price_preserve_original_data():
    source = {'N Interno': '2026_04_08_12', 'Órgão': 'Prefeitura de Seberi',
              'Data Disputa': '22/04/2026', 'Nº Pregão': '12/2026',
              'itens': [{'descricao': 'Switch 16 portas', 'preco': 'R$ 408,87', 'quantidade': '3'}]}
    normalized = normalize_analysis_result(source)
    assert normalized['n_interno'] == '2026_04_08_12'
    assert normalized['edital']['orgao'] == 'Prefeitura de Seberi'
    assert normalized['edital']['numero_pregao'] == '12/2026'
    assert normalized['itens_elegiveis'][0]['preco_unitario'] == 'R$ 408,87'
    assert normalized['itens_elegiveis'][0]['_raw_input'] == source['itens'][0]
    assert normalized['Órgão'] == source['Órgão']
    assert 'n_interno' not in source


def test_legacy_envelope_unwrapped_and_canonical_fields_take_precedence():
    inner = {'N Interno': 'old-id', 'n_interno': 'canonical-id', 'Órgão': 'Old organ',
             'edital': {'orgao': 'Canonical organ'}, 'itens': []}
    normalized = normalize_analysis_result({'model': 'local-model', 'result': inner})
    assert normalized['n_interno'] == 'canonical-id'
    assert normalized['edital']['orgao'] == 'Canonical organ'
    assert normalized['result'] == inner
    assert normalized['model'] == 'local-model'


def _v8_item(direction="Não identificado"):
    return {
        "categoria": "Transceiver",
        "numero_item_edital": "4",
        "descricao_original": "Transceiver SFP+ 10G monomodo",
        "direcionamento_marca": direction,
        "caracteristicas_bi": {
            "transceiver": {
                "identificacao": {
                    "form_factor": "SFP+",
                    "velocidade_nominal_gbps": "10",
                },
                "fibra_conector": {"tipo_fibra": "Monomodo", "alcance_m": "10000"},
            }
        },
        "requisitos_tecnicos": [
            {
                "campo": "alcance_m",
                "operador": ">=",
                "valor": "10000",
                "unidade": "m",
                "condicao": "fibra monomodo",
                "texto_original": "alcance mínimo de 10 km",
            }
        ],
        "evidencias": {
            "fibra_conector.alcance_m": [{"arquivo": "termo.pdf", "pagina": "12"}]
        },
    }


def test_v8_preserves_nested_features_requirements_and_sources():
    source = {
        "schema_version": "8.0",
        "controle": {"versao_analisador": "V8", "data_processamento": "2026-09-21"},
        "auditoria": {"fontes_consultadas": ["edital.pdf", "termo.pdf"]},
        "itens_elegiveis": [_v8_item()],
    }

    normalized = normalize_analysis_result(source)
    item = normalized["itens_elegiveis"][0]

    assert normalized["schema_version"] == "8.0"
    assert normalized["auditoria"]["fontes_consultadas"] == ["edital.pdf", "termo.pdf"]
    assert item["caracteristicas_bi"]["transceiver"]["identificacao"]["form_factor"] == "SFP+"
    assert item["requisitos_tecnicos"][0]["campo"] == "alcance_m"
    assert item["evidencias"]["fibra_conector.alcance_m"][0]["pagina"] == "12"
    assert item["direcionamento_marca"] == "Não identificado"
    assert "_raw_input" not in item


def test_v8_brand_direction_text_is_adapted_for_crm():
    source = {
        "controle": {"versao_analisador": "V8"},
        "itens_elegiveis": [
            _v8_item(
                "Sim — Marca/modelo: ACME X10 | Tipo: Modelo | "
                "Justificativa: referência nominal aceita com equivalente"
            )
        ],
    }

    normalized = normalize_analysis_result(source)
    assert normalized["itens_elegiveis"][0]["direcionamento_marca"].startswith("Sim")
    direction = normalize_brand_direction(
        normalized["itens_elegiveis"][0]["direcionamento_marca"]
    )

    assert direction == {
        "existe": True,
        "marca_modelo": "ACME X10",
        "tipo": "Modelo",
        "justificativa": "referência nominal aceita com equivalente",
        "texto_original": (
            "Sim — Marca/modelo: ACME X10 | Tipo: Modelo | "
            "Justificativa: referência nominal aceita com equivalente"
        ),
    }
