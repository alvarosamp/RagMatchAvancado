def test_check_requirements():
    switch_specs = {
        "portas_rj45": "16 portas",
        "gerenciavel": "sim",
        "poe": "sim",
        "velocidade_porta_mbps": "1000 Mbps",
        "alimentacao_bivolt": "sim",
        "certificacao_anatel": "sim",
    }

    result = check_requirements(switch_specs)
    
    assert result["portas_rj45"]["status"] == "✅ Atende"
    assert result["gerenciavel"]["status"] == "✅ Atende"
    assert result["poe"]["status"] == "✅ Atende"