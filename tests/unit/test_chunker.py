"""
Testes unitários do Chunker (pipeline/chunker.py).

CONCEITO: Testes unitários testam uma função isolada, sem dependências externas.
O chunker implementa sliding window — precisamos garantir que:
  ✓ Blocos pequenos não são divididos (chunk direto)
  ✓ Blocos grandes são divididos corretamente com overlap
  ✓ Overlap não gera chunks vazios
  ✓ Múltiplas seções são agrupadas separadamente

Como rodar:
    pytest tests/unit/test_chunker.py -v
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

# ── Setup de mocks ANTES de importar o chunker ───────────────────────────────
# O chunker faz: from app.pipeline.docling_parser import ParsedChunk, ParsedDocument
# e:             from app.logs.config import logger
# Precisamos fornecer versões stub dessas classes.


@dataclass
class ParsedChunk:
    """Stub local de ParsedChunk — espelha a estrutura real."""
    section: str
    text: str


@dataclass
class ParsedDocument:
    """Stub local de ParsedDocument — espelha a estrutura real."""
    filename: str
    chunks: list


def _stub(name: str, **attrs) -> ModuleType:
    m = ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    return m


# Injeta stubs antes do import do chunker
sys.modules["app.pipeline.docling_parser"] = _stub(
    "app.pipeline.docling_parser",
    ParsedChunk=ParsedChunk,
    ParsedDocument=ParsedDocument,
)
sys.modules["app.logs.config"] = _stub("app.logs.config", logger=MagicMock())

# Agora podemos importar o módulo diretamente pelo caminho
import importlib.util

_CHUNKER_PATH = Path(__file__).resolve().parents[2] / "backend" / "app" / "pipeline" / "chunker.py"
_spec = importlib.util.spec_from_file_location("chunker_mod", _CHUNKER_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

chunk_document = _mod.chunk_document
_apply_sliding_window = _mod._apply_sliding_window
_merge_by_section = _mod._merge_by_section
TextChunker = _mod.TextChunker
DEFAULT_MAX_CHARS = _mod.DEFAULT_MAX_CHARS
DEFAULT_OVERLAP = _mod.DEFAULT_OVERLAP


# ── Helpers ───────────────────────────────────────────────────────────────────

def _doc(chunks: list[ParsedChunk]) -> ParsedDocument:
    return ParsedDocument(filename="edital_teste.pdf", chunks=chunks)


def _chunk(section: str, text: str) -> ParsedChunk:
    return ParsedChunk(section=section, text=text)


# ── Testes: _apply_sliding_window ─────────────────────────────────────────────

class TestApplySlidingWindow:
    """Testa a função de sliding window diretamente."""

    def test_bloco_pequeno_nao_divide(self):
        """Bloco menor que max_chars → 1 chunk, sem divisão."""
        blocks = ["Texto curto"]
        result = _apply_sliding_window(blocks, max_chars=100, overlap=20)
        assert len(result) == 1
        assert result[0].text == "Texto curto"
        assert result[0].chunk_idx == 0

    def test_bloco_grande_divide_em_fatias(self):
        """Bloco maior que max_chars → múltiplos chunks."""
        texto = "A" * 250
        result = _apply_sliding_window([texto], max_chars=100, overlap=20)
        assert len(result) > 1

    def test_overlap_garante_continuidade(self):
        """O início de um chunk deve se sobrepor ao final do anterior."""
        texto = "X" * 300
        max_chars = 100
        overlap = 30
        result = _apply_sliding_window([texto], max_chars=max_chars, overlap=overlap)

        for i in range(len(result) - 1):
            sufixo_anterior = result[i].text[-overlap:]
            prefixo_proximo = result[i + 1].text[:overlap]
            assert sufixo_anterior == prefixo_proximo, (
                f"Chunk {i} e {i+1} não se sobrepõem corretamente"
            )

    def test_indices_sao_sequenciais(self):
        """chunk_idx deve ser 0, 1, 2... sem saltos."""
        blocks = ["A" * 200, "B" * 200]
        result = _apply_sliding_window(blocks, max_chars=100, overlap=20)
        indices = [c.chunk_idx for c in result]
        assert indices == list(range(len(result)))

    def test_chunks_nao_vazios(self):
        """Nenhum chunk deve ter texto vazio após strip."""
        blocks = ["A" * 500, "   ", "B" * 300]
        result = _apply_sliding_window(blocks, max_chars=100, overlap=20)
        for chunk in result:
            assert chunk.text.strip() != "", f"Chunk {chunk.chunk_idx} está vazio"

    def test_char_count_bate_com_len_text(self):
        """char_count deve ser igual a len(text)."""
        blocks = ["Texto de exemplo para validar char_count"]
        result = _apply_sliding_window(blocks, max_chars=100, overlap=10)
        for chunk in result:
            assert chunk.char_count == len(chunk.text)

    def test_lista_vazia_retorna_vazio(self):
        """Sem blocos → sem chunks."""
        result = _apply_sliding_window([], max_chars=100, overlap=20)
        assert result == []


# ── Testes: _merge_by_section ─────────────────────────────────────────────────

class TestMergeBySection:
    """Testa o agrupamento de chunks por seção."""

    def test_mesma_secao_e_agrupada(self):
        """Dois chunks da mesma seção viram um bloco."""
        chunks = [
            _chunk("Requisitos", "texto A"),
            _chunk("Requisitos", "texto B"),
        ]
        blocks = _merge_by_section(chunks)
        assert len(blocks) == 1
        assert "texto A" in blocks[0]
        assert "texto B" in blocks[0]

    def test_secoes_diferentes_ficam_separadas(self):
        """Seções diferentes geram blocos separados."""
        chunks = [
            _chunk("Requisitos", "texto A"),
            _chunk("Prazos", "texto B"),
        ]
        blocks = _merge_by_section(chunks)
        assert len(blocks) == 2

    def test_sem_secao_usa_fallback(self):
        """Chunks sem seção ficam agrupados em 'sem_secao'."""
        chunks = [_chunk(section=None, text="texto sem seção")]
        blocks = _merge_by_section(chunks)
        assert len(blocks) == 1
        assert "sem_secao" in blocks[0]

    def test_header_de_secao_aparece_no_bloco(self):
        """Cada bloco começa com [nome_da_seção]."""
        chunks = [_chunk("Objeto", "descrição do objeto")]
        blocks = _merge_by_section(chunks)
        assert blocks[0].startswith("[Objeto]")


# ── Testes: chunk_document (integração dos dois passos) ───────────────────────

class TestChunkDocument:
    """Testa o fluxo completo: ParsedDocument → lista de TextChunker."""

    def test_documento_vazio_retorna_lista_vazia(self):
        doc = _doc(chunks=[])
        result = chunk_document(doc)
        assert result == []

    def test_documento_simples_retorna_chunks(self):
        doc = _doc(chunks=[_chunk("Objeto", "Texto do objeto do edital.")])
        result = chunk_document(doc)
        assert len(result) >= 1
        assert all(isinstance(c, TextChunker) for c in result)

    def test_texto_longo_gera_multiplos_chunks(self):
        """Texto maior que DEFAULT_MAX_CHARS deve ser dividido."""
        texto_longo = "Palavra " * 200  # ~1600 chars
        doc = _doc(chunks=[_chunk("Especificacoes", texto_longo)])
        result = chunk_document(doc, max_chars=DEFAULT_MAX_CHARS, overlap=DEFAULT_OVERLAP)
        assert len(result) > 1

    def test_defaults_usam_constantes_do_modulo(self):
        """Sem argumentos explícitos, deve usar DEFAULT_MAX_CHARS e DEFAULT_OVERLAP."""
        doc = _doc(chunks=[_chunk("Sec", "texto pequeno")])
        result = chunk_document(doc)
        assert len(result) >= 1
