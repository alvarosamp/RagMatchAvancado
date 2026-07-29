from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session, selectinload

from app.crm.models import (
    CrmChecklistStatus,
    CrmNotice,
    CrmNoticeDocument,
    CrmNoticeHistory,
)
from app.db.models import Edital, Product


POSITIVE_TERMS = {
    "switch",
    "roteador",
    "firewall",
    "access point",
    "wifi",
    "wi-fi",
    "poe",
    "sfp",
    "gbic",
    "rede",
    "cabeamento",
}

DISQUALIFYING_TERMS = {
    "obra",
    "merenda",
    "medicamento",
    "material odontologico",
    "combustivel",
    "limpeza urbana",
    "pavimentacao",
}

RISK_PATTERNS = {
    "marca_modelo": r"\b(marca\s+e\s+modelo|modelo\s+referencia|similar\s+ao|equivalente\s+ao)\b",
    "prazo_curto": r"\b(24\s*h|48\s*h|72\s*h|imediat[ao]|urgente|pronta\s+entrega)\b",
    "vistoria": r"\b(vistoria|visita\s+tecnica)\b",
    "atestados": r"\b(atestado\s+de\s+capacidade|capacidade\s+tecnica|comprovacao\s+tecnica)\b",
    "amostra": r"\b(amostra|prova\s+de\s+conceito|poc)\b",
    "penalidades": r"\b(multa|sancao|penalidade|inidoneidade|impedimento)\b",
}

DOC_REQUIREMENTS = {
    "Contrato Social / Estatuto": r"\b(contrato\s+social|estatuto)\b",
    "CNPJ atualizado": r"\b(cnpj|cadastro\s+nacional)\b",
    "Certidao Negativa Federal": r"\b(cnd\s+federal|certidao\s+federal|receita\s+federal)\b",
    "Certidao Negativa Estadual": r"\b(certidao\s+estadual|fazenda\s+estadual)\b",
    "Certidao Negativa Municipal": r"\b(certidao\s+municipal|fazenda\s+municipal)\b",
    "CRF FGTS": r"\b(fgts|crf)\b",
    "CNDT (Trabalhista)": r"\b(cndt|trabalhista)\b",
    "Atestado de Capacidade Tecnica": r"\b(atestado\s+de\s+capacidade|capacidade\s+tecnica)\b",
    "Balanco Patrimonial": r"\b(balanco\s+patrimonial|balan[cç]o)\b",
    "Certidao Negativa de Falencia": r"\b(falencia|recuperacao\s+judicial)\b",
}


def generate_decision_intelligence(
    *,
    notice: CrmNotice,
    edital: Edital | None = None,
    full_text: str | None = None,
    products: list[Product] | None = None,
) -> dict[str, Any]:
    text = _normalize_text(full_text or getattr(edital, "full_text", None) or "")
    title = _normalize_text(notice.title or "")
    combined = f"{title}\n{text}"

    matched_terms = sorted(term for term in POSITIVE_TERMS if term in combined)
    off_segment_terms = sorted(term for term in DISQUALIFYING_TERMS if term in combined)
    risk_flags = _risk_flags(combined)
    doc_requirements = _document_requirements(combined)
    technical_requirements = _technical_requirements(combined)
    deadlines = _deadline_signals(combined, notice)
    products_count = len(products or [])
    catalog_fit = _catalog_fit(matched_terms, products or [])

    risk_score = min(100, 12 * len(risk_flags) + 10 * len(off_segment_terms))
    fit_score = min(100, len(matched_terms) * 12 + catalog_fit)
    deadline_score = deadlines["score"]
    confidence = _confidence(text, matched_terms, doc_requirements)
    final_score = max(0, min(100, round(fit_score * 0.45 + deadline_score * 0.15 + (100 - risk_score) * 0.25 + confidence * 0.15)))
    recommendation = _recommendation(final_score, risk_score, off_segment_terms, matched_terms)

    return {
        "schema": "decision_intelligence.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "recommendation": recommendation,
        "score": final_score,
        "risk_score": risk_score,
        "confidence": confidence,
        "executive_summary": _summary(notice, matched_terms, risk_flags, deadlines, products_count),
        "technical_requirements": technical_requirements,
        "document_requirements": doc_requirements,
        "deadline_signals": deadlines,
        "risk_flags": risk_flags,
        "matched_terms": matched_terms,
        "off_segment_terms": off_segment_terms,
        "next_actions": _next_actions(recommendation, risk_flags, doc_requirements, technical_requirements),
    }


def persist_notice_decision_intelligence(
    db: Session,
    *,
    notice_id: str,
    edital: Edital | None = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    notice = (
        db.query(CrmNotice)
        .options(selectinload(CrmNotice.notice_documents))
        .filter(CrmNotice.id == notice_id)
        .first()
    )
    if notice is None:
        raise LookupError("Edital CRM nao encontrado.")

    products = db.query(Product).filter(Product.is_competitor.is_(False)).all()
    payload = generate_decision_intelligence(notice=notice, edital=edital, products=products)
    notice.decision_intelligence = payload
    notice.decision_recommendation = payload["recommendation"]
    notice.decision_score = payload["score"]
    notice.decision_risk_score = payload["risk_score"]
    notice.analysis_status = "Parecer IA gerado"
    notice.analysis_confidence = _confidence_label(payload["confidence"])
    _sync_checklist_from_intelligence(notice, payload)
    db.add(
        CrmNoticeHistory(
            tenant_id=notice.tenant_id,
            notice_id=notice.id,
            user_id=user_id,
            action="Parecer IA de decisao gerado",
            details={
                "recommendation": payload["recommendation"],
                "score": payload["score"],
                "risk_score": payload["risk_score"],
            },
        )
    )
    db.commit()
    return payload


def serialize_decision_intelligence(notice: CrmNotice) -> dict[str, Any] | None:
    payload = notice.decision_intelligence
    if not payload:
        return None
    return {
        **payload,
        "notice_id": notice.id,
        "notice_number": notice.tor_id or notice.number,
        "decision_recommendation": notice.decision_recommendation,
        "decision_score": notice.decision_score,
        "decision_risk_score": notice.decision_risk_score,
    }


def _normalize_text(value: str) -> str:
    return str(value or "").lower()


def _risk_flags(text: str) -> list[dict[str, str]]:
    flags = []
    labels = {
        "marca_modelo": "Possivel direcionamento por marca/modelo",
        "prazo_curto": "Prazo operacional curto",
        "vistoria": "Exige vistoria ou visita tecnica",
        "atestados": "Exige atestado de capacidade tecnica",
        "amostra": "Exige amostra ou prova de conceito",
        "penalidades": "Clausulas de penalidade relevantes",
    }
    for key, pattern in RISK_PATTERNS.items():
        if re.search(pattern, text):
            flags.append({"code": key, "label": labels[key]})
    return flags


def _document_requirements(text: str) -> list[dict[str, Any]]:
    items = []
    for name, pattern in DOC_REQUIREMENTS.items():
        required = bool(re.search(pattern, text))
        items.append({"name": name, "required": required, "status": "verificar" if required else "nao_identificado"})
    return items


def _technical_requirements(text: str) -> list[str]:
    patterns = [
        r"\b\d+\s*portas?\b.{0,60}",
        r"\bpoe\b.{0,80}",
        r"\bsfp\+?\b.{0,80}",
        r"\bgerenci[aá]vel\b.{0,80}",
        r"\bfirewall\b.{0,80}",
        r"\bwi-?fi\b.{0,80}",
    ]
    found: list[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, text):
            cleaned = " ".join(str(match).split())
            if cleaned and cleaned not in found:
                found.append(cleaned[:160])
    return found[:12]


def _deadline_signals(text: str, notice: CrmNotice) -> dict[str, Any]:
    days_until_auction = None
    if notice.auction_date:
        now = datetime.now(notice.auction_date.tzinfo) if notice.auction_date.tzinfo else datetime.now()
        days_until_auction = max(0, (notice.auction_date - now).days)
    explicit = bool(re.search(RISK_PATTERNS["prazo_curto"], text))
    score = 45
    if days_until_auction is not None:
        if days_until_auction <= 2:
            score = 90
        elif days_until_auction <= 7:
            score = 70
        elif days_until_auction <= 15:
            score = 55
    if explicit:
        score = min(100, score + 20)
    return {"days_until_auction": days_until_auction, "short_deadline_terms": explicit, "score": score}


def _catalog_fit(matched_terms: list[str], products: list[Product]) -> int:
    if not products:
        return 0
    catalog_text = " ".join(
        f"{item.model or ''} {item.category or ''} {item.manufacturer or ''} {item.data or ''}".lower()
        for item in products
    )
    hits = sum(1 for term in matched_terms if term in catalog_text)
    return min(35, hits * 7)


def _confidence(text: str, matched_terms: list[str], docs: list[dict[str, Any]]) -> int:
    score = 35
    if len(text) > 3000:
        score += 25
    elif len(text) > 800:
        score += 15
    score += min(20, len(matched_terms) * 4)
    score += 10 if any(item["required"] for item in docs) else 0
    return min(95, score)


def _recommendation(score: int, risk_score: int, off_segment_terms: list[str], matched_terms: list[str]) -> str:
    if off_segment_terms and not matched_terms:
        return "nao_disputar"
    if score >= 72 and risk_score <= 45:
        return "disputar"
    if score >= 50:
        return "analisar"
    return "nao_disputar"


def _summary(
    notice: CrmNotice,
    matched_terms: list[str],
    risk_flags: list[dict[str, str]],
    deadlines: dict[str, Any],
    products_count: int,
) -> str:
    subject = notice.title or notice.number
    terms = ", ".join(matched_terms[:5]) or "sem aderencia tecnica clara"
    risks = ", ".join(flag["label"] for flag in risk_flags[:3]) or "sem risco critico evidente"
    prazo = deadlines.get("days_until_auction")
    prazo_txt = f"{prazo} dia(s) ate a disputa" if prazo is not None else "prazo de disputa nao identificado"
    return (
        f"{subject}. Sinais tecnicos: {terms}. Catalogo ativo: {products_count} produto(s). "
        f"Prazos: {prazo_txt}. Riscos principais: {risks}."
    )[:1400]


def _next_actions(
    recommendation: str,
    risks: list[dict[str, str]],
    docs: list[dict[str, Any]],
    technical: list[str],
) -> list[str]:
    actions = []
    if recommendation == "disputar":
        actions.append("Validar preco minimo e margem antes de preparar proposta.")
    elif recommendation == "analisar":
        actions.append("Enviar para analise tecnica/comercial antes de confirmar disputa.")
    else:
        actions.append("Registrar motivo de nao participacao ou manter em monitoramento.")
    if technical:
        actions.append("Conferir aderencia dos itens tecnicos extraidos com o catalogo.")
    if any(item["required"] for item in docs):
        actions.append("Separar certidoes e documentos de habilitacao identificados no edital.")
    if risks:
        actions.append("Revisar riscos destacados e decidir mitigacao antes da proposta.")
    return actions


def _sync_checklist_from_intelligence(notice: CrmNotice, payload: dict[str, Any]) -> None:
    docs_by_name: dict[str, CrmNoticeDocument] = {doc.name: doc for doc in notice.notice_documents}
    if docs_by_name.get("Analisar requisitos tecnicos"):
        docs_by_name["Analisar requisitos tecnicos"].status = CrmChecklistStatus.READY
        docs_by_name["Analisar requisitos tecnicos"].notes = "Parecer IA gerado com requisitos tecnicos preliminares."
    if docs_by_name.get("Validar documentacao de habilitacao"):
        required_docs = [item["name"] for item in payload.get("document_requirements", []) if item.get("required")]
        docs_by_name["Validar documentacao de habilitacao"].status = CrmChecklistStatus.IN_PROGRESS if required_docs else CrmChecklistStatus.PENDING
        docs_by_name["Validar documentacao de habilitacao"].notes = ", ".join(required_docs[:8]) or "Nenhuma exigencia documental especifica identificada automaticamente."


def _confidence_label(value: int) -> str:
    if value >= 75:
        return "alta"
    if value >= 55:
        return "media"
    return "baixa"
