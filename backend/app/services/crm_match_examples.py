"""Retrieve tenant-owned human matches as precedents, not technical verdicts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable

from app.services.crm_match_scoring import lexical_similarity, normalize_text


MAX_MANUAL_EXAMPLES = 3
MIN_EXAMPLE_SIMILARITY = 0.30


@dataclass(frozen=True)
class ManualMatchExample:
    notice_id: str
    item_id: str
    catalog_id: str
    item_text: str
    catalog_title: str


def similar_manual_examples(
    item_text: str,
    examples: Iterable[ManualMatchExample],
    *,
    notice_id: str,
    item_id: str,
    limit_per_product: int = MAX_MANUAL_EXAMPLES,
) -> dict[str, list[tuple[float, ManualMatchExample]]]:
    """Group precedents by selected catalog product, excluding the held-out notice."""
    if not normalize_text(item_text):
        return {}
    grouped: dict[str, list[tuple[float, ManualMatchExample]]] = {}
    seen: set[tuple[str, str]] = set()
    for example in examples:
        if example.notice_id == notice_id or example.item_id == item_id:
            continue
        signature = (example.catalog_id, normalize_text(example.item_text))
        if not signature[1] or signature in seen:
            continue
        seen.add(signature)
        similarity = lexical_similarity(item_text, example.item_text)
        if similarity < MIN_EXAMPLE_SIMILARITY:
            continue
        grouped.setdefault(example.catalog_id, []).append((similarity, example))
    for catalog_id, matches in grouped.items():
        grouped[catalog_id] = sorted(matches, key=lambda pair: pair[0], reverse=True)[:limit_per_product]
    return grouped


def manual_examples_prompt(examples: list[tuple[float, ManualMatchExample]]) -> str:
    """Bound prompt size and mark manual choices as examples, not certified facts."""
    if not examples:
        return ""
    rows = [
        {
            "item_do_edital": example.item_text[:400],
            "produto_escolhido_manualmente": example.catalog_title[:180],
        }
        for _, example in examples[:MAX_MANUAL_EXAMPLES]
    ]
    return (
        "CASOS SEMELHANTES ESCOLHIDOS POR PESSOAS (referencia, nao prova de atendimento tecnico):\n"
        + json.dumps(rows, ensure_ascii=False)
        + "\nCompare o item atual com o produto candidato pelas especificacoes. "
        "Nao copie a escolha humana automaticamente; explicite requisitos ausentes e conflitos."
    )


def summarize_manual_retrieval_trials(
    trials: Iterable[tuple[str, list[str], list[str]]],
) -> dict[str, object]:
    """Compare Top-K without claiming a technical-verdict or LLM quality score."""
    pairs = list(trials)

    def metrics(index: int) -> dict[str, int | float | None]:
        ranks = [next((i for i, value in enumerate(pair[index], 1) if value == pair[0]), None) for pair in pairs]
        count = len(ranks)
        hits = {k: sum(rank is not None and rank <= k for rank in ranks) for k in (1, 3, 5, 10)}
        return {
            "evaluated_items": count,
            "without_suggestion": sum(not pair[index] for pair in pairs),
            **{f"top{k}_hits": hits[k] for k in hits},
            **{f"recall_at_{k}": round(hits[k] / count, 4) if count else None for k in hits},
        }

    return {"baseline": metrics(1), "with_manual_examples": metrics(2)}
