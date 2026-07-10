"""
services/attribute_parsers.py
──────────────────────────────
Parsers e comparadores especializados por TIPO de atributo técnico
(portas, velocidade, PoE, tensão, temperatura, uplink).

Por que existir?
  Um regex genérico que "pega o primeiro número da string" quebra em casos
  reais de switches/telecom:
    "10/100/1000 Mbps"  → qual dos 3 números é a velocidade real? (é o maior)
    "100–240 VAC"        → é uma FAIXA, não um valor único
    "PoE 370W"           → é booleano (tem PoE) + orçamento, na mesma string
    "48 portas + 4 SFP"  → dois tipos de porta na mesma string
  Cada tipo de atributo tem uma forma própria de ser lido e comparado — não
  dá pra tratar tudo como "extrai o primeiro número e compara >=".

Usado por requirements_checker.py (comparação dict-based, retorna status) e
match_engine.py (score 0.0-1.0 via Requirement do banco) — os dois tinham
cada um sua própria cópia de `_extract_number`; agora leem daqui.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_NUM_RE = re.compile(r"-?\d+(?:[.,]\d+)?")
# Aceita unidade colada no primeiro número ("-10°C a 60°C", "100–240 VAC")
# entre o valor e o separador de faixa.
_RANGE_RE = re.compile(
    r"(-?\d+(?:[.,]\d+)?)\s*(?:°\s*)?[A-Za-zÀ-ÿ]{0,4}\s*(?:–|—|-|~|a|até|to)\s*(-?\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fallback genérico (compatível com o comportamento antigo)
# ─────────────────────────────────────────────────────────────────────────────

def extract_number(value) -> float | None:
    """Extrai o primeiro número (inteiro ou decimal) de um valor."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = _NUM_RE.search(str(value))
    return float(match.group().replace(",", ".")) if match else None


def extract_all_numbers(value) -> list[float]:
    """Extrai TODOS os números de uma string, na ordem em que aparecem."""
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    return [float(n.replace(",", ".")) for n in _NUM_RE.findall(str(value))]


# ─────────────────────────────────────────────────────────────────────────────
# Classificação do tipo de atributo pelo nome do campo
# ─────────────────────────────────────────────────────────────────────────────

def classify_field(field_name: str) -> str:
    """Infere o tipo de atributo a partir do nome do campo/requisito."""
    name = (field_name or "").lower()
    if "poe" in name:
        return "poe"
    if "tens" in name or "volt" in name or "vac" in name:
        return "tensao"
    if "temperat" in name:
        return "temperatura"
    if "uplink" in name:
        return "uplink"
    if "veloc" in name or "throughput" in name or "mbps" in name or "gbps" in name:
        return "velocidade"
    if "porta" in name or "rj45" in name or "rj-45" in name:
        return "porta"
    return "generic"


# ─────────────────────────────────────────────────────────────────────────────
# Parsers por tipo
# ─────────────────────────────────────────────────────────────────────────────

def parse_port_count(value) -> int | None:
    """
    "24x 1G" → 24 | "8x 1G" → 8 | "48 portas + 4 SFP" → 48 (uplinks à parte)
    "16" → 16
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value)

    m = re.match(r"\s*(\d+)\s*x\b", s, re.IGNORECASE)
    if m:
        return int(m.group(1))

    primary = s.split("+")[0]
    m = re.search(r"(\d+)\s*(?:portas?|p\b)", primary, re.IGNORECASE)
    if m:
        return int(m.group(1))

    n = extract_number(primary)
    return int(n) if n is not None else None


def parse_speed_mbps(value) -> float | None:
    """
    "10/100/1000 Mbps" → 1000.0 (o maior)  | "24x 1G" → 1000.0
    "10G"/"10Gbps" → 10000.0               | "100 Mbps" → 100.0
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).lower()

    slash = re.search(r"\d+(?:\s*/\s*\d+)+", s)
    if slash:
        nums = [float(n) for n in re.findall(r"\d+", slash.group())]
        base = max(nums)
        return base * 1000 if re.search(r"\bg(?:b(?:ps)?)?\b", s) else base

    m = re.search(r"(\d+(?:[.,]\d+)?)\s*g(?:b(?:ps)?)?\b", s)
    if m:
        return float(m.group(1).replace(",", ".")) * 1000

    m = re.search(r"(\d+(?:[.,]\d+)?)\s*m(?:b(?:ps)?)?\b", s)
    if m:
        return float(m.group(1).replace(",", "."))

    return extract_number(s)


def parse_poe(value) -> dict:
    """
    True/False → {"has_poe": bool, "budget_w": None}
    "PoE 370W" → {"has_poe": True, "budget_w": 370.0}
    """
    if isinstance(value, bool):
        return {"has_poe": value, "budget_w": None}
    s = str(value).strip()
    if not s or s.lower() in ("false", "não", "nao", "-", "0", "sem poe"):
        return {"has_poe": False, "budget_w": None}

    budget = None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*w\b", s, re.IGNORECASE)
    if m:
        budget = float(m.group(1).replace(",", "."))
    return {"has_poe": True, "budget_w": budget}


def _parse_range(value) -> tuple[float, float] | None:
    """Faixa min/max. Valor único vira faixa degenerada (v, v)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return (float(value), float(value))
    s = str(value)

    m = _RANGE_RE.search(s)
    if m:
        a = float(m.group(1).replace(",", "."))
        b = float(m.group(2).replace(",", "."))
        return (min(a, b), max(a, b))

    n = extract_number(s)
    return (n, n) if n is not None else None


def parse_voltage_range(value) -> tuple[float, float] | None:
    """"100–240 VAC" → (100.0, 240.0) | "220 VAC" → (220.0, 220.0)"""
    return _parse_range(value)


def parse_temperature_range(value) -> tuple[float, float] | None:
    """"-10°C a 60°C" → (-10.0, 60.0) | "0 a 50 °C" → (0.0, 50.0)"""
    return _parse_range(value)


def parse_uplink(value) -> dict:
    """"2 portas 10G SFP+" → {"quantidade": 2, "velocidade_mbps": 10000.0}"""
    if isinstance(value, bool):
        return {"quantidade": None, "velocidade_mbps": None}
    s = str(value)
    quantidade = parse_port_count(s)
    velocidade = parse_speed_mbps(s)
    return {"quantidade": quantidade, "velocidade_mbps": velocidade}


def compare_range(actual_range, required_range) -> bool | None:
    """A faixa real cobre a faixa exigida? (actual_min <= req_min e req_max <= actual_max)"""
    if actual_range is None or required_range is None:
        return None
    a_min, a_max = actual_range
    r_min, r_max = required_range
    return a_min <= r_min and r_max <= a_max


# ─────────────────────────────────────────────────────────────────────────────
# Comparador único, usado pelos dois callers
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ComparisonResult:
    match: bool | None   # None = inconclusivo (não deu para extrair/comparar)
    detail: str


def compare_attribute(field_name: str, actual, required) -> ComparisonResult:
    """
    Compara actual x required de acordo com o tipo de atributo (inferido pelo
    nome do campo via `classify_field`). Só trata os tipos especializados —
    para "generic", o caller deve seguir com sua própria lógica de fallback
    (número genérico >= ou substring).
    """
    kind = classify_field(field_name)

    if kind == "poe":
        act = parse_poe(actual)
        req = parse_poe(required) if isinstance(required, bool) else {
            "has_poe": True, "budget_w": extract_number(required) if not isinstance(required, bool) else None,
        }
        if not act["has_poe"]:
            return ComparisonResult(False, f"PoE nao presente (esperado: {required})")
        if req.get("budget_w") is not None:
            if act["budget_w"] is None:
                return ComparisonResult(None, "PoE presente mas orcamento (W) nao informado no catalogo")
            ok = act["budget_w"] >= req["budget_w"]
            return ComparisonResult(ok, f"PoE {act['budget_w']}W {'>=' if ok else '<'} {req['budget_w']}W (exigido)")
        return ComparisonResult(True, f"PoE presente: {actual}")

    if kind in ("tensao", "temperatura"):
        act_range = _parse_range(actual)
        req_range = _parse_range(required)
        ok = compare_range(act_range, req_range)
        if ok is None:
            return ComparisonResult(None, f"Nao foi possivel comparar faixas: '{actual}' x '{required}'")
        label = "cobre" if ok else "nao cobre"
        return ComparisonResult(ok, f"Faixa do produto {act_range} {label} a faixa exigida {req_range}")

    if kind == "porta":
        act_n = parse_port_count(actual)
        req_n = parse_port_count(required)
        if act_n is None or req_n is None:
            return ComparisonResult(None, f"Nao foi possivel extrair contagem de portas de '{actual}'/'{required}'")
        ok = act_n >= req_n
        return ComparisonResult(ok, f"{act_n} portas {'>=' if ok else '<'} {req_n} (exigido)")

    if kind == "velocidade":
        act_v = parse_speed_mbps(actual)
        req_v = parse_speed_mbps(required)
        if act_v is None or req_v is None:
            return ComparisonResult(None, f"Nao foi possivel extrair velocidade de '{actual}'/'{required}'")
        ok = act_v >= req_v
        return ComparisonResult(ok, f"{act_v}Mbps {'>=' if ok else '<'} {req_v}Mbps (exigido)")

    if kind == "uplink":
        act_u = parse_uplink(actual)
        req_u = parse_uplink(required)
        if act_u["quantidade"] is None or req_u["quantidade"] is None:
            return ComparisonResult(None, f"Nao foi possivel extrair uplink de '{actual}'/'{required}'")
        qty_ok = act_u["quantidade"] >= req_u["quantidade"]
        speed_ok = (
            act_u["velocidade_mbps"] is None
            or req_u["velocidade_mbps"] is None
            or act_u["velocidade_mbps"] >= req_u["velocidade_mbps"]
        )
        ok = qty_ok and speed_ok
        return ComparisonResult(ok, f"Uplink {act_u} x exigido {req_u}")

    return ComparisonResult(None, "generic")
