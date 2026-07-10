"""
tests/unit/test_attribute_parsers.py
─────────────────────────────────────
Casos-limite de telecom que uma regex "pega o primeiro número" erra:
"24x 1G", "10/100/1000 Mbps", "100–240 VAC", "48 portas + 4 SFP",
"2 portas 10G SFP+", "PoE 370W".
"""

from app.services.attribute_parsers import (
    classify_field,
    compare_attribute,
    compare_product_specs,
    compare_products,
    compare_range,
    extract_number,
    parse_poe,
    parse_port_count,
    parse_speed_mbps,
    parse_temperature_range,
    parse_uplink,
    parse_voltage_range,
)


class TestClassifyField:
    def test_portas(self):
        assert classify_field("Portas RJ45") == "porta"

    def test_poe(self):
        assert classify_field("PoE") == "poe"

    def test_tensao(self):
        assert classify_field("Power Requirement / Tensão de Entrada") == "tensao"

    def test_temperatura(self):
        assert classify_field("Temperatura de Operação") == "temperatura"

    def test_velocidade(self):
        assert classify_field("Velocidade de Encaminhamento") == "velocidade"

    def test_uplink(self):
        assert classify_field("Uplink") == "uplink"

    def test_generic(self):
        assert classify_field("Camada") == "generic"


class TestParsePortCount:
    def test_nx_formato(self):
        assert parse_port_count("24x 1G") == 24
        assert parse_port_count("8x 1G") == 8

    def test_ignora_uplinks_apos_mais(self):
        assert parse_port_count("48 portas + 4 SFP") == 48

    def test_numero_puro(self):
        assert parse_port_count("16") == 16

    def test_n_portas(self):
        assert parse_port_count("24 portas") == 24


class TestParseSpeedMbps:
    def test_multi_velocidade_pega_maior(self):
        assert parse_speed_mbps("10/100/1000 Mbps") == 1000.0

    def test_notacao_g(self):
        assert parse_speed_mbps("24x 1G") == 1000.0
        assert parse_speed_mbps("10G") == 10000.0
        assert parse_speed_mbps("2 portas 10G SFP+") == 10000.0

    def test_mbps_simples(self):
        assert parse_speed_mbps("100 Mbps") == 100.0


class TestParsePoe:
    def test_bool(self):
        assert parse_poe(True) == {"has_poe": True, "budget_w": None}
        assert parse_poe(False) == {"has_poe": False, "budget_w": None}

    def test_com_orcamento(self):
        assert parse_poe("PoE 370W") == {"has_poe": True, "budget_w": 370.0}

    def test_sem_poe_string(self):
        assert parse_poe("Não")["has_poe"] is False


class TestParseRange:
    def test_faixa_en_dash(self):
        assert parse_voltage_range("100–240 VAC, 50/60 Hz") == (100.0, 240.0)

    def test_faixa_hifen_ascii(self):
        assert parse_voltage_range("100-240 VAC") == (100.0, 240.0)

    def test_valor_unico_vira_faixa_degenerada(self):
        assert parse_voltage_range("220 VAC") == (220.0, 220.0)

    def test_temperatura_negativa(self):
        assert parse_temperature_range("-10°C a 60°C") == (-10.0, 60.0)


class TestCompareRange:
    def test_cobre(self):
        assert compare_range((100.0, 240.0), (100.0, 100.0)) is True

    def test_nao_cobre(self):
        # bug antigo: "220 VAC" (ponto único) passava como >= 100 mesmo não
        # sendo bivolt; a comparação por faixa corrige isso.
        assert compare_range((220.0, 220.0), (100.0, 100.0)) is False


class TestParseUplink:
    def test_quantidade_e_velocidade(self):
        result = parse_uplink("2 portas 10G SFP+")
        assert result["quantidade"] == 2
        assert result["velocidade_mbps"] == 10000.0


class TestCompareAttribute:
    def test_portas_atende(self):
        result = compare_attribute("Portas RJ45", "24x 1G", "16")
        assert result.match is True

    def test_portas_nao_atende(self):
        result = compare_attribute("Portas RJ45", "8x 1G", "16")
        assert result.match is False

    def test_tensao_bivolt_atende(self):
        result = compare_attribute(
            "Power Requirement / Tensão de Entrada", "100–240 VAC, 50/60 Hz", "100"
        )
        assert result.match is True

    def test_tensao_nao_bivolt_nao_atende(self):
        result = compare_attribute("Power Requirement / Tensão de Entrada", "220 VAC", "100")
        assert result.match is False

    def test_generic_retorna_none(self):
        result = compare_attribute("Camada", "L3 Full", "L3")
        assert result.match is None


class TestCompareProducts:
    def test_mais_portas_vence(self):
        result = compare_products("Portas RJ45", "24x 1G", "8x 1G")
        assert result.winner == "a"

    def test_empate_portas(self):
        result = compare_products("Portas RJ45", "24 portas", "24x 1G")
        assert result.winner == "tie"

    def test_poe_presente_vence_ausente(self):
        result = compare_products("PoE", True, False)
        assert result.winner == "a"

    def test_poe_budget_maior_vence(self):
        result = compare_products("PoE", "PoE 370W", "PoE 120W")
        assert result.winner == "a"

    def test_faixa_tensao_mais_larga_vence(self):
        result = compare_products(
            "Power Requirement / Tensão de Entrada", "100–240 VAC", "220 VAC",
        )
        assert result.winner == "a"

    def test_campo_ausente_em_um_lado(self):
        result = compare_products("Portas RJ45", "24x 1G", None)
        assert result.winner == "a"

    def test_ambos_ausentes_empata(self):
        result = compare_products("Portas RJ45", None, "-")
        assert result.winner == "tie"

    def test_travessao_e_tratado_como_sem_dado(self):
        # catálogo usa "—" (em-dash), não só "-", pra sinalizar campo vazio
        result = compare_products("PoE", "—", True)
        assert result.winner == "b"

    def test_capacidade_negativa_nao_e_vantagem_sobre_branco(self):
        """
        "Uplinks": "—" (nosso, sem dado) vs "Não" (concorrente, resposta
        negativa real) — nenhum dos dois tem a capacidade, então não é
        vantagem de ninguém. Bug real encontrado testando a UI.
        """
        result = compare_products("Uplinks", "—", "Não")
        assert result.winner in (None, "tie")

    def test_poe_none_cru_e_tratado_como_sem_poe(self):
        # dict.get em campo que nem existe devolve None puro, não string
        result = compare_products("PoE", None, True)
        assert result.winner == "b"

    def test_quantitativo_ausente_favorece_quem_tem_dado(self):
        # portas/velocidade continuam favorecendo o lado com número real
        result = compare_products("Portas RJ45", None, "24x 1G")
        assert result.winner == "b"

    def test_texto_livre_igual_empata(self):
        result = compare_products("Camada", "L2", "L2")
        assert result.winner == "tie"

    def test_texto_livre_diferente_sem_vencedor(self):
        result = compare_products("Tipo de Gerenciamento", "Managed (CLI/Web)", "Unmanaged")
        assert result.winner is None


class TestCompareProductSpecs:
    def test_une_campos_dos_dois_lados(self):
        specs_a = {"Portas RJ45": "24x 1G", "PoE": True}
        specs_b = {"Portas RJ45": "8x 1G", "VLANs": "256"}
        results = compare_product_specs(specs_a, specs_b)
        fields = {r.field for r in results}
        assert fields == {"Portas RJ45", "PoE", "VLANs"}

        by_field = {r.field: r for r in results}
        assert by_field["Portas RJ45"].winner == "a"
        assert by_field["PoE"].winner == "a"  # so o produto A tem o campo
        assert by_field["VLANs"].winner == "b"


class TestExtractNumber:
    def test_compatibilidade_regressao(self):
        assert extract_number("24 portas") == 24.0
        assert extract_number("10Gbps") == 10.0
        assert extract_number("N/A") is None
