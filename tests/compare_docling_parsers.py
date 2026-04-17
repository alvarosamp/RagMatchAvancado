"""
Compare extraction quality and runtime between docling_parser and docling_parser2.

Usage examples:
  python tests/compare_docling_parsers.py --pdf C:\\docs\\edital.pdf
  python tests/compare_docling_parsers.py --pdf C:\\docs\\a.pdf C:\\docs\\b.pdf --batch-size 12 --repeats 2
  python tests/compare_docling_parsers.py --pdf C:\\docs\\edital.pdf --json-out tests/docling_compare_report.json
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import statistics
import sys
import time
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = PROJECT_ROOT / "backend"

if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))


@dataclass
class RunMetrics:
    elapsed_seconds: float
    full_text_chars: int
    full_text_words: int
    chunk_count: int
    chunks_with_page: int
    chunks_with_section: int
    fallback_chunks: int
    text_hash: str


@dataclass
class ParserSummary:
    parser_name: str
    runs: list[RunMetrics]
    error: str | None = None

    def mean(self, field_name: str) -> float:
        if not self.runs:
            return 0.0
        return statistics.mean(getattr(run, field_name) for run in self.runs)


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def _build_metrics(parsed_doc: Any, elapsed_seconds: float) -> RunMetrics:
    chunks = parsed_doc.chunks
    normalized_text = _normalize_text(parsed_doc.full_text)

    return RunMetrics(
        elapsed_seconds=elapsed_seconds,
        full_text_chars=len(parsed_doc.full_text),
        full_text_words=len(normalized_text.split(" ")) if normalized_text else 0,
        chunk_count=len(chunks),
        chunks_with_page=sum(1 for c in chunks if getattr(c, "page", None) is not None),
        chunks_with_section=sum(1 for c in chunks if bool(getattr(c, "section", None))),
        fallback_chunks=sum(1 for c in chunks if getattr(c, "section", None) == "fallback"),
        text_hash=hashlib.sha256(normalized_text.encode("utf-8")).hexdigest(),
    )


def _load_parsers() -> tuple[Callable[..., Any], Callable[..., Any]]:
    from app.pipeline import docling_parser, docling_parser2

    parser_v1 = docling_parser.parse_pdf
    parser_v2 = docling_parser2.parse_pdf
    return parser_v1, parser_v2


def _run_parser(
    parser_label: str,
    parse_fn: Callable[..., Any],
    pdf_path: Path,
    repeats: int,
    batch_size: int | None,
    use_batch_size: bool,
    show_traceback: bool,
) -> ParserSummary:
    runs: list[RunMetrics] = []

    for index in range(repeats):
        start = time.perf_counter()

        try:
            if use_batch_size:
                parsed_doc = parse_fn(
                    source=pdf_path,
                    filename=pdf_path.name,
                    batch_size=batch_size,
                )
            else:
                parsed_doc = parse_fn(source=pdf_path, filename=pdf_path.name)
        except Exception as exc:
            if show_traceback:
                traceback.print_exc()
            return ParserSummary(
                parser_name=parser_label,
                runs=runs,
                error=f"run {index + 1}: {type(exc).__name__}: {exc}",
            )

        elapsed = time.perf_counter() - start
        runs.append(_build_metrics(parsed_doc, elapsed))
        gc.collect()

    return ParserSummary(parser_name=parser_label, runs=runs)


def _recommend(v1: ParserSummary, v2: ParserSummary) -> tuple[str, str]:
    if v1.error and not v2.error:
        return "docling_parser2.py", "parser 1 failed and parser 2 succeeded"
    if v2.error and not v1.error:
        return "docling_parser.py", "parser 2 failed and parser 1 succeeded"
    if v1.error and v2.error:
        return "none", "both parsers failed for this file"

    v1_time = v1.mean("elapsed_seconds")
    v2_time = v2.mean("elapsed_seconds")
    v1_chars = v1.mean("full_text_chars")
    v2_chars = v2.mean("full_text_chars")
    v1_chunks = v1.mean("chunk_count")
    v2_chunks = v2.mean("chunk_count")

    speedup = (v1_time / v2_time) if v2_time > 0 else 0.0
    char_ratio = (v2_chars / v1_chars) if v1_chars > 0 else 0.0
    chunk_ratio = (v2_chunks / v1_chunks) if v1_chunks > 0 else 0.0

    # Keep parser 2 when it preserves extraction quality while being noticeably faster.
    if speedup >= 1.15 and char_ratio >= 0.95 and chunk_ratio >= 0.95:
        return "docling_parser2.py", "faster with similar extraction volume"

    # Keep parser 1 when parser 2 loses too much extracted content/chunks.
    if char_ratio < 0.85 or chunk_ratio < 0.85:
        return "docling_parser.py", "parser 2 lost too much extracted content"

    # Small differences: prefer parser 2 only if still faster.
    if speedup >= 1.05:
        return "docling_parser2.py", "slightly faster and extraction stayed close"

    return "docling_parser.py", "no measurable gain from parser 2"


def _format_float(value: float, decimals: int = 2) -> str:
    return f"{value:.{decimals}f}"


def _print_summary(pdf_path: Path, v1: ParserSummary, v2: ParserSummary) -> None:
    print("=" * 90)
    print(f"PDF: {pdf_path}")

    if v1.error:
        print(f"- docling_parser.py error:  {v1.error}")
    if v2.error:
        print(f"- docling_parser2.py error: {v2.error}")

    if not v1.error and not v2.error:
        headers = ("metric", "docling_parser.py", "docling_parser2.py")
        rows = [
            ("avg runtime (s)", _format_float(v1.mean("elapsed_seconds")), _format_float(v2.mean("elapsed_seconds"))),
            ("avg full_text chars", _format_float(v1.mean("full_text_chars"), 0), _format_float(v2.mean("full_text_chars"), 0)),
            ("avg full_text words", _format_float(v1.mean("full_text_words"), 0), _format_float(v2.mean("full_text_words"), 0)),
            ("avg chunk count", _format_float(v1.mean("chunk_count"), 0), _format_float(v2.mean("chunk_count"), 0)),
            (
                "avg chunks with page",
                _format_float(v1.mean("chunks_with_page"), 0),
                _format_float(v2.mean("chunks_with_page"), 0),
            ),
            (
                "avg chunks with section",
                _format_float(v1.mean("chunks_with_section"), 0),
                _format_float(v2.mean("chunks_with_section"), 0),
            ),
            (
                "avg fallback chunks",
                _format_float(v1.mean("fallback_chunks"), 0),
                _format_float(v2.mean("fallback_chunks"), 0),
            ),
            ("normalized text hash", v1.runs[0].text_hash[:12], v2.runs[0].text_hash[:12]),
        ]

        widths = [
            max(len(headers[0]), *(len(row[0]) for row in rows)),
            max(len(headers[1]), *(len(row[1]) for row in rows)),
            max(len(headers[2]), *(len(row[2]) for row in rows)),
        ]

        header_line = (
            f"{headers[0]:<{widths[0]}} | "
            f"{headers[1]:<{widths[1]}} | "
            f"{headers[2]:<{widths[2]}}"
        )
        divider = "-" * len(header_line)
        print(header_line)
        print(divider)

        for metric, left, right in rows:
            print(f"{metric:<{widths[0]}} | {left:<{widths[1]}} | {right:<{widths[2]}}")

    keep, reason = _recommend(v1, v2)
    print(f"Recommendation for this PDF: keep {keep} ({reason})")


def _validate_pdfs(pdf_paths: list[str]) -> list[Path]:
    resolved: list[Path] = []
    for path_str in pdf_paths:
        path = Path(path_str).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"PDF not found: {path}")
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"Not a PDF file: {path}")
        resolved.append(path)
    return resolved


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare docling_parser.py and docling_parser2.py on one or more PDFs.",
    )
    parser.add_argument(
        "--pdf",
        nargs="+",
        required=True,
        help="One or more PDF paths to benchmark.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Batch size used only by docling_parser2.py (default: parser internal behavior).",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="How many runs per parser for each PDF (default: 1).",
    )
    parser.add_argument(
        "--json-out",
        type=str,
        default=None,
        help="Optional output path for a JSON report.",
    )
    parser.add_argument(
        "--show-traceback",
        action="store_true",
        help="Print full traceback if a parser run fails.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.repeats <= 0:
        raise ValueError("--repeats must be >= 1")
    if args.batch_size is not None and args.batch_size <= 0:
        raise ValueError("--batch-size must be > 0 when provided")

    pdf_paths = _validate_pdfs(args.pdf)
    parser_v1, parser_v2 = _load_parsers()

    report: dict[str, Any] = {
        "pdf_count": len(pdf_paths),
        "batch_size": args.batch_size,
        "repeats": args.repeats,
        "results": [],
    }

    keep_count = {
        "docling_parser.py": 0,
        "docling_parser2.py": 0,
        "none": 0,
    }

    for pdf_path in pdf_paths:
        v1 = _run_parser(
            parser_label="docling_parser.py",
            parse_fn=parser_v1,
            pdf_path=pdf_path,
            repeats=args.repeats,
            batch_size=None,
            use_batch_size=False,
            show_traceback=args.show_traceback,
        )
        v2 = _run_parser(
            parser_label="docling_parser2.py",
            parse_fn=parser_v2,
            pdf_path=pdf_path,
            repeats=args.repeats,
            batch_size=args.batch_size,
            use_batch_size=True,
            show_traceback=args.show_traceback,
        )

        keep, reason = _recommend(v1, v2)
        keep_count[keep] += 1

        _print_summary(pdf_path, v1, v2)

        report["results"].append(
            {
                "pdf": str(pdf_path),
                "parser_v1": asdict(v1),
                "parser_v2": asdict(v2),
                "recommendation": {
                    "keep": keep,
                    "reason": reason,
                },
            }
        )

    global_keep = max(keep_count.items(), key=lambda item: item[1])[0]
    report["global_recommendation"] = {
        "keep": global_keep,
        "vote_count": keep_count[global_keep],
        "votes": keep_count,
    }

    print("=" * 90)
    print(
        "Global recommendation:",
        report["global_recommendation"]["keep"],
        "| votes:",
        report["global_recommendation"]["votes"],
    )

    if args.json_out:
        output_path = Path(args.json_out).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"JSON report saved to: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())