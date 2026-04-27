"""
Script de avaliação de qualidade dos runs de matching.

CONCEITO MLOPS: Model Evaluation
  Depois de rodar o pipeline, você precisa responder:
  "O sistema está funcionando bem? Os scores fazem sentido?"

  Este script faz exatamente isso:
    1. Carrega os runs recentes do MLflow
    2. Analisa a distribuição dos scores
    3. Detecta padrões problemáticos
    4. Gera um relatório de saúde

Como usar:
    # Via Makefile:
    make evaluate

    # Direto:
    PYTHONPATH=backend python mlops/scripts/evaluate.py
    PYTHONPATH=backend python mlops/scripts/evaluate.py --experiment edital_matching --top 20
    PYTHONPATH=backend python mlops/scripts/evaluate.py --results-file resultados.json
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Adiciona backend ao path para importar os módulos da app
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s │ %(message)s")
logger = logging.getLogger(__name__)


def _carregar_runs_mlflow(experiment_name: str, top_n: int) -> list[dict]:
    """Carrega runs recentes do MLflow e converte para o formato do evaluator."""
    try:
        import mlflow

        tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
        mlflow.set_tracking_uri(tracking_uri)

        runs = mlflow.search_runs(
            experiment_names=[experiment_name],
            order_by=["start_time DESC"],
            max_results=top_n,
        )

        if runs.empty:
            logger.warning(f"Nenhum run encontrado no experimento '{experiment_name}'")
            return []

        resultados = []
        for _, run in runs.iterrows():
            score = run.get("metrics.score_medio", 0.0)
            pct_atende = run.get("metrics.pct_atende", 0.0)

            status = "ATENDE" if score >= 0.75 else ("VERIFICAR" if score >= 0.45 else "NAO_ATENDE")
            resultados.append({
                "modelo": run.get("tags.mlflow.runName", run.get("run_id", "unknown")),
                "score_geral": float(score) if score else 0.0,
                "status_geral": status,
                "detalhes": [],
                "_run_id": run.get("run_id"),
                "_pct_atende": pct_atende,
            })

        logger.info(f"✓ {len(resultados)} runs carregados do MLflow ({experiment_name})")
        return resultados

    except Exception as e:
        logger.error(f"Erro ao conectar no MLflow: {e}")
        logger.info("Dica: verifique se o MLflow está rodando (make up) e MLFLOW_TRACKING_URI está correto")
        return []


def _carregar_de_arquivo(filepath: str) -> list[dict]:
    """Carrega resultados de um arquivo JSON (útil para testes offline)."""
    path = Path(filepath)
    if not path.exists():
        logger.error(f"Arquivo não encontrado: {filepath}")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    logger.info(f"✓ {len(data)} resultados carregados de {filepath}")
    return data


def _imprimir_relatorio(relatorio: dict) -> None:
    """Formata e imprime o relatório de saúde no terminal."""
    print("\n" + "=" * 60)
    print("  RELATÓRIO DE QUALIDADE — EDITAL MATCHING")
    print("=" * 60)

    dist = relatorio.get("distribuicao", {})
    if "erro" not in dist:
        saude = relatorio.get("saude_geral", 0)
        emoji = "🟢" if saude >= 80 else ("🟡" if saude >= 50 else "🔴")
        print(f"\n{emoji}  Saúde Geral: {saude}/100")
        print(f"\n📊 Distribuição de Scores:")
        print(f"   Total avaliado : {dist.get('total_produtos', 0)} produtos")
        print(f"   Média          : {dist.get('score_media', 0):.3f}")
        print(f"   Mediana        : {dist.get('score_mediana', 0):.3f}")
        print(f"   Desvio padrão  : {dist.get('desvio_padrao', 0):.3f}")
        print(f"   Mínimo / Máximo: {dist.get('score_minimo', 0):.3f} / {dist.get('score_maximo', 0):.3f}")
        print(f"   Zona incerteza : {dist.get('pct_zona_incerteza', 0):.1f}%")

        alertas = dist.get("alertas", [])
        if alertas:
            print(f"\n⚠️  Alertas ({len(alertas)}):")
            for a in alertas:
                print(f"   • {a}")
        else:
            print("\n✅  Nenhum alerta de qualidade")

    cob = relatorio.get("cobertura_requisitos", {})
    if "erro" not in cob:
        problemas = cob.get("requisitos_problematicos", [])
        if problemas:
            print(f"\n🔍 Requisitos com Cobertura Fraca (score médio < 0.50):")
            for p in problemas[:5]:
                print(f"   • {p['requisito']}: {p['score_medio']:.3f}")
            if len(problemas) > 5:
                print(f"   ... e mais {len(problemas) - 5} outros")
        else:
            print("\n✅  Todos os requisitos com boa cobertura")

    print("\n" + "=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Avalia a qualidade dos runs de matching via MLflow ou arquivo JSON"
    )
    parser.add_argument(
        "--experiment", default="edital_matching",
        help="Nome do experimento MLflow (default: edital_matching)"
    )
    parser.add_argument(
        "--top", type=int, default=50,
        help="Quantos runs recentes analisar (default: 50)"
    )
    parser.add_argument(
        "--results-file", default=None,
        help="Caminho para JSON de resultados (ignora MLflow)"
    )
    parser.add_argument(
        "--output", default=None,
        help="Salvar relatório em JSON (ex: --output relatorio.json)"
    )
    args = parser.parse_args()

    # ── Carrega dados ─────────────────────────────────────────────────────────
    if args.results_file:
        resultados = _carregar_de_arquivo(args.results_file)
    else:
        resultados = _carregar_runs_mlflow(args.experiment, args.top)

    if not resultados:
        logger.error("Nenhum resultado para avaliar. Abortando.")
        sys.exit(1)

    # ── Avalia ────────────────────────────────────────────────────────────────
    from app.mlops.evaluator import MatchingEvaluator
    evaluator = MatchingEvaluator()
    relatorio = evaluator.gerar_relatorio_completo(
        edital_id="avaliacao_batch",
        resultados=resultados,
    )

    # ── Exibe relatório ───────────────────────────────────────────────────────
    _imprimir_relatorio(relatorio)

    # ── Salva JSON (opcional) ─────────────────────────────────────────────────
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(relatorio, f, ensure_ascii=False, indent=2)
        logger.info(f"Relatório salvo em {args.output}")

    saude = relatorio.get("saude_geral", 0)
    sys.exit(0 if saude >= 60 else 1)


if __name__ == "__main__":
    main()
