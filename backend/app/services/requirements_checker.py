"""
services/requirements_checker.py
──────────────────────────────────
Verifica se um switch do catálogo atende aos requisitos de um edital.

As chaves usadas aqui espelham EXATAMENTE as do all_devices.json:
  "Portas RJ45", "PoE", "Managed Web", etc.
"""

import re
from sqlalchemy.orm import Session

from app.db.models import Product
from app.logs.config import logger


# ──────────────────────────────────────────────────────────────────────────────
# Requisitos padrão (baseados no edital de exemplo)
# Chaves = campos do all_devices.json  |  Valores = exigência mínima
# ──────────────────────────────────────────────────────────────────────────────

REQUIREMENTS: dict[str, str | int | bool] = {
    "Portas RJ45":                      "16",          # mínimo 16 portas
    "Managed Web":                      True,          # deve ser gerenciável
    "PoE":                              True,          # deve ter PoE
    "Power Requirement / Tensão de Entrada": "100",   # bivolt (contém "100")
}


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _extract_number(value) -> float | None:
    """Extrai o primeiro número inteiro ou decimal de uma string."""
    if isinstance(value, (int, float)):
        return float(value)
    m = re.search(r"[\d]+(?:[.,]\d+)?", str(value))
    return float(m.group().replace(",", ".")) if m else None


def _check_field(actual, requirement) -> dict:
    """
    Compara um valor do catálogo com o requisito do edital.
    Retorna dict com 'status' e 'details'.
    """
    # ── Booleano ──────────────────────────────────────────────────────────────
    if isinstance(requirement, bool):
        ok = bool(actual) == requirement if not isinstance(actual, bool) else actual == requirement
        if isinstance(actual, str):
            ok = actual.strip().lower() not in ("false", "não", "nao", "-", "")
        return (
            {"status": "✅ Atende",    "details": f"Valor: {actual}"}
            if ok else
            {"status": "❌ Não atende", "details": f"Esperado: {requirement}, encontrado: {actual}"}
        )

    # ── Numérico ──────────────────────────────────────────────────────────────
    req_num = _extract_number(requirement)
    act_num = _extract_number(actual)
    if req_num is not None and act_num is not None:
        if act_num >= req_num:
            return {"status": "✅ Atende",    "details": f"{act_num} ≥ {req_num} (exigido)"}
        else:
            return {"status": "❌ Não atende", "details": f"{act_num} < {req_num} (exigido)"}

    # ── Texto (substring) ─────────────────────────────────────────────────────
    req_str = str(requirement).strip().lower()
    act_str = str(actual).strip().lower()
    if req_str in act_str:
        return {"status": "✅ Atende",    "details": f"'{requirement}' encontrado em '{actual}'"}

    return {"status": "❌ Não atende", "details": f"'{actual}' ≠ '{requirement}'"}


# ──────────────────────────────────────────────────────────────────────────────
# Função principal
# ──────────────────────────────────────────────────────────────────────────────

def check_requirements(
    switch_specs: dict,
    requirements: dict | None = None,
) -> dict:
    """
    Compara as especificações de um switch com os requisitos do edital.

    Args:
        switch_specs:  dict com specs do switch (campos do all_devices.json)
        requirements:  dict de requisitos customizados (usa REQUIREMENTS se None)

    Returns:
        dict { campo: {"status": "✅/❌/⚠️", "details": "..."} }
    """
    reqs   = requirements or REQUIREMENTS
    result = {}

    for field, requirement in reqs.items():
        if field not in switch_specs:
            result[field] = {
                "status":  "⚠️ Verificar",
                "details": f"Campo '{field}' não encontrado no catálogo",
            }
            continue

        actual = switch_specs[field]

        # Campo ausente ou vazio
        if actual in (None, "-", "", False) and requirement is True:
            result[field] = {
                "status":  "❌ Não atende",
                "details": f"Campo '{field}' não preenchido ou falso",
            }
            continue

        result[field] = _check_field(actual, requirement)

    logger.info(f"[RequirementsChecker] Resultado: {result}")
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Verificação em lote (banco de dados)
# ──────────────────────────────────────────────────────────────────────────────

def verify_switch_requirements(db: Session, requirements: dict | None = None) -> dict:
    """
    Verifica todos os switches do banco contra os requisitos.
    Útil para rodar via script ou endpoint de auditoria.
    """
    switches = db.query(Product).filter(Product.category == "switch").all()

    results = []
    for switch in switches:
        verification = check_requirements(switch.data, requirements)
        results.append({"model": switch.model, "verification": verification})
        logger.info(f"[RequirementsChecker] {switch.model}: {verification}")

    return {
        "message":           "Verificação completa",
        "switches_verified": len(switches),
        "results":           results,
    }