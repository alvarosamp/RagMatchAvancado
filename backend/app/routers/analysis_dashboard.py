from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.db.models import AnalysisDocument, AnalysisItem
from app.db.session import get_db

router = APIRouter(prefix="/analysis", tags=["analysis"])

Period = Literal["day", "week", "month", "year"]


@router.get("/dashboard")
def get_dashboard(
    period: Period = Query(default="month"),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    base_docs = db.query(AnalysisDocument).filter(
        AnalysisDocument.tenant_id == current_user.tenant_id,
        AnalysisDocument.source_kind == "edital",
    )
    if date_from is not None:
        base_docs = base_docs.filter(AnalysisDocument.created_at >= date_from)
    if date_to is not None:
        base_docs = base_docs.filter(AnalysisDocument.created_at <= date_to)
    doc_ids = [row.id for row in base_docs.with_entities(AnalysisDocument.id).all()]

    if not doc_ids:
        return {
            "period": period,
            "kpis": {
                "editais_selecionados": 0,
                "itens_categorizados": 0,
                "unidades_mapeadas": 0,
                "editais_com_risco": 0,
                "editais_com_me_epp": 0,
                "unidades_switches": 0,
                "unidades_access_points": 0,
                "unidades_transceivers": 0,
                "editais_com_switches": 0,
                "editais_com_access_points": 0,
            },
            "categories": [],
            "series": [],
        }

    items_q = db.query(AnalysisItem).filter(AnalysisItem.analysis_id.in_(doc_ids))

    itens_categorizados = items_q.count()
    unidades_mapeadas = items_q.with_entities(
        func.coalesce(func.sum(AnalysisItem.quantity), 0)
    ).scalar() or 0

    risco_identificado = func.json_extract_path_text(
        AnalysisDocument.result, "riscos", "risco_identificado"
    )
    exclusividade_me_epp = func.json_extract_path_text(
        AnalysisDocument.result, "edital", "exclusividade_me_epp"
    )
    editais_com_risco = base_docs.filter(
        risco_identificado.isnot(None),
        risco_identificado != "Nenhum",
    ).count()
    editais_com_me_epp = base_docs.filter(
        exclusividade_me_epp.isnot(None),
        exclusividade_me_epp != "Ampla concorrência",
    ).count()

    category_summary = _category_summary(items_q)

    kpis = {
        "editais_selecionados": len(doc_ids),
        "itens_categorizados": itens_categorizados,
        "unidades_mapeadas": unidades_mapeadas,
        "editais_com_risco": editais_com_risco,
        "editais_com_me_epp": editais_com_me_epp,
        "unidades_switches": category_summary["units"].get("Switch", 0),
        "unidades_access_points": category_summary["units"].get("Access Point", 0),
        "unidades_transceivers": _sum_categories(
            category_summary["units"],
            "Transceiver",
            "MÃ³dulo Ã³ptico",
            "Módulo óptico",
            "Modulo optico",
        ),
        "editais_com_switches": category_summary["documents"].get("Switch", 0),
        "editais_com_access_points": category_summary["documents"].get("Access Point", 0),
    }

    category_rows = (
        items_q.with_entities(
            AnalysisItem.categoria,
            func.count(AnalysisItem.id),
            func.coalesce(func.sum(AnalysisItem.quantity), 0),
            func.coalesce(func.sum(AnalysisItem.total_value), 0),
        )
        .group_by(AnalysisItem.categoria)
        .all()
    )

    categories: list[dict[str, Any]] = []
    for categoria, itens, unidades, valor_mapeado in category_rows:
        if not categoria:
            continue
        categories.append(
            {
                "categoria": categoria,
                "itens": itens,
                "unidades": unidades,
                "valor_mapeado": valor_mapeado,
                "breakdowns": _breakdowns_for_category(db, doc_ids, categoria),
                "ufs": _uf_breakdown_for_category(db, doc_ids, categoria),
            }
        )

    bucket = func.date_trunc(period, AnalysisDocument.created_at).label("bucket")
    series_rows = (
        db.query(bucket, func.count(AnalysisItem.id))
        .join(AnalysisItem, AnalysisItem.analysis_id == AnalysisDocument.id)
        .filter(AnalysisDocument.id.in_(doc_ids))
        .group_by(bucket)
        .order_by(bucket)
        .all()
    )
    series = [{"bucket": bucket_value, "itens": count} for bucket_value, count in series_rows]

    return {"period": period, "kpis": kpis, "categories": categories, "series": series}


_BREAKDOWN_FIELDS = {
    "Switch": ["quantidade_portas", "gerenciamento", "alimentacao_poe", "portas_acesso", "uplinks", "camada"],
    "Access Point": ["tecnologia_wifi", "ambiente", "alimentacao"],
    "Módulo óptico": ["formato", "velocidade", "tipo_meio", "alcance"],
    "Modulo optico": ["formato", "velocidade", "tipo_meio", "alcance"],
    "Transceiver": ["formato", "velocidade", "tipo_meio", "alcance"],
}

def _category_summary(items_q) -> dict[str, dict[str, Any]]:
    rows = (
        items_q.with_entities(
            AnalysisItem.categoria,
            AnalysisItem.analysis_id,
            func.coalesce(func.sum(AnalysisItem.quantity), 0),
        )
        .group_by(AnalysisItem.categoria, AnalysisItem.analysis_id)
        .all()
    )
    units: dict[str, float] = {}
    documents_by_category: dict[str, set[int]] = {}
    for categoria, analysis_id, quantity in rows:
        if not categoria:
            continue
        units[categoria] = units.get(categoria, 0) + float(quantity or 0)
        documents_by_category.setdefault(categoria, set()).add(analysis_id)
    return {
        "units": units,
        "documents": {key: len(value) for key, value in documents_by_category.items()},
    }


def _sum_categories(values: dict[str, float], *categories: str) -> float:
    return sum(values.get(category, 0) for category in categories)


def _breakdowns_for_category(
    db: Session, doc_ids: list[int], categoria: str
) -> dict[str, list[dict[str, Any]]]:
    fields = _BREAKDOWN_FIELDS.get(categoria, [])
    breakdowns: dict[str, list[dict[str, Any]]] = {}
    for field in fields:
        valor = func.json_extract_path_text(AnalysisItem.caracteristicas_bi, field).label("valor")
        rows = (
            db.query(
                valor,
                func.count(AnalysisItem.id),
            )
            .filter(
                AnalysisItem.analysis_id.in_(doc_ids),
                AnalysisItem.categoria == categoria,
            )
            .group_by("valor")
            .all()
        )
        breakdowns[field] = [
            {"valor": valor, "unidades": count} for valor, count in rows if valor is not None
        ]
    return breakdowns


def _uf_breakdown_for_category(
    db: Session, doc_ids: list[int], categoria: str
) -> list[dict[str, Any]]:
    rows = (
        db.query(
            AnalysisItem.uf,
            func.coalesce(func.sum(AnalysisItem.quantity), 0),
        )
        .filter(
            AnalysisItem.analysis_id.in_(doc_ids),
            AnalysisItem.categoria == categoria,
            AnalysisItem.uf.isnot(None),
        )
        .group_by(AnalysisItem.uf)
        .order_by(func.coalesce(func.sum(AnalysisItem.quantity), 0).desc())
        .limit(8)
        .all()
    )
    return [{"uf": uf, "unidades": unidades} for uf, unidades in rows if uf]


@router.get("/editais-listagem")
def get_editais_listagem(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    query = db.query(AnalysisDocument).filter(
        AnalysisDocument.tenant_id == current_user.tenant_id,
        AnalysisDocument.source_kind == "edital",
    )
    if date_from is not None:
        query = query.filter(AnalysisDocument.created_at >= date_from)
    if date_to is not None:
        query = query.filter(AnalysisDocument.created_at <= date_to)
    documents = query.order_by(AnalysisDocument.created_at.desc()).limit(200).all()

    result = []
    for document in documents:
        edital = (document.result or {}).get("edital") or {}
        riscos = (document.result or {}).get("riscos") or {}
        result.append(
            {
                "id": document.id,
                "source_name": document.source_name,
                "orgao": edital.get("orgao"),
                "uf": edital.get("uf"),
                "numero_pregao": edital.get("numero_pregao"),
                "data_disputa": edital.get("data_disputa"),
                "risco_identificado": riscos.get("risco_identificado"),
                "exclusividade_me_epp": edital.get("exclusividade_me_epp"),
                "items": [
                    {
                        "categoria": item.categoria,
                        "description": item.description,
                        "caracteristicas_bi": item.caracteristicas_bi,
                        "quantity": item.quantity,
                        "unit_value": item.unit_value,
                        "prazo_entrega": item.prazo_entrega,
                        "garantia": item.garantia,
                        "lote_grupo": item.lote_grupo,
                    }
                    for item in document.items
                ],
            }
        )
    return result
