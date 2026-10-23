from app.services.analysis_normalizer import normalize_analysis_result
from app.services.edital_analysis import _infer_type


def test_cables_are_not_confused_with_transceivers():
    assert _infer_type('Cabo DAC SFP+ 10G 3m') == 'Cabo DAC'
    assert _infer_type('Cabo AOC QSFP28') == 'Cabo óptico AOC'
    assert _infer_type('Cordão óptico LC-LC monomodo') == 'Cabo óptico'
    assert _infer_type('Transceiver SFP+ 10G') == 'transceiver'
    assert _infer_type('Switch 24 portas com cabo DAC') == 'switch'


def test_normalizer_preserves_flexible_nested_cable_attributes():
    features = {'cabo_dac': {'comprimento_m': 3, 'conectores': ['SFP+', 'SFP+']}}
    source = {'itens_elegiveis': [{'categoria': 'cabos dac', 'caracteristicas_bi': features}]}
    item = normalize_analysis_result(source)['itens_elegiveis'][0]
    assert item['categoria'] == 'Cabo DAC'
    assert item['caracteristicas_bi'] == features
    assert source['itens_elegiveis'][0]['categoria'] == 'cabos dac'
