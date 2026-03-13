"""
pipeline/docling_parser.py
──────────────────────────
Recebe um arquivo PDF (path ou bytes) e retorna:
  - texto completo extraído
  - lista de chunks com metadados

Versão otimizada com processamento em lotes (batch) e OCR via Tesseract.
"""

from __future__ import annotations

import gc
import json
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

import pypdf
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    TableStructureOptions,
    TesseractCliOcrOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption

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
# Utilitários para manipulação de PDFs
# ──────────────────────────────────────────

def get_total_pages(pdf_path: Path) -> int:
    """Retorna o número total de páginas de um arquivo PDF."""
    with open(pdf_path, "rb") as f:
        reader = pypdf.PdfReader(f)
        return len(reader.pages)


def extract_pages_to_temp(pdf_path: Path, start_page: int, end_page: int) -> Path:
    """
    Extrai páginas [start_page, end_page) (0‑based) para um PDF temporário.
    Retorna o Path do arquivo criado.
    """
    reader = pypdf.PdfReader(str(pdf_path))
    writer = pypdf.PdfWriter()

    for page_num in range(start_page, end_page):
        writer.add_page(reader.pages[page_num])

    # delete=False porque no Windows não podemos deletar arquivos abertos
    tmp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    with open(tmp_file.name, "wb") as f:
        writer.write(f)

    return Path(tmp_file.name)


def safe_unlink(path: Path) -> None:
    """Tenta deletar o arquivo; ignora se ainda estiver em uso (Windows)."""
    try:
        path.unlink(missing_ok=True)
    except PermissionError:
        logger.warning(
            f"Não foi possível deletar o arquivo temporário agora: {path}. "
            "Ele será removido pelo sistema operacional posteriormente."
        )


# ──────────────────────────────────────────
# Construção do conversor Docling (otimizado)
# ──────────────────────────────────────────

def _build_converter() -> DocumentConverter:
    """
    Configura o Docling com:
      - OCR via Tesseract (executável do sistema)
      - Detecção de tabelas
      - Acelerador automático (CPU/GPU)
      - batch_size para OCR
    """
    ocr_options = TesseractCliOcrOptions(lang=["por"])
    ocr_options.force_full_page_ocr = False  # OCR apenas onde não há texto nativo

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True            # ativa OCR (controlado pelo ocr_options)
    pipeline_options.do_table_structure = True
    pipeline_options.ocr_batch_size = 16
    pipeline_options.table_structure_options = TableStructureOptions(
        do_cell_matching=True
    )
    pipeline_options.ocr_options = ocr_options
    pipeline_options.accelerator_options = AcceleratorOptions(
        num_threads=1, device=AcceleratorDevice.AUTO
    )

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )


_converter: DocumentConverter | None = None  # singleton (usado apenas no modo não‑batch)


def _get_converter() -> DocumentConverter:
    global _converter
    if _converter is None:
        logger.info("Inicializando Docling DocumentConverter (modo não‑batch)...")
        _converter = _build_converter()
    return _converter


# ──────────────────────────────────────────
# Extração de chunks estruturais
# ──────────────────────────────────────────

# Labels que não carregam conteúdo útil — ignorados
_SKIP_LABELS = {"page_footer", "page_header", "page_number", "picture"}


def _extract_chunks_from_doc(doc, base_page: int = 0) -> list[ParsedChunk]:
    """
    Itera pelos elementos do documento Docling e cria chunks por seção.
    - base_page: número da primeira página do documento (para ajustar page absoluta)
    """
    chunks: list[ParsedChunk] = []
    idx = 0
    current_section = "Início"

    for item, _ in doc.iterate_items():
        label = getattr(item, "label", "")
        text = getattr(item, "text", "").strip()
        if not text:
            continue

        # Atualiza seção corrente mas não vira chunk
        if label in ("section_header", "title"):
            current_section = text
            continue

        # Pula elementos sem conteúdo relevante
        if label in _SKIP_LABELS:
            continue

        # Obtém página do item, se disponível
        page_num = None
        if hasattr(item, "page") and item.page is not None:
            page_num = base_page + item.page  # item.page normalmente é 0‑based

        chunks.append(
            ParsedChunk(
                chunk_idx=idx,
                text=text,
                page=page_num,
                section=current_section,
            )
        )
        idx += 1

    return chunks


def _full_text_fallback(full_text: str, filename: str) -> list[ParsedChunk]:
    """
    Fallback: divide o markdown exportado pelo Docling em blocos por
    parágrafo duplo ('\\n\\n'). Usado quando nenhum chunk estrutural
    foi encontrado (PDFs com layout não‑padrão).
    """
    paragraphs = [p.strip() for p in full_text.split("\n\n") if p.strip()]
    chunks = [
        ParsedChunk(chunk_idx=i, text=p, section="fallback")
        for i, p in enumerate(paragraphs)
    ]
    logger.info(f"[Docling] '{filename}' fallback → {len(chunks)} blocos de parágrafo")
    return chunks


# ──────────────────────────────────────────
# Processamento de um lote (batch)
# ──────────────────────────────────────────

def _parse_pdf_batch(
    pdf_path: Path, start_page: int, end_page: int, filename: str
) -> tuple[str, list[ParsedChunk]]:
    """
    Processa um intervalo de páginas [start_page, end_page) (0‑based).
    Retorna (full_text_do_lote, chunks_do_lote_com página absoluta).
    """
    tmp_pdf = extract_pages_to_temp(pdf_path, start_page, end_page)
    try:
        converter = _build_converter()  # cada lote tem seu próprio conversor (não compartilha estado)
        result = converter.convert(tmp_pdf)
        doc = result.document

        full_text = doc.export_to_markdown()
        chunks = _extract_chunks_from_doc(doc, base_page=start_page)

        # Fallback se nenhum chunk estrutural foi encontrado
        if not chunks and full_text.strip():
            logger.warning(
                f"[Docling] '{filename}' (págs {start_page+1}-{end_page}) → "
                "0 chunks estruturais, ativando fallback"
            )
            # O fallback não tem informação de página, então usamos None
            para_chunks = _full_text_fallback(full_text, filename)
            # Ajusta índices (serão recombinados depois)
            chunks = para_chunks

        # Limpeza
        del converter, result, doc
        gc.collect()

        return full_text, chunks

    finally:
        safe_unlink(tmp_pdf)


# ──────────────────────────────────────────
# Função principal (com suporte a batch)
# ──────────────────────────────────────────

def parse_pdf(
    source: Union[str, Path, bytes],
    filename: str = "document.pdf",
    batch_size: Optional[int] = None,
) -> ParsedDocument:
    """
    Processa um PDF com Docling, opcionalmente em lotes para economia de memória.

    Args:
        source:       caminho do arquivo (str/Path) ou bytes do PDF
        filename:     nome original do arquivo (para log)
        batch_size:   se None, processa o documento inteiro de uma vez.
                      se > 0, processa em lotes com esse número de páginas.

    Returns:
        ParsedDocument com texto completo e chunks.
    """
    # Se a entrada for bytes, salva em um arquivo temporário
    if isinstance(source, bytes):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(source)
            tmp_path = Path(tmp.name)
        source_path = tmp_path
        is_temp = True
    else:
        source_path = Path(source)
        is_temp = False

    try:
        total_pages = get_total_pages(source_path)

        # Modo não‑batch (original)
        if batch_size is None or batch_size <= 0 or batch_size >= total_pages:
            logger.info(f"[Docling] Processando '{filename}' inteiro (sem batch)...")
            converter = _get_converter()
            result = converter.convert(source_path)
            doc = result.document
            full_text = doc.export_to_markdown()
            chunks = _extract_chunks_from_doc(doc)
            if not chunks and full_text.strip():
                logger.warning(f"[Docling] '{filename}' → 0 chunks estruturais, ativando fallback")
                chunks = _full_text_fallback(full_text, filename)
            return ParsedDocument(filename=filename, full_text=full_text, chunks=chunks)

        # Modo batch
        logger.info(
            f"[Docling] Processando '{filename}' em lotes de {batch_size} páginas "
            f"(total: {total_pages} págs)"
        )

        batches = [
            (i, min(i + batch_size, total_pages))
            for i in range(0, total_pages, batch_size)
        ]

        all_full_text: list[str] = []
        all_chunks: list[ParsedChunk] = []
        chunk_offset = 0

        for idx, (start, end) in enumerate(batches, 1):
            logger.info(f"  Lote {idx}/{len(batches)}: páginas {start+1}–{end} ...")
            t0 = time.time()

            batch_text, batch_chunks = _parse_pdf_batch(
                source_path, start, end, filename
            )

            # Ajusta índices dos chunks do lote
            for c in batch_chunks:
                c.chunk_idx += chunk_offset

            all_full_text.append(batch_text)
            all_chunks.extend(batch_chunks)
            chunk_offset += len(batch_chunks)

            logger.info(f"    Lote {idx} concluído em {time.time() - t0:.1f}s")

        # Junta os textos dos lotes (separador duplo \n para simular quebra de página)
        full_text_combined = "\n\n".join(all_full_text)

        logger.info(
            f"[Docling] '{filename}' → {len(full_text_combined)} chars, "
            f"{len(all_chunks)} chunks (processamento em lotes)"
        )

        return ParsedDocument(
            filename=filename, full_text=full_text_combined, chunks=all_chunks
        )

    finally:
        # Se criamos um arquivo temporário a partir de bytes, apaga
        if is_temp:
            safe_unlink(source_path)