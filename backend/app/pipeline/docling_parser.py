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
import time
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


def _env_flag(name: str, default: bool = True) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return str(v).strip().lower() not in {"0", "false", "no", "off"}


def _try_pdf_page_count(source: Union[str, Path, bytes], filename: str) -> int | None:
    """Tenta obter número de páginas do PDF para diagnóstico de páginas perdidas."""
    try:
        import pypdf
    except Exception:
        return None

    try:
        if isinstance(source, bytes):
            reader = pypdf.PdfReader(BytesIO(source))
        else:
            reader = pypdf.PdfReader(str(source))
        return len(reader.pages)
    except Exception as exc:
        logger.warning("[Docling] Falha ao contar páginas (pypdf) para '%s': %s", filename, exc)
        return None


def _try_pdf_size_bytes(source: Union[str, Path, bytes]) -> int | None:
    try:
        if isinstance(source, bytes):
            return len(source)
        return Path(source).stat().st_size
    except Exception:
        return None


_MARKER_PATTERNS: list[str] = [
    r"LOTE\s+\d+",
    r"Item\s*:\s*\d+",
    r"Unidade\s*:\s*\S+",
    r"Quant(?:\.|idade)\s*:\s*\d+",
    r"Descrição\s*:\s*",
    r"Marca\s*:\s*",
    r"Modelo\s*:\s*",
    r"Lance\s*:\s*",
    r"Num\s*:\s*\d+",
    r"Val\.\s*Ref\.\s*:\s*",
    r"Total\s*Item\s*:\s*",
    r"Valor\s*Unit\.?\s*:\s*",
    r"Total\s*:\s*",
]


def _normalize_extracted_text(text: str) -> str:
    """Normaliza quebras de linha/colagens típicas de OCR.

    Objetivo: reduzir casos onde marcadores (LOTE, Item, etc.) ficam colados
    em outras palavras/linhas, o que costuma "sumir" linhas na leitura do LLM.
    """
    if not text:
        return ""

    t = text.replace("\r\n", "\n").replace("\r", "\n")

    # Colagens recorrentes (ex.: "150\n\nKGPESO" ou "KGPESO")
    t = re.sub(r"(?i)\bKG(?=PESO\b)", "KG\n\n", t)

    # Garante que marcadores iniciem em nova linha quando estiverem colados.
    for pat in _MARKER_PATTERNS:
        t = re.sub(rf"(?i)(?<!\n)({pat})", r"\n\1", t)

    # Colapsa excesso de linhas em branco
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t


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
    normalize_text = _env_flag("DOCLING_NORMALIZE_TEXT", default=True)
    page_count = _try_pdf_page_count(source, filename)
    size_bytes = _try_pdf_size_bytes(source)
    size_kb = f"{(size_bytes / 1024):.1f}KB" if size_bytes is not None else "n/a"

    if DOCLING_DISPONIVEL:
        converter = _get_converter()

        t0 = time.perf_counter()

        # Se vier como bytes, salva em temp
        try:
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
        except Exception as exc:
            logger.exception(
                "[Docling] Falha no convert('%s') pages=%s size=%s: %s — usando fallback pypdf",
                filename,
                page_count if page_count is not None else "n/a",
                size_kb,
                exc,
            )
            full_text = _extrair_texto_pypdf(source, filename)
            if normalize_text:
                full_text = _normalize_extracted_text(full_text)
            raw_chunks = []
            if full_text.strip():
                raw_chunks = _full_text_fallback(full_text, filename)
            logger.info(
                "[Docling] '%s' fallback(pypdf) pages=%s size=%s chars=%s chunks=%s",
                filename,
                page_count if page_count is not None else "n/a",
                size_kb,
                len(full_text),
                len(raw_chunks),
            )
            return ParsedDocument(filename=filename, full_text=full_text, chunks=raw_chunks)

        t_convert = time.perf_counter()

        doc = result.document

        # Exporta markdown (preserva estrutura de seções e tabelas)
        full_text_raw: str = doc.export_to_markdown()
        t_export = time.perf_counter()
        full_text = _normalize_extracted_text(full_text_raw) if normalize_text else full_text_raw

        # Extrai chunks por elemento estrutural (parágrafos / tabelas)
        raw_chunks = _extract_chunks_from_doc(doc, normalize_text=normalize_text)
        t_chunks = time.perf_counter()

        logger.info(
            "[Docling] '%s' pages=%s size=%s convert=%.2fs export=%.2fs chunks=%.2fs markdown_chars=%s chunks=%s",
            filename,
            page_count if page_count is not None else "n/a",
            size_kb,
            t_convert - t0,
            t_export - t_convert,
            t_chunks - t_export,
            len(full_text),
            len(raw_chunks),
        )
    else:
        global _docling_warning_emitted
        if not _docling_warning_emitted:
            logger.warning("Docling não encontrado. Usando fallback sem OCR (texto nativo do PDF).")
            _docling_warning_emitted = True
        full_text = _extrair_texto_pypdf(source, filename)
        if normalize_text:
            full_text = _normalize_extracted_text(full_text)
        raw_chunks = []

    # Fallback: se não extraiu nenhum chunk estrutural, divide o markdown por parágrafos
    if not raw_chunks and full_text.strip():
        logger.warning(f"[Docling] '{filename}' -> 0 chunks estruturais, ativando fallback por paragrafo")
        raw_chunks = _full_text_fallback(full_text, filename)

    logger.info(
        "[Docling] '%s' pages=%s size=%s -> %s chars, %s chunks",
        filename,
        page_count if page_count is not None else "n/a",
        size_kb,
        len(full_text),
        len(raw_chunks),
    )
    return ParsedDocument(filename=filename, full_text=full_text, chunks=raw_chunks)


# ──────────────────────────────────────────
# Extração de chunks estruturais
# ──────────────────────────────────────────

# Labels que não carregam conteúdo útil — ignorados
_SKIP_LABELS = {"page_footer", "page_header", "page_number", "picture"}

def _extract_chunks_from_doc(doc, normalize_text: bool = True) -> list[ParsedChunk]:
    """
    Itera pelos elementos do documento Docling e cria chunks por seção.
    Aceita QUALQUER label de conteúdo (parágrafo, tabela, lista, etc.),
    pulando apenas elementos decorativos (rodapé, nº de página, imagem).
    """
    chunks: list[ParsedChunk] = []
    idx = 0
    current_section = "Início"

    total_items = 0
    skipped_empty = 0
    skipped_label = 0
    section_headers = 0
    page_chunks: dict[int | str, int] = {}   # page -> nº de chunks nessa página

    for item, _ in doc.iterate_items():
        total_items += 1
        label = getattr(item, "label", "")
        text = getattr(item, "text", "")
        text = text.strip() if isinstance(text, str) else ""

        if not text:
            skipped_empty += 1
            continue

        if normalize_text:
            text = _normalize_extracted_text(text)

        # Tentativa best-effort de capturar número de página, se o item carregar.
        page = (
            getattr(item, "page", None)
            or getattr(item, "page_no", None)
            or getattr(item, "page_number", None)
        )
        if isinstance(page, str) and page.isdigit():
            page = int(page)
        if not isinstance(page, int):
            page = None

        # Atualiza seção corrente mas não vira chunk
        if label in ("section_header", "title"):
            current_section = text
            section_headers += 1
            continue

        # Pula elementos sem conteúdo relevante
        if label in _SKIP_LABELS:
            skipped_label += 1
            continue

        page = _guess_page(item)

        chunks.append(ParsedChunk(
            chunk_idx = idx,
            text      = text,
            page      = page,
            section   = current_section,
        ))
        idx += 1

        # Contabiliza chunk por página para diagnóstico
        page_key: int | str = page if page is not None else "?"
        page_chunks[page_key] = page_chunks.get(page_key, 0) + 1

    logger.info(
        "[Docling] iterate_items: total=%s sections=%s skipped_empty=%s skipped_label=%s chunks=%s",
        total_items,
        section_headers,
        skipped_empty,
        skipped_label,
        len(chunks),
    )

    # Log por página — ajuda a identificar páginas inteiras perdidas
    if page_chunks:
        sorted_pages = sorted(
            page_chunks.items(),
            key=lambda kv: (0, kv[0]) if isinstance(kv[0], int) else (1, str(kv[0])),
        )
        for pg_key, pg_count in sorted_pages:
            logger.info("[Docling]   page=%s chunks=%s", pg_key, pg_count)

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