from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault("OLLAMA_HOST", "http://127.0.0.1:11434")
os.environ.setdefault("OLLAMA_MODEL", "llama3.2:1b")
os.environ.setdefault("OLLAMA_EMBED_MODEL", "nomic-embed-text")

from app.services.analysis_normalizer import normalize_analysis_result
from app.services.crm_match_scoring import (
    _has_hard_category_conflict,
    combine_scores,
    cosine_similarity,
    lexical_similarity,
    normalize_text,
    score_to_level,
    technical_compatibility_score,
    try_llm_rerank,
)
from app.services.datasheet_extractor import extract_specs_from_pdf


DEFAULT_DATASHEETS_DIR = Path(
    r"D:\TOR\ARQUIVOS PRONTOS PARA SITE-20260727T014743Z-1-001\ARQUIVOS PRONTOS PARA SITE"
)
DEFAULT_ANALYSES_DIR = Path(r"D:\TOR\Analisados\AnalisadosAtualizado")
DEFAULT_OUTPUT_DIR = ROOT / "data" / "validation_reports"


@dataclass
class ValidationRow:
    pdf_path: str
    json_path: str
    item_number: str
    edital_orgao: str
    edital_resumo: str
    item_category: str
    item_description: str
    datasheet_model: str
    datasheet_category: str
    datasheet_specs: str
    ocr_chars: int
    lexical_score: float
    semantic_score: float | None
    technical_score: float | None
    llm_score: float | None
    raw_overall_score: float
    final_score: float
    final_level: str
    decision: str
    expected_by_category: str
    hard_conflict: bool
    rationale: str
    conflicts: str
    extraction_quality: str


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Valida OCR + extracao de datasheet + match contra JSONs analisados."
    )
    parser.add_argument("--datasheets-dir", type=Path, default=DEFAULT_DATASHEETS_DIR)
    parser.add_argument("--analyses-dir", type=Path, default=DEFAULT_ANALYSES_DIR)
    parser.add_argument("--pdf-file", type=Path, action="append", default=[], help="PDF especifico para validar.")
    parser.add_argument("--json-file", type=Path, action="append", default=[], help="JSON especifico para validar.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--pdf-limit", type=int, default=10)
    parser.add_argument("--json-limit", type=int, default=10)
    parser.add_argument("--max-pairs", type=int, default=100)
    parser.add_argument(
        "--item-category",
        action="append",
        default=[],
        help="Filtra itens por categoria canonica. Pode repetir. Ex: --item-category transceiver",
    )
    parser.add_argument(
        "--datasheet-category",
        action="append",
        default=[],
        help="Filtra datasheets por categoria canonica. Pode repetir. Ex: --datasheet-category transceiver",
    )
    parser.add_argument("--no-llm", action="store_true", help="Desativa rerank LLM.")
    parser.add_argument("--no-embeddings", action="store_true", help="Desativa score semantico.")
    args = parser.parse_args()

    pdfs = args.pdf_file or sorted(args.datasheets_dir.glob("*.pdf"))[: args.pdf_limit]
    jsons = args.json_file or sorted(args.analyses_dir.rglob("*.json"))[: args.json_limit]
    if not pdfs:
        raise SystemExit(f"Nenhum PDF encontrado em {args.datasheets_dir}")
    if not jsons:
        raise SystemExit(f"Nenhum JSON encontrado em {args.analyses_dir}")

    wanted_datasheet_categories = {cat.strip() for cat in args.datasheet_category if cat.strip()}
    datasheets = [
        datasheet
        for datasheet in (_extract_datasheet(path) for path in pdfs)
        if not wanted_datasheet_categories or datasheet["category"] in wanted_datasheet_categories
    ]
    notices = [_load_notice(path) for path in jsons]
    if wanted_datasheet_categories and not datasheets:
        raise SystemExit(f"Nenhum datasheet nas categorias: {sorted(wanted_datasheet_categories)}")

    rows: list[ValidationRow] = []
    embedding_cache: dict[str, list[float]] = {}
    wanted_item_categories = {cat.strip() for cat in args.item_category if cat.strip()}
    for notice in notices:
        for item in notice["items"]:
            if wanted_item_categories and _canonical_category(item.get("categoria")) not in wanted_item_categories:
                continue
            notice_text = _notice_text(item)
            for datasheet in datasheets:
                if len(rows) >= args.max_pairs:
                    break
                row = _score_pair(
                    notice=notice,
                    item=item,
                    notice_text=notice_text,
                    datasheet=datasheet,
                    use_llm=not args.no_llm,
                    use_embeddings=not args.no_embeddings,
                    embedding_cache=embedding_cache,
                )
                rows.append(row)
            if len(rows) >= args.max_pairs:
                break
        if len(rows) >= args.max_pairs:
            break

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = args.output_dir / f"datasheet_match_validation_{stamp}.csv"
    json_path = args.output_dir / f"datasheet_match_validation_{stamp}.json"

    _write_csv(csv_path, rows)
    summary = _build_summary(rows)
    json_path.write_text(
        json.dumps({"summary": summary, "rows": [asdict(row) for row in rows]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps({"summary": summary, "csv": str(csv_path), "json": str(json_path)}, ensure_ascii=False, indent=2))
    return 0


def _extract_datasheet(path: Path) -> dict[str, Any]:
    extracted = extract_specs_from_pdf(path.read_bytes(), filename=path.name)
    return {
        "path": path,
        "model": extracted.get("model") or path.stem,
        "manufacturer": extracted.get("manufacturer") or "",
        "category": _canonical_category(extracted.get("category")),
        "specs": extracted.get("specs") or {},
        "raw_text": extracted.get("raw_text") or "",
    }


def _load_notice(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    normalized = normalize_analysis_result(payload)
    edital = normalized.get("edital") or {}
    return {
        "path": path,
        "edital": edital,
        "items": normalized.get("itens_elegiveis") or [],
    }


def _score_pair(
    *,
    notice: dict[str, Any],
    item: dict[str, Any],
    notice_text: str,
    datasheet: dict[str, Any],
    use_llm: bool,
    use_embeddings: bool,
    embedding_cache: dict[str, list[float]],
) -> ValidationRow:
    catalog_text = _datasheet_text(datasheet)
    lexical = lexical_similarity(notice_text, catalog_text)
    semantic = _semantic_score(notice_text, catalog_text, embedding_cache) if use_embeddings else None
    hard_conflict = _has_hard_category_conflict(notice_text, catalog_text)
    technical = technical_compatibility_score(notice_text, catalog_text)

    llm_payload = None
    if use_llm:
        llm_payload = try_llm_rerank(
            notice_text=notice_text,
            candidate_title=str(datasheet.get("model") or datasheet["path"].stem),
            candidate_text=catalog_text[:5000],
        )

    score = combine_scores(lexical, semantic, llm_payload.get("score") if llm_payload else None)
    final_score = score.overall_score
    if technical is not None:
        final_score = max(final_score, technical.score)
    final_score = min(final_score, 0.25) if hard_conflict else final_score
    final_level = "none" if hard_conflict else score_to_level(final_score)
    conflicts = list(llm_payload.get("conflicts") or []) if llm_payload else []
    if technical is not None:
        conflicts.extend(technical.conflicts)
    if hard_conflict and not conflicts:
        conflicts.append("Familia tecnica incompativel entre item do edital e produto do catalogo.")

    item_category = _canonical_category(item.get("categoria"))
    datasheet_category = _canonical_category(datasheet.get("category"))
    return ValidationRow(
        pdf_path=str(datasheet["path"]),
        json_path=str(notice["path"]),
        item_number=str(item.get("numero_item_edital") or ""),
        edital_orgao=str((notice.get("edital") or {}).get("orgao") or ""),
        edital_resumo=str((notice.get("edital") or {}).get("resumo_itens") or ""),
        item_category=item_category,
        item_description=str(item.get("descricao_original") or ""),
        datasheet_model=str(datasheet.get("model") or ""),
        datasheet_category=datasheet_category,
        datasheet_specs=json.dumps(datasheet.get("specs") or {}, ensure_ascii=False, sort_keys=True),
        ocr_chars=len(datasheet.get("raw_text") or ""),
        lexical_score=round(score.lexical_score, 4),
        semantic_score=score.semantic_score,
        technical_score=technical.score if technical is not None else None,
        llm_score=score.llm_score,
        raw_overall_score=round(score.overall_score, 4),
        final_score=round(final_score, 4),
        final_level=final_level,
        decision=_decision(final_score, hard_conflict),
        expected_by_category=_expected_by_category(item_category, datasheet_category, hard_conflict),
        hard_conflict=hard_conflict,
        rationale=str((llm_payload or {}).get("rationale") or ""),
        conflicts="; ".join(conflicts),
        extraction_quality=_extraction_quality(datasheet),
    )


def _semantic_score(notice_text: str, catalog_text: str, embedding_cache: dict[str, list[float]]) -> float | None:
    try:
        from app.pipeline.embedder import embed_texts_batch

        missing = [text for text in (notice_text, catalog_text) if text not in embedding_cache]
        if missing:
            vectors = embed_texts_batch(missing)
            for text, vector in zip(missing, vectors):
                embedding_cache[text] = vector
        notice_embedding = embedding_cache[notice_text]
        catalog_embedding = embedding_cache[catalog_text]
        return round(cosine_similarity(notice_embedding, catalog_embedding), 4)
    except Exception:
        return None


def _notice_text(item: dict[str, Any]) -> str:
    parts = [
        item.get("descricao_original"),
        item.get("categoria"),
        item.get("caracteristicas_tecnicas"),
        json.dumps(item.get("caracteristicas_bi") or {}, ensure_ascii=False),
        item.get("direcionamento_marca", {}).get("marca_modelo") if isinstance(item.get("direcionamento_marca"), dict) else None,
    ]
    return " | ".join(str(part) for part in parts if part)


def _datasheet_text(datasheet: dict[str, Any]) -> str:
    parts = [
        datasheet.get("model"),
        datasheet.get("manufacturer"),
        datasheet.get("category"),
        json.dumps(datasheet.get("specs") or {}, ensure_ascii=False, sort_keys=True),
        (datasheet.get("raw_text") or "")[:3000],
    ]
    return " | ".join(str(part) for part in parts if part)


def _canonical_category(value: Any) -> str:
    text = normalize_text(str(value or ""))
    if not text:
        return ""
    tokens = set(text.split())
    if "access point" in text or "wifi" in tokens or ("wi" in tokens and "fi" in tokens):
        return "access_point"
    if any(term in text for term in ("transceiver", "transceptor", "sfp", "modulo optico", "modulo otico")):
        return "transceiver"
    if "switch" in text:
        return "switch"
    return text.replace(" ", "_")


def _decision(score: float, hard_conflict: bool) -> str:
    if hard_conflict or score < 0.46:
        return "nao_match"
    if score < 0.82:
        return "parcial"
    return "match"


def _expected_by_category(item_category: str, datasheet_category: str, hard_conflict: bool) -> str:
    if hard_conflict:
        return "negativo"
    if item_category and datasheet_category and item_category == datasheet_category:
        return "positivo_provavel"
    if item_category and datasheet_category:
        return "negativo_provavel"
    return "indefinido"


def _extraction_quality(datasheet: dict[str, Any]) -> str:
    specs = datasheet.get("specs") or {}
    if len(specs) >= 4 and datasheet.get("category"):
        return "boa"
    if specs and datasheet.get("category"):
        return "parcial"
    return "fraca"


def _write_csv(path: Path, rows: list[ValidationRow]) -> None:
    fieldnames = list(ValidationRow.__dataclass_fields__.keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def _build_summary(rows: list[ValidationRow]) -> dict[str, Any]:
    total = len(rows)
    decisions = _count_by(rows, "decision")
    expected = _count_by(rows, "expected_by_category")
    hard_conflicts = sum(1 for row in rows if row.hard_conflict)
    good_extractions = sum(1 for row in rows if row.extraction_quality == "boa")
    avg_score = round(sum(row.final_score for row in rows) / total, 4) if total else 0.0
    return {
        "total_pairs": total,
        "decisions": decisions,
        "expected_by_category": expected,
        "hard_conflicts": hard_conflicts,
        "good_extractions": good_extractions,
        "avg_final_score": avg_score,
    }


def _count_by(rows: list[ValidationRow], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(getattr(row, field))
        counts[value] = counts.get(value, 0) + 1
    return counts


if __name__ == "__main__":
    raise SystemExit(main())
