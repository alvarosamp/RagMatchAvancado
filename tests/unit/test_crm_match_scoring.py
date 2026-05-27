from app.services.crm_match_scoring import build_match_summary, combine_scores, lexical_similarity, normalize_text, score_to_level
from app.services.crm_item_matcher import build_product_reuse_signature


def test_normalize_text_removes_accents_and_symbols():
    assert normalize_text("Notebook Corporativo 14\" - São Paulo") == "notebook corporativo 14 sao paulo"


def test_lexical_similarity_rewards_overlap():
    strong = lexical_similarity("notebook corporativo i5 16gb ssd 512", "dell notebook corporativo i5 16gb com ssd 512")
    weak = lexical_similarity("mouse sem fio", "switch 24 portas gigabit")
    assert strong > 0.7
    assert weak < 0.3


def test_combine_scores_prefers_semantic_and_llm_signal():
    match = combine_scores(0.62, 0.84, 0.9)
    assert match.overall_score > 0.75
    assert match.source_method == "hybrid_llm"
    assert score_to_level(match.overall_score) in {"strong", "possible"}


def test_build_match_summary_reports_general_match():
    summary = build_match_summary(
        [
            {"best_score": 0.9, "reference_value": 1000.0},
            {"best_score": 0.74, "reference_value": 500.0},
            {"best_score": 0.2, "reference_value": 250.0},
        ],
        total_reference_value=1750.0,
    )
    assert summary["total_items"] == 3
    assert summary["strong_items"] == 1
    assert summary["possible_items"] == 1
    assert summary["unmatched_items"] == 1
    assert summary["label"] in {"Alta aderencia", "Aderencia parcial"}
    assert 0.0 <= summary["overall_score"] <= 1.0


def test_build_product_reuse_signature_ignores_case_and_accents():
    original = build_product_reuse_signature("Notebook Corporativo 14 Polegadas", "ABC-10")
    equivalent = build_product_reuse_signature("notebook corporativo 14 polegadas", "abc 10")
    different = build_product_reuse_signature("Mouse sem fio", "ABC-10")

    assert original == equivalent
    assert original != different
