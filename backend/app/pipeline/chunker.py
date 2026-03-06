'''
Recebo os chunks do Docling e aplica uma estrategia de sliding window
para garantir contexto suficiente em cada chunk antes de embeder
'''
from __future__ import annotations
from dataclasses import dataclass
from app.pipeline.docling_parser import ParsedChunk, parsedDocument
from app.logs.config import logger

@dataclass
class TextChunker:
    chunk_idx : int
    text : str
    char_count : int
    
    
#Configuração
DEFAULT_MAX_CHARS =1_000 # Tamanho maximo de cada chunk
DEFAULT_OVERLAP = 150  #sobreposição entre chunks consecutivos


#Chunker

def chunk_document(
    doc : parsedDocument,
    max_chars : int = DEFAULT_MAX_CHARS,
    overlap : int = DEFAULT_OVERLAP,
) -> list[TextChunker]:
    '''
    Estrategia em dois passos :
    1. Agrupa os chunks do Docling por seção (mantendo contexto semantico)
    2. Aplica sliding window com overlap para chunks maiores que max_chars
    '''
    merged = _merge_by_section(doc.chunks)
    final  = _apply_sliding_window(merged, max_chars, overlap)

    logger.info(
        f"[Chunker] '{doc.filename}' → {len(doc.chunks)} chunks Docling "
        f"→ {len(final)} chunks finais"
    )
    return final

def _merge_by_section(chunks: list[ParsedChunk]) -> list[str]:
    """Agrupa chunks da mesma seção em blocos de texto."""
    sections: dict[str, list[str]] = {}
    for c in chunks:
        key = c.section or "sem_secao"
        sections.setdefault(key, []).append(c.text)

    merged = []
    for section, texts in sections.items():
        block = f"[{section}]\n" + "\n".join(texts)
        merged.append(block)
    return merged


def _apply_sliding_window(
    blocks: list[str],
    max_chars: int,
    overlap: int,
) -> list[TextChunk]:
    """
    Se um bloco cabe em max_chars → chunk direto.
    Se não → divide em fatias com sobreposição.
    """
    result: list[TextChunk] = []
    idx = 0

    for block in blocks:
        if len(block) <= max_chars:
            result.append(TextChunk(chunk_idx=idx, text=block, char_count=len(block)))
            idx += 1
        else:
            start = 0
            while start < len(block):
                end   = min(start + max_chars, len(block))
                slice_ = block[start:end].strip()
                if slice_:
                    result.append(TextChunk(chunk_idx=idx, text=slice_, char_count=len(slice_)))
                    idx += 1
                if end == len(block):
                    break
                start = end - overlap  # sobreposição
    return result
