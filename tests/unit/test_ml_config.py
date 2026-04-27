"""
Testes unitários do MLConfig (core/ml_config.py).

Verifica que:
  ✓ Os valores default estão corretos
  ✓ Variáveis de ambiente sobrescrevem os defaults (padrão ML_*)
  ✓ Os thresholds são consistentes (verificar < atende)
  ✓ Os pesos somam 1.0

Como rodar:
    pytest tests/unit/test_ml_config.py -v
"""

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import patch

# ── Carrega ml_config pelo caminho ────────────────────────────────────────────
# ml_config usa pydantic-settings — precisa estar instalado no ambiente de teste.
# Se não estiver, pula os testes com pytest.importorskip.
pydantic_settings = pytest = None
try:
    import pytest
    import pydantic_settings  # noqa
except ImportError:
    pass

if pytest is None:
    import pytest  # type: ignore

_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "backend" / "app" / "core" / "ml_config.py"
)
_spec = importlib.util.spec_from_file_location("ml_config_mod", _CONFIG_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

MLConfig = _mod.MLConfig
get_ml_config = _mod.get_ml_config


class TestMLConfigDefaults:

    def test_modelos_default(self):
        cfg = MLConfig()
        assert cfg.llm_model == "phi3"
        assert cfg.embed_model == "nomic-embed-text"
        assert cfg.embed_dims == 768

    def test_thresholds_default(self):
        cfg = MLConfig()
        assert cfg.threshold_atende == 0.75
        assert cfg.threshold_verificar == 0.45

    def test_verificar_menor_que_atende(self):
        """Invariante: verificar < atende sempre."""
        cfg = MLConfig()
        assert cfg.threshold_verificar < cfg.threshold_atende

    def test_pesos_somam_um(self):
        """Pesos heurística + LLM devem somar 1.0."""
        cfg = MLConfig()
        soma = cfg.score_weight_heuristic + cfg.score_weight_llm
        assert abs(soma - 1.0) < 1e-9, f"Pesos somam {soma}, esperado 1.0"

    def test_chunk_max_chars_positivo(self):
        cfg = MLConfig()
        assert cfg.chunk_max_chars > 0

    def test_chunk_overlap_menor_que_max_chars(self):
        cfg = MLConfig()
        assert cfg.chunk_overlap < cfg.chunk_max_chars


class TestMLConfigEnvOverride:

    def test_env_sobrescreve_threshold_atende(self):
        """ML_THRESHOLD_ATENDE=0.80 deve sobrescrever o default 0.75."""
        with patch.dict(os.environ, {"ML_THRESHOLD_ATENDE": "0.80"}):
            cfg = MLConfig()
            assert cfg.threshold_atende == 0.80

    def test_env_sobrescreve_llm_model(self):
        with patch.dict(os.environ, {"ML_LLM_MODEL": "llama3"}):
            cfg = MLConfig()
            assert cfg.llm_model == "llama3"
