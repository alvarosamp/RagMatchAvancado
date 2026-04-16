"""Pipeline completo: Docling (PDF) -> texto -> analisador GPT (pipelinegpt).

Uso típico:
    python3 scripts/run_docling_gpt_pdf.py                      # roda em Ata#1179 - BLL.pdf
    python3 scripts/run_docling_gpt_pdf.py "Ata#1004 - BLL.pdf"  # roda em outro PDF da pasta de teste
    python3 scripts/run_docling_gpt_pdf.py /caminho/para/arquivo.pdf  # caminho absoluto/relativo
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_BASE = ROOT / "Pncp" / "Base de teste do analisador de atas"
OUT_DIR = ROOT / "Pncp" / "AnaliseAtaGPT" / "results_from_pdf"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# backend/app precisa estar no PYTHONPATH para importar app.pipeline
backend_root = ROOT / "backend"
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

# Repo root para importar pipelinegpt
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.pipeline.docling_parser import parse_pdf  # type: ignore[import]
from Pncp.AnaliseAtaGPT.pipelinegpt import analisar_ata, resultado_para_json  # type: ignore[import]


def main(argv: list[str]) -> None:
    args = argv[1:]

    if args:
        pdf_path = Path(args[0])
        if not pdf_path.is_absolute():
            # Se for apenas o nome, assumimos a pasta de teste
            candidate = TEST_BASE / pdf_path
            pdf_path = candidate if candidate.exists() else pdf_path
    else:
        pdf_path = TEST_BASE / "Ata#1179 - BLL.pdf"

    if not pdf_path.exists():
        print("PDF não encontrado:", pdf_path)
        return

    print(f"[Pipeline] Rodando Docling + GPT em: {pdf_path}")

    doc = parse_pdf(pdf_path, filename=pdf_path.name)
    texto = doc.full_text

    if not texto.strip():
        print("[Aviso] Texto extraído vazio. Verifique instalação do Docling/pypdf.")
        return

    resultado = analisar_ata(texto, id_pncp=pdf_path.stem)
    out_json = OUT_DIR / f"{pdf_path.stem}.json"
    out_json.write_text(resultado_para_json(resultado, indent=2), encoding="utf-8")

    print(f"[OK] Resultado salvo em: {out_json}")
    print(f"      Itens extraídos: {len(resultado.itens)} | tokens usados: {resultado.tokens_usados}")


if __name__ == "__main__":
    main(sys.argv)
