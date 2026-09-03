from __future__ import annotations

import json
import math
import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable

from app.core.ml_config import get_ml_config
from app.logs.config import logger

STOPWORDS = {
    "a", "ao", "aos", "as", "com", "da", "das", "de", "do", "dos", "e", "em", "na", "nas", "no", "nos",
    "o", "os", "ou", "para", "por", "um", "uma", "uns", "umas", "the", "of", "for", "and", "item", "lote",
}

DEFAULT_EMBEDDING_WEIGHT = float(os.environ.get("CRM_MATCH_EMBEDDING_WEIGHT", "0.55"))
DEFAULT_LEXICAL_WEIGHT = 1.0 - DEFAULT_EMBEDDING_WEIGHT
LLM_MODEL = os.environ.get("CRM_MATCH_LLM_MODEL", "llama3.2:1b")
_ML_CONFIG = get_ml_config()
THRESHOLD_ATENDE = _ML_CONFIG.threshold_atende
THRESHOLD_VERIFICAR = _ML_CONFIG.threshold_verificar
THRESHOLD_POSSIBLE = THRESHOLD_VERIFICAR + ((THRESHOLD_ATENDE - THRESHOLD_VERIFICAR) / 2)


@dataclass(frozen=True)
class MatchScore:
    lexical_score: float
    semantic_score: float | None
    llm_score: float | None
    overall_score: float
    level: str
    source_method: str
    rationale: str | None = None
    matched_features: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()


@dataclass(frozen=True)
class TechnicalScore:
    score: float
    matched_features: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def tokenize_text(value: str | None) -> list[str]:
    normalized = normalize_text(value)
    if not normalized:
        return []
    tokens = [token for token in normalized.split(" ") if token and token not in STOPWORDS]
    return tokens


def lexical_similarity(source: str | None, candidate: str | None) -> float:
    source_tokens = tokenize_text(source)
    candidate_tokens = tokenize_text(candidate)
    if not source_tokens or not candidate_tokens:
        return 0.0

    source_set = set(source_tokens)
    candidate_set = set(candidate_tokens)
    overlap = source_set & candidate_set
    coverage = len(overlap) / len(source_set)
    precision = len(overlap) / len(candidate_set)
    jaccard = len(overlap) / len(source_set | candidate_set)

    substring_bonus = 0.0
    source_normalized = " ".join(source_tokens)
    candidate_normalized = " ".join(candidate_tokens)
    if source_normalized and source_normalized in candidate_normalized:
        substring_bonus = 0.15
    elif candidate_normalized and candidate_normalized in source_normalized:
        substring_bonus = 0.10

    numeric_overlap = _numeric_overlap_score(source_set, candidate_set)
    raw = (coverage * 0.45) + (precision * 0.2) + (jaccard * 0.2) + (numeric_overlap * 0.15) + substring_bonus
    return max(0.0, min(1.0, raw))


def cosine_similarity(a: Iterable[float], b: Iterable[float]) -> float:
    a_list = list(a)
    b_list = list(b)
    if not a_list or not b_list or len(a_list) != len(b_list):
        return 0.0
    dot = sum(x * y for x, y in zip(a_list, b_list))
    norm_a = math.sqrt(sum(x * x for x in a_list))
    norm_b = math.sqrt(sum(y * y for y in b_list))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    cosine = dot / (norm_a * norm_b)
    return max(0.0, min(1.0, (cosine + 1) / 2))


def combine_scores(lexical_score: float, semantic_score: float | None, llm_score: float | None) -> MatchScore:
    method = "lexical"
    base_score = lexical_score

    if semantic_score is not None:
        method = "hybrid"
        base_score = (lexical_score * DEFAULT_LEXICAL_WEIGHT) + (semantic_score * DEFAULT_EMBEDDING_WEIGHT)

    if llm_score is not None:
        method = "hybrid_llm"
        overall_score = (base_score * 0.65) + (llm_score * 0.35)
    else:
        overall_score = base_score

    overall_score = max(0.0, min(1.0, overall_score))
    return MatchScore(
        lexical_score=round(lexical_score, 4),
        semantic_score=round(semantic_score, 4) if semantic_score is not None else None,
        llm_score=round(llm_score, 4) if llm_score is not None else None,
        overall_score=round(overall_score, 4),
        level=score_to_level(overall_score),
        source_method=method,
    )


def score_to_level(score: float) -> str:
    if score >= THRESHOLD_ATENDE:
        return "strong"
    if score >= THRESHOLD_POSSIBLE:
        return "possible"
    if score >= THRESHOLD_VERIFICAR:
        return "weak"
    return "none"


def build_match_summary(best_scores: list[dict[str, Any]], total_reference_value: float) -> dict[str, Any]:
    total_items = len(best_scores)
    strong_items = sum(1 for item in best_scores if item["best_score"] >= THRESHOLD_ATENDE)
    possible_items = sum(1 for item in best_scores if THRESHOLD_POSSIBLE <= item["best_score"] < THRESHOLD_ATENDE)
    weak_items = sum(1 for item in best_scores if THRESHOLD_VERIFICAR <= item["best_score"] < THRESHOLD_POSSIBLE)
    unmatched_items = sum(1 for item in best_scores if item["best_score"] < THRESHOLD_VERIFICAR)

    covered_reference_value = sum(
        float(item.get("reference_value") or 0.0)
        for item in best_scores
        if item["best_score"] >= THRESHOLD_POSSIBLE
    )
    weighted_denominator = total_reference_value or float(total_items or 1)
    weighted_numerator = covered_reference_value or float(strong_items + possible_items)
    coverage_ratio = weighted_numerator / weighted_denominator if weighted_denominator else 0.0

    if total_reference_value > 0:
        weighted_scores = sum(item["best_score"] * float(item.get("reference_value") or 0.0) for item in best_scores)
        score_denominator = total_reference_value
    else:
        weighted_scores = sum(item["best_score"] for item in best_scores)
        score_denominator = float(total_items or 1)
    overall_score = weighted_scores / score_denominator if score_denominator else 0.0

    if overall_score >= 0.78 and coverage_ratio >= 0.7:
        label = "Alta aderencia"
    elif overall_score >= 0.55 or coverage_ratio >= 0.4:
        label = "Aderencia parcial"
    else:
        label = "Baixa aderencia"

    return {
        "total_items": total_items,
        "strong_items": strong_items,
        "possible_items": possible_items,
        "weak_items": weak_items,
        "unmatched_items": unmatched_items,
        "coverage_ratio": round(coverage_ratio, 4),
        "overall_score": round(overall_score, 4),
        "label": label,
        "covered_reference_value": round(covered_reference_value, 2),
        "total_reference_value": round(total_reference_value, 2),
    }


def try_llm_rerank(*, notice_text: str, candidate_title: str, candidate_text: str) -> dict[str, Any] | None:
    if os.environ.get("CRM_MATCH_USE_LLM", "1") in {"0", "false", "False"}:
        return None
    if _has_hard_category_conflict(notice_text, candidate_text):
        return {
            "score": 0.0,
            "level": "none",
            "rationale": "Familia tecnica incompativel entre item do edital e produto do catalogo.",
            "matched_features": (),
            "conflicts": ("Familia tecnica incompativel entre item do edital e produto do catalogo.",),
        }
    try:
        import ollama

        client = ollama.Client(host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
        prompt = f"""
Voce esta avaliando se um item de edital combina com um produto do catalogo da empresa.
Considere compatibilidade tecnica, uso esperado, marca/modelo quando houver e especificacoes relevantes.
Responda SOMENTE JSON valido:
{{
  "score": 0.0,
  "level": "strong|possible|weak|none",
  "rationale": "motivo curto em portugues",
  "matched_features": ["..."],
  "conflicts": ["..."]
}}

ITEM DO EDITAL:
{notice_text}

PRODUTO DO CATALOGO:
Titulo: {candidate_title}
Detalhes: {candidate_text}
""".strip()
        response = client.generate(model=LLM_MODEL, prompt=prompt, options={"temperature": 0.0})
        raw = response.get("response") if isinstance(response, dict) else getattr(response, "response", "")
        if not raw:
            return None
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        payload = _parse_llm_json(match.group(0) if match else raw)
        if payload is None:
            logger.warning("[CRM Match] LLM retornou JSON invalido para rerank: %s", raw[:300])
            return None
        score = float(payload.get("score", 0.0) or 0.0)
        conflicts = tuple(payload.get("conflicts") or ())
        return {
            "score": max(0.0, min(1.0, score)),
            "level": payload.get("level") or score_to_level(score),
            "rationale": payload.get("rationale"),
            "matched_features": tuple(payload.get("matched_features") or ()),
            "conflicts": conflicts,
        }
    except Exception as exc:
        logger.warning("[CRM Match] LLM local indisponivel para rerank: %s", exc)
        return None


def _parse_llm_json(raw: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    try:
        parsed = json.loads(re.sub(r",\s*([}\]])", r"\1", raw))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def technical_compatibility_score(notice_text: str | None, candidate_text: str | None) -> TechnicalScore | None:
    notice = normalize_text(notice_text)
    candidate = normalize_text(candidate_text)
    if not notice or not candidate:
        return None
    if _has_hard_category_conflict(notice, candidate):
        return TechnicalScore(0.0, conflicts=("Familia tecnica incompativel entre item do edital e produto do catalogo.",))

    notice_optical = _is_optical_text(notice)
    candidate_optical = _is_optical_text(candidate)
    if notice_optical and candidate_optical:
        return _optical_technical_score(notice, candidate)
    return None


def _numeric_overlap_score(source_tokens: set[str], candidate_tokens: set[str]) -> float:
    source_numbers = {token for token in source_tokens if any(ch.isdigit() for ch in token)}
    candidate_numbers = {token for token in candidate_tokens if any(ch.isdigit() for ch in token)}
    if not source_numbers or not candidate_numbers:
        return 0.0
    overlap = source_numbers & candidate_numbers
    return len(overlap) / max(len(source_numbers), 1)


def _optical_technical_score(notice: str, candidate: str) -> TechnicalScore:
    matched: list[str] = []
    conflicts: list[str] = []
    score = 0.45
    weight = 0.45

    req_speed = _extract_speed_gbps(notice)
    cand_speed = _extract_speed_gbps(candidate)
    if req_speed is not None:
        weight += 0.25
        if cand_speed is not None and cand_speed + 0.05 >= req_speed:
            score += 0.25
            matched.append(f"velocidade {cand_speed:g}Gbps >= {req_speed:g}Gbps")
        elif cand_speed is not None:
            conflicts.append(f"velocidade {cand_speed:g}Gbps < {req_speed:g}Gbps")

    req_medium = _extract_optical_medium(notice)
    cand_medium = _extract_optical_medium(candidate)
    if req_medium:
        weight += 0.15
        if cand_medium == req_medium:
            score += 0.15
            matched.append(f"meio {cand_medium}")
        elif cand_medium:
            conflicts.append(f"meio {cand_medium} diferente de {req_medium}")

    req_reach = _extract_reach_km(notice)
    cand_reach = _extract_reach_km(candidate)
    if req_reach is not None:
        weight += 0.15
        if cand_reach is not None and cand_reach + 0.001 >= req_reach:
            score += 0.15
            matched.append(f"alcance {cand_reach:g}km >= {req_reach:g}km")
        elif cand_reach is not None:
            conflicts.append(f"alcance {cand_reach:g}km < {req_reach:g}km")

    req_form = _extract_optical_form(notice)
    cand_form = _extract_optical_form(candidate)
    if req_form:
        weight += 0.10
        if cand_form == req_form or (req_form == "sfp+" and cand_form == "sfp"):
            score += 0.10
            matched.append(f"formato {cand_form}")
        elif cand_form:
            conflicts.append(f"formato {cand_form} diferente de {req_form}")

    normalized_score = score / weight if weight else 0.0
    if conflicts:
        normalized_score = min(normalized_score, 0.62)
    return TechnicalScore(round(max(0.0, min(1.0, normalized_score)), 4), tuple(matched), tuple(conflicts))


def _is_optical_text(text: str) -> bool:
    return any(term in text for term in ("sfp", "transceiver", "transceptor", "fibra", "monomodo", "multimodo"))


def _extract_speed_gbps(text: str) -> float | None:
    if match := re.search(r"(\d+)\s+(\d+)\s*(?:g|gb|gbps|gigabit|gigabits|ge)\b", text):
        return float(f"{match.group(1)}.{match.group(2)}")
    if match := re.search(r"(\d+(?:[.,]\d+)?)\s*(?:g|gb|gbps|gigabit|gigabits|ge)\b", text):
        return float(match.group(1).replace(",", "."))
    if match := re.search(r"(\d+)\s+(\d+)\s*(?:m|mb|mbps)\b", text):
        return float(f"{match.group(1)}.{match.group(2)}") / 1000.0
    if match := re.search(r"(\d+(?:[.,]\d+)?)\s*(?:m|mb|mbps)\b", text):
        return float(match.group(1).replace(",", ".")) / 1000.0
    if "10gbase" in text:
        return 10.0
    if "1000base" in text or "1gbase" in text:
        return 1.0
    return None


def _extract_reach_km(text: str) -> float | None:
    values: list[float] = []
    for whole, decimal, unit in re.findall(r"(\d+)\s+(\d+)\s*(km|m)\b", text):
        number = float(f"{whole}.{decimal}")
        values.append(number if unit == "km" else number / 1000.0)
    for value, unit in re.findall(r"(\d+(?:[.,]\d+)?)\s*(km|m)\b", text):
        number = float(value.replace(",", "."))
        values.append(number if unit == "km" else number / 1000.0)
    return max(values) if values else None


def _extract_optical_medium(text: str) -> str | None:
    if any(term in text for term in ("monomodo", "single mode", "smf", "1310", "1550", "1270", "1330")):
        return "monomodo"
    if any(term in text for term in ("multimodo", "multi modo", "multi mode", "mmf", "sr", "850", "om3", "om4")):
        return "multimodo"
    if "rj45" in text or "10gbase t" in text or "1000base t" in text:
        return "rj45"
    return None


def _extract_optical_form(text: str) -> str | None:
    if "sfp28" in text:
        return "sfp28"
    if "sfp+" in text or "sfp plus" in text:
        return "sfp+"
    if "sfp" in text:
        return "sfp"
    if "qsfp28" in text:
        return "qsfp28"
    return None


def _has_hard_category_conflict(notice_text: str | None, candidate_text: str | None) -> bool:
    notice = normalize_text(notice_text)
    candidate = normalize_text(candidate_text)
    if not notice or not candidate:
        return False

    notice_is_ap = any(term in notice for term in ("access point", "wifi", "wi fi", "802 11", "ruckus r650"))
    candidate_is_optical = any(term in candidate for term in ("sfp", "transceiver", "transceptor", "fibra", "monomodo", "multimodo"))
    if notice_is_ap and candidate_is_optical:
        return True

    notice_is_optical = any(term in notice for term in ("sfp", "transceiver", "transceptor", "fibra", "monomodo", "multimodo"))
    candidate_is_ap = any(term in candidate for term in ("access point", "wifi", "wi fi", "802 11", "ruckus r650"))
    if notice_is_optical and candidate_is_ap:
        return True

    notice_is_switch_device = _is_switch_device_text(notice, candidate_is_optical=False)
    candidate_is_switch_device = _is_switch_device_text(candidate, candidate_is_optical=candidate_is_optical)
    if notice_is_switch_device and candidate_is_optical:
        return True
    return notice_is_optical and candidate_is_switch_device


def _is_switch_device_text(text: str, *, candidate_is_optical: bool) -> bool:
    if candidate_is_optical:
        return False
    has_switch_word = "switch" in text
    has_switch_features = any(
        term in text
        for term in ("portas", "porta rj", "rj45", "vlan", "poe", "layer", "gerenciavel", "nway")
    )
    return has_switch_word and has_switch_features
