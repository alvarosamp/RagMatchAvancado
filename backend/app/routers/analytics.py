"""
routers/analytics.py
─────────────────────
Endpoints de análise de dados dos produtos.

GET /analytics/overview          → KPIs gerais do tenant
GET /analytics/produtos          → ranking + performance por produto
GET /analytics/requisitos        → requisitos com mais falhas (gaps)
GET /analytics/evolucao          → scores ao longo do tempo (por edital)
GET /analytics/distribuicao      → histograma de scores
"""

from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Edital, MatchingResult, MatchStatus, Product, Requirement
from app.auth.models import User
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/analytics", tags=["analytics"])


# ─────────────────────────────────────────────────────────────────────────────
# GET /analytics/overview — KPIs gerais
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/overview")
def overview(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    KPIs gerais do tenant:
      - total de editais processados
      - total de matchings realizados
      - score médio geral
      - produto com melhor performance
      - taxa de atendimento geral
    """
    tenant_id = current_user.tenant.slug

    # Editais do tenant
    editais = db.query(Edital).filter(Edital.tenant_id == tenant_id).all()
    edital_ids = [e.id for e in editais]

    if not edital_ids:
        return {
            "total_editais":    0,
            "total_matchings":  0,
            "score_medio":      0,
            "taxa_atendimento":  0,
            "melhor_produto":   None,
            "total_requisitos": 0,
        }

    # Todos os resultados de matching do tenant
    results = (
        db.query(MatchingResult)
        .join(Requirement, MatchingResult.requirements_id == Requirement.id)
        .filter(Requirement.edital_id.in_(edital_ids))
        .all()
    )

    total    = len(results)
    scores   = [r.score for r in results if r.score is not None]
    atende   = [r for r in results if r.status == MatchStatus.ATENDE]

    # Produto com melhor score médio
    by_product = defaultdict(list)
    for r in results:
        by_product[r.product.model].append(r.score or 0)

    melhor = None
    if by_product:
        melhor = max(by_product, key=lambda p: sum(by_product[p]) / len(by_product[p]))

    return {
        "total_editais":    len(editais),
        "total_matchings":  total,
        "score_medio":      round(sum(scores) / len(scores), 3) if scores else 0,
        "taxa_atendimento": round(len(atende) / total, 3) if total else 0,
        "melhor_produto":   melhor,
        "total_requisitos": db.query(Requirement).filter(Requirement.edital_id.in_(edital_ids)).count(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /analytics/produtos — ranking + performance por produto
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/produtos")
def produtos(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Para cada produto:
      - score médio, mediana, desvio
      - contagem por status (atende / verificar / não atende)
      - total de matchings
      - aparições como melhor resultado
    """
    tenant_id  = current_user.tenant.slug
    edital_ids = [e.id for e in db.query(Edital).filter(Edital.tenant_id == tenant_id).all()]

    if not edital_ids:
        return []

    results = (
        db.query(MatchingResult)
        .join(Requirement, MatchingResult.requirements_id == Requirement.id)
        .filter(Requirement.edital_id.in_(edital_ids))
        .all()
    )

    # Agrupa por produto
    by_product = defaultdict(lambda: {
        "scores": [], "atende": 0, "verificar": 0, "nao_atende": 0
    })

    for r in results:
        model = r.product.model
        by_product[model]["scores"].append(r.score or 0)
        if   r.status == MatchStatus.ATENDE:     by_product[model]["atende"]     += 1
        elif r.status == MatchStatus.VERIFICAR:  by_product[model]["verificar"]  += 1
        else:                                    by_product[model]["nao_atende"] += 1

    output = []
    for model, data in by_product.items():
        scores = sorted(data["scores"])
        n      = len(scores)
        media  = sum(scores) / n if n else 0
        mediana = scores[n // 2] if n else 0
        variancia = sum((s - media) ** 2 for s in scores) / n if n else 0
        desvio    = variancia ** 0.5

        output.append({
            "produto":     model,
            "total":       n,
            "score_medio": round(media,   3),
            "mediana":     round(mediana, 3),
            "desvio":      round(desvio,  3),
            "atende":      data["atende"],
            "verificar":   data["verificar"],
            "nao_atende":  data["nao_atende"],
            "taxa_atendimento": round(data["atende"] / n, 3) if n else 0,
        })

    return sorted(output, key=lambda x: x["score_medio"], reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# GET /analytics/requisitos — gaps (requisitos sistematicamente mal atendidos)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/requisitos")
def requisitos(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Requisitos que mais produtos falham — indica gaps no catálogo.
    Ordenado do mais problemático para o menos.
    """
    tenant_id  = current_user.tenant.slug
    edital_ids = [e.id for e in db.query(Edital).filter(Edital.tenant_id == tenant_id).all()]

    if not edital_ids:
        return []

    reqs = db.query(Requirement).filter(Requirement.edital_id.in_(edital_ids)).all()
    output = []

    for req in reqs:
        results = req.matching_results
        if not results:
            continue

        n         = len(results)
        scores    = [r.score or 0 for r in results]
        atende    = sum(1 for r in results if r.status == MatchStatus.ATENDE)
        nao_atende= sum(1 for r in results if r.status == MatchStatus.NAO_ATENDE)
        verificar = sum(1 for r in results if r.status == MatchStatus.VERIFICAR)

        output.append({
            "requisito":    req.attribute,
            "raw_value":    req.raw_value,
            "edital_id":    req.edital_id,
            "total":        n,
            "score_medio":  round(sum(scores) / n, 3),
            "atende":       atende,
            "verificar":    verificar,
            "nao_atende":   nao_atende,
            "taxa_falha":   round((nao_atende + verificar) / n, 3),
        })

    return sorted(output, key=lambda x: x["taxa_falha"], reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# GET /analytics/evolucao — score médio por edital ao longo do tempo
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/evolucao")
def evolucao(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Score médio de cada edital processado, em ordem cronológica.
    Permite ver se a qualidade dos matchings está melhorando.
    """
    tenant_id = current_user.tenant.slug
    editais   = (
        db.query(Edital)
        .filter(Edital.tenant_id == tenant_id)
        .order_by(Edital.parsed_at)
        .all()
    )

    output = []
    for edital in editais:
        results = []
        for req in edital.requirements:
            results.extend(req.matching_results)

        if not results:
            continue

        scores     = [r.score or 0 for r in results]
        atende     = sum(1 for r in results if r.status == MatchStatus.ATENDE)
        nao_atende = sum(1 for r in results if r.status == MatchStatus.NAO_ATENDE)

        output.append({
            "edital_id":        edital.id,
            "filename":         edital.filename,
            "data":             edital.parsed_at.isoformat() if edital.parsed_at else None,
            "score_medio":      round(sum(scores) / len(scores), 3),
            "total_resultados": len(results),
            "atende":           atende,
            "nao_atende":       nao_atende,
            "taxa_atendimento": round(atende / len(results), 3),
        })

    return output


# ─────────────────────────────────────────────────────────────────────────────
# GET /analytics/distribuicao — histograma de scores
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/distribuicao")
def distribuicao(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Distribuição de todos os scores em buckets de 10%.
    Ex: quantos matchings ficaram entre 0.0-0.1, 0.1-0.2, etc.
    """
    tenant_id  = current_user.tenant.slug
    edital_ids = [e.id for e in db.query(Edital).filter(Edital.tenant_id == tenant_id).all()]

    if not edital_ids:
        return {"buckets": [], "total": 0}

    results = (
        db.query(MatchingResult)
        .join(Requirement, MatchingResult.requirements_id == Requirement.id)
        .filter(Requirement.edital_id.in_(edital_ids))
        .all()
    )

    # Inicializa 10 buckets: 0-10%, 10-20%, ..., 90-100%
    buckets = [0] * 10
    for r in results:
        score = r.score or 0
        idx   = min(int(score * 10), 9)   # clamp para evitar index 10
        buckets[idx] += 1

    return {
        "total": len(results),
        "buckets": [
            {
                "faixa":  f"{i*10}-{(i+1)*10}%",
                "min":    i / 10,
                "max":    (i + 1) / 10,
                "count":  buckets[i],
                "pct":    round(buckets[i] / len(results), 3) if results else 0,
            }
            for i in range(10)
        ],
    }