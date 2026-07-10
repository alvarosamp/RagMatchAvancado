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


class TestExtractNumber:
    def test_compatibilidade_regressao(self):
        assert extract_number("24 portas") == 24.0
        assert extract_number("10Gbps") == 10.0
        assert extract_number("N/A") is None
