from types import SimpleNamespace

from app.services.crm_item_matcher import (
    _attached_products_llm_row,
    flatten_attached_products_report_items,
)


def _product(source: str | None, outcome: str):
    notice = SimpleNamespace(
        id="notice-1",
        number="001/2026",
        tor_id="TOR-001",
        bid_number="001/2026",
        title="Edital de teste",
        organ=None,
        portal=None,
        municipality_name="Goiania",
        state="GO",
        modality="pregao",
        auction_date=None,
        estimated_value=None,
        stage=SimpleNamespace(value="result"),
        outcome=outcome,
        outcome_reason="Sem interesse comercial" if outcome == "not_pursued" else None,
        decision_recommendation=None,
        decision_score=None,
        bi_item_summary=None,
        bi_criterion=None,
        bi_exclusivity=None,
        bi_risk_identified=None,
        particularities=None,
    )
    catalog = SimpleNamespace(
        id="catalog-1",
        name="Switch de teste",
        description=None,
        category="switch",
        brand="TOR",
        model="S1",
        manufacturer_part_number="S1",
        sku="S1",
        specification="24 portas",
        keywords="switch 24 portas",
        unit="UN",
        cost=None,
        min_price=None,
        computed_min_price=None,
        tax_percent=None,
        margin_percent=None,
        notes=None,
        is_active=True,
    )
    return SimpleNamespace(
        id="item-1",
        notice=notice,
        notice_id=notice.id,
        catalog_product=catalog,
        catalog_product_id=catalog.id,
        catalog_match_source=source,
        catalog_match_confirmed_by=None,
        catalog_match_confirmed_at=None,
        catalog_match_model_version=None,
        catalog_lpu_version=None,
        catalog_match_notes=None,
        item_number="1",
        lot=None,
        product_code=None,
        description="Switch gerenciavel de 24 portas",
        quantity=1,
        unit="UN",
        warranty=None,
        delivery_deadline=None,
        category="Switch",
        technical_characteristics="24 portas",
        risk_associated=None,
        reference_price=None,
        reference_total_price=None,
        brand_direction_exists=False,
        brand_direction_model=None,
        brand_direction_type=None,
        brand_direction_justification=None,
        exclusive_epp_label=None,
        bi_features=None,
        raw_payload=None,
        notes=None,
        product_matches=[],
    )


def test_discarded_notice_is_kept_and_explicitly_marked_in_training_export():
    row = _attached_products_llm_row(_product("manual_confirmed", "not_pursued"))
    flat = flatten_attached_products_report_items({"items": [row]})[0]

    assert flat["notice_outcome"] == "not_pursued"
    assert flat["notice_is_discarded"] is True
    assert flat["training_label"] == "positive_confirmed"
    assert flat["training_use"] == "train_positive"
    assert flat["training_review_required"] is False


def test_unverified_attachment_requires_review_before_training():
    row = _attached_products_llm_row(_product(None, "pending"))
    flat = flatten_attached_products_report_items({"items": [row]})[0]

    assert flat["notice_is_discarded"] is False
    assert flat["training_label"] == "unverified_link"
    assert flat["training_use"] == "review_before_training"
    assert flat["training_review_required"] is True
