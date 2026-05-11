"""
ChatBot para análise de editais de licitação.

Uso:
    python main.py edital.pdf
    python main.py edital.pdf --provider openai
    python main.py edital.pdf --provider ollama --model llama3.2

Variáveis de ambiente (.env):
    LLM_PROVIDER        = ollama | openai   (padrão: ollama)
    OLLAMA_MODEL        = llama3.2          (padrão)
    OLLAMA_EMBED_MODEL  = nomic-embed-text  (padrão)
    OPENAI_API_KEY      = sk-...
    OPENAI_MODEL        = gpt-4o-mini       (padrão)
    TOP_K               = 5                 (chunks recuperados por pergunta)
"""

from __future__ import annotations

import hashlib
import os
import pickle
import sys
import time
docker tag ragmatchavan-ado-api:latest alvarocareli/ragmatchavan-ado-api:latestimport warnings
from pathlib import Path
from typing import List, Tuple

import numpy as np


# Silencia warnings conhecidos de libs de terceiros (docling/pydantic v2).
warnings.filterwarnings(
    "ignore",
    message=r'.*protected namespace "model_".*',
    category=UserWarning,
    module=r"pydantic\._internal\._fields",
)


# ── Logger simples com timestamp ────────────────────────────────────────────
def _log(tag: str, msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] [{tag}] {msg}", flush=True)

def _vlog(tag: str, msg: str) -> None:
    if VERBOSE:
        _log(tag, msg)

# Adiciona o backend ao path para reusar o docling_parser
_BACKEND = Path(__file__).parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

try:
    from app.pipeline.docling_parser import ParsedChunk, ParsedDocument, parse_pdf
    _PARSER_OK = True
except ImportError as _e:
    _log("Aviso", f"docling_parser não encontrado ({_e}). Usando fallback pypdf.")
    _PARSER_OK = False

# ── Config via env ──────────────────────────────────────────────────────────
def _env(name: str, default: str) -> str:
    # Remove espaços/quebras de linha acidentais vindos do .env
    return os.environ.get(name, default).strip()

PROVIDER          = _env("LLM_PROVIDER",       "ollama")
OLLAMA_MODEL      = _env("OLLAMA_MODEL",        "llama3.1:8b")
OLLAMA_EMBED      = _env("OLLAMA_EMBED_MODEL",  "nomic-embed-text")
OPENAI_MODEL      = _env("OPENAI_MODEL",        "gpt-4o-mini")
OPENAI_API_KEY    = _env("OPENAI_API_KEY",      "")
TOP_K             = int(_env("TOP_K",           "5"))
CACHE_DIR         = Path(__file__).parent / ".cache"
VERBOSE           = False  # ligado com --verbose

# ── Chunker por tamanho (usado no fallback) ─────────────────────────────────
_CHUNK_SIZE    = 800   # chars por chunk
_CHUNK_OVERLAP = 100   # overlap entre chunks consecutivos

def _split_text(text: str, page: int, chunk_idx_start: int, ChunkClass) -> list:
    """Divide texto em chunks de ~_CHUNK_SIZE chars com overlap."""
    chunks = []
    idx = chunk_idx_start
    start = 0
    while start < len(text):
        end = start + _CHUNK_SIZE
        # Tenta quebrar em espaço/newline para não cortar palavra
        if end < len(text):
            cut = text.rfind(" ", start, end)
            if cut == -1:
                cut = end
            end = cut
        piece = text[start:end].strip()
        if piece:
            chunks.append(ChunkClass(chunk_idx=idx, text=piece, page=page))
            idx += 1
        start = end - _CHUNK_OVERLAP
    return chunks


# ── Fallback parser sem docling ─────────────────────────────────────────────
def _fallback_parse(pdf_path: str) -> ParsedDocument:
    """Parse básico com pypdf quando docling não está disponível."""
    try:
        import pypdf
    except ImportError:
        raise RuntimeError("Instale pypdf: pip install pypdf")

    from dataclasses import dataclass, field as dc_field

    @dataclass
    class _Chunk:
        chunk_idx: int
        text: str
        page: int | None = None
        section: str | None = None

    @dataclass
    class _Doc:
        filename: str
        full_text: str
        chunks: list = dc_field(default_factory=list)

    reader = pypdf.PdfReader(pdf_path)
    total_pages = len(reader.pages)
    _log("pypdf", f"{total_pages} paginas encontradas — dividindo em chunks de ~{_CHUNK_SIZE} chars")
    chunks, full_parts = [], []
    for i, page in enumerate(reader.pages):
        txt = (page.extract_text() or "").strip()
        if not txt:
            continue
        full_parts.append(txt)
        page_chunks = _split_text(txt, page=i + 1, chunk_idx_start=len(chunks), ChunkClass=_Chunk)
        chunks.extend(page_chunks)
        if (i + 1) % 10 == 0 or (i + 1) == total_pages:
            _log("pypdf", f"Pagina {i + 1}/{total_pages} | total chunks ate agora: {len(chunks)}")

    _log("pypdf", f"Total: {len(chunks)} chunks extraidos de {total_pages} paginas")
    return _Doc(filename=Path(pdf_path).name, full_text="\n\n".join(full_parts), chunks=chunks)


def _rechunk(doc) -> list:
    """Re-divide chunks que excedem _CHUNK_SIZE (evita erro de contexto no embed)."""
    result = []
    oversized = 0
    for chunk in doc.chunks:
        if len(chunk.text) <= _CHUNK_SIZE:
            result.append(chunk)
        else:
            oversized += 1
            sub = _split_text(chunk.text, page=getattr(chunk, "page", None),
                               chunk_idx_start=len(result), ChunkClass=type(chunk))
            result.extend(sub)
    if oversized:
        _log("Parser", f"Re-chunked {oversized} chunks grandes -> {len(result)} chunks finais")
    return result


def _parse(pdf_path: str) -> tuple:
    if _PARSER_OK:
        doc = parse_pdf(pdf_path, filename=Path(pdf_path).name)
    else:
        doc = _fallback_parse(pdf_path)
    chunks = _rechunk(doc)
    return doc, chunks


# ── Embeddings ──────────────────────────────────────────────────────────────
def _embed_ollama(texts: List[str]) -> np.ndarray:
    import ollama
    result = []
    t0 = time.perf_counter()
    for i, t in enumerate(texts):
        resp = ollama.embeddings(model=OLLAMA_EMBED, prompt=t)
        result.append(resp["embedding"])
        if (i + 1) % 25 == 0 or (i + 1) == len(texts):
            elapsed = time.perf_counter() - t0
            speed = (i + 1) / elapsed
            _vlog("Embed", f"{i + 1}/{len(texts)} chunks | {elapsed:.1f}s | {speed:.1f} chunks/s")
    return np.array(result, dtype=np.float32)


def _embed_openai(texts: List[str]) -> np.ndarray:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    result = []
    t0 = time.perf_counter()
    for i in range(0, len(texts), 100):
        batch = texts[i : i + 100]
        resp = client.embeddings.create(model="text-embedding-3-small", input=batch)
        result.extend(item.embedding for item in resp.data)
        done = min(i + 100, len(texts))
        _log("Embed", f"{done}/{len(texts)} chunks | {time.perf_counter() - t0:.1f}s")
    return np.array(result, dtype=np.float32)


def embed(texts: List[str]) -> np.ndarray:
    if PROVIDER == "openai":
        return _embed_openai(texts)
    return _embed_ollama(texts)


# ── Vector Store (NumPy cosine similarity) ──────────────────────────────────
class VectorStore:
    def __init__(self, chunks: list, embeddings: np.ndarray):
        self.chunks = chunks
        # Normaliza para cosine similarity via dot product
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-10
        self.embeddings = embeddings / norms

    def search(self, query_emb: np.ndarray, top_k: int = 5) -> List[Tuple[float, object]]:
        q = query_emb / (np.linalg.norm(query_emb) + 1e-10)
        scores = self.embeddings @ q
        idxs = np.argsort(scores)[::-1][:top_k]
        return [(float(scores[i]), self.chunks[i]) for i in idxs]


# ── Cache (evita re-parsear PDFs grandes) ───────────────────────────────────
def _cache_key(pdf_path: str) -> str:
    stat = Path(pdf_path).stat()
    raw = f"{pdf_path}:{stat.st_size}:{stat.st_mtime}:{PROVIDER}:{OLLAMA_EMBED}"
    return hashlib.md5(raw.encode()).hexdigest()


def load_or_build_store(pdf_path: str) -> VectorStore:
    CACHE_DIR.mkdir(exist_ok=True)
    cache_file = CACHE_DIR / f"{_cache_key(pdf_path)}.pkl"

    if cache_file.exists():
        t0 = time.perf_counter()
        _log("Cache", "Carregando indice do cache...")
        with open(cache_file, "rb") as f:
            chunks, embeddings = pickle.load(f)
        _log("Cache", f"Pronto — {len(chunks)} chunks em {time.perf_counter() - t0:.2f}s")
        return VectorStore(chunks, embeddings)

    pdf_size = Path(pdf_path).stat().st_size / 1024
    _log("Parser", f"Iniciando OCR — arquivo: {Path(pdf_path).name} ({pdf_size:.0f} KB)")
    t_parse = time.perf_counter()
    doc, chunks = _parse(pdf_path)
    t_parse_end = time.perf_counter()
    total_chars = sum(len(c.text) for c in chunks)
    _log("Parser", f"Concluido — {len(chunks)} chunks | {total_chars} chars | {t_parse_end - t_parse:.1f}s")

    embed_model = OLLAMA_EMBED if PROVIDER == "ollama" else "text-embedding-3-small"
    _log("Embed", f"Gerando embeddings com '{embed_model}' para {len(chunks)} chunks...")
    t_emb = time.perf_counter()
    texts = [c.text for c in chunks]
    embeddings = embed(texts)
    t_emb_end = time.perf_counter()
    _log("Embed", f"Concluido — {embeddings.shape} | {t_emb_end - t_emb:.1f}s")

    _log("Cache", f"Salvando indice em {cache_file.name}...")
    with open(cache_file, "wb") as f:
        pickle.dump((chunks, embeddings), f)

    total = time.perf_counter() - t_parse
    _log("Cache", f"Pronto — total de preparacao: {total:.1f}s")
    return VectorStore(chunks, embeddings)


# ── LLM (com streaming) ─────────────────────────────────────────────────────
def _stream_ollama(messages: list) -> str:
    import ollama
    from ollama import ResponseError

    def _to_prompt(msgs: list[dict]) -> str:
        parts = []
        for m in msgs:
            role = (m.get("role") or "user").upper()
            content = (m.get("content") or "").strip()
            if content:
                parts.append(f"[{role}]\n{content}")
        parts.append("[ASSISTANT]\n")
        return "\n\n".join(parts)

    requested_model = OLLAMA_MODEL.strip()
    tried = [requested_model]

    # Alguns ambientes registram o modelo com sufixo :latest.
    if ":" not in requested_model:
        tried.append(f"{requested_model}:latest")

    if requested_model.endswith(":latest"):
        tried.append(requested_model.removesuffix(":latest"))

    # Resolve para o nome exatamente como o servidor anuncia via ollama list.
    try:
        listed_models = [m.model for m in ollama.list().models]
    except Exception:
        listed_models = []

    if requested_model in listed_models:
        tried.insert(0, requested_model)
    else:
        req_base = requested_model.split(":", 1)[0]
        for listed in listed_models:
            listed_base = listed.split(":", 1)[0]
            if listed_base == req_base:
                tried.insert(0, listed)
                break

    # Remove duplicados preservando ordem.
    models_to_try = list(dict.fromkeys(tried))

    full = ""
    last_error = None
    for model_name in models_to_try:
        try:
            for chunk in ollama.chat(model=model_name, messages=messages, stream=True):
                piece = chunk["message"]["content"]
                print(piece, end="", flush=True)
                full += piece
            print()
            return full
        except ResponseError as exc:
            if exc.status_code != 404:
                raise
            last_error = exc
            _log("LLM", f"Modelo '{model_name}' não encontrado no Ollama (404). Tentando próximo alias...")
            # Fallback: alguns ambientes aceitam generate mesmo quando chat falha.
            try:
                prompt = _to_prompt(messages)
                full = ""
                for chunk in ollama.generate(model=model_name, prompt=prompt, stream=True):
                    piece = chunk.get("response", "")
                    print(piece, end="", flush=True)
                    full += piece
                print()
                _log("LLM", f"Usando fallback generate() com modelo '{model_name}'.")
                return full
            except ResponseError as gen_exc:
                if gen_exc.status_code != 404:
                    raise
                _log("LLM", f"Fallback generate também não encontrou '{model_name}' (404).")

    if last_error is not None:
        raise RuntimeError(
            "Nenhum alias do modelo Ollama foi encontrado. "
            f"Tentados: {', '.join(models_to_try)}"
        ) from last_error

    return full


def _stream_openai(messages: list) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    stream = client.chat.completions.create(
        model=OPENAI_MODEL, messages=messages, stream=True
    )
    full = ""
    for chunk in stream:
        piece = chunk.choices[0].delta.content or ""
        print(piece, end="", flush=True)
        full += piece
    print()
    return full


def stream_llm(messages: list) -> str:
    if PROVIDER == "openai":
        return _stream_openai(messages)
    return _stream_ollama(messages)


# ── RAG ─────────────────────────────────────────────────────────────────────
_SYSTEM = (
    "Você é um assistente especializado em editais de licitação brasileiros (pregões). "
    "Responda com base exclusivamente nos trechos do edital fornecidos no contexto. "
    "Se a informação não estiver no contexto, diga claramente. "
    "Seja preciso e mencione seção ou página quando disponível."
)


def _build_user_msg(query: str, results: List[Tuple[float, object]]) -> str:
    parts = []
    for score, chunk in results:
        header = f"[Seção: {getattr(chunk, 'section', None) or 'N/A'}"
        if getattr(chunk, "page", None):
            header += f" | Página: {chunk.page}"
        header += f" | Relevância: {score:.2f}]"
        parts.append(f"{header}\n{chunk.text}")
    context = "\n\n---\n\n".join(parts)
    return f"Trechos do edital:\n\n{context}\n\nPergunta: {query}"


# ── CLI ──────────────────────────────────────────────────────────────────────
def run(pdf_path: str) -> None:
    model_label = OLLAMA_MODEL if PROVIDER == "ollama" else OPENAI_MODEL
    print(f"\n{'='*55}")
    print(f"  ChatBot de Edital")
    print(f"  PDF     : {pdf_path}")
    print(f"  LLM     : {PROVIDER} / {model_label}")
    print(f"  Chunks  : top-{TOP_K} por pergunta")
    print(f"{'='*55}")
    print("  Digite sua pergunta ou 'sair' para encerrar.\n")

    store = load_or_build_store(pdf_path)

    history: list[dict] = [{"role": "system", "content": _SYSTEM}]

    while True:
        try:
            query = input("Você: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nEncerrando.")
            break

        if not query:
            continue
        if query.lower() in ("sair", "exit", "quit", "q"):
            break

        t_emb = time.perf_counter()
        q_emb = embed([query])[0]
        t_search = time.perf_counter()
        results = store.search(q_emb, top_k=TOP_K)
        t_search_end = time.perf_counter()

        _vlog("RAG", f"embed: {t_search - t_emb:.2f}s | busca: {t_search_end - t_search:.3f}s | chunks: {len(results)}")
        for rank, (score, chunk) in enumerate(results, 1):
            page = getattr(chunk, "page", None)
            sec = getattr(chunk, "section", None) or "N/A"
            preview = chunk.text[:60].replace("\n", " ")
            _vlog("RAG", f"  #{rank} score={score:.3f} pag={page} sec='{sec}' | {preview}...")

        user_msg = _build_user_msg(query, results)
        history.append({"role": "user", "content": user_msg})

        print("\nAssistente: ", end="", flush=True)
        t_llm = time.perf_counter()
        response = stream_llm(history)
        _vlog("LLM", f"resposta em {time.perf_counter() - t_llm:.1f}s | {len(response)} chars")
        print()

        history.append({"role": "assistant", "content": response})

        # Mantém histórico em ~10 turnos para não explodir o contexto
        if len(history) > 21:
            history = [history[0]] + history[-20:]


if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
    load_dotenv(dotenv_path=Path(__file__).parent / ".env")

    ap = argparse.ArgumentParser(description="ChatBot RAG para editais de licitação")
    ap.add_argument("pdf", help="Caminho do PDF do edital")
    ap.add_argument("--provider", choices=["ollama", "openai"], default=None)
    ap.add_argument("--model", default=None, help="Modelo LLM (ex: llama3.2, gpt-4o)")
    ap.add_argument("--top-k", type=int, default=None, help="Chunks recuperados por pergunta")
    ap.add_argument("--verbose", action="store_true", help="Mostra logs de RAG e embed durante o chat")
    args = ap.parse_args()

    if args.provider:
        PROVIDER = args.provider
    if args.model:
        if PROVIDER == "ollama":
            OLLAMA_MODEL = args.model
        else:
            OPENAI_MODEL = args.model
    if args.top_k:
        TOP_K = args.top_k
    if args.verbose:
        VERBOSE = True

    run(args.pdf)
