"""
routers/editais.py
──────────────────
Endpoints para:
  POST /editais/upload          → cria job assíncrono, retorna job_id
  POST /editais/{id}/match      → cria job de matching, retorna job_id
  POST /editais/{id}/requirements → adiciona requisitos (síncrono — rápido)
  GET  /editais                 → lista editais do tenant
  GET  /editais/{id}/results    → resultados de matching salvos

MUDANÇAS COM JOB ORCHESTRATOR:
  - Upload e match agora são assíncronos — retornam job_id imediatamente
  - Cliente consulta GET /jobs/{job_id} para acompanhar progresso
  - Sem mais timeouts em PDFs grandes
"""

from __future__ import annotations

import os
import re
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import Edital, Requirement, Product, DocumentChunk
from app.auth.models import User
from app.auth.dependencies import get_current_user, require_role
from app.jobs.queue import JobQueue
from app.logs.config import logger

router = APIRouter(prefix="/editais", tags=["editais"])
_queue = JobQueue()


class JobCreatedResponse(BaseModel):
    """
    Resposta imediata após criar um job assíncrono.
    O cliente usa o job_id para consultar progresso: GET /jobs/{job_id}
    """
    job_id:  str
    status:  str = "pending"
    message: str


class EditalResponse(BaseModel):
    id:                 int
    filename:           str
    chunks_count:       int
    requirements_count: int
    model_config = {"from_attributes": True}


# ── Upload (assíncrono) ───────────────────────────────────────────────────────

@router.post("/upload", response_model=JobCreatedResponse, status_code=202)
async def upload_edital(
    file:             UploadFile      = File(..., description="PDF do edital"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user:     User            = Depends(require_role("admin", "editor")),
    db:               Session         = Depends(get_db),
):
    """
    Recebe o PDF e cria job assíncrono (OCR → Chunk → Embed).
    Retorna imediatamente com job_id (HTTP 202 Accepted).
    Acompanhe em: GET /jobs/{job_id}
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF são aceitos.")

    pdf_bytes = await file.read()
    tenant_id = current_user.tenant.slug

    logger.info(f"[Editais] Upload recebido | arquivo={file.filename} | tenant={tenant_id}")

    job_id = _queue.criar_job_upload(
        background_tasks = background_tasks,
        pdf_bytes        = pdf_bytes,
        filename         = file.filename,
        tenant_id        = tenant_id,
        user_id          = current_user.id,
        db               = db,
    )

    return JobCreatedResponse(
        job_id  = job_id,
        message = f"PDF '{file.filename}' recebido. Acompanhe em GET /jobs/{job_id}",
    )


# ── Requisitos (síncrono — rápido) ───────────────────────────────────────────

@router.post("/{edital_id}/requirements")
def add_requirements(
    edital_id:    int,
    requirements: list[dict],
    current_user: User    = Depends(require_role("admin", "editor")),
    db:           Session = Depends(get_db),
):
    """
    Adiciona requisitos a um edital já processado.
    Síncrono — cadastrar requisitos é apenas INSERT no banco.
    """
    edital = _get_edital_do_tenant(edital_id, current_user, db)

    added = []
    for r in requirements:
        req = Requirement(
            edital_id    = edital_id,
            attribute    = r.get("attribute"),
            raw_value    = r.get("raw_value"),
            parsed_value = r.get("parsed_value"),
            unit         = r.get("unit"),
        )
        db.add(req)
        added.append(req)

    db.commit()
    return {"edital_id": edital_id, "requirements_added": len(added)}


# ── Matching (assíncrono) ─────────────────────────────────────────────────────

@router.post("/{edital_id}/match", response_model=JobCreatedResponse, status_code=202)
def match_edital(
    edital_id:        int,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user:     User            = Depends(require_role("admin", "editor")),
    db:               Session         = Depends(get_db),
):
    """
    Cria job assíncrono de matching (RAG + Heurísticas + LLM).
    Retorna imediatamente com job_id (HTTP 202 Accepted).
    Acompanhe em: GET /jobs/{job_id}
    """
    edital = _get_edital_do_tenant(edital_id, current_user, db)

    if not edital.requirements:
        raise HTTPException(
            status_code=400,
            detail="Edital sem requisitos. Use POST /editais/{id}/requirements primeiro.",
        )

    produtos = db.query(Product).filter(Product.category == "switch").all()
    if not produtos:
        raise HTTPException(status_code=404, detail="Nenhum produto no catálogo.")

    logger.info(
        f"[Editais] Matching agendado | edital={edital_id} | "
        f"produtos={len(produtos)} | tenant={current_user.tenant.slug}"
    )

    job_id = _queue.criar_job_matching(
        background_tasks = background_tasks,
        edital_id        = edital_id,
        tenant_id        = current_user.tenant.slug,
        user_id          = current_user.id,
        db               = db,
    )

    return JobCreatedResponse(
        job_id  = job_id,
        message = f"Matching iniciado para edital {edital_id}. Acompanhe em GET /jobs/{job_id}",
    )


# ── Listagem e consulta ───────────────────────────────────────────────────────

@router.get("/")
def list_editais(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """Lista editais do tenant autenticado."""
    editais = (
        db.query(Edital)
        .filter(Edital.tenant_id == current_user.tenant.slug)
        .all()
    )
    return [
        {
            "id":           e.id,
            "filename":     e.filename,
            "chunks":       len(e.chunks),
            "requirements": len(e.requirements),
            "parsed_at":    e.parsed_at,
        }
        for e in editais
    ]


@router.get("/{edital_id}/results")
def get_results(
    edital_id:    int,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """Retorna resultados de matching salvos para um edital."""
    edital = _get_edital_do_tenant(edital_id, current_user, db)

    results = []
    for req in edital.requirements:
        for mr in req.matching_results:
            results.append({
                "product":   mr.product.model,
                "attribute": req.attribute,
                "status":    mr.status,
                "score":     mr.score,
                "reasoning": mr.llm_reasoning,
            })

    return {"edital_id": edital_id, "results": results}


# ── Chat RAG ─────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    question: str
    model: str = "gpt"           # "gpt" ou "ollama"
    history: List[ChatMessage] = []

class ChatSource(BaseModel):
    chunk_idx: int
    text: str

class ChatResponse(BaseModel):
    answer: str
    sources: List[ChatSource]
    model_used: str


def _score_chunk(text: str, question_words: set[str]) -> int:
    """Pontuação simples por frequência de palavras da pergunta no chunk."""
    text_lower = text.lower()
    return sum(1 for w in question_words if len(w) > 3 and w in text_lower)


def _find_relevant_chunks(
    chunks: list,
    question: str,
    top_k: int = 5,
) -> list:
    """Retorna os chunks mais relevantes via busca por palavras-chave."""
    # Remove stopwords PT básico para não enviesar o score
    stopwords = {"que", "para", "com", "uma", "por", "como", "mais", "este", "esta",
                 "esse", "essa", "pelo", "pela", "sobre", "qual", "quando", "onde"}
    words = {w for w in re.sub(r"[^\w\s]", " ", question.lower()).split()
             if w not in stopwords}

    scored = sorted(chunks, key=lambda c: _score_chunk(c.text, words), reverse=True)
    return scored[:top_k]


def _call_llm_chat(messages: list[dict], model: str) -> tuple[str, str]:
    """Chama GPT ou Ollama e retorna (resposta, nome_modelo)."""
    if model == "gpt":
        try:
            from openai import OpenAI
            client = OpenAI()
            model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            response = client.responses.create(
                model=model_name,
                input=messages,
            )
            return response.output_text.strip(), model_name
        except Exception as e:
            logger.error("[Chat] Falha GPT: %s", e)
            raise HTTPException(status_code=502, detail=f"Erro ao chamar GPT: {e}")
    else:
        try:
            import ollama
            ollama_model = os.getenv("OLLAMA_MODEL", "llama3")
            resp = ollama.chat(model=ollama_model, messages=messages)
            return resp["message"]["content"].strip(), ollama_model
        except Exception as e:
            logger.error("[Chat] Falha Ollama: %s", e)
            raise HTTPException(status_code=502, detail=f"Erro ao chamar Ollama: {e}")


@router.post("/{edital_id}/chat", response_model=ChatResponse)
def chat_edital(
    edital_id:    int,
    req:          ChatRequest,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Mini-RAG: responde perguntas sobre um edital específico.

    Fluxo:
      1. Busca chunks relevantes do edital via keyword scoring
      2. Monta contexto com os top-5 chunks
      3. Chama GPT ou Ollama com histórico de mensagens
      4. Retorna resposta + fontes usadas
    """
    edital = _get_edital_do_tenant(edital_id, current_user, db)

    if not edital.chunks:
        raise HTTPException(
            status_code=400,
            detail="Edital ainda não processado (sem chunks). Aguarde o OCR concluir.",
        )

    # 1. Recupera chunks relevantes
    relevant = _find_relevant_chunks(edital.chunks, req.question, top_k=5)
    context  = "\n\n---\n\n".join(c.text for c in relevant)

    # 2. Monta system prompt com contexto do edital
    system_prompt = (
        f"Você é um assistente especializado em licitações públicas brasileiras da empresa Tor Tecnologias.\n"
        f"Responda com base APENAS no conteúdo do edital '{edital.filename}' fornecido abaixo.\n"
        f"Se a informação não estiver no edital, diga claramente que não encontrou.\n"
        f"Seja objetivo e direto. Use português do Brasil.\n\n"
        f"CONTEÚDO DO EDITAL:\n{context}"
    )

    messages = [{"role": "system", "content": system_prompt}]

    # 3. Adiciona histórico recente (últimas 3 trocas = 6 mensagens)
    for msg in req.history[-6:]:
        messages.append({"role": msg.role, "content": msg.content})

    messages.append({"role": "user", "content": req.question})

    # 4. Chama o LLM
    answer, model_used = _call_llm_chat(messages, req.model)

    logger.info(
        "[Chat] edital=%s | modelo=%s | chunks=%s | pergunta=%.60s",
        edital_id, model_used, len(relevant), req.question,
    )

    sources = [
        ChatSource(chunk_idx=c.chunk_idx, text=c.text[:300])
        for c in relevant
        if _score_chunk(c.text, set(req.question.lower().split())) > 0
    ]

    return ChatResponse(answer=answer, sources=sources, model_used=model_used)


# ── Helper — isolamento de tenant ─────────────────────────────────────────────

def _get_edital_do_tenant(edital_id: int, current_user: User, db: Session) -> Edital:
    """Busca edital e garante que pertence ao tenant do usuário."""
    edital = (
        db.query(Edital)
        .filter(
            Edital.id        == edital_id,
            Edital.tenant_id == current_user.tenant.slug,
        )
        .first()
    )
    if not edital:
        raise HTTPException(status_code=404, detail="Edital não encontrado.")
    return edital