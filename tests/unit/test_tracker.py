"""
Testes unitários do MatchingTracker (mlops/tracker.py).

CONCEITO: Quando testamos código que usa um serviço externo (MLflow),
usamos 'mocks' — objetos falsos que registram as chamadas feitas.
Assim verificamos: "o tracker chamou mlflow.log_params com os valores certos?"
sem precisar de um servidor MLflow rodando.

Como rodar:
    pytest tests/unit/test_tracker.py -v
"""

import sys
import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch, call

# ── Mock do mlflow ANTES de importar o tracker ───────────────────────────────
# O tracker faz "import mlflow" no topo. Se mlflow não estiver em sys.modules,
# Python vai tentar importar o pacote real (pode falhar no CI sem mlflow instalado).
# Injetamos um stub antes que o módulo seja carregado.

mock_mlflow = MagicMock()
mock_mlflow.tracking = MagicMock()

# O context manager do start_run precisa de __enter__/__exit__
mock_run_ctx = MagicMock()
mock_run_ctx.__enter__ = MagicMock(return_value=MagicMock())
mock_run_ctx.__exit__ = MagicMock(return_value=False)
mock_mlflow.start_run.return_value = mock_run_ctx

sys.modules["mlflow"] = mock_mlflow

# ── Carrega o tracker pelo caminho ────────────────────────────────────────────
_TRACKER_PATH = (
    Path(__file__).resolve().parents[2] / "backend" / "app" / "mlops" / "tracker.py"
)
_spec = importlib.util.spec_from_file_location("tracker_mod", _TRACKER_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

MatchingTracker = _mod.MatchingTracker


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _tracker() -> MatchingTracker:
    """Cria um tracker com MLflow mockado."""
    mock_mlflow.reset_mock()
    return MatchingTracker(experiment_name="test_experiment")


def _resultados_exemplo() -> list[dict]:
    return [
        {"modelo": "Switch A", "score_geral": 0.90, "status_geral": "ATENDE"},
        {"modelo": "Switch B", "score_geral": 0.60, "status_geral": "VERIFICAR"},
        {"modelo": "Switch C", "score_geral": 0.30, "status_geral": "NAO_ATENDE"},
    ]


# ── Testes: inicialização ─────────────────────────────────────────────────────

class TestTrackerInit:

    def test_configura_tracking_uri(self):
        """__init__ deve chamar mlflow.set_tracking_uri."""
        tracker = _tracker()
        mock_mlflow.set_tracking_uri.assert_called_once()

    def test_configura_experimento(self):
        """__init__ deve chamar mlflow.set_experiment com o nome correto."""
        tracker = _tracker()
        mock_mlflow.set_experiment.assert_called_once_with("test_experiment")


# ── Testes: log_params ────────────────────────────────────────────────────────

class TestLogParams:

    def test_serializa_todos_valores_para_string(self):
        """log_params converte todos os valores para str antes de logar."""
        tracker = _tracker()
        tracker.log_params({"modelo": "phi3", "peso": 0.7, "flag": True})
        # Captura os args com que mlflow.log_params foi chamado
        args, _ = mock_mlflow.log_params.call_args
        params_logados = args[0]
        for v in params_logados.values():
            assert isinstance(v, str), f"Valor '{v}' não foi serializado para string"

    def test_chaves_sao_preservadas(self):
        """Nomes dos parâmetros não devem ser alterados."""
        tracker = _tracker()
        tracker.log_params({"llm_model": "phi3", "embed_model": "nomic"})
        args, _ = mock_mlflow.log_params.call_args
        params_logados = args[0]
        assert "llm_model" in params_logados
        assert "embed_model" in params_logados


# ── Testes: log_metrics ───────────────────────────────────────────────────────

class TestLogMetrics:

    def test_chama_mlflow_log_metrics(self):
        tracker = _tracker()
        tracker.log_metrics({"score_medio": 0.85, "tempo_execucao_segundos": 3.2})
        mock_mlflow.log_metrics.assert_called_once()

    def test_sem_step_passa_none(self):
        tracker = _tracker()
        tracker.log_metrics({"score": 0.8})
        _, kwargs = mock_mlflow.log_metrics.call_args
        assert kwargs.get("step") is None


# ── Testes: log_matching_run ──────────────────────────────────────────────────

class TestLogMatchingRun:

    def test_calcula_metricas_corretamente(self):
        """
        Dado 1 ATENDE, 1 VERIFICAR, 1 NAO_ATENDE:
        pct_atende = 33.33, pct_verificar = 33.33, pct_nao_atende = 33.33
        """
        tracker = _tracker()
        tracker.log_matching_run(
            edital_id="42",
            resultados=_resultados_exemplo(),
        )
        # Verifica que log_metrics foi chamado (dentro do context manager)
        mock_mlflow.log_metrics.assert_called()

    def test_loga_parametros_do_modelo(self):
        """Parametros como llm_model e embed_model devem ser logados."""
        tracker = _tracker()
        tracker.log_matching_run(
            edital_id="1",
            resultados=_resultados_exemplo(),
            llm_model="llama3",
            embed_model="nomic-embed-text",
        )
        mock_mlflow.log_params.assert_called()
        args, _ = mock_mlflow.log_params.call_args
        params = args[0]
        assert params.get("llm_model") == "llama3"
        assert params.get("embed_model") == "nomic-embed-text"

    def test_resultados_vazios_nao_loga_metricas(self):
        """Com lista vazia, não deve tentar calcular scores."""
        tracker = _tracker()
        mock_mlflow.log_metrics.reset_mock()
        tracker.log_matching_run(edital_id="99", resultados=[])
        mock_mlflow.log_metrics.assert_not_called()

    def test_usa_context_manager_do_start_run(self):
        """log_matching_run deve abrir e fechar um run MLflow."""
        tracker = _tracker()
        tracker.log_matching_run(edital_id="7", resultados=_resultados_exemplo())
        mock_mlflow.start_run.assert_called_once()
        mock_run_ctx.__enter__.assert_called_once()
        mock_run_ctx.__exit__.assert_called_once()


# ── Testes: model registry ────────────────────────────────────────────────────

class TestModelRegistry:

    def test_register_model_chama_mlflow_register(self):
        tracker = _tracker()
        mock_mlflow.register_model.return_value = MagicMock(version="1")
        version = tracker.register_model(run_id="abc123", model_name="edital_matching")
        mock_mlflow.register_model.assert_called_once()
        assert version == "1"

    def test_register_model_erro_retorna_none(self):
        tracker = _tracker()
        mock_mlflow.register_model.side_effect = Exception("server error")
        version = tracker.register_model(run_id="bad_id")
        assert version is None

    def test_promote_model_stage_invalido_retorna_false(self):
        tracker = _tracker()
        result = tracker.promote_model("edital_matching", "1", stage="InvalidStage")
        assert result is False

    def test_promote_model_stage_valido(self):
        tracker = _tracker()
        mock_client = MagicMock()
        mock_mlflow.tracking.MlflowClient.return_value = mock_client
        result = tracker.promote_model("edital_matching", "2", stage="Production")
        assert result is True
        mock_client.transition_model_version_stage.assert_called_once_with(
            name="edital_matching",
            version="2",
            stage="Production",
            archive_existing_versions=True,
        )
