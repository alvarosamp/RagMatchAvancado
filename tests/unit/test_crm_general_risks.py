from app.crm.json_analysis_importer import _general_risks


def test_general_risks_accepts_top_level_aliases():
    assert _general_risks({"riscos gerais": ["Prazo curto", "Fornecedor unico"]}, {}) == "Prazo curto\nFornecedor unico"


def test_general_risks_preserves_nested_object_information():
    value = _general_risks({"riscos": {"risco_geral": {"nivel": "alto", "motivos": ["prazo"]}}}, {})
    assert '"nivel": "alto"' in value
    assert '"motivos": ["prazo"]' in value
