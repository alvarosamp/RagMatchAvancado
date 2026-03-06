"""
routers/editais.py
──────────────────
Endpoints para:
  POST /editais/upload   → faz OCR, chunka, embeda e salva no banco
  POST /editais/{id}/match → roda matching para todos os switches
  GET  /editais           → lista editais
  GET  /editais/{id}/results → resultados de matching
"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import Edital, Requirement, Product
from app.pipeline.docling_parser import parse_pdf
from app.pipeline.chunker import chunk_document
from app.vector.pgvector_store import save_chunks
from app.services.matching_engine import run_matching
from app.logs.config import logger

router = APIRouter(prefix="/editais", tags=["editais"])


# ──────────────────────────────────────────
# Schemas de resposta
# ──────────────────────────────────────────

class EditalResponse(BaseModel):
    id: int
    filename: str
    chunks_count: int
    requirements_count: int

    class Config:
        from_attributes = True


# ──────────────────────────────────────────
# Upload + Processamento
# ──────────────────────────────────────────

@router.post("/upload", response_model=EditalResponse)
async def upload_edital(
    file:      UploadFile = File(..., description="PDF do edital"),
    tenant_id: Optional[str] = Form(None),
    db:        Session = Depends(get_db),
):
    """
    Pipeline completo:
    1. Recebe o PDF
    2. Docling → extrai texto e estrutura
    3. Chunker → divide em blocos semânticos
    4. Embedder + PGVector → gera e salva embeddings
    5. Salva Edital no banco
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF são aceitos.")

    logger.info(f"[Editais] Recebendo: {file.filename} (tenant={tenant_id})")
    pdf_bytes = await file.read()

    # 1. Parse com Docling
    parsed_doc = parse_pdf(pdf_bytes, filename=file.filename)

    # 2. Salva edital no banco
    edital = Edital(
        filename  = file.filename,
        full_text = parsed_doc.full_text,
        tenant_id = tenant_id,
    )
    db.add(edital)
    db.flush()  # gera edital.id sem commit final

    # 3. Chunking
    chunks = chunk_document(parsed_doc)

    # 4. Embeddings + pgvector
    saved = save_chunks(db, edital, chunks)

    db.commit()
    db.refresh(edital)

    logger.info(f"[Editais] Edital {edital.id} salvo com {saved} chunks")
    return EditalResponse(
        id                  = edital.id,
        filename            = edital.filename,
        chunks_count        = saved,
        requirements_count  = len(edital.requirements),
    )


# ──────────────────────────────────────────
# Importar requisitos (JSON manual ou extraído)
# ──────────────────────────────────────────

@router.post("/{edital_id}/requirements")
def add_requirements(
    edital_id:    int,
    requirements: list[dict],
    db: Session = Depends(get_db),
):
    """
    Importa lista de requisitos para um edital.
    
    Payload esperado:
    [
      {"attribute": "portas_rj45", "raw_value": "mínimo 16 portas RJ-45", "parsed_value": "16", "unit": "portas"},
      ...
    ]
    """
    edital = db.get(Edital, edital_id)
    if not edital:
        raise HTTPException(404, detail="Edital não encontrado")

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


# ──────────────────────────────────────────
# Matching
# ──────────────────────────────────────────

@router.post("/{edital_id}/match")
def match_edital(
    edital_id: int,
    db: Session = Depends(get_db),
):
    """
    Executa o matching de TODOS os produtos do catálogo
    contra os requisitos do edital.

    Retorna relatório consolidado por produto.
    """
    edital = db.get(Edital, edital_id)
    if not edital:
        raise HTTPException(404, "Edital não encontrado")

    requirements = edital.requirements
    if not requirements:
        raise HTTPException(400, "Edital não possui requisitos cadastrados. Use POST /editais/{id}/requirements primeiro.")

    products = db.query(Product).filter(Product.category == "switch").all()
    if not products:
        raise HTTPException(404, "Nenhum produto no catálogo")

    logger.info(f"[Matching] Edital {edital_id}: {len(products)} produtos × {len(requirements)} requisitos")

    reports = []
    for product in products:
        report = run_matching(db, product, requirements)
        reports.append({
            "model":         report.product_model,
            "overall_score": report.overall_score,
            "status":        report.status,
            "summary":       report.summary,
            "details": [
                {
                    "attribute":   d.attribute,
                    "required":    d.required,
                    "found":       d.found,
                    "final_score": d.final_score,
                    "status":      d.status,
                    "reasoning":   d.reasoning,
                }
                for d in report.details
            ],
        })

    # Ordena por score decrescente
    reports.sort(key=lambda r: r["overall_score"], reverse=True)

    return {
        "edital_id":     edital_id,
        "total_products": len(reports),
        "best_match":    reports[0] if reports else None,
        "results":       reports,
    }


# ──────────────────────────────────────────
# Listagem e consulta
# ──────────────────────────────────────────

@router.get("/")
def list_editais(db: Session = Depends(get_db)):
    """Lista todos os editais cadastrados."""
    editais = db.query(Edital).all()
    return [
        {
            "id":       e.id,
            "filename": e.filename,
            "chunks":   len(e.chunks),
            "requirements": len(e.requirements),
            "parsed_at": e.parsed_at,
        }
        for e in editais
    ]


@router.get("/{edital_id}/results")
def get_results(edital_id: int, db: Session = Depends(get_db)):
    """Retorna resultados de matching já salvos para um edital."""
    edital = db.get(Edital, edital_id)
    if not edital:
        raise HTTPException(404, "Edital não encontrado")

    results = []
    for req in edital.requirements:
        for mr in req.matching_results:
            results.append({
                "product":    mr.product.model,
                "attribute":  req.attribute,
                "status":     mr.status,
                "score":      mr.score,
                "reasoning":  mr.llm_reasoning,
            })

    return {"edital_id": edital_id, "results": results}