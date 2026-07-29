from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable

from app.services.crm_match_scoring import lexical_similarity, technical_compatibility_score


DEFAULT_TOR_TERMS = {
    "switch",
    "switches",
    "roteador",
    "router",
    "firewall",
    "access point",
    "ap ",
    "wi-fi",
    "wifi",
    "wireless",
    "sfp",
    "gbic",
    "transceiver",
    "rack",
    "poe",
    "vlan",
    "rede",
    "redes",
    "cabeamento",
    "fibra",
}

RISK_TERMS = {
    "marca exclusiva",
    "marca especifica",
    "marca específica",
    "similaridade",
    "visita tecnica",
    "visita técnica",
    "amostra",
    "homologado",
    "certificacao obrigatoria",
    "certificação obrigatória",
    "prazo imediato",
    "24 horas",
    "48 horas",
}

DISQUALIFYING_TERMS = {
    "obra",
    "merenda",
    "medicamento",
    "combustivel",
    "combustível",
    "locacao de veiculo",
    "locação de veículo",
    "material odontologico",
    "material odontológico",
}


@dataclass(frozen=True)
class OpportunityScore:
    score: int
    priority: str
    technical_fit: int
    commercial_fit: int
    urgency: int
    risk: int
    matched_terms: list[str]
    risk_flags: list[str]
    reasons: list[str]
    recommendation: str


@dataclass(frozen=True)
class CompetitorEntryPrediction:
    product_id: int | None
    model: str
    manufacturer: str | None
    category: str | None
    probability: int
    level: str
    evidence: list[str]
    conflicts: list[str]


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_notice_text(item: dict[str, Any]) -> str:
    parts = [
        item.get("objeto"),
        item.get("objetoCompra"),
        item.get("descricaoObjeto"),
        item.get("descricao"),
        item.get("titulo"),
        item.get("informacaoComplementar"),
        item.get("informacao_complementar"),
        " ".join(str(row.get("descricao") or "") for row in item.get("radar_items") or []),
    ]
    return normalize_text(" ".join(str(part) for part in parts if part))


def product_search_text(product: Any) -> str:
    parts = [
        getattr(product, "model", None),
        getattr(product, "manufacturer", None),
        getattr(product, "category", None),
    ]
    data = getattr(product, "data", None)
    if isinstance(data, dict):
        for key, value in data.items():
            parts.append(key)
            if isinstance(value, (str, int, float, bool)):
                parts.append(value)
    return " ".join(str(part) for part in parts if part not in (None, ""))


def build_catalog_terms(products: Iterable[Any]) -> set[str]:
    terms = set(DEFAULT_TOR_TERMS)
    for product in products:
        for value in (
            getattr(product, "model", None),
            getattr(product, "category", None),
            getattr(product, "manufacturer", None),
        ):
            terms.update(_meaningful_terms(value))

        data = getattr(product, "data", None)
        if isinstance(data, dict):
            for key, value in data.items():
                terms.update(_meaningful_terms(key))
                if isinstance(value, (str, int, float)):
                    terms.update(_meaningful_terms(value))

    return {term for term in terms if len(term.strip()) >= 3}


def predict_competitor_entries(
    item: dict[str, Any],
    competitor_products: Iterable[Any],
    *,
    limit: int = 5,
) -> list[CompetitorEntryPrediction]:
    notice_text = get_notice_text(item)
    if not notice_text:
        return []

    predictions: list[CompetitorEntryPrediction] = []
    for product in competitor_products:
        candidate_text = product_search_text(product)
        if not candidate_text.strip():
            continue

        lexical = lexical_similarity(notice_text, candidate_text)
        technical = technical_compatibility_score(notice_text, candidate_text)
        technical_score = technical.score if technical is not None else None
        conflicts = list(technical.conflicts if technical is not None else ())
        matched_features = list(technical.matched_features if technical is not None else ())

        if technical_score is not None:
            raw_probability = (technical_score * 0.72) + (lexical * 0.28)
        else:
            raw_probability = lexical * 0.82

        if conflicts:
            raw_probability = min(raw_probability, 0.62)

        probability = int(round(max(0.0, min(1.0, raw_probability)) * 100))
        if probability < 18:
            continue

        evidence = _prediction_evidence(lexical, technical_score, matched_features, product)
        predictions.append(CompetitorEntryPrediction(
            product_id=getattr(product, "id", None),
            model=str(getattr(product, "model", "") or "Modelo nao informado"),
            manufacturer=getattr(product, "manufacturer", None),
            category=getattr(product, "category", None),
            probability=probability,
            level=_prediction_level(probability, conflicts),
            evidence=evidence,
            conflicts=conflicts[:5],
        ))

    predictions.sort(key=lambda row: row.probability, reverse=True)
    return predictions[:limit]


def serialize_competitor_prediction(prediction: CompetitorEntryPrediction) -> dict[str, Any]:
    return {
        "product_id": prediction.product_id,
        "model": prediction.model,
        "manufacturer": prediction.manufacturer,
        "category": prediction.category,
        "probability": prediction.probability,
        "level": prediction.level,
        "evidence": prediction.evidence,
        "conflicts": prediction.conflicts,
    }


def score_opportunity(item: dict[str, Any], catalog_terms: Iterable[str] | None = None) -> OpportunityScore:
    terms = set(catalog_terms or DEFAULT_TOR_TERMS)
    text = get_notice_text(item)
    matched_terms = sorted(term.strip() for term in terms if term.strip() and term.lower() in text)
    risk_flags = sorted(term for term in RISK_TERMS if term in text)
    disqualifying = sorted(term for term in DISQUALIFYING_TERMS if term in text)

    technical_fit = min(100, 18 + len(matched_terms) * 14)
    if any(term in matched_terms for term in ("switch", "switches", "roteador", "router", "firewall")):
        technical_fit += 14
    if any(term in matched_terms for term in ("sfp", "gbic", "poe", "vlan", "access point")):
        technical_fit += 8
    if not matched_terms:
        technical_fit = 15
    if disqualifying and not matched_terms:
        technical_fit = 5
    technical_fit = min(100, technical_fit)

    value = _extract_value(item)
    commercial_fit = _commercial_score(value)

    urgency = _urgency_score(item)
    risk = min(100, len(risk_flags) * 22 + len(disqualifying) * 30)

    raw_score = int(round(
        technical_fit * 0.55
        + commercial_fit * 0.22
        + urgency * 0.13
        + (100 - risk) * 0.10
    ))
    if disqualifying and technical_fit < 35:
        raw_score = min(raw_score, 28)
    score = max(0, min(100, raw_score))

    priority = _priority(score)
    reasons = _build_reasons(
        matched_terms=matched_terms,
        value=value,
        urgency=urgency,
        risk_flags=risk_flags,
        disqualifying=disqualifying,
        technical_fit=technical_fit,
    )
    recommendation = _recommendation(priority, risk_flags, matched_terms)

    return OpportunityScore(
        score=score,
        priority=priority,
        technical_fit=technical_fit,
        commercial_fit=commercial_fit,
        urgency=urgency,
        risk=risk,
        matched_terms=matched_terms[:12],
        risk_flags=(risk_flags + disqualifying)[:8],
        reasons=reasons,
        recommendation=recommendation,
    )


def serialize_score(score: OpportunityScore) -> dict[str, Any]:
    return {
        "score": score.score,
        "priority": score.priority,
        "technical_fit": score.technical_fit,
        "commercial_fit": score.commercial_fit,
        "urgency": score.urgency,
        "risk": score.risk,
        "matched_terms": score.matched_terms,
        "risk_flags": score.risk_flags,
        "reasons": score.reasons,
        "recommendation": score.recommendation,
    }


def _prediction_evidence(
    lexical: float,
    technical_score: float | None,
    matched_features: list[str],
    product: Any,
) -> list[str]:
    evidence: list[str] = []
    if technical_score is not None:
        evidence.append(f"Aderencia tecnica estimada: {int(round(technical_score * 100))}%.")
    if lexical >= 0.18:
        evidence.append(f"Termos do edital aparecem no datasheet/catalogo: {int(round(lexical * 100))}%.")
    evidence.extend(matched_features[:3])
    category = getattr(product, "category", None)
    if category:
        evidence.append(f"Mesma familia candidata: {category}.")
    return evidence[:5] or ["Sinal fraco, baseado em similaridade textual do produto concorrente."]


def _prediction_level(probability: int, conflicts: list[str]) -> str:
    if conflicts:
        return "risco_tecnico"
    if probability >= 72:
        return "provavel"
    if probability >= 45:
        return "possivel"
    return "baixo_sinal"


def _meaningful_terms(value: Any) -> set[str]:
    text = normalize_text(value)
    if not text:
        return set()
    chunks = re.split(r"[^a-z0-9áéíóúâêôãõç+\-]+", text)
    return {chunk for chunk in chunks if len(chunk) >= 4 and not chunk.isdigit()}


def _extract_value(item: dict[str, Any]) -> float | None:
    for key in (
        "valorTotalEstimado",
        "valor_total_estimado",
        "valorEstimado",
        "valorGlobal",
        "valor_total",
    ):
        value = item.get(key)
        if value is None or value == "":
            continue
        try:
            return float(str(value).replace(".", "").replace(",", "."))
        except ValueError:
            continue
    return None


def _commercial_score(value: float | None) -> int:
    if value is None or value <= 0:
        return 45
    if value >= 500_000:
        return 100
    if value >= 150_000:
        return 86
    if value >= 50_000:
        return 72
    if value >= 15_000:
        return 58
    return 42


def _urgency_score(item: dict[str, Any]) -> int:
    date_value = (
        item.get("dataEncerramentoProposta")
        or item.get("data_encerramento_proposta")
        or item.get("dataAberturaProposta")
        or item.get("data_abertura_proposta")
    )
    parsed = _parse_date(date_value)
    if not parsed:
        return 45
    days = (parsed - date.today()).days
    if days < 0:
        return 20
    if days <= 3:
        return 100
    if days <= 10:
        return 82
    if days <= 25:
        return 65
    return 45


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[: len(fmt)], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _priority(score: int) -> str:
    if score >= 75:
        return "alta"
    if score >= 50:
        return "analisar"
    return "descartar"


def _build_reasons(
    *,
    matched_terms: list[str],
    value: float | None,
    urgency: int,
    risk_flags: list[str],
    disqualifying: list[str],
    technical_fit: int,
) -> list[str]:
    reasons: list[str] = []
    if matched_terms:
        reasons.append("Termos tecnicos encontrados: " + ", ".join(matched_terms[:6]))
    else:
        reasons.append("Baixa aderencia tecnica ao vocabulario do catalogo.")
    if value:
        reasons.append(f"Valor estimado considerado no score: R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    else:
        reasons.append("Valor estimado ausente ou nao informado pelo PNCP.")
    if urgency >= 80:
        reasons.append("Prazo de proposta exige atencao imediata.")
    if risk_flags:
        reasons.append("Possiveis riscos encontrados: " + ", ".join(risk_flags[:4]))
    if disqualifying and technical_fit < 35:
        reasons.append("Objeto aparenta ser de outro segmento.")
    return reasons[:5]


def _recommendation(priority: str, risk_flags: list[str], matched_terms: list[str]) -> str:
    if priority == "alta" and not risk_flags:
        return "Priorizar triagem e importar documentos para analise completa."
    if priority == "alta":
        return "Priorizar, mas revisar riscos antes de proposta."
    if priority == "analisar" and matched_terms:
        return "Enviar para analista validar itens tecnicos."
    if priority == "analisar":
        return "Manter em observacao; faltam sinais tecnicos fortes."
    return "Descartar por baixa aderencia inicial."
