"""
tests/test_requirements.py
───────────────────────────
Testes unitários para o requirements_checker.
Usa as chaves REAIS do all_devices.json.
"""

import pytest
from app.services.requirements_checker import check_requirements


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def switch_que_atende():
    """Switch com specs que atendem todos os requisitos padrão."""
    return {
        "Portas RJ45":                          "24x 1G",      # 24 ≥ 16 ✅
        "Managed Web":                          True,           # gerenciável ✅
        "PoE":                                  True,           # PoE ✅
        "Power Requirement / Tensão de Entrada": "100–240 VAC, 50/60 Hz",  # bivolt ✅
        # campos extras do catálogo (não afetam o teste)
        "Tipo de Gerenciamento": "Managed (CLI/Web)",
        "Camada":                "L2/L2+",
        "PoE":                   True,
        "Portas PoE":            "24",
        "Budget PoE (W)":        "384",
    }

@pytest.fixture
def switch_que_nao_atende():
    """Switch com specs insuficientes."""
    return {
        "Portas RJ45":                          "8x 1G",       # 8 < 16 ❌
        "Managed Web":                          False,          # não gerenciável ❌
        "PoE":                                  False,          # sem PoE ❌
        "Power Requirement / Tensão de Entrada": "220 VAC",    # não bivolt ❌
    }


# ──────────────────────────────────────────────────────────────────────────────
# Testes — switch que ATENDE
# ──────────────────────────────────────────────────────────────────────────────

def test_portas_rj45_atende(switch_que_atende):
    result = check_requirements(switch_que_atende)
    assert result["Portas RJ45"]["status"] == "✅ Atende"

def test_managed_web_atende(switch_que_atende):
    result = check_requirements(switch_que_atende)
    assert result["Managed Web"]["status"] == "✅ Atende"

def test_poe_atende(switch_que_atende):
    result = check_requirements(switch_que_atende)
    assert result["PoE"]["status"] == "✅ Atende"

def test_bivolt_atende(switch_que_atende):
    result = check_requirements(switch_que_atende)
    assert result["Power Requirement / Tensão de Entrada"]["status"] == "✅ Atende"

def test_todos_requisitos_atendem(switch_que_atende):
    result = check_requirements(switch_que_atende)
    for field, res in result.items():
        assert res["status"] == "✅ Atende", f"Falhou em: {field} → {res}"


# ──────────────────────────────────────────────────────────────────────────────
# Testes — switch que NÃO ATENDE
# ──────────────────────────────────────────────────────────────────────────────

def test_portas_insuficientes(switch_que_nao_atende):
    result = check_requirements(switch_que_nao_atende)
    assert result["Portas RJ45"]["status"] == "❌ Não atende"

def test_sem_poe(switch_que_nao_atende):
    result = check_requirements(switch_que_nao_atende)
    assert result["PoE"]["status"] == "❌ Não atende"

def test_nao_gerenciavel(switch_que_nao_atende):
    result = check_requirements(switch_que_nao_atende)
    assert result["Managed Web"]["status"] == "❌ Não atende"


# ──────────────────────────────────────────────────────────────────────────────
# Testes — campos ausentes
# ──────────────────────────────────────────────────────────────────────────────

def test_campo_ausente_retorna_verificar():
    result = check_requirements({})  # specs vazias
    for field, res in result.items():
        assert res["status"] == "⚠️ Verificar", f"Esperado ⚠️ em '{field}'"


# ──────────────────────────────────────────────────────────────────────────────
# Testes — requisitos customizados
# ──────────────────────────────────────────────────────────────────────────────

def test_requisitos_customizados():
    """Permite passar requisitos diferentes dos padrão."""
    custom_reqs = {"Camada": "L3"}
    specs_ok    = {"Camada": "L3 Full"}
    specs_nok   = {"Camada": "L2"}

    assert check_requirements(specs_ok,  custom_reqs)["Camada"]["status"] == "✅ Atende"
    assert check_requirements(specs_nok, custom_reqs)["Camada"]["status"] == "❌ Não atende"