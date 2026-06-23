from __future__ import annotations

from types import SimpleNamespace

from app.services.edital_analysis import build_analysis_payload, extract_items_from_edital_text


def test_extract_items_from_edital_text_parses_switch_item() -> None:
    text = """
    1 - Switch Descrição Detalhada: Switch Quantidade Portas: 48UN,
    Tipo Portas: Gigabit Ethernet, Suporte Vlan: IEEE 802.1Q,
    Características Adicionais: Gerenciável, SNMP, 4 portas SFP.
    """

    items = extract_items_from_edital_text(text)

    assert len(items) == 1
    assert items[0].numero_item == "1"
    assert items[0].tipo == "switch"
    assert items[0].quantidade == 48
    assert "VLAN" in (items[0].especificacoes or [])
    assert "gerenciavel" in (items[0].especificacoes or [])


def test_build_analysis_payload_is_frontend_compatible() -> None:
    edital = SimpleNamespace(
        id=10,
        full_text="1 - Switch Descrição Detalhada: Switch 24 portas gigabit.",
    )

    payload = build_analysis_payload(edital)

    assert payload["id_pncp"] == "10"
    assert payload["itens"][0]["numero_item"] == "1"
    assert payload["itens"][0]["tipo"] == "switch"
    assert "aviso" in payload

