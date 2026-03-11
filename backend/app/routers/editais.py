"""
──────────────────
Endpoints para:
  POST /editais/upload          → faz OCR, chunka, embeda e salva no banco
  POST /editais/{id}/match      → roda matching para todos os switches
  GET  /editais                 → lista editais DO tenant autenticado
  GET  /editais/{id}/results    → resultados de matching

MUDANÇAS COM AUTH:
  - Todos os endpoints exigem JWT válido (Authorization: Bearer <token>)
  - tenant_id é extraído do token — nunca mais vem do Form
  - Queries filtradas por tenant_id automaticamente
  - Upload e match exigem role "admin" ou "editor"
  - Listagem e resultados aceitam qualquer role autenticado
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import Edital, Requirement, Product
from app.pipeline.docling_parser import parse_pdf
from app.pipeline.chunker import chunk_document
from app.vector.pgvector_store import save_chunks
from app.services.matching_engine import run_matching, match_all_products
from app.logs.config import logger

# ── Auth imports ──────────────────────────────────────────────────────────────
from app.auth.models import User
from app.auth.dependencies import get_current_user, require_role

router = APIRouter(prefix="/editais", tags=["editais"])


# ──────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────

class EditalResponse(BaseModel):
    id:                 int
    filename:           str
    chunks_count:       int
    requirements_count: int

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────
# Upload + Processamento
# ──────────────────────────────────────────

@router.post("/upload", response_model=EditalResponse)
async def upload_edital(
    file:         UploadFile = File(..., description="PDF do edital"),
    # MUDANÇA: tenant_id não vem mais do Form — vem do JWT
    # require_role("admin", "editor") = só admin e editor podem fazer upload
    current_user: User    = Depends(require_role("admin", "editor")),
    db:           Session = Depends(get_db),
):
    """
    Pipeline completo:
    1. Recebe o PDF
    2. Docling → extrai texto e estrutura
    3. Chunker → divide em blocos semânticos
    4. Embedder + PGVector → gera e salva embeddings
    5. Salva Edital com tenant_id do token

    Requer: Authorization: Bearer <token> com role admin ou editor
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF são aceitos.")

    # tenant_id extraído do JWT — não pode ser manipulado pelo cliente
    tenant_id = current_user.tenant.slug

    logger.info(f"[Editais] Upload: {file.filename} | tenant={tenant_id} | user={current_user.email}")
    pdf_bytes = await file.read()

    # 1. Parse com Docling
    parsed_doc = parse_pdf(pdf_bytes, filename=file.filename)

    # 2. Salva edital vinculado ao tenant
    edital = Edital(
        filename  = file.filename,
        full_text = parsed_doc.full_text,
        tenant_id = tenant_id,   # ← vem do JWT, não do Form
    )
    db.add(edital)
    db.flush()

    # 3. Chunking
    chunks = chunk_document(parsed_doc)

    # 4. Embeddings + pgvector
    saved = save_chunks(db, edital, chunks)

    db.commit()
    db.refresh(edital)

    logger.info(f"[Editais] Edital {edital.id} salvo | chunks={saved} | tenant={tenant_id}")
    return EditalResponse(
        id                  = edital.id,
        filename            = edital.filename,
        chunks_count        = saved,
        requirements_count  = len(edital.requirements),
    )


# ──────────────────────────────────────────
# Requisitos
# ──────────────────────────────────────────

@router.post("/{edital_id}/requirements")
def add_requirements(
    edital_id:    int,
    requirements: list[dict],
    current_user: User    = Depends(require_role("admin", "editor")),
    db:           Session = Depends(get_db),
):
    """
    Importa lista de requisitos para um edital.

    ISOLAMENTO: verifica que o edital pertence ao tenant do usuário.
    Um tenant não consegue adicionar requisitos a editais de outro tenant.

    Requer: role admin ou editor
    """
    # Busca edital e verifica que pertence ao tenant do usuário
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


# ──────────────────────────────────────────
# Matching
# ──────────────────────────────────────────

@router.post("/{edital_id}/match")
def match_edital(
    edital_id:    int,
    current_user: User    = Depends(require_role("admin", "editor")),
    db:           Session = Depends(get_db),
):
    """
    Executa matching de TODOS os produtos contra os requisitos do edital.

    ISOLAMENTO: verifica que o edital pertence ao tenant.
    O tenant_slug é passado para o MLOps para separar os experimentos.

    Requer: role admin ou editor
    """
    edital = _get_edital_do_tenant(edital_id, current_user, db)

    requirements = edital.requirements
    if not requirements:
        raise HTTPException(
            status_code = 400,
            detail      = "Edital não possui requisitos. Use POST /editais/{id}/requirements primeiro.",
        )

    products = db.query(Product).filter(Product.category == "switch").all()
    if not products:
        raise HTTPException(status_code=404, detail="Nenhum produto no catálogo.")

    logger.info(
        f"[Matching] Edital {edital_id} | "
        f"{len(products)} produtos × {len(requirements)} requisitos | "
        f"tenant={current_user.tenant.slug}"
    )

    # Passa tenant_slug para o MLOps — cada tenant vê seus próprios experimentos
    reports_obj = match_all_products(
        db,
        products,
        requirements,
        edital_id  = edital_id,
        tenant_id  = current_user.tenant.slug,   # ← MLOps recebe o tenant
    )

    reports = [
        {
            "model":         r.product_model,
            "overall_score": r.overall_score,
            "status":        r.status,
            "summary":       r.summary,
            "details": [
                {
                    "attribute":   d.attribute,
                    "required":    d.required,
                    "found":       d.found,
                    "final_score": d.final_score,
                    "status":      d.status,
                    "reasoning":   d.reasoning,
                }
                for d in r.details
            ],
        }
        for r in reports_obj
    ]

    return {
        "edital_id":      edital_id,
        "total_products": len(reports),
        "best_match":     reports[0] if reports else None,
        "results":        reports,
    }


# ──────────────────────────────────────────
# Listagem e consulta
# ──────────────────────────────────────────

@router.get("/")
def list_editais(
    current_user: User    = Depends(get_current_user),  # qualquer role autenticado
    db:           Session = Depends(get_db),
):
    """
    Lista editais DO tenant autenticado.

    ISOLAMENTO: filtra por tenant_id — nunca retorna editais de outros tenants.
    """
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
    """
    Retorna resultados de matching salvos para um edital.

    ISOLAMENTO: verifica que o edital pertence ao tenant.
    """
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


# ──────────────────────────────────────────
# Helper interno — isolamento de tenant
# ──────────────────────────────────────────

def _get_edital_do_tenant(edital_id: int, current_user: User, db: Session) -> Edital:
    """
    Busca um edital e verifica que pertence ao tenant do usuário autenticado.

    ISOLAMENTO: Se o edital existir mas pertencer a outro tenant,
    retorna 404 (não 403) — para não revelar que o edital existe.

    Raises:
        404: edital não encontrado ou pertence a outro tenant
    """
    edital = (
        db.query(Edital)
        .filter(
            Edital.id        == edital_id,
            Edital.tenant_id == current_user.tenant.slug,  # ← filtro de tenant
        )
        .first()
    )
    if not edital:
        raise HTTPException(status_code=404, detail="Edital não encontrado.")
    return edital