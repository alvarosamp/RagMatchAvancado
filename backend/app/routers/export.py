"""
routers/export.py
──────────────────
Endpoints de exportação dos resultados de matching.

GET /editais/{id}/export/xlsx  → planilha Excel
GET /editais/{id}/export/pdf   → relatório PDF
GET /editais/{id}/export/csv   → CSV bruto
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Edital, MatchingResult
from app.services.export_service import export_xlsx, export_pdf, export_csv
from app.logs.config import logger

router = APIRouter(prefix="/editais", tags=["exportação"])


# ─────────────────────────────────────────────────────────────────────────────
# Helper — monta o dict de resultados do banco
# ─────────────────────────────────────────────────────────────────────────────

def _build_results_data(edital_id: int, db: Session) -> dict:
    """
    Lê os MatchingResults do banco e monta o mesmo formato
    retornado pelo endpoint POST /editais/{id}/match.
    """
    edital = db.get(Edital, edital_id)
    if not edital:
        raise HTTPException(404, detail="Edital não encontrado")

    # Agrupa por produto
    products: dict[int, dict] = {}

    for req in edital.requirements:
        for mr in req.matching_results:
            pid = mr.product_id
            if pid not in products:
                products[pid] = {
                    "model":         mr.product.model,
                    "overall_score": 0.0,
                    "status":        "",
                    "summary":       "",
                    "details":       [],
                    "_scores":       [],
                }

            products[pid]["details"].append({
                "attribute":   req.attribute or "",
                "required":    req.raw_value or "",
                "found":       mr.details or "",
                "final_score": mr.score or 0.0,
                "status":      mr.status.value if mr.status else "",
                "reasoning":   mr.llm_reasoning or "",
            })
            products[pid]["_scores"].append(mr.score or 0.0)

    # Calcula score geral e status por produto
    result_list = []
    for pid, p in products.items():
        scores = p.pop("_scores")
        overall = round(sum(scores) / len(scores), 3) if scores else 0.0
        p["overall_score"] = overall

        if overall >= 0.75:
            p["status"] = "atende"
        elif overall >= 0.45:
            p["status"] = "verificar"
        else:
            p["status"] = "nao_atende"

        atende     = sum(1 for d in p["details"] if d["status"] == "atende")
        nao_atende = sum(1 for d in p["details"] if d["status"] == "nao_atende")
        verificar  = sum(1 for d in p["details"] if d["status"] == "verificar")
        p["summary"] = (
            f"{p['model']}: score {overall:.0%} | "
            f"✅ {atende} · ⚠️ {verificar} · ❌ {nao_atende}"
        )
        result_list.append(p)

    result_list.sort(key=lambda x: x["overall_score"], reverse=True)

    return {
        "edital_id":      edital_id,
        "total_products": len(result_list),
        "best_match":     result_list[0] if result_list else None,
        "results":        result_list,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{edital_id}/export/xlsx")
def download_xlsx(edital_id: int, db: Session = Depends(get_db)):
    """
    Exporta resultados de matching como planilha Excel.
    Contém aba de Resumo (ranking) e aba de Detalhes (produto × requisito).
    """
    data     = _build_results_data(edital_id, db)
    filename = f"matching_edital_{edital_id}.xlsx"

    logger.info(f"[Export] XLSX solicitado — edital {edital_id}")
    return Response(
        content     = export_xlsx(data),
        media_type  = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers     = {"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{edital_id}/export/pdf")
def download_pdf(edital_id: int, db: Session = Depends(get_db)):
    """
    Exporta relatório de matching em PDF formatado,
    pronto para anexar em processo de licitação.
    """
    data     = _build_results_data(edital_id, db)
    filename = f"relatorio_edital_{edital_id}.pdf"

    logger.info(f"[Export] PDF solicitado — edital {edital_id}")
    return Response(
        content     = export_pdf(data),
        media_type  = "application/pdf",
        headers     = {"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{edital_id}/export/csv")
def download_csv(edital_id: int, db: Session = Depends(get_db)):
    """
    Exporta dados brutos de matching em CSV (separado por ;).
    Compatível com Excel BR (UTF-8 com BOM).
    """
    data     = _build_results_data(edital_id, db)
    filename = f"matching_edital_{edital_id}.csv"

    logger.info(f"[Export] CSV solicitado — edital {edital_id}")
    return Response(
        content     = export_csv(data),
        media_type  = "text/csv; charset=utf-8",
        headers     = {"Content-Disposition": f'attachment; filename="{filename}"'},
    )