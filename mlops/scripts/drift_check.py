"""
Script de detecção de drift nos scores de matching.

CONCEITO MLOPS: Drift Detection
  O modelo não muda — mas os DADOS mudam.
  Um edital de redes de 2024 tem requisitos diferentes de um de 2026.
  Se o sistema começa a errar mais, você precisa saber ANTES que o usuário reclame.

  Este script monitora duas coisas:
    1. Score Drift    → a média de scores está caindo ao longo do tempo?
    2. Feature Drift  → os editais estão pedindo coisas novas?

  Se detectar drift, retorna exit code 1 (útil para CI/CD alertas).

Como usar:
    # Via Makefile:
    make drift-check

    # Direto:
    PYTHONPATH=backend python mlops/scripts/drift_check.py
    PYTHONPATH=backend python mlops/scripts/drift_check.py --janela 15 --history /data/drift_history
    PYTHONPATH=backend python mlops/scripts/drift_check.py --report evidently  # gera HTML
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s │ %(message)s")
logger = logging.getLogger(__name__)


def _imprimir_resultado_drift(resultado: dict) -> bool:
    """Imprime o resultado e retorna True se drift foi detectado."""
    status = resultado.get("status", "desconhecido")
    drift = resultado.get("drift_detectado", False)

    print("\n" + "─" * 50)
    if status == "dados_insuficientes":
        print(f"⏳  {resultado.get('mensagem', 'Dados insuficientes')}")
        print("    Continue usando o sistema para acumular histórico.")
        return False

    emoji = "🔴" if drift else "🟢"
    print(f"{emoji}  Status: {status.upper()}")
    print(f"    Referência (passado) : {resultado.get('media_referencia', 0):.4f}")
    print(f"    Atual (recente)      : {resultado.get('media_atual', 0):.4f}")
    print(f"    Delta                : {resultado.get('delta', 0):.4f}")
    print(f"    Direção              : {resultado.get('direcao', 'N/A')}")

    if drift:
        print(f"\n    ⚠️  {resultado.get('alerta', '')}")
        print("\n    O que fazer:")
        print("      1. Revise os editais processados recentemente")
        print("      2. Compare prompts antigos vs novos no MLflow UI")
        print("      3. Considere re-treinar com dados mais recentes")
    else:
        print("\n    ✅  Scores dentro do esperado. Nenhuma ação necessária.")

    print("─" * 50 + "\n")
    return drift


def main():
    parser = argparse.ArgumentParser(
        description="Detecta drift nos scores de matching ao longo do tempo"
    )
    parser.add_argument(
        "--history", default="/data/drift_history",
        help="Caminho do histórico de drift (default: /data/drift_history)"
    )
    parser.add_argument(
        "--janela", type=int, default=10,
        help="Tamanho da janela de comparação em runs (default: 10)"
    )
    parser.add_argument(
        "--report", choices=["none", "evidently"], default="none",
        help="Gerar relatório HTML com Evidently (default: none)"
    )
    parser.add_argument(
        "--output-json", default=None,
        help="Salvar resultado em JSON (ex: drift_result.json)"
    )
    args = parser.parse_args()

    from app.mlops.drift_monitor import DriftMonitor
    monitor = DriftMonitor(storage_path=args.history)

    print("\n" + "=" * 50)
    print("  DETECÇÃO DE DRIFT — EDITAL MATCHING")
    print("=" * 50)

    # ── Analisa drift nos scores ──────────────────────────────────────────────
    print("\n📈 Análise de Score Drift:")
    resultado_scores = monitor.detectar_drift_scores(janela_runs=args.janela)
    drift_detectado = _imprimir_resultado_drift(resultado_scores)

    # ── Relatório Evidently (opcional) ────────────────────────────────────────
    if args.report == "evidently":
        print("📄 Gerando relatório HTML com Evidently...")
        output_path = monitor.gerar_relatorio_evidently()
        if output_path:
            print(f"   ✓ Relatório salvo em: {output_path}")
            print(f"   Abra no navegador para ver os gráficos.")
        else:
            print("   ⚠️  Não foi possível gerar (dados insuficientes ou Evidently não instalado)")

    # ── Salva JSON (para CI/CD ou dashboards) ─────────────────────────────────
    resultado_completo = {
        "score_drift": resultado_scores,
        "drift_detectado": drift_detectado,
    }

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(resultado_completo, f, ensure_ascii=False, indent=2)
        logger.info(f"Resultado salvo em {args.output_json}")

    # Exit code 1 se drift detectado — permite alertas em pipelines CI/CD
    sys.exit(1 if drift_detectado else 0)


if __name__ == "__main__":
    main()
