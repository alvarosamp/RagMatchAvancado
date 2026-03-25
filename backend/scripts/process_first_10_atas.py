"""Processa as 10 primeiras atas da pasta de teste usando Docling + LLM.

Como usar (a partir de backend/):
  PYTHONPATH=. python scripts/process_first_10_atas.py

O script:
 - lista os PDFs em `Pncp/Base de teste do analisador de atas`
 - pega os 10 primeiros (ordenados por nome)
 - executa `app.pipeline.docling_parser3.parse_pdf` para extrair texto
 - chama o wrapper LLM `analisar_texto_ata_extraido` carregado diretamente do
   arquivo `Pncp/AnaliseAtaLLM/pipelinellm.py` (import seguro via importlib)
 - salva um JSON com o resultado em `Pncp/results_llm/{stem}_llm.json`
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_DIR = REPO_ROOT / "Pncp" / "Base de teste do analisador de atas"
OUT_DIR = REPO_ROOT / "Pncp" / "results_llm"


def _load_pipelinellm_module() -> object:
    path = REPO_ROOT / "Pncp" / "AnaliseAtaLLM" / "pipelinellm.py"
    # garante que o pacote `shared` usado por pipelinellm seja resolvível
    # (existe em Pncp/apiPncp/shared)
    api_shared = REPO_ROOT / "Pncp" / "apiPncp"
    import sys

    if str(api_shared) not in sys.path:
        sys.path.insert(0, str(api_shared))

    spec = importlib.util.spec_from_file_location("pipelinellm", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Não foi possível carregar {path}")
    mod = importlib.util.module_from_spec(spec)
    import sys
    # registra o módulo antes de executar para que decoradores/dataclasses
    # que consultem sys.modules funcione corretamente
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _list_first_n_pdfs(directory: Path, n: int = 10) -> List[Path]:
    files = [p for p in sorted(directory.iterdir()) if p.suffix.lower() == ".pdf"]
    return files[:n]


def main() -> None:
    if not TEST_DIR.exists():
        raise FileNotFoundError(f"Pasta de testes não encontrada: {TEST_DIR}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pipelinellm = _load_pipelinellm_module()

    # import docling parser (fallback to docling_parser present in this branch)
    from app.pipeline.docling_parser import parse_pdf

    pdfs = _list_first_n_pdfs(TEST_DIR, 10)
    logger.info(f"Encontrados {len(pdfs)} PDFs — processando {len(pdfs)} arquivos")

    for pdf in pdfs:
        stem = pdf.stem
        logger.info(f"Processando: {pdf.name}")
        try:
            doc = parse_pdf(pdf, filename=pdf.name)

            # chama o wrapper que usa o LLM
            resultado = pipelinellm.analisar_texto_ata_extraido(doc.full_text, id_pncp=stem, nome_arquivo=pdf.name)

            if resultado is None:
                logger.warning(f"LLM não retornou resultado para {pdf.name}")
                continue

            out_path = OUT_DIR / f"{stem}_llm.json"
            out_path.write_text(pipelinellm.resultado_para_json(resultado, indent=2), encoding="utf-8")
            logger.info(f"Resultado salvo: {out_path}")

        except Exception as e:
            logger.exception(f"Erro processando {pdf.name}: {e}")


if __name__ == "__main__":
    main()
