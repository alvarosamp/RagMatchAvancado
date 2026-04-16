"""Roda OCR/parse via Docling para todos os PDFs em atas_baixadas/.

Uso (a partir da raiz do repo):
  PYTHONPATH=backend python backend/scripts/run_docling_all_atas.py

Opções úteis:
  --limit 20        processa só os 20 primeiros
  --overwrite       sobrescreve arquivos .docling.md existentes

Saída:
  Para cada PDF X.pdf, salva X.docling.md no mesmo diretório.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
ATAS_DIR = REPO_ROOT / "atas_baixadas"


def _iter_pdfs(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.pdf") if p.is_file())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=str, default=str(ATAS_DIR), help="Diretório raiz (default: atas_baixadas)")
    parser.add_argument("--file", type=str, default=None, help="Processa apenas este PDF específico (caminho absoluto ou relativo ao --root)")
    parser.add_argument("--limit", type=int, default=0, help="Processa no máximo N PDFs (0 = sem limite)")
    parser.add_argument("--overwrite", action="store_true", help="Sobrescreve .docling.md existente")
    args = parser.parse_args()

    root = Path(args.root)

    from app.pipeline.docling_parser import parse_pdf

    if args.file:
        file_path = Path(args.file)
        if not file_path.is_absolute():
            file_path = root / args.file
        if not file_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
        pdfs = [file_path]
    else:
        if not root.exists():
            raise FileNotFoundError(f"Diretório não encontrado: {root}")
        pdfs = _iter_pdfs(root)
        if args.limit and args.limit > 0:
            pdfs = pdfs[: args.limit]

    logger.info("Encontrados %s PDFs em %s", len(pdfs), root)

    ok = skipped = failed = 0

    for pdf in pdfs:
        out_md = pdf.with_suffix(".docling.md")
        if out_md.exists() and not args.overwrite:
            skipped += 1
            continue

        logger.info("Docling: %s", pdf)
        try:
            parsed = parse_pdf(pdf, filename=pdf.name)
            text = parsed.full_text or ""
            out_md.write_text(text, encoding="utf-8")
            ok += 1
        except Exception as exc:
            failed += 1
            logger.exception("Falha em %s: %s", pdf, exc)

    logger.info("Concluído: ok=%s skipped=%s failed=%s", ok, skipped, failed)


if __name__ == "__main__":
    main()
