import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from app.services import crm_item_matcher
from app.services.technical_matching import compare_item_product


def switch_item():
    return {"categoria": "switch", "requisitos": {
        "portas_rj45": {"operador": ">=", "valor": 24},
        "poe_budget_w": {"operador": ">=", "valor": 370},
        "portas_sfp_plus": {"operador": ">=", "valor": 4},
    }}


def switch_product(**overrides):
    return {"sku": "SW-001", "categoria": "switch", "atributos": {
        "portas_rj45": 24, "poe_budget_w": 410, "portas_sfp_plus": 4, **overrides,
    }}


def test_switch_matches_and_exposes_evidence():
    result = compare_item_product(switch_item(), switch_product())
    assert result["status"] == "ATENDE"
    assert result["score"] == result["cobertura"] == result["compatibilidade_conhecida"] == 1
    assert len(result["detalhes"]) == 4  # category plus three requirements
    poe = result["detalhes"][2]
    assert poe["encontrado_normalizado"] == 410
    assert poe["exigido_normalizado"] == 370
    assert poe["fontes"] == [{"atributo": "poe_budget_w", "valor": 410}]
    json.dumps(result, allow_nan=False)


def test_mandatory_poe_failure_overrides_other_matches():
    result = compare_item_product(switch_item(), switch_product(poe_budget_w=180))
    assert result["status"] == "NAO_ATENDE"
    assert result["falhas_obrigatorias"] == ["poe_budget_w"]
    assert result["score"] == pytest.approx(2 / 3, abs=0.0001)


def test_missing_value_is_pending_and_does_not_inflate_score():
    result = compare_item_product(switch_item(), switch_product(poe_budget_w=None))
    assert result["status"] == "VERIFICAR"
    assert result["pendencias"] == ["poe_budget_w"]
    assert result["score"] == result["cobertura"] == 0.6667
    assert result["compatibilidade_conhecida"] == 1


def test_aliases_and_units_are_normalized():
    item = {"requisitos": {
        "poe_budget": {"operador": ">=", "valor": 0.37, "unidade": "kW"},
        "velocidade_uplink": {"operador": ">=", "valor": "1 Gbps"},
    }}
    product = {"atributos": {"orçamento PoE": "410 W", "uplink_speed_mbps": 1000}}
    result = compare_item_product(item, product)
    assert result["status"] == "ATENDE"
    assert result["detalhes"][0]["exigido_normalizado"] == 370
    assert result["detalhes"][1]["exigido_normalizado"] == 1000


def test_sfp_cannot_satisfy_sfp_plus():
    product = switch_product()
    del product["atributos"]["portas_sfp_plus"]
    product["atributos"]["Portas SFP"] = 4
    result = compare_item_product(switch_item(), product)
    assert result["status"] == "VERIFICAR"
    assert "portas_sfp_plus" in result["pendencias"]


@pytest.mark.parametrize("value", ["24x 1G", "24 ou 48", "-", True, float("nan"), float("inf"), "24 bananas", "24 Gbps", {}, []])
def test_ambiguous_or_invalid_port_counts_never_approve(value):
    assert compare_item_product(switch_item(), switch_product(portas_rj45=value))["status"] == "VERIFICAR"


@pytest.mark.parametrize("rule", [None, {}, {"valor": 24, "operador": "~"}, {"valor": 24, "operador": []},
                                  {"valor": 24, "peso": -1}, {"valor": 24, "peso": 0},
                                  {"valor": 24, "peso": True}, {"valor": 24, "peso": float("nan")},
                                  {"valor": 24, "obrigatorio": "false"}])
def test_invalid_rules_are_pending(rule):
    item = {"requisitos": {"portas_rj45": rule}}
    assert compare_item_product(item, switch_product())["status"] == "VERIFICAR"


@pytest.mark.parametrize("op,expected,status", [("==", 24, "ATENDE"), (">=", 24, "ATENDE"),
    ("<=", 24, "ATENDE"), (">", 24, "NAO_ATENDE"), ("<", 25, "ATENDE")])
def test_numeric_operators(op, expected, status):
    item = {"requisitos": {"portas_rj45": {"operador": op, "valor": expected}}}
    assert compare_item_product(item, switch_product())["status"] == status


@pytest.mark.parametrize("value,status", [("Sim", "ATENDE"), (True, "ATENDE"), ("Não", "NAO_ATENDE"), (False, "NAO_ATENDE"), (1, "VERIFICAR"), (None, "VERIFICAR")])
def test_boolean_comparison_is_strict(value, status):
    item = {"requisitos": {"gerenciavel": {"valor": True}}}
    assert compare_item_product(item, {"atributos": {"managed": value}})["status"] == status


def test_conflicting_aliases_require_review():
    result = compare_item_product(switch_item(), switch_product(poe_budget=180))
    assert result["status"] == "VERIFICAR"
    assert "conflitantes" in result["detalhes"][2]["motivo"]


def test_equivalent_aliases_can_be_compared():
    assert compare_item_product(switch_item(), switch_product(poe_budget="0.410 kW"))["status"] == "ATENDE"


@pytest.mark.parametrize("expected,found", [("L2+", "L2"), ("1.0", "1-0"), ("A/B", "A-B")])
def test_technical_text_punctuation_is_not_discarded(expected, found):
    result = compare_item_product({"requisitos": {"padrao": {"valor": expected}}}, {"atributos": {"padrao": found}})
    assert result["status"] == "NAO_ATENDE"


def test_optional_failure_reduces_weighted_score_without_rejecting():
    item = switch_item()
    item["requisitos"]["poe_budget_w"].update(obrigatorio=False, peso=2)
    result = compare_item_product(item, switch_product(poe_budget_w=180))
    assert result["status"] == "ATENDE"
    assert result["score"] == 0.5
    assert result["falhas_obrigatorias"] == []


def test_large_finite_weights_do_not_overflow_scores():
    item = switch_item()
    for rule in item["requisitos"].values():
        rule["peso"] = 1e308
    result = compare_item_product(item, switch_product())
    assert result["score"] == result["cobertura"] == 1
    json.dumps(result, allow_nan=False)


def test_category_conflict_rejects_and_missing_category_is_pending():
    assert compare_item_product(switch_item(), {**switch_product(), "categoria": "access point"})["status"] == "NAO_ATENDE"
    assert compare_item_product(switch_item(), {**switch_product(), "categoria": None})["status"] == "VERIFICAR"


@pytest.mark.parametrize("requirements", [None, {}, [], "invalid"])
def test_empty_or_invalid_requirements_never_approve(requirements):
    assert compare_item_product({"requisitos": requirements}, switch_product())["status"] == "VERIFICAR"


def catalog(name, attributes):
    return SimpleNamespace(id=name, name=name, sku=name, category="switch", specification=json.dumps({"atributos": attributes}))


def test_crm_structured_ranking_skips_ai_and_compares_before_preselection(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Structured matching must not invoke AI")
    monkeypatch.setattr(crm_item_matcher, "try_llm_rerank", forbidden)
    monkeypatch.setattr(crm_item_matcher, "_attach_semantic_scores", forbidden)
    monkeypatch.setattr(crm_item_matcher, "PRESELECT_LIMIT", 2)
    notice = SimpleNamespace(raw_payload=switch_item())
    rejected = catalog("rejected", switch_product(poe_budget_w=180)["atributos"])
    pending = catalog("pending", switch_product(poe_budget_w=None)["atributos"])
    accepted = catalog("accepted", switch_product()["atributos"])
    ranked = crm_item_matcher._rank_candidates(notice, [rejected, pending, accepted], embedding_cache={}, use_llm=True, use_embeddings=True)
    assert [c["catalog"].id for c in ranked] == ["accepted", "pending"]
    assert ranked[0]["score"].overall_score == 1
    assert ranked[0]["score"].semantic_score is None
    assert ranked[0]["score"].llm_score is None
    assert ranked[1]["score"].level != "strong"


def test_crm_rejected_candidate_is_explained_and_has_zero_summary_score():
    notice = SimpleNamespace(technical_characteristics=json.dumps(switch_item()))
    product = catalog("bad-poe", switch_product(poe_budget_w=180)["atributos"])
    score = crm_item_matcher._rank_candidates(notice, [product], embedding_cache={}, use_llm=False)[0]["score"]
    assert score.overall_score == 0
    assert score.level == "none"
    assert "poe_budget_w: NAO_ATENDE" in score.rationale
    assert "180" in score.conflicts[0]


def test_crm_text_only_catalog_requires_review_for_structured_item():
    product = SimpleNamespace(sku="text-only", category="switch", specification="24 RJ45, 410 W, 4 SFP+")
    ranked = crm_item_matcher._rank_candidates(SimpleNamespace(raw_payload=switch_item()), [product], embedding_cache={}, use_llm=True)
    assert ranked[0]["technical_match"]["status"] == "VERIFICAR"
    assert ranked[0]["score"].overall_score == 0


def test_crm_invalid_structured_requirements_do_not_fall_back_to_legacy():
    assert crm_item_matcher._structured_item(SimpleNamespace(raw_payload={"requisitos": None})) is not None
    assert crm_item_matcher._structured_item(SimpleNamespace(technical_characteristics="24 portas")) is None


def test_crm_run_persists_rejection_without_ai_reuse_or_auto_confirmation(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Structured requirements must be evaluated without AI or reuse")

    product = SimpleNamespace(
        id="item", raw_payload=switch_item(), product_matches=[],
        catalog_product_id="bad", reference_total_price=100,
    )
    notice = SimpleNamespace(id="notice", notice_products=[product])
    bad = catalog("bad", switch_product(poe_budget_w=180)["atributos"])
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [bad]
    match_model = MagicMock(side_effect=lambda **kwargs: SimpleNamespace(**kwargs))
    history_model = MagicMock(side_effect=lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(crm_item_matcher, "_load_notice", lambda *args: notice)
    monkeypatch.setattr(crm_item_matcher, "_build_reusable_match_index", lambda *args: {})
    monkeypatch.setattr(crm_item_matcher, "get_notice_item_match_payload", lambda *args: {})
    monkeypatch.setattr(crm_item_matcher, "_find_reusable_catalog_product", forbidden)
    monkeypatch.setattr(crm_item_matcher, "ensure_catalog_embeddings", forbidden)
    monkeypatch.setattr(crm_item_matcher, "ai_feature_enabled", lambda *args: True)
    monkeypatch.setattr(crm_item_matcher, "CrmCatalogProduct", MagicMock())
    monkeypatch.setattr(crm_item_matcher, "CrmNoticeProductMatch", match_model)
    monkeypatch.setattr(crm_item_matcher, "CrmNoticeHistory", history_model)

    crm_item_matcher.run_notice_item_match(db, SimpleNamespace(id=1, tenant_id=2), "notice")

    persisted = match_model.call_args.kwargs
    assert persisted["status"] == crm_item_matcher.CrmNoticeProductMatchStatus.SUGGESTED
    assert persisted["overall_score"] == 0
    assert "poe_budget_w: NAO_ATENDE" in persisted["rationale"]
    history = history_model.call_args.kwargs["details"]
    assert history["strong_items"] == 0
    assert history["embedding"] == {"status": "not_used", "reason": "deterministic_json"}
    assert product.catalog_product_id == "bad"
    db.commit.assert_called_once()
