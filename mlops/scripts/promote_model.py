"""
Script de promoção de modelos no MLflow Model Registry.

CONCEITO MLOPS: Model Registry & Staging
  Antes de publicar uma versão do modelo em produção, você passa por etapas:
    None → Staging → Production → Archived

  Staging   = Homologação. Testa em ambiente parecido com prod, sem afetar usuários.
  Production = Em uso real. A API usa esta versão.
  Archived  = Aposentado. Mantido no histórico, não está em uso.

  Por que isso importa?
    - Rollback em 1 comando (promote v3 de volta para Production)
    - Rastreabilidade: quem promoveu, quando, qual run gerou
    - Zero downtime: promoção não reinicia a API

Como usar:
    # Listar versões disponíveis:
    PYTHONPATH=backend python mlops/scripts/promote_model.py --list

    # Promover para Staging (homologação):
    PYTHONPATH=backend python mlops/scripts/promote_model.py --model edital_matching --version 2 --stage Staging

    # Promover para Produção:
    PYTHONPATH=backend python mlops/scripts/promote_model.py --model edital_matching --version 2 --stage Production

    # Via Makefile:
    make promote MODEL=edital_matching VERSION=2 STAGE=Production

    # Promover o MELHOR run automaticamente:
    PYTHONPATH=backend python mlops/scripts/promote_model.py --auto-best --model edital_matching
"""

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s │ %(message)s")
logger = logging.getLogger(__name__)

VALID_STAGES = ["Staging", "Production", "Archived", "None"]


def _get_mlflow_client():
    import mlflow
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    mlflow.set_tracking_uri(tracking_uri)
    return mlflow.tracking.MlflowClient(), mlflow


def _listar_versoes(model_name: str) -> None:
    """Lista todas as versões de um modelo no registry."""
    client, _ = _get_mlflow_client()
    try:
        versoes = client.search_model_versions(f"name='{model_name}'")
    except Exception as e:
        logger.error(f"Erro ao listar versões: {e}")
        logger.info("Dica: verifique se o MLflow está rodando (make up)")
        sys.exit(1)

    if not versoes:
        print(f"\nNenhuma versão registrada para '{model_name}'")
        print("Execute o pipeline de matching para registrar modelos.")
        return

    print(f"\nVersões de '{model_name}' no Model Registry:")
    print("─" * 60)
    print(f"{'Versão':<8} {'Stage':<14} {'Run ID':<36} {'Status'}")
    print("─" * 60)
    for v in sorted(versoes, key=lambda x: int(x.version)):
        stage_emoji = {"Production": "🟢", "Staging": "🟡", "Archived": "⚫", "None": "⚪"}
        emoji = stage_emoji.get(v.current_stage, "⚪")
        print(f"{v.version:<8} {emoji} {v.current_stage:<12} {v.run_id:<36} {v.status}")
    print("─" * 60 + "\n")


def _promover_melhor_run(model_name: str, metric: str, stage: str) -> None:
    """Registra e promove o run com melhor score automaticamente."""
    from app.mlops.tracker import MatchingTracker

    tracker = MatchingTracker()
    melhor = tracker.get_best_run(metric_name=metric)

    if not melhor:
        logger.error("Nenhum run encontrado para promover.")
        sys.exit(1)

    run_id = melhor.get("run_id")
    score = melhor.get(f"metrics.{metric}", "N/A")
    logger.info(f"Melhor run encontrado: {run_id} | {metric}={score}")

    version = tracker.register_model(run_id=run_id, model_name=model_name)
    if not version:
        logger.error("Falha ao registrar modelo.")
        sys.exit(1)

    logger.info(f"Modelo registrado como versão {version}. Promovendo para {stage}...")
    success = tracker.promote_model(model_name, version, stage)

    if success:
        print(f"\n✅  {model_name} v{version} promovido para {stage}")
        print(f"   Run ID   : {run_id}")
        print(f"   {metric}: {score}\n")
    else:
        logger.error("Falha ao promover modelo.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Gerencia versões de modelos no MLflow Model Registry"
    )
    parser.add_argument("--model", default="edital_matching",
                        help="Nome do modelo no registry")
    parser.add_argument("--version", default=None,
                        help="Versão a promover (ex: '3')")
    parser.add_argument("--stage", default="Staging", choices=VALID_STAGES,
                        help="Stage destino (default: Staging)")
    parser.add_argument("--list", action="store_true",
                        help="Listar versões disponíveis")
    parser.add_argument("--auto-best", action="store_true",
                        help="Registra e promove o run com melhor score_medio")
    parser.add_argument("--metric", default="score_medio",
                        help="Métrica para --auto-best (default: score_medio)")
    args = parser.parse_args()

    if args.list:
        _listar_versoes(args.model)
        return

    if args.auto_best:
        _promover_melhor_run(args.model, args.metric, args.stage)
        return

    if not args.version:
        parser.error("Informe --version ou use --auto-best")

    from app.mlops.tracker import MatchingTracker
    tracker = MatchingTracker()
    success = tracker.promote_model(args.model, args.version, args.stage)

    if success:
        print(f"\n✅  {args.model} v{args.version} → {args.stage}\n")
    else:
        logger.error("Falha ao promover modelo.")
        sys.exit(1)


if __name__ == "__main__":
    main()
