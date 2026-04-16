"""Rodar Docling nos PDFs de teste e inspecionar páginas/chunks.

- Gera markdown extraído pelo Docling para cada PDF.
- Mostra um resumo por arquivo (chars, chunks, páginas com/sem texto).

Uso rápido:
    python scripts/run_docling_debug.py              # roda apenas Ata#1004
    python scripts/run_docling_debug.py --first10    # roda nos 10 primeiros PDFs
    python scripts/run_docling_debug.py --all        # roda em todos os PDFs
"""

from __future__ import annotations

import sys
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
TEST_BASE = ROOT / "Pncp" / "Base de teste do analisador de atas"
OUT_DIR = TEST_BASE / "docling_md"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# backend/app precisa estar no PYTHONPATH para importar app.pipeline
backend_root = ROOT / "backend"
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.pipeline.docling_parser import parse_pdf  # type: ignore[import]


def _iter_pdfs(limit: int | None = None):
    files = sorted([p for p in TEST_BASE.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"])
    if limit is not None:
        files = files[:limit]
    return files


def process_file(path: Path) -> None:
    print(f"\n[Docling] Processando {path.name}...")
    doc = parse_pdf(path, filename=path.name)

    # Salva markdown completo para inspeção manual
    md_path = OUT_DIR / f"{path.stem}.docling.md"
    md_path.write_text(doc.full_text, encoding="utf-8")

    # Estatísticas locais por página (usando ParsedChunk.page)
    pages = [c.page for c in doc.chunks if c.page is not None]
    page_counts = Counter(pages)

    print(f"  -> chars extraídos: {len(doc.full_text)}")
    print(f"  -> chunks: {len(doc.chunks)}")
    if page_counts:
        sorted_counts = sorted(page_counts.items())
        pages_str = ", ".join(f"p{p}={n}" for p, n in sorted_counts)
        print(f"  -> chunks por página: {pages_str}")
    else:
        print("  -> nenhum número de página disponível nos chunks (provavelmente fallback/pypdf)")

    print(f"  -> markdown salvo em: {md_path}")


def main(argv: list[str]) -> None:
    args = argv[1:]
    if not TEST_BASE.exists():
        print("Pasta de teste não encontrada:", TEST_BASE)
        return

    # Modos:
    #  - sem args: roda só Ata#1004
    #  - --first10: primeiros 10 PDFs
    #  - --all: todos
    if not args:
        target = TEST_BASE / "Ata#1004 - BLL.pdf"
        if not target.exists():
            print("Arquivo padrão não encontrado:", target)
            return
        process_file(target)
        return

    if "--first10" in args:
        pdfs = _iter_pdfs(limit=10)
    elif "--all" in args:
        pdfs = _iter_pdfs()
    else:
        # Tratar argumento como caminho de arquivo específico
        target = Path(args[0])
        if not target.is_absolute():
            target = TEST_BASE / target
        if not target.exists():
            print("Arquivo não encontrado:", target)
            return
        process_file(target)
        return

    print(f"Encontrados {len(pdfs)} PDFs em {TEST_BASE}")
    for p in pdfs:
        process_file(p)


if __name__ == "__main__":
    main(sys.argv)
