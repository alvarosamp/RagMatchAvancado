"""
pipeline/docling_parser.py
──────────────────────────
Recebe um arquivo PDF (path ou bytes) e retorna:
  - texto completo extraído
  - lista de chunks com metadados
"""

from __future__ import annotations

import re
import os
import tempfile
from io import BytesIO
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

try:
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.datamodel.base_models import InputFormat
    DOCLING_DISPONIVEL = True
except ImportError:
    DocumentConverter = None  # type: ignore[assignment]
    PdfFormatOption = None  # type: ignore[assignment]
    PdfPipelineOptions = None  # type: ignore[assignment]
    InputFormat = None  # type: ignore[assignment]
    DOCLING_DISPONIVEL = False

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
    if not DOCLING_DISPONIVEL:
        raise RuntimeError("Docling não está disponível neste ambiente")

    pipeline_opts = PdfPipelineOptions(do_ocr=True, do_table_structure=True)
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_opts)}
    )


_converter: DocumentConverter | None = None  # singleton
_docling_warning_emitted = False


def _get_converter() -> DocumentConverter:
    global _converter
    if _converter is None:
        logger.info("Inicializando Docling DocumentConverter...")
        _converter = _build_converter()
    return _converter


def _extrair_texto_pypdf(source: Union[str, Path, bytes], filename: str) -> str:
    """Fallback sem OCR: extrai texto nativo do PDF com pypdf."""
    try:
        import pypdf
    except ImportError:
        logger.warning("pypdf não encontrado; retorno de texto vazio para '%s'", filename)
        return ""

    try:
        if isinstance(source, bytes):
            reader = pypdf.PdfReader(BytesIO(source))
        else:
            reader = pypdf.PdfReader(str(source))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        logger.warning("Falha no fallback pypdf para '%s': %s", filename, exc)
        return ""


def parse_pdf(source: Union[str, Path, bytes], filename: str = "document.pdf") -> ParsedDocument:
    """
    Processa um PDF com Docling.

    Args:
        source:   caminho do arquivo (str/Path) ou bytes do PDF
        filename: nome original do arquivo (para log)

    Returns:
        ParsedDocument com texto completo e chunks
    """
    if DOCLING_DISPONIVEL:
        converter = _get_converter()

        # Se vier como bytes, salva em temp
        if isinstance(source, bytes):
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
    else:
        global _docling_warning_emitted
        if not _docling_warning_emitted:
            logger.warning("Docling não encontrado. Usando fallback sem OCR (texto nativo do PDF).")
            _docling_warning_emitted = True
        full_text = _extrair_texto_pypdf(source, filename)
        raw_chunks = []

    # Fallback: se não extraiu nenhum chunk estrutural, divide o markdown por parágrafos
    if not raw_chunks and full_text.strip():
        logger.warning(f"[Docling] '{filename}' -> 0 chunks estruturais, ativando fallback por paragrafo")
        raw_chunks = _full_text_fallback(full_text, filename)

    logger.info(f"[Docling] '{filename}' -> {len(full_text)} chars, {len(raw_chunks)} chunks")
    return ParsedDocument(filename=filename, full_text=full_text, chunks=raw_chunks)


# ──────────────────────────────────────────
# Extração de chunks estruturais
# ──────────────────────────────────────────

# Labels que não carregam conteúdo útil — ignorados
_SKIP_LABELS = {"page_footer", "page_header", "page_number", "picture"}

def _extract_chunks_from_doc(doc) -> list[ParsedChunk]:
    """
    Itera pelos elementos do documento Docling e cria chunks por seção.
    Aceita QUALQUER label de conteúdo (parágrafo, tabela, lista, etc.),
    pulando apenas elementos decorativos (rodapé, nº de página, imagem).
    """
    chunks: list[ParsedChunk] = []
    idx = 0
    current_section = "Início"

    for item, _ in doc.iterate_items():
        label = getattr(item, "label", "")
        text  = getattr(item, "text",  "").strip()

        if not text:
            continue

        # Atualiza seção corrente mas não vira chunk
        if label in ("section_header", "title"):
            current_section = text
            continue

        # Pula elementos sem conteúdo relevante
        if label in _SKIP_LABELS:
            continue

        chunks.append(ParsedChunk(
            chunk_idx = idx,
            text      = text,
            section   = current_section,
        ))
        idx += 1

    return chunks


def _full_text_fallback(full_text: str, filename: str) -> list[ParsedChunk]:
    """
    Fallback: divide o markdown exportado pelo Docling em blocos por
    parágrafo duplo ('\\n\\n'). Usado quando nenhum chunk estrutural
    foi encontrado (PDFs com layout não-padrão).
    """
    paragraphs = [p.strip() for p in full_text.split("\n\n") if p.strip()]
    chunks = [
        ParsedChunk(chunk_idx=i, text=p, section="fallback")
        for i, p in enumerate(paragraphs)
    ]
    logger.info(f"[Docling] '{filename}' fallback -> {len(chunks)} blocos de paragrafo")
    return chunks