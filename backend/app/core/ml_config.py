"""
Configuração centralizada de todos os parâmetros de ML.

Por que centralizar?
  Antes: thresholds espalhados em evaluator.py (0.75), chunker.py (1000),
  drift_monitor.py (0.10), match_engine.py (0.3/0.7)... impossível de rastrear.

  Agora: um só lugar para alterar. Se quiser testar threshold=0.80,
  mude aqui e todos os módulos pegam automaticamente.

  Em CI/CD, as variáveis com prefixo ML_ sobrescrevem os defaults via env vars:
    ML_THRESHOLD_ATENDE=0.80 python mlops/scripts/evaluate.py

Uso:
    from app.core.ml_config import get_ml_config
    cfg = get_ml_config()
    if score >= cfg.threshold_atende:
        status = "ATENDE"
"""

from functools import lru_cache
from pydantic_settings import BaseSettings


class MLConfig(BaseSettings):
    # ── Modelos ───────────────────────────────────────────────────────────────
    llm_model: str = "llama3.2:1b"
    embed_model: str = "nomic-embed-text"
    embed_dims: int = 768

    # ── Pesos do score final ──────────────────────────────────────────────────
    # score_final = (score_heuristica * peso_h) + (score_llm * peso_l)
    score_weight_heuristic: float = 0.30
    score_weight_llm: float = 0.70

    # ── Thresholds de classificação ───────────────────────────────────────────
    # score >= threshold_atende              → ATENDE
    # threshold_verificar <= score < atende  → VERIFICAR
    # score < threshold_verificar            → NÃO ATENDE
    threshold_atende: float = 0.75
    threshold_verificar: float = 0.45

    # ── Chunker ───────────────────────────────────────────────────────────────
    chunk_max_chars: int = 1_000
    chunk_overlap: int = 150

    # ── Detecção de drift ─────────────────────────────────────────────────────
    drift_score_delta: float = 0.10   # variação > 0.10 na média = drift
    drift_janela_runs: int = 10       # quantos runs comparar em cada janela

    # ── Alertas de qualidade ──────────────────────────────────────────────────
    quality_max_pct_incerteza: float = 40.0  # % máx de scores na zona cinza
    quality_min_desvio_padrao: float = 0.05  # desvio mínimo esperado
    quality_max_score_medio: float = 0.90    # acima disso = sistema muito confiante

    model_config = {"env_prefix": "ML_"}


@lru_cache
def get_ml_config() -> MLConfig:
    """Singleton — lê .env e variáveis de ambiente uma única vez."""
    return MLConfig()
