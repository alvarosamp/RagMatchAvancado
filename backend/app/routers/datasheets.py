"""
routers/datasheets.py
──────────────────────
Inteligência comercial: extrai specs de um datasheet (nosso ou de concorrente)
e compara produto x produto usando os mesmos parsers tipados do matching
(attribute_parsers.py) — só que aqui não há "atende/não atende", e sim "quem
leva vantagem" em cada atributo.

Fluxo:
  1. POST /datasheets/extract  — sobe o PDF, roda OCR + LLM, devolve um preview
     (NÃO salva ainda — o usuário confere/edita antes de importar).
  2. POST /datasheets/import   — salva o preview (editado ou não) como Product.
  3. GET  /datasheets/products — lista produtos pra popular os seletores.
  4. GET  /datasheets/compare  — compara dois produtos já salvos, campo a campo.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.db.models import Product
from app.db.session import get_db
from app.logs.config import logger
from app.services.attribute_parsers import compare_product_specs
from app.services.competitive_intelligence import build_competitive_intelligence
from app.services.datasheet_extractor import extract_specs_from_pdf
from app.services.tor_datasheet_generator import (
    build_tor_datasheet_preview,
    export_tor_datasheet_pdf,
)

router = APIRouter(prefix="/datasheets", tags=["datasheets"])


@router.post("/extract")
async def extract_datasheet(
    file: UploadFile = File(..., description="PDF do datasheet (nosso ou de concorrente)"),
    current_user: User = Depends(require_role("admin", "editor")),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF sao aceitos.")

    pdf_bytes = await file.read()
    logger.info("[Datasheets] Extraindo specs | arquivo=%s | tenant=%s", file.filename, current_user.tenant_id)

    extracted = extract_specs_from_pdf(pdf_bytes, filename=file.filename)
    if not extracted["specs"]:
        raise HTTPException(
            status_code=422,
            detail="Nao foi possivel extrair especificacoes do datasheet. Preencha manualmente.",
        )
    return extracted


@router.post("/tor/preview")
async def preview_tor_datasheet(
    file: UploadFile = File(..., description="PDF original do fabricante"),
    pn_tor: str | None = Form(default=None),
    category: str | None = Form(default=None),
    current_user: User = Depends(require_role("admin", "editor")),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF sao aceitos.")

    pdf_bytes = await file.read()
    logger.info("[Datasheets] Gerando preview TOR | arquivo=%s | tenant=%s", file.filename, current_user.tenant_id)
    extracted = extract_specs_from_pdf(pdf_bytes, filename=file.filename)
    preview = build_tor_datasheet_preview(extracted, pn_tor=pn_tor, category=category)
    return {"preview": preview, "extracted": extracted}


@router.post("/tor/export/pdf")
def export_tor_datasheet(
    payload: dict[str, Any] = Body(...),
    current_user: User = Depends(require_role("admin", "editor")),
):
    preview = payload.get("preview") if "preview" in payload else payload
    if not isinstance(preview, dict):
        raise HTTPException(status_code=400, detail="Payload de datasheet invalido.")

    content = export_tor_datasheet_pdf(preview)
    pn = str(preview.get("pn_tor") or "datasheet_tor").strip() or "datasheet_tor"
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", pn)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="datasheet_tor_{safe_name}.pdf"'},
    )


class ImportDatasheetRequest(BaseModel):
    model: str
    manufacturer: str | None = None
    category: str | None = None
    specs: dict[str, Any]
    is_competitor: bool = True


@router.post("/import")
def import_datasheet(
    payload: ImportDatasheetRequest,
    current_user: User = Depends(require_role("admin", "editor")),
    db: Session = Depends(get_db),
):
    if not payload.model.strip():
        raise HTTPException(status_code=400, detail="Informe o modelo do produto.")

    product = db.query(Product).filter(Product.model == payload.model).first()
    if product is None:
        product = Product(model=payload.model)
        db.add(product)

    product.category = payload.category or product.category
    product.manufacturer = payload.manufacturer
    product.is_competitor = payload.is_competitor
    product.data = payload.specs

    db.commit()
    db.refresh(product)
    logger.info(
        "[Datasheets] Produto importado | model=%s | competitor=%s | tenant=%s",
        product.model, product.is_competitor, current_user.tenant_id,
    )
    return _serialize_product(product)


@router.get("/products")
def list_products(
    is_competitor: bool | None = Query(default=None),
    category: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Product)
    if is_competitor is not None:
        query = query.filter(Product.is_competitor == is_competitor)
    if category:
        query = query.filter(Product.category == category)
    products = query.order_by(Product.model).limit(200).all()
    return [_serialize_product(product) for product in products]


@router.get("/compare")
def compare_datasheets(
    product_a_id: int = Query(...),
    product_b_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product_a = db.query(Product).filter(Product.id == product_a_id).first()
    product_b = db.query(Product).filter(Product.id == product_b_id).first()
    if product_a is None or product_b is None:
        raise HTTPException(status_code=404, detail="Produto nao encontrado.")

    comparisons = compare_product_specs(product_a.data or {}, product_b.data or {})
    vantagem_a = sum(1 for c in comparisons if c.winner == "a")
    vantagem_b = sum(1 for c in comparisons if c.winner == "b")

    return {
        "product_a": _serialize_product(product_a),
        "product_b": _serialize_product(product_b),
        "fields": [
            {"field": c.field, "value_a": c.value_a, "value_b": c.value_b, "winner": c.winner}
            for c in comparisons
        ],
        "summary": {"vantagem_a": vantagem_a, "vantagem_b": vantagem_b, "empates_ou_sem_dado": len(comparisons) - vantagem_a - vantagem_b},
    }


@router.get("/gaps")
def competitive_gaps(
    category: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Agrega TODAS as combinações produto próprio x concorrente já salvos e
    ranqueia os atributos onde o concorrente mais leva vantagem — "onde
    perdemos mais", pra priorizar o que evoluir no catálogo. Recalculado
    ao vivo a cada chamada (não fica desatualizado conforme você importa
    mais datasheets ou atualiza specs do catálogo).
    """
    own_query = db.query(Product).filter(Product.is_competitor.is_(False))
    competitor_query = db.query(Product).filter(Product.is_competitor.is_(True))
    if category:
        own_query = own_query.filter(Product.category == category)
        competitor_query = competitor_query.filter(Product.category == category)

    own_products = own_query.all()
    competitor_products = competitor_query.all()

    field_stats: dict[str, dict[str, int]] = {}
    comparisons_run = 0
    for own in own_products:
        for competitor in competitor_products:
            comparisons_run += 1
            for comparison in compare_product_specs(own.data or {}, competitor.data or {}):
                stats = field_stats.setdefault(comparison.field, {"perdas": 0, "vitorias": 0, "empates": 0})
                if comparison.winner == "b":
                    stats["perdas"] += 1
                elif comparison.winner == "a":
                    stats["vitorias"] += 1
                elif comparison.winner == "tie":
                    stats["empates"] += 1

    gaps = sorted(
        (
            {"field": field, **stats}
            for field, stats in field_stats.items()
            if stats["perdas"] > 0
        ),
        key=lambda item: item["perdas"],
        reverse=True,
    )

    return {
        "gaps": gaps[:20],
        "comparisons_run": comparisons_run,
        "own_count": len(own_products),
        "competitor_count": len(competitor_products),
    }


@router.get("/competitive-intelligence")
def competitive_intelligence(
    category: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return build_competitive_intelligence(db, category=category, limit=limit)


def _serialize_product(product: Product) -> dict:
    return {
        "id": product.id,
        "model": product.model,
        "manufacturer": product.manufacturer,
        "category": product.category,
        "is_competitor": bool(product.is_competitor),
        "data": product.data,
    }
