from app.services.analysis_store import build_business_key, build_source_hash


def test_build_source_hash_is_stable_for_same_document():
    first = build_source_hash("edital", "texto extraido", "edital.pdf")
    second = build_source_hash("edital", "texto extraido", "edital.pdf")

    assert first == second


def test_build_source_hash_changes_when_content_changes():
    first = build_source_hash("edital", "texto extraido", "edital.pdf")
    second = build_source_hash("edital", "texto alterado", "edital.pdf")

    assert first != second


class TestBuildBusinessKey:
    def test_usa_n_interno_quando_presente(self):
        result = {"n_interno": "PE-12-2026", "edital": {"numero_pregao": "99/2026"}}
        assert build_business_key(result, "arquivo.json") == "analysis-json|PE-12-2026"

    def test_mesmo_n_interno_gera_mesma_chave_mesmo_com_conteudo_diferente(self):
        result_a = {"n_interno": "PE-12-2026", "itens_elegiveis": [{"a": 1}]}
        result_b = {"n_interno": "PE-12-2026", "itens_elegiveis": [{"a": 2}, {"b": 3}]}
        assert build_business_key(result_a, "a.json") == build_business_key(result_b, "b.json")

    def test_sem_n_interno_usa_pregao_orgao_data(self):
        result = {"edital": {"numero_pregao": "12/2026", "orgao": "Prefeitura X", "data_disputa": "10/10/2026"}}
        key = build_business_key(result, "arquivo.json")
        assert key is not None
        assert key.startswith("analysis-json|")

    def test_pregao_orgao_iguais_geram_mesma_chave_independente_do_filename(self):
        result_a = {"edital": {"numero_pregao": "12/2026", "orgao": "Prefeitura X", "data_disputa": "10/10/2026"}}
        result_b = dict(result_a)
        assert build_business_key(result_a, "a.json") == build_business_key(result_b, "outro_nome.json")

    def test_pregao_diferente_gera_chave_diferente(self):
        result_a = {"edital": {"numero_pregao": "12/2026", "orgao": "Prefeitura X"}}
        result_b = {"edital": {"numero_pregao": "13/2026", "orgao": "Prefeitura X"}}
        assert build_business_key(result_a, None) != build_business_key(result_b, None)

    def test_sem_dado_suficiente_retorna_none(self):
        assert build_business_key({}, None) is None
        assert build_business_key({"edital": {}}, None) is None

    def test_n_interno_vazio_cai_no_fallback(self):
        result = {"n_interno": "", "edital": {"numero_pregao": "12/2026"}}
        key = build_business_key(result, None)
        assert key is not None and "12/2026" not in key  # vira hash, nao texto puro
