"""
tests/unit/test_match_engine_scoring.py
─────────────────────────────────────────
Testes de _rule_score e _aggregate_report — score com penalidades críticas
e dado faltante. Usa SimpleNamespace no lugar de Requirement/Product (ORM)
porque essas funções só leem atributos, não precisam de sessão de banco.
"""

from types import SimpleNamespace

from app.db.models import MatchStatus
from app.services.match_engine import (
    ATTRIBUTE_WEIGHTS,
    MatchDetail,
    _aggregate_report,
    _rule_score,
    _score_to_status,
)


def _req(attribute, raw_value, parsed_value=None):
    return SimpleNamespace(attribute=attribute, raw_value=raw_value, parsed_value=parsed_value)


def _product(model="Switch X", **specs):
    return SimpleNamespace(model=model, data=specs, id=1)


class TestRuleScoreMissingData:
    def test_campo_ausente_marca_missing_data(self):
        result = _rule_score({}, _req("Portas RJ45", "16"))
        assert result.score == 0.5
        assert result.missing_data is True
        assert result.critical_fail is False


class TestRuleScoreCriticalFail:
    def test_tensao_incompativel_e_critica(self):
        result = _rule_score({"Power Requirement / Tensão de Entrada": "220 VAC"}, _req(
            "Power Requirement / Tensão de Entrada", "100",
        ))
        assert result.score == 0.0
        assert result.critical_fail is True

    def test_tensao_compativel_nao_e_falha(self):
        result = _rule_score({"Power Requirement / Tensão de Entrada": "100-240 VAC"}, _req(
            "Power Requirement / Tensão de Entrada", "100",
        ))
        assert result.score == 1.0
        assert result.critical_fail is False

    def test_portas_insuficientes_nao_e_critica(self):
        """Faltar porta é ruim, mas não é uma incompatibilidade física como tensão."""
        result = _rule_score({"Portas RJ45": "8x 1G"}, _req("Portas RJ45", "16"))
        assert result.score == 0.0
        assert result.critical_fail is False


class TestAggregateReportCriticalPropagation:
    def _detail(self, attribute, final_score, critical_fail=False, missing_data=False):
        return MatchDetail(
            attribute=attribute, required="x", found="y",
            rule_score=final_score, llm_score=final_score, final_score=final_score,
            status=_score_to_status(final_score),
            critical_fail=critical_fail, missing_data=missing_data,
        )

    def test_falha_critica_forca_nao_atende_mesmo_com_media_alta(self):
        """
        9 requisitos com score 1.0 (atende bem) + 1 tensão incompatível
        (critical_fail=True, score 0.0). Média simples ficaria em 0.9 (Atende),
        mas a falha crítica tem que desqualificar o produto de qualquer forma.
        """
        details = [self._detail("Portas RJ45", 1.0) for _ in range(9)]
        details.append(self._detail("Power Requirement / Tensão de Entrada", 0.0, critical_fail=True))

        report = _aggregate_report(_product(), edital_id=1, details=details)

        assert report.status == MatchStatus.NAO_ATENDE
        assert "Power Requirement / Tensão de Entrada" in report.critical_failures

    def test_sem_falha_critica_usa_status_do_score(self):
        details = [self._detail("Portas RJ45", 1.0) for _ in range(5)]
        report = _aggregate_report(_product(), edital_id=1, details=details)
        assert report.status == MatchStatus.ATENDE
        assert report.critical_failures == []

    def test_peso_por_atributo_pesa_mais_que_media_simples(self):
        """
        1 requisito 'tensao' (peso 1.5) com score 0.0 e 1 requisito genérico
        (peso 1.0) com score 1.0. Média simples seria 0.5 (Verificar); com
        peso, a tensão pesa mais e o resultado cai mais perto de NAO_ATENDE.
        """
        details = [
            self._detail("Power Requirement / Tensão de Entrada", 0.0),  # sem critical_fail aqui, só peso
            self._detail("Camada", 1.0),
        ]
        report = _aggregate_report(_product(), edital_id=1, details=details)

        simple_mean = 0.5
        assert report.overall_score < simple_mean

    def test_sem_detalhes_retorna_verificar(self):
        report = _aggregate_report(_product(), edital_id=1, details=[])
        assert report.status == MatchStatus.VERIFICAR
        assert report.overall_score == 0.0


class TestAttributeWeights:
    def test_pesos_criticos_sao_maiores_que_generico(self):
        assert ATTRIBUTE_WEIGHTS["tensao"] > ATTRIBUTE_WEIGHTS["generic"]
        assert ATTRIBUTE_WEIGHTS["temperatura"] > ATTRIBUTE_WEIGHTS["generic"]
