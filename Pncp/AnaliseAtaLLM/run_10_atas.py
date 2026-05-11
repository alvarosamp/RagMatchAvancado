"""
Processa 10 atas:
- Copia as extrações Docling para resultados/docling/
- Roda o pipeline LLM e salva JSON em resultados/json/
"""

from __future__ import annotations

import json
import logging
import shutil
import sys
import time
from pathlib import Path

# Garante que o módulo pipeline está no path
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from pipelinellm_prompt_ajustado import analisar_ata, resultado_para_dict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_10_atas")

BASE = Path(__file__).resolve().parent
DOCLING_SRC = Path(
    r"C:\Users\vish8\OneDrive\Documentos\RagMatchAvan-ado\Pncp"
    r"\Base de teste do analisador de atas\docling_md"
)
OUT_DOCLING = BASE / "resultados" / "docling"
OUT_JSON = BASE / "resultados" / "json"

OUT_DOCLING.mkdir(parents=True, exist_ok=True)
OUT_JSON.mkdir(parents=True, exist_ok=True)

arquivos = sorted(DOCLING_SRC.glob("*.docling.md"))[:10]

if not arquivos:
    logger.error("Nenhum arquivo .docling.md encontrado em %s", DOCLING_SRC)
    sys.exit(1)

logger.info("Processando %s atas...", len(arquivos))

for i, src in enumerate(arquivos, 1):
    stem = src.stem.replace(".docling", "")
    logger.info("[%s/%s] %s", i, len(arquivos), src.name)

    # 1. Copia extração Docling
    dst_docling = OUT_DOCLING / src.name
    shutil.copy2(src, dst_docling)
    logger.info("  Docling salvo: %s", dst_docling.name)

    # 2. Lê texto e roda LLM
    texto = src.read_text(encoding="utf-8")
    t0 = time.time()

    try:
        resultado = analisar_ata(texto, id_pncp=stem)
    except Exception as e:
        logger.error("  ERRO no LLM: %s", e)
        resultado = None

    elapsed = time.time() - t0
    logger.info("  LLM concluído em %.1fs", elapsed)

    # 3. Salva JSON
    json_name = f"{stem}.json"
    dst_json = OUT_JSON / json_name
    if resultado is not None:
        payload = resultado_para_dict(resultado)
        dst_json.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("  JSON salvo: %s (%s itens)", dst_json.name, len(resultado.itens))
    else:
        dst_json.write_text(
            json.dumps({"erro": "falha no LLM", "arquivo": src.name}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.warning("  JSON de erro salvo: %s", dst_json.name)

logger.info("Concluído. Resultados em:\n  Docling: %s\n  JSON:    %s", OUT_DOCLING, OUT_JSON)
