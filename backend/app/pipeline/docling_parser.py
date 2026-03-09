"""
pipeline/docling_parser.py
──────────────────────────
Recebe um arquivo PDF (path ou bytes) e retorna:
  - texto completo extraído
  - lista de chunks com metadados
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat

from app.logs.config import logger


# ──────────────────────────────────────────
# Tipos de saída
# ──────────────────────────────────────────

@dataclass
class ParsedChunk:
    chunk_idx: int
    text: str
    page: int | None = None
    section: str | None = None


@dataclass
class ParsedDocument:
    filename: str
    full_text: str
    chunks: list[ParsedChunk] = field(default_factory=list)


# ──────────────────────────────────────────
# Parser principal
# ──────────────────────────────────────────

def _build_converter() -> DocumentConverter:
    """Configura o Docling com OCR ativado para PDFs escaneados."""
    pipeline_opts = PdfPipelineOptions(do_ocr=True, do_table_structure=True)
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_opts)}
    )


_converter: DocumentConverter | None = None  # singleton


def _get_converter() -> DocumentConverter:
    global _converter
    if _converter is None:
        logger.info("Inicializando Docling DocumentConverter...")
        _converter = _build_converter()
    return _converter


def parse_pdf(source: Union[str, Path, bytes], filename: str = "document.pdf") -> ParsedDocument:
    """
    Processa um PDF com Docling.

    Args:
        source:   caminho do arquivo (str/Path) ou bytes do PDF
        filename: nome original do arquivo (para log)

    Returns:
        ParsedDocument com texto completo e chunks
    """
    converter = _get_converter()

    # Se vier como bytes, salva em temp
    if isinstance(source, bytes):
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(source)
            tmp_path = tmp.name
        try:
            result = converter.convert(tmp_path)
        finally:
            os.unlink(tmp_path)
    else:
        result = converter.convert(str(source))

    doc = result.document

    # Exporta markdown (preserva estrutura de seções e tabelas)
    full_text: str = doc.export_to_markdown()

    # Extrai chunks por elemento estrutural (parágrafos / tabelas)
    raw_chunks = _extract_chunks_from_doc(doc)

    logger.info(f"[Docling] '{filename}' → {len(full_text)} chars, {len(raw_chunks)} chunks")
    return ParsedDocument(filename=filename, full_text=full_text, chunks=raw_chunks)


# ──────────────────────────────────────────
# Extração de chunks estruturais
# ──────────────────────────────────────────

def _extract_chunks_from_doc(doc) -> list[ParsedChunk]:
    """
    Itera pelos elementos do documento Docling e cria chunks por seção.
    Cada item de texto relevante (parágrafo, célula de tabela, título) vira um chunk.
    """
    chunks: list[ParsedChunk] = []
    idx = 0
    current_section = "Início"

    for item, _ in doc.iterate_items():
        label = getattr(item, "label", "")
        text  = getattr(item, "text",  "").strip()

        if not text:
            continue

        if label in ("section_header", "title"):
            current_section = text
            continue                          # seção vira contexto, não chunk

        if label in ("paragraph", "list_item", "table", "caption", "footnote"):
            chunks.append(ParsedChunk(
                chunk_idx = idx,
                text      = text,
                section   = current_section,
            ))
            idx += 1

    return chunks