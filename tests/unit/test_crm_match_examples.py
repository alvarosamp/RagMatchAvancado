from types import SimpleNamespace
from unittest.mock import MagicMock
import sys

from app.services import crm_item_matcher
from app.services.crm_match_scoring import try_llm_rerank
from app.services.crm_match_scoring import _has_hard_category_conflict
from app.services.crm_match_examples import (
    ManualMatchExample, manual_examples_prompt, similar_manual_examples,
    summarize_manual_retrieval_trials,
)


def _example(notice, item, catalog, text):
    return ManualMatchExample(notice, item, catalog, text, f"Produto {catalog}")


def test_examples_exclude_same_notice_self_and_duplicate_manual_choices():
    examples = [
        _example("holdout", "item-2", "a", "switch 48 portas poe"),
        _example("other", "item-1", "a", "switch 48 portas poe"),
        _example("other", "item-3", "a", "switch 48 portas poe"),
        _example("another", "item-4", "a", "switch 48 portas poe"),
        _example("other", "item-5", "b", "mouse sem fio"),
    ]
    result = similar_manual_examples(
        "switch 48 portas poe", examples, notice_id="holdout", item_id="item-1"
    )
    assert list(result) == ["a"]
    assert len(result["a"]) == 1
    assert result["a"][0][1].item_id == "item-3"


def test_prompt_marks_human_choice_as_precedent_not_technical_proof():
    prompt = manual_examples_prompt([(1.0, _example("n", "i", "c", "switch " + "x" * 1000))])
    assert "nao prova de atendimento tecnico" in prompt
    assert "Nao copie a escolha humana automaticamente" in prompt
    assert len(prompt) < 900
    assert manual_examples_prompt([]) == ""


def test_retrieval_comparison_counts_top_k_and_has_no_fake_zero_on_empty_sample():
    trials = [
        ("a", ["b", "a"], ["a", "b"]),
        ("c", [], ["b", "c"]),
    ]
    report = summarize_manual_retrieval_trials(trials)
    assert report["baseline"]["top1_hits"] == 0
    assert report["baseline"]["top3_hits"] == 1
    assert report["with_manual_examples"]["top3_hits"] == 2
    assert report["with_manual_examples"]["recall_at_3"] == 1.0
    assert summarize_manual_retrieval_trials([])["baseline"]["recall_at_1"] is None


def test_manual_precedent_can_change_preselection_without_overriding_strong_score(monkeypatch):
    item = SimpleNamespace(
        id="current", notice_id="holdout", description="switch 48 portas poe 6 sfp",
        product_code=None, item_number=None, lot=None, notes=None,
        category=None, technical_characteristics=None,
    )
    stronger_lexical = SimpleNamespace(
        id="baseline", name="switch 48 portas poe sfp", brand=None, model=None,
        sku=None, specification=None, description=None, keywords=None, notes=None,
    )
    human_choice = SimpleNamespace(
        id="human", name="switch 48 portas poe", brand=None, model=None,
        sku=None, specification=None, description=None, keywords=None, notes=None,
    )
    monkeypatch.setattr(crm_item_matcher, "PRESELECT_LIMIT", 1)
    kwargs = dict(embedding_cache={}, use_llm=False, use_embeddings=False)
    baseline = crm_item_matcher._rank_candidates(item, [stronger_lexical, human_choice], **kwargs)
    assisted = crm_item_matcher._rank_candidates(
        item, [stronger_lexical, human_choice],
        manual_examples=[_example("other", "other-item", "human", "switch 48 portas poe 6 sfp")],
        **kwargs,
    )
    assert baseline[0]["catalog"].id == "baseline"
    assert assisted[0]["catalog"].id == "human"
    assert assisted[0]["score"].source_method == "lexical"
    assert assisted[0]["score"].conflicts == ()


def test_switch_with_sfp_uplinks_is_not_confused_with_transceiver():
    assert not _has_hard_category_conflict(
        "Switch 48 portas PoE 6 SFP+", "Switch gerenciavel 48 portas PoE"
    )
    assert _has_hard_category_conflict(
        "Switch 48 portas PoE 6 SFP+", "Transceiver optico SFP+ 10G SR"
    )


def test_llm_receives_bounded_manual_precedents_and_must_justify(monkeypatch):
    client = MagicMock()
    client.generate.return_value = {
        "response": '{"score":0.6,"level":"possible","rationale":"Verificar PoE",'
                    '"matched_features":["48 portas"],"conflicts":["PoE incerto"]}'
    }
    monkeypatch.setattr(sys.modules["ollama"], "Client", lambda **kwargs: client)
    precedent = manual_examples_prompt([(0.9, _example("old", "i", "c", "switch 48 portas"))])
    result = try_llm_rerank(
        notice_text="switch 48 portas poe", candidate_title="Switch C",
        candidate_text="switch 48 portas", manual_precedents=precedent,
    )
    prompt = client.generate.call_args.kwargs["prompt"]
    assert "CASOS SEMELHANTES ESCOLHIDOS POR PESSOAS" in prompt
    assert "Nao copie a escolha humana automaticamente" in prompt
    assert result["conflicts"] == ("PoE incerto",)


def test_read_only_evaluation_compares_same_label_without_provider(monkeypatch):
    item = SimpleNamespace(catalog_product_id="human", match_review_verdict=None)
    catalog = [SimpleNamespace(id="baseline"), SimpleNamespace(id="human")]
    product_model = SimpleNamespace(
        tenant_id=MagicMock(), catalog_match_source=MagicMock(),
        catalog_product_id=MagicMock(), catalog_match_confirmed_at=MagicMock(),
    )
    catalog_model = SimpleNamespace(tenant_id=MagicMock(), is_active=MagicMock())
    monkeypatch.setattr(crm_item_matcher, "CrmNoticeProduct", product_model)
    monkeypatch.setattr(crm_item_matcher, "CrmCatalogProduct", catalog_model)

    class Query:
        def __init__(self, rows):
            self.rows = rows

        def filter(self, *args):
            return self

        def order_by(self, *args):
            return self

        def limit(self, value):
            return self

        def all(self):
            return self.rows

    db = SimpleNamespace(query=lambda model: Query(
        [item] if model is product_model else catalog
    ))
    monkeypatch.setattr(crm_item_matcher, "_load_manual_examples", lambda *args: [
        _example("other", "old", "human", "switch 48 portas")
    ])
    calls = []

    def rank(product, candidates, *, manual_examples, use_llm, use_embeddings, **kwargs):
        calls.append((bool(manual_examples), use_llm, use_embeddings))
        ordered = candidates[::-1] if manual_examples else candidates
        return [{"catalog": candidate, "score": SimpleNamespace(overall_score=0.8)} for candidate in ordered]

    monkeypatch.setattr(crm_item_matcher, "_rank_candidates", rank)
    result = crm_item_matcher.evaluate_manual_example_retrieval(
        db, SimpleNamespace(tenant_id=1), limit=1
    )
    assert result["baseline"]["top1_hits"] == 0
    assert result["with_manual_examples"]["top1_hits"] == 1
    assert calls == [(False, False, False), (True, False, False)]


def test_exact_reuse_ignores_ambiguous_or_nonhuman_links():
    first = SimpleNamespace(id="a", is_active=True)
    second = SimpleNamespace(id="b", is_active=True)

    def match(catalog, source):
        return SimpleNamespace(
            catalog_product=catalog,
            notice_product=SimpleNamespace(
                description="switch 48 portas", product_code=None,
                catalog_match_source=source,
            ),
        )

    assert crm_item_matcher._index_reusable_matches([
        match(first, "manual_confirmed"), match(second, "manual_confirmed")
    ]) == {}
    assert crm_item_matcher._index_reusable_matches([
        match(first, None), match(first, "manual_confirmed")
    ]) == {"switch 48 portas": first}
