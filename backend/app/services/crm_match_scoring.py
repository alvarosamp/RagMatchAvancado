from __future__ import annotations

import json
import math
import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable

from app.logs.config import logger

STOPWORDS = {
    "a", "ao", "aos", "as", "com", "da", "das", "de", "do", "dos", "e", "em", "na", "nas", "no", "nos",
    "o", "os", "ou", "para", "por", "um", "uma", "uns", "umas", "the", "of", "for", "and", "item", "lote",
}

DEFAULT_EMBEDDING_WEIGHT = float(os.environ.get("CRM_MATCH_EMBEDDING_WEIGHT", "0.55"))
DEFAULT_LEXICAL_WEIGHT = 1.0 - DEFAULT_EMBEDDING_WEIGHT
LLM_MODEL = os.environ.get("CRM_MATCH_LLM_MODEL", "llama3.2:1b")


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
    if score >= 0.82:
        return "strong"
    if score >= 0.64:
        return "possible"
    if score >= 0.46:
        return "weak"
    return "none"


def build_match_summary(best_scores: list[dict[str, Any]], total_reference_value: float) -> dict[str, Any]:
    total_items = len(best_scores)
    strong_items = sum(1 for item in best_scores if item["best_score"] >= 0.82)
    possible_items = sum(1 for item in best_scores if 0.64 <= item["best_score"] < 0.82)
    weak_items = sum(1 for item in best_scores if 0.46 <= item["best_score"] < 0.64)
    unmatched_items = sum(1 for item in best_scores if item["best_score"] < 0.46)

    covered_reference_value = sum(
        float(item.get("reference_value") or 0.0)
        for item in best_scores
        if item["best_score"] >= 0.64
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
        payload = json.loads(match.group(0) if match else raw)
        score = float(payload.get("score", 0.0) or 0.0)
        return {
            "score": max(0.0, min(1.0, score)),
            "level": payload.get("level") or score_to_level(score),
            "rationale": payload.get("rationale"),
            "matched_features": tuple(payload.get("matched_features") or ()),
            "conflicts": tuple(payload.get("conflicts") or ()),
        }
    except Exception as exc:
        logger.warning("[CRM Match] LLM local indisponivel para rerank: %s", exc)
        return None


def _numeric_overlap_score(source_tokens: set[str], candidate_tokens: set[str]) -> float:
    source_numbers = {token for token in source_tokens if any(ch.isdigit() for ch in token)}
    candidate_numbers = {token for token in candidate_tokens if any(ch.isdigit() for ch in token)}
    if not source_numbers or not candidate_numbers:
        return 0.0
    overlap = source_numbers & candidate_numbers
    return len(overlap) / max(len(source_numbers), 1)
