from datetime import datetime
from types import SimpleNamespace

from app.services.match_eval_dataset import (
    DATASET_VERSION,
    FIELD_MANIFEST,
    build_dataset_envelope,
    build_match_evaluation_record,
    evaluate_retrieval_records,
)


def _catalog(product_id: str, model: str):
    return SimpleNamespace(
        id=product_id,
        name=f"Produto {model}",
        description=f"Descricao {model}",
        category="switch",
        brand="TOR",
        model=model,
        manufacturer_part_number=model,
        sku=model,
        specification="24 portas PoE",
        keywords="switch poe",
        equivalent_skus=None,
        unit="UN",
    )


def _match(product_id: str, rank: int, score: float):
    return SimpleNamespace(
        catalog_product_id=product_id,
        catalog_product=_catalog(product_id, product_id.upper()),
        match_rank=rank,
        source_method="hybrid",
        status=SimpleNamespace(value="suggested"),
        match_level=SimpleNamespace(value="strong" if rank == 1 else "possible"),
        lexical_score=score - 0.1,
        semantic_score=score,
        llm_score=None,
        overall_score=score,
        rationale=None,
        matched_features=["24 portas"],
        conflicts=[],
    )


def _notice_product(label_id: str = "catalog-2"):
    notice = SimpleNamespace(
        title="Switch gerenciavel para rede corporativa",
        number="001/2026",
        modality="pregao",
        organ=SimpleNamespace(name="Orgao X"),
        portal=SimpleNamespace(name="PNCP"),
        outcome=SimpleNamespace(value="pending"),
        decision_recommendation="analisar",
    )
    return SimpleNamespace(
        id="item-1",
        notice_id="notice-1",
        notice=notice,
        item_number="1",
        lot="1",
        product_code="SW24",
        description="Switch gerenciavel com 24 portas PoE",
        category="switch",
        technical_characteristics="24 portas, PoE, 4 uplinks SFP",
        warranty="36 meses",
        delivery_deadline="30 dias",
        brand_direction_exists=False,
        brand_direction_model=None,
        brand_direction_type=None,
        brand_direction_justification=None,
        bi_features={"quantidade_portas": "24"},
        raw_payload={"descricao_original": "Switch 24P"},
        quantity=2,
        unit="UN",
        reference_price=1200.0,
        reference_total_price=2400.0,
        cost=700.0,
        unit_price=950.0,
        selected_for_dispute=True,
        catalog_product_id=label_id,
        catalog_product=_catalog(label_id, "S24P"),
        catalog_match_source="manual_confirmed",
        catalog_match_confirmed_at=datetime(2026, 8, 28, 12, 0, 0),
        catalog_match_confirmed_by=7,
        catalog_match_notes="Conferido no datasheet",
        catalog_match_model_version="hybrid-v1",
        product_matches=[
            _match("catalog-1", 1, 0.91),
            _match("catalog-2", 2, 0.84),
        ],
    )


def test_crm_fields_are_separated_between_features_labels_and_commercial_context():
    assert FIELD_MANIFEST["notice_product.description"] == {"role": "feature", "technical_match": True}
    assert FIELD_MANIFEST["notice_product.catalog_product_id"]["role"] == "retrieval_label"
    assert FIELD_MANIFEST["notice_product.selected_for_dispute"]["technical_match"] is False
    assert FIELD_MANIFEST["notice.outcome"]["technical_match"] is False


def test_record_keeps_crm_selection_as_label_without_leaking_it_into_technical_input():
    record = build_match_evaluation_record(_notice_product())

    assert record["label"]["catalog_product_id"] == "catalog-2"
    assert record["label"]["review_ready"] is True
    assert "catalog_product_id" not in str(record["technical_input"])
    assert "outcome" not in record["technical_input"]["notice"]
    assert record["commercial_context"]["notice"]["outcome"] == "pending"
    assert record["commercial_context"]["item"]["selected_for_dispute"] is True
    assert record["prediction_snapshot"]["label_rank"] == 2


def test_retrieval_metrics_use_the_human_selected_product_rank():
    records = [
        build_match_evaluation_record(_notice_product("catalog-2")),
        build_match_evaluation_record(_notice_product("catalog-1")),
    ]
    metrics = evaluate_retrieval_records(records)

    assert metrics["evaluated_records"] == 2
    assert metrics["recall_at_1"] == 0.5
    assert metrics["recall_at_3"] == 1.0
    assert metrics["mrr"] == 0.75
    assert metrics["decision_metrics_available"] is False


def test_dataset_envelope_is_versioned_and_reports_review_readiness():
    record = build_match_evaluation_record(_notice_product())
    dataset = build_dataset_envelope([record], limit=500)

    assert dataset["dataset_version"] == DATASET_VERSION
    assert dataset["summary"]["records"] == 1
    assert dataset["summary"]["review_ready_records"] == 1
    assert dataset["evaluation"]["recall_at_3"] == 1.0


def test_human_verdict_enables_false_accept_metrics():
    product = _notice_product("catalog-2")
    product.match_review_verdict = "NAO_ATENDE"
    product.match_review_confidence = 1.0
    product.match_review_reason_codes = ["temperatura"]
    product.match_review_evidence = [{"source": "datasheet", "page": 4}]
    product.match_review_notes = "Faixa de temperatura insuficiente."
    product.match_reviewed_by = 7
    product.match_reviewed_at = datetime(2026, 8, 29, 9, 0, 0)

    metrics = evaluate_retrieval_records([build_match_evaluation_record(product)])

    assert metrics["decision_metrics_available"] is True
    assert metrics["decision_evaluated_records"] == 1
    assert metrics["false_accept_count"] == 1
    assert metrics["false_accept_rate"] == 1.0
