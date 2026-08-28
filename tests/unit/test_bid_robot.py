import pytest

from app.services.bid_robot import BidLot, create_session, execute_authorized_bid, recommend_bid


def test_create_session_accepts_compras_gov_portal():
    session = create_session(
        tenant_id=1,
        portal="COMPRAS_GOV",
        process_number="90001/2026",
        entity="Ministerio da Gestao",
        dispute_at=None,
        mode="assistido",
        lots=[
            {
                "number": "1",
                "description": "Notebook",
                "quantity": 2,
                "unit_cost": 2500,
                "current_best_bid": 6000,
                "decrement": 10,
                "minimum_margin_percent": 8,
            }
        ],
    )

    assert session.portal == "COMPRAS_GOV"
    assert session.lots[0].number == "1"


def test_execute_authorized_bid_requires_authorized_mode(monkeypatch):
    monkeypatch.setenv("COMPRAS_GOV_BID_ADAPTER_URL", "mock://success")
    session = create_session(
        tenant_id=1,
        portal="COMPRAS_GOV",
        process_number="90001/2026",
        entity="Ministerio da Gestao",
        dispute_at=None,
        mode="assistido",
        lots=[
            {
                "number": "1",
                "description": "Notebook",
                "quantity": 2,
                "unit_cost": 2500,
                "current_best_bid": 6000,
                "decrement": 10,
                "minimum_margin_percent": 8,
            }
        ],
    )

    with pytest.raises(ValueError, match="modo autorizado"):
        execute_authorized_bid(session, session.lots[0].id)


def test_execute_authorized_bid_uses_configured_adapter(monkeypatch):
    monkeypatch.setenv("COMPRAS_GOV_BID_ADAPTER_URL", "mock://success")
    session = create_session(
        tenant_id=1,
        portal="COMPRAS_GOV",
        process_number="90001/2026",
        entity="Ministerio da Gestao",
        dispute_at=None,
        mode="autorizado",
        lots=[
            {
                "number": "1",
                "description": "Notebook",
                "quantity": 2,
                "unit_cost": 2500,
                "current_best_bid": 6000,
                "decrement": 10,
                "minimum_margin_percent": 8,
            }
        ],
    )

    updated = execute_authorized_bid(session, session.lots[0].id)

    assert updated.lots[0].last_confirmed_bid == 5990
    assert updated.lots[0].current_best_bid == 5990
    assert updated.events[0].type == "auto_bid_sent"


def test_recommend_bid_respects_decrement_and_margin_floor():
    lot = BidLot(
        id="lot-1",
        number="1",
        description="Switch",
        quantity=10,
        unit_cost=100,
        current_best_bid=1300,
        decrement=25,
        minimum_margin_percent=10,
    )

    recommendation = recommend_bid(lot)

    assert recommendation["can_bid"] is True
    assert recommendation["suggested_bid"] == 1275
    assert recommendation["floor_bid"] == 1100


def test_recommend_bid_stops_when_best_bid_is_below_margin_floor():
    lot = BidLot(
        id="lot-1",
        number="1",
        description="Switch",
        quantity=10,
        unit_cost=100,
        current_best_bid=1090,
        decrement=25,
        minimum_margin_percent=10,
    )

    recommendation = recommend_bid(lot)

    assert recommendation["can_bid"] is False
    assert recommendation["suggested_bid"] is None
