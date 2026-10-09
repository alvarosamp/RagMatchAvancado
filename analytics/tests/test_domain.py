from decimal import Decimal

import pytest
from app.market_intelligence.domain import (
    coverage,
    gtin,
    number,
    payload_hash,
    technical_attributes,
    technical_conflicts,
    valid_cnpj,
)


@pytest.mark.parametrize("value", ["00.000.000/E08G-12", "00.000.000/0001-91"])
def test_numeric_and_alphanumeric_cnpj(value):
    assert valid_cnpj(value)


@pytest.mark.parametrize(
    "value", ["00000000000000", "00.000.000/E08G-11", "XYZ", "12345678000100"]
)
def test_invalid_identifiers_do_not_auto_match(value):
    assert not valid_cnpj(value)


def test_gtin_preserves_zeroes_and_validates_check_digit():
    assert gtin("7891000053508") == "07891000053508"
    assert gtin("7891000053509") is None


def test_missing_cost_is_unknown_and_money_is_decimal():
    assert number(None) is None
    assert number(0, positive=True) is None
    assert number("nan") is None
    assert number("0.1") + number("0.2") == Decimal("0.300000")


def test_link_and_rejected_selection_do_not_prove_catalogue_coverage():
    assert coverage(None, linked=True) == "pending_review"
    assert coverage("NAO_ATENDE", linked=True) == "rejected_selection"
    assert coverage("ATENDE", linked=True) == "covered"
    assert coverage(None) == "unassessed"


def test_numeric_constraints_include_source_evidence():
    attrs = technical_attributes("Switch 48 portas, 10 Gbps, garantia de 24 meses")
    assert attrs["ports"][0]["evidence"] == "48 portas"
    conflicts = technical_conflicts("48 portas 10 Gbps", "24 portas 1 Gbps")
    assert {c["attribute"] for c in conflicts} == {"ports", "speed_gbps"}


def test_payload_hash_is_stable_for_field_order():
    assert payload_hash({"a": 1, "b": 2}) == payload_hash({"b": 2, "a": 1})
