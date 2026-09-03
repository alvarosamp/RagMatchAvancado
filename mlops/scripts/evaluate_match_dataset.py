"""Avalia um JSON exportado por GET /api/crm/matches/evaluation-dataset.

Uso:
    PYTHONPATH=backend python mlops/scripts/evaluate_match_dataset.py dataset.json
    PYTHONPATH=backend python mlops/scripts/evaluate_match_dataset.py dataset.json --json
    PYTHONPATH=backend python mlops/scripts/evaluate_match_dataset.py dataset.json --calibration --json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.match_eval_dataset import build_match_calibration_report, evaluate_retrieval_records


def main() -> int:
    parser = argparse.ArgumentParser(description="Avalia retrieval/ranking do Match V2 a partir do gold dataset do CRM.")
    parser.add_argument("dataset", type=Path, help="Arquivo JSON exportado pelo endpoint evaluation-dataset.")
    parser.add_argument("--calibration", action="store_true", help="Inclui recomendacao de peso semantico e thresholds.")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Imprime apenas JSON estruturado.")
    args = parser.parse_args()

    payload = json.loads(args.dataset.read_text(encoding="utf-8"))
    records = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise SystemExit("Dataset invalido: esperado objeto com 'records' ou uma lista de registros.")

    metrics = evaluate_retrieval_records(records)
    output = {
        "evaluation": metrics,
        "calibration": build_match_calibration_report(records) if args.calibration else None,
    }
    if args.as_json:
        print(json.dumps(output if args.calibration else metrics, ensure_ascii=False, indent=2))
        return 0

    print(f"Dataset: {payload.get('dataset_version', 'desconhecido') if isinstance(payload, dict) else 'lista'}")
    print(f"Registros rotulados: {metrics['labelled_records']}")
    print(f"Registros avaliados: {metrics['evaluated_records']}")
    print(f"Labels fora do ranking: {metrics['hidden_label_count']}")
    for k in (1, 3, 5, 10):
        print(f"Recall@{k}: {metrics[f'recall_at_{k}']:.4f}")
    print(f"MRR: {metrics['mrr']:.4f}")
    print(f"NDCG: {metrics['ndcg_at_all']:.4f}")
    if metrics["decision_metrics_available"]:
        print(f"Decisoes avaliadas: {metrics['decision_evaluated_records']}")
        print(f"Macro-F1: {metrics['macro_f1']:.4f}")
        print(f"False accept rate: {metrics['false_accept_rate']:.4f}")
    else:
        print(f"Metricas de decisao pendentes: {metrics['decision_metrics_blocker']}")
    if args.calibration:
        calibration = output["calibration"] or {}
        retrieval_best = (calibration.get("retrieval") or {}).get("best") or {}
        decision_best = (calibration.get("decision_thresholds") or {}).get("best") or {}
        print("Calibracao recomendada:")
        print(f"  CRM_MATCH_EMBEDDING_WEIGHT={retrieval_best.get('embedding_weight')}")
        print(f"  ML_THRESHOLD_ATENDE={decision_best.get('threshold_atende')}")
        print(f"  ML_THRESHOLD_VERIFICAR={decision_best.get('threshold_verificar')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
