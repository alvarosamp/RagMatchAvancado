from types import SimpleNamespace

from app.services.opportunity_radar import build_catalog_terms, predict_competitor_entries, score_opportunity


def test_high_priority_for_switch_notice_with_good_value():
    item = {
        "objeto": "Aquisicao de switch gerenciavel 24 portas PoE com uplinks SFP para rede corporativa",
        "valorTotalEstimado": 250000,
        "dataEncerramentoProposta": "2099-01-10",
    }

    result = score_opportunity(item, {"switch", "gerenciavel", "poe", "sfp", "rede"})

    assert result.priority == "alta"
    assert result.score >= 75
    assert "switch" in result.matched_terms


def test_low_priority_for_unrelated_notice():
    item = {
        "objeto": "Contratacao de merenda escolar e generos alimenticios",
        "valorTotalEstimado": 900000,
    }

    result = score_opportunity(item, {"switch", "firewall", "roteador"})

    assert result.priority == "descartar"
    assert result.technical_fit <= 15


def test_risk_flags_do_not_hide_good_technical_fit():
    item = {
        "objeto": "Aquisicao de firewall com licencas e amostra obrigatoria para homologacao",
        "valorTotalEstimado": 180000,
    }

    result = score_opportunity(item, {"firewall", "licencas"})

    assert result.priority in {"alta", "analisar"}
    assert result.risk > 0
    assert result.risk_flags


def test_catalog_terms_include_product_metadata_and_specs():
    products = [
        SimpleNamespace(
            model="TOR-SW-24P",
            category="switch",
            manufacturer="Tor",
            data={"Portas RJ45": "24", "Uplinks SFP": "4"},
        )
    ]

    terms = build_catalog_terms(products)

    assert "switch" in terms
    assert "portas" in terms
    assert "uplinks" in terms


def test_predict_competitor_entries_ranks_compatible_optical_product():
    item = {
        "objeto": "Aquisicao de transceiver SFP+ 10G monomodo LC alcance minimo 10km",
    }
    products = [
        SimpleNamespace(
            id=1,
            model="SFPX10GDLR10KM",
            manufacturer="Concorrente A",
            category="transceiver",
            data={
                "Formato": "SFP+",
                "Velocidade": "10 Gbps",
                "Tipo de meio": "Fibra monomodo",
                "Alcance": "10 km",
            },
        ),
        SimpleNamespace(
            id=2,
            model="SFP1GDSR550M",
            manufacturer="Concorrente B",
            category="transceiver",
            data={
                "Formato": "SFP",
                "Velocidade": "1,25 Gbps",
                "Tipo de meio": "Fibra multimodo",
                "Alcance": "550 m",
            },
        ),
    ]

    predictions = predict_competitor_entries(item, products)

    assert predictions
    assert predictions[0].model == "SFPX10GDLR10KM"
    assert predictions[0].probability >= 70
    assert predictions[0].level == "provavel"


def test_predict_competitor_entries_marks_conflicting_product_as_technical_risk():
    item = {
        "objeto": "Aquisicao de transceiver SFP+ 10G monomodo LC alcance minimo 10km",
    }
    products = [
        SimpleNamespace(
            id=2,
            model="SFP1GDSR550M",
            manufacturer="Concorrente B",
            category="transceiver",
            data={
                "Formato": "SFP",
                "Velocidade": "1,25 Gbps",
                "Tipo de meio": "Fibra multimodo",
                "Alcance": "550 m",
            },
        ),
    ]

    predictions = predict_competitor_entries(item, products)

    assert predictions
    assert predictions[0].level == "risco_tecnico"
    assert predictions[0].probability <= 62
    assert predictions[0].conflicts
