'''
Recebe um arquivo PDF e retorna:
    - texto completo extraido
    - lista de chunks com metadados
'''

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat
from app.logs.config import logger


# ──────────────────────────────────────────
# Tipos de saida
# ──────────────────────────────────────────

@dataclass
class ParsedChunk:
    chunk_idx: int
    text: str
    page: int | None = None
    section: str | None = None

@dataclass
class parsedDocument:
    filename: str
    full_text: str
    chunks: list[ParsedChunk] = field(default_factory=list)

# Alias com inicial maiúscula para consistência
ParsedDocument = parsedDocument


# ──────────────────────────────────────────
# Singleton do converter
# ──────────────────────────────────────────

def _build_converter() -> DocumentConverter:
    """Configura o Docling com OCR ativado para PDFs escaneados."""
    pipeline_opts = PdfPipelineOptions(do_ocr=True, do_table_structure=True)
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_opts)}
    )

_converter: DocumentConverter | None = None

def _get_converter() -> DocumentConverter:
    """Retorna (ou cria) o singleton do DocumentConverter."""
    global _converter
    if _converter is None:
        _converter = _build_converter()
    return _converter


# ──────────────────────────────────────────
# Parser principal
# ──────────────────────────────────────────

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
    full_text: str = doc.export_to_markdown()

    raw_chunks = _extract_chunks_from_doc(doc)

    # Fallback: se nenhum chunk estrutural foi encontrado, divide pelo full_text
    if not raw_chunks and full_text.strip():
        logger.warning(f"[Docling] '{filename}' → nenhum chunk estrutural; usando fallback por parágrafo")
        raw_chunks = _full_text_fallback(full_text)

    logger.info(f"[Docling] '{filename}' → {len(full_text)} chars, {len(raw_chunks)} chunks")
    return ParsedDocument(filename=filename, full_text=full_text, chunks=raw_chunks)


# ──────────────────────────────────────────
# Extração de chunks estruturais
# ──────────────────────────────────────────

def _extract_chunks_from_doc(doc) -> list[ParsedChunk]:
    """
    Itera pelos elementos do documento Docling e cria chunks por seção.
    Aceita qualquer label que contenha texto — filtra apenas elementos vazios.
    """
    chunks: list[ParsedChunk] = []
    idx = 0
    current_section = "Início"

    SECTION_LABELS = {"section_header", "title", "page_header"}
    SKIP_LABELS    = {"page_footer", "page_number", "picture"}

    for item, _ in doc.iterate_items():
        label = str(getattr(item, "label", "") or "")
        text  = str(getattr(item, "text",  "") or "").strip()

        if not text:
            continue
        if label in SKIP_LABELS:
            continue
        if label in SECTION_LABELS:
            current_section = text
            continue

        chunks.append(ParsedChunk(
            chunk_idx=idx,
            text=text,
            section=current_section,
        ))
        idx += 1

    return chunks


def _full_text_fallback(full_text: str) -> list[ParsedChunk]:
    """
    Fallback: divide o full_text em blocos separados por linha em branco.
    Usado quando o Docling não retorna chunks estruturais.
    """
    chunks: list[ParsedChunk] = []
    blocks = [b.strip() for b in full_text.split("\n\n") if b.strip()]
    for idx, block in enumerate(blocks):
        chunks.append(ParsedChunk(chunk_idx=idx, text=block, section="Documento"))
    return chunks
