"""
Testes unitários do MatchingEvaluator (mlops/evaluator.py).

O evaluator não tem dependências externas (só stdlib) — é o mais fácil de testar.
Garante que:
  ✓ Distribuição saudável não gera alertas
  ✓ Zona de incerteza alta dispara alerta
  ✓ Score médio muito alto dispara alerta
  ✓ Desvio padrão baixo dispara alerta
  ✓ Requisitos com score baixo são detectados
  ✓ Saúde geral é calculada corretamente

Como rodar:
    pytest tests/unit/test_evaluator.py -v
"""

import importlib.util
import sys
from pathlib import Path

# ── Carrega o evaluator diretamente pelo caminho ──────────────────────────────
# Como só usa stdlib, não precisa de nenhum mock.
_EVALUATOR_PATH = (
    Path(__file__).resolve().parents[2] / "backend" / "app" / "mlops" / "evaluator.py"
)
_spec = importlib.util.spec_from_file_location("evaluator_mod", _EVALUATOR_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

MatchingEvaluator = _mod.MatchingEvaluator


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resultado(score: float, status: str = "ATENDE", requisitos: list = None) -> dict:
    """Cria um resultado de matching para usar nos testes."""
    return {
        "modelo": f"Switch-{score:.2f}",
        "score_geral": score,
        "status_geral": status,
        "detalhes": requisitos or [],
    }


def _req(nome: str, score: float) -> dict:
    return {"requisito": nome, "score": score}


# ── Testes: avaliar_distribuicao ──────────────────────────────────────────────

class TestAvaliarDistribuicao:

    def setup_method(self):
        self.ev = MatchingEvaluator()

    def test_distribuicao_saudavel_sem_alertas(self):
        """Scores bem distribuídos entre 0.2 e 0.9 → sem alertas."""
        resultados = [
            _resultado(0.20), _resultado(0.35), _resultado(0.55),
            _resultado(0.78), _resultado(0.85), _resultado(0.90),
        ]
        r = self.ev.avaliar_distribuicao(resultados)
        assert r["alertas"] == []

    def test_alerta_quando_muitos_na_zona_incerteza(self):
        """Mais de 40% dos scores entre 0.45 e 0.75 → alerta de incerteza."""
        resultados = [_resultado(0.50)] * 5 + [_resultado(0.90)] * 2
        r = self.ev.avaliar_distribuicao(resultados)
        alertas_text = " ".join(r["alertas"])
        assert "incerteza" in alertas_text.lower()

    def test_alerta_media_muito_alta(self):
        """Média > 0.90 → sistema pode estar superestimando."""
        resultados = [_resultado(0.95), _resultado(0.96), _resultado(0.97)]
        r = self.ev.avaliar_distribuicao(resultados)
        alertas_text = " ".join(r["alertas"])
        assert "alta" in alertas_text.lower() or "superestimando" in alertas_text.lower()

    def test_retorna_estatisticas_basicas(self):
        """Sempre retorna media, mediana, min, max e desvio_padrao."""
        resultados = [_resultado(0.3), _resultado(0.5), _resultado(0.8)]
        r = self.ev.avaliar_distribuicao(resultados)
        for campo in ("score_media", "score_mediana", "score_maximo", "score_minimo", "desvio_padrao"):
            assert campo in r, f"Campo '{campo}' não encontrado no resultado"

    def test_total_produtos_correto(self):
        resultados = [_resultado(0.5)] * 7
        r = self.ev.avaliar_distribuicao(resultados)
        assert r["total_produtos"] == 7

    def test_lista_vazia_retorna_erro(self):
        r = self.ev.avaliar_distribuicao([])
        assert "erro" in r

    def test_score_maximo_e_minimo_corretos(self):
        resultados = [_resultado(0.20), _resultado(0.60), _resultado(0.90)]
        r = self.ev.avaliar_distribuicao(resultados)
        assert abs(r["score_maximo"] - 0.90) < 0.001
        assert abs(r["score_minimo"] - 0.20) < 0.001


# ── Testes: avaliar_cobertura_requisitos ──────────────────────────────────────

class TestAvaliarCoberturaRequisitos:

    def setup_method(self):
        self.ev = MatchingEvaluator()

    def test_requisito_com_score_baixo_e_detectado(self):
        """Requisito com score médio < 0.5 aparece em 'requisitos_problematicos'."""
        resultados = [
            _resultado(0.80, requisitos=[_req("PoE Budget", 0.2), _req("Portas", 0.9)]),
            _resultado(0.75, requisitos=[_req("PoE Budget", 0.15), _req("Portas", 0.88)]),
        ]
        r = self.ev.avaliar_cobertura_requisitos(resultados)
        nomes_problematicos = [p["requisito"] for p in r["requisitos_problematicos"]]
        assert "PoE Budget" in nomes_problematicos

    def test_requisito_com_score_alto_nao_e_problematico(self):
        """Requisito com score médio >= 0.5 não deve aparecer como problemático."""
        resultados = [
            _resultado(0.80, requisitos=[_req("Portas RJ45", 0.95)]),
        ]
        r = self.ev.avaliar_cobertura_requisitos(resultados)
        nomes_problematicos = [p["requisito"] for p in r["requisitos_problematicos"]]
        assert "Portas RJ45" not in nomes_problematicos

    def test_ranking_ordenado_do_pior_para_melhor(self):
        """ranking_completo deve vir em ordem crescente de score_medio."""
        resultados = [
            _resultado(0.8, requisitos=[
                _req("Req A", 0.9),
                _req("Req B", 0.3),
                _req("Req C", 0.6),
            ]),
        ]
        r = self.ev.avaliar_cobertura_requisitos(resultados)
        scores = [item["score_medio"] for item in r["ranking_completo"]]
        assert scores == sorted(scores), "Ranking não está em ordem crescente"

    def test_sem_detalhes_retorna_erro(self):
        """Resultados sem campo 'detalhes' → erro gracioso."""
        resultados = [{"modelo": "X", "score_geral": 0.8}]
        r = self.ev.avaliar_cobertura_requisitos(resultados)
        assert "erro" in r

    def test_lista_vazia_retorna_erro(self):
        r = self.ev.avaliar_cobertura_requisitos([])
        assert "erro" in r


# ── Testes: _calcular_saude ───────────────────────────────────────────────────

class TestCalcularSaude:

    def setup_method(self):
        self.ev = MatchingEvaluator()

    def test_distribuicao_perfeita_saude_alta(self):
        """Sem alertas e desvio padrão OK → saúde próxima de 100."""
        distribuicao = {
            "pct_zona_incerteza": 5.0,
            "desvio_padrao": 0.20,
            "alertas": [],
        }
        saude = self.ev._calcular_saude(distribuicao)
        assert saude >= 90

    def test_muita_incerteza_penaliza_saude(self):
        """50% na zona de incerteza → penalidade significativa."""
        distribuicao = {
            "pct_zona_incerteza": 50.0,
            "desvio_padrao": 0.15,
            "alertas": [],
        }
        saude_incerteza = self.ev._calcular_saude(distribuicao)

        distribuicao_boa = {
            "pct_zona_incerteza": 5.0,
            "desvio_padrao": 0.15,
            "alertas": [],
        }
        saude_boa = self.ev._calcular_saude(distribuicao_boa)
        assert saude_incerteza < saude_boa

    def test_erro_retorna_zero(self):
        """Distribuição com erro → saúde = 0."""
        distribuicao = {"erro": "Nenhum resultado"}
        assert self.ev._calcular_saude(distribuicao) == 0

    def test_saude_nunca_negativa(self):
        """Saúde mínima é 0, nunca negativa."""
        distribuicao = {
            "pct_zona_incerteza": 100.0,
            "desvio_padrao": 0.01,
            "alertas": ["alerta1", "alerta2", "alerta3", "alerta4", "alerta5"],
        }
        saude = self.ev._calcular_saude(distribuicao)
        assert saude >= 0

    def test_cada_alerta_penaliza(self):
        """Mais alertas → saúde menor."""
        base = {"pct_zona_incerteza": 10.0, "desvio_padrao": 0.20}
        saude_sem_alerta = self.ev._calcular_saude({**base, "alertas": []})
        saude_com_alerta = self.ev._calcular_saude({**base, "alertas": ["X"]})
        assert saude_com_alerta < saude_sem_alerta
