"""Pipeline completo: PDF → Docling OCR → GPT → JSON → pronto para tabela.

Como usar (a partir da raiz do repo):
  PYTHONPATH=backend python backend/scripts/process_first_10_atas.py

Opções:
  --file   <caminho.pdf>   Processa apenas este PDF específico
  --limit  N               Processa os N primeiros PDFs (padrão: 10; 0 = todos)
  --all                    Processa todos os PDFs da pasta de teste
  --overwrite              Reprocessa mesmo que já exista JSON de saída
  --root   <pasta>         Pasta raiz com os PDFs (padrão: Base de teste do analisador de atas)

Exemplos:
  # Apenas a ata 1004
  PYTHONPATH=backend python backend/scripts/process_first_10_atas.py \\
      --file "Pncp/Base de teste do analisador de atas/Ata#1004 - BLL.pdf"

  # Todos os PDFs, sobrescrevendo resultados existentes
  PYTHONPATH=backend python backend/scripts/process_first_10_atas.py --all --overwrite
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_DIR  = REPO_ROOT / "Pncp" / "Base de teste do analisador de atas"
OUT_DIR   = REPO_ROOT / "Pncp" / "AnaliseAtaGPT" / "resultado_modelo_menor"


def _load_pipelinegpt():
    path = REPO_ROOT / "Pncp" / "AnaliseAtaGPT" / "pipelinegpt.py"
    api_shared = REPO_ROOT / "Pncp" / "apiPncp"
    if str(api_shared) not in sys.path:
        sys.path.insert(0, str(api_shared))
    spec = importlib.util.spec_from_file_location("pipelinegpt", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Não foi possível carregar {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _processar(pdf: Path, parse_pdf, pipelinegpt, overwrite: bool) -> str:
    """Processa um único PDF. Retorna 'ok', 'skipped' ou 'erro'."""
    stem     = pdf.stem
    out_path = OUT_DIR / f"{stem}_llm.json"

    if out_path.exists() and not overwrite:
        logger.info("Já existe, pulando: %s", out_path.name)
        return "skipped"

    logger.info("─── Processando: %s", pdf.name)

    # 1. OCR via Docling
    try:
        doc = parse_pdf(pdf, filename=pdf.name)
    except Exception as e:
        logger.exception("Docling falhou em %s: %s", pdf.name, e)
        return "erro"

    if not doc.full_text or not doc.full_text.strip():
        logger.warning("Docling não retornou texto para %s", pdf.name)
        return "erro"

    logger.info("  Texto extraído: %s chars", len(doc.full_text))

    # 2. Análise GPT
    try:
        resultado = pipelinegpt.analisar_texto_ata_extraido(
            doc.full_text,
            id_pncp=stem,
            nome_arquivo=pdf.name,
        )
    except Exception as e:
        logger.exception("GPT falhou em %s: %s", pdf.name, e)
        return "erro"

    if resultado is None:
        logger.warning("GPT não retornou resultado para %s", pdf.name)
        return "erro"

    logger.info(
        "  Itens extraídos: %s | tokens: %s | aviso: %s",
        len(resultado.itens),
        resultado.tokens_usados,
        resultado.aviso or "—",
    )

    # 3. Salva JSON
    out_path.write_text(
        pipelinegpt.resultado_para_json(resultado, indent=2),
        encoding="utf-8",
    )
    logger.info("  Salvo: %s", out_path)
    return "ok"


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline PDF → Docling → GPT → JSON")
    parser.add_argument("--file",      type=str, default=None,
                        help="Processa apenas este PDF (caminho relativo à raiz do repo ou absoluto)")
    parser.add_argument("--root",      type=str, default=str(TEST_DIR),
                        help="Pasta com os PDFs (padrão: Base de teste do analisador de atas)")
    parser.add_argument("--limit",     type=int, default=10,
                        help="Processa os N primeiros PDFs (padrão: 10; ignorado com --file ou --all)")
    parser.add_argument("--all",       action="store_true",
                        help="Processa todos os PDFs da pasta")
    parser.add_argument("--overwrite", action="store_true",
                        help="Reprocessa mesmo que JSON já exista")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Importa dependências
    from app.pipeline.docling_parser import parse_pdf
    pipelinegpt = _load_pipelinegpt()

    # Resolve lista de PDFs
    if args.file:
        pdf_path = Path(args.file)
        if not pdf_path.is_absolute():
            pdf_path = REPO_ROOT / pdf_path
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF não encontrado: {pdf_path}")
        pdfs = [pdf_path]
    else:
        root = Path(args.root)
        if not root.exists():
            raise FileNotFoundError(f"Pasta não encontrada: {root}")
        pdfs = sorted(p for p in root.iterdir() if p.suffix.lower() == ".pdf")
        if not args.all and args.limit > 0:
            pdfs = pdfs[:args.limit]

    logger.info("PDFs a processar: %s", len(pdfs))

    ok = skipped = erro = 0
    for pdf in pdfs:
        status = _processar(pdf, parse_pdf, pipelinegpt, overwrite=args.overwrite)
        if status == "ok":
            ok += 1
        elif status == "skipped":
            skipped += 1
        else:
            erro += 1

    logger.info("─── Concluído: ok=%s skipped=%s erro=%s", ok, skipped, erro)


if __name__ == "__main__":
    main()
