from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from app.integrations.conlicitacao.mapper import map_tender

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "conlicitacao" / "bulletin.json"


def test_mapper_normalizes_documented_bidding_payload():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))["licitacoes"][0]

    tender = map_tender(payload, base_url="https://provider.example.test")

    assert tender.provider == "conlicitacao"
    assert tender.external_id == "13157470"
    assert tender.title == "Edital PE/118/2020 - Prefeitura Municipal de Exemplo"
    assert tender.uasg == "987683"
    assert tender.public_body_state == "PR"
    assert tender.opening_at and tender.opening_at.isoformat() == "2020-11-26T08:30:00"
    assert tender.proposal_deadline_at
    assert tender.proposal_deadline_at.isoformat() == "2020-11-25T17:00:00"
    assert tender.estimated_value == Decimal("125000.50")
    assert tender.documents[0].url.startswith("https://provider.example.test/")
    assert tender.raw_payload["id"] == 13157470
