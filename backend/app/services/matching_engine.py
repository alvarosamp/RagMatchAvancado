"""
services/matching_engine.py
────────────────────────────
Motor de matching em três camadas:

  1. Busca vetorial (RAG) → recupera trechos relevantes do edital
  2. Regras + heurísticas → score rápido por atributo
  3. LLM (Ollama)         → raciocínio fino e justificativa

Retorna MatchingResult com score 0–1 e reasoning do LLM.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import os
import ollama
from sqlalchemy.orm import Session

_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
_ollama_client = ollama.Client(host=_OLLAMA_HOST)

from app.db.models import MatchingResult, MatchStatus, Product, Requirement
from app.vector.pgvector_store import search_similar
from app.logs.config import logger

LLM_MODEL = "llama3"   # troque por qualquer modelo que tiver no seu Ollama


# ──────────────────────────────────────────
# Tipos internos
# ──────────────────────────────────────────

@dataclass
class MatchDetail:
    attribute:    str
    required:     str
    found:        str
    rule_score:   float          # 0.0 – 1.0  (heurística)
    llm_score:    float          # 0.0 – 1.0  (LLM)
    final_score:  float          # média ponderada
    status:       MatchStatus
    reasoning:    str = ""


@dataclass
class MatchReport:
    product_model:  str
    edital_id:      int
    overall_score:  float
    status:         MatchStatus
    details:        list[MatchDetail] = field(default_factory=list)
    summary:        str = ""


# ──────────────────────────────────────────
# Motor principal
# ──────────────────────────────────────────

def run_matching(
    db: Session,
    product: Product,
    requirements: list[Requirement],
) -> MatchReport:
    """
    Executa o pipeline completo de matching para um produto.

    1. Para cada requisito, busca chunks relevantes (RAG).
    2. Aplica heurísticas rápidas.
    3. Chama o LLM para decisão final.
    4. Persiste MatchingResults no banco.
    5. Retorna MatchReport consolidado.
    """
    if not requirements:
        logger.warning(f"[Matching] Produto {product.model}: nenhum requisito para avaliar")
        return MatchReport(
            product_model="", edital_id=0,
            overall_score=0.0, status=MatchStatus.VERIFICAR,
        )

    details: list[MatchDetail] = []

    for req in requirements:
        context_chunks = search_similar(
            db,
            query     = f"{req.attribute} {req.raw_value}",
            edital_id = req.edital_id,
            top_k     = 4,
        )
        context_text = "\n---\n".join(c["text"] for c in context_chunks)

        rule_score = _rule_score(product.data, req)
        llm_score, reasoning = _llm_score(product, req, context_text)

        # Ponderação: regras têm peso 30%, LLM 70%
        final_score = round(0.3 * rule_score + 0.7 * llm_score, 3)
        status = _score_to_status(final_score)

        detail = MatchDetail(
            attribute   = req.attribute or "",
            required    = req.raw_value or "",
            found       = str(product.data.get(req.attribute, "N/A")),
            rule_score  = rule_score,
            llm_score   = llm_score,
            final_score = final_score,
            status      = status,
            reasoning   = reasoning,
        )
        details.append(detail)

        # Persiste no banco
        db.add(MatchingResult(
            product_id      = product.id,
            requirements_id = req.id,
            status          = status,
            score           = final_score,
            details         = detail.found,
            llm_reasoning   = reasoning,
        ))

    db.commit()

    overall  = round(sum(d.final_score for d in details) / len(details), 3)
    status   = _score_to_status(overall)
    summary  = _generate_summary(product, details, overall)

    return MatchReport(
        product_model = product.model,
        edital_id     = requirements[0].edital_id,
        overall_score = overall,
        status        = status,
        details       = details,
        summary       = summary,
    )


# ──────────────────────────────────────────
# Camada 1 – Heurísticas / Regras
# ──────────────────────────────────────────

def _rule_score(specs: dict, req: Requirement) -> float:
    """
    Score rápido por comparação direta.
    Retorna 1.0 (atende) / 0.5 (parcial) / 0.0 (não atende).
    """
    key = req.attribute
    if not key or key not in specs:
        return 0.5   # sem dados → inconclusivo

    actual   = str(specs[key]).strip().lower()
    required = str(req.parsed_value or req.raw_value or "").strip().lower()

    if not required:
        return 0.5

    # Comparação booleana
    bool_yes = {"sim", "yes", "true", "1"}
    if required in bool_yes:
        return 1.0 if actual in bool_yes else 0.0

    # Comparação numérica
    actual_num   = _extract_number(actual)
    required_num = _extract_number(required)
    if actual_num is not None and required_num is not None:
        if actual_num >= required_num:
            return 1.0
        elif actual_num >= required_num * 0.8:
            return 0.5
        return 0.0

    # Comparação textual simples
    return 1.0 if required in actual or actual in required else 0.0


def _extract_number(text: str) -> float | None:
    """Extrai o primeiro número de uma string."""
    m = re.search(r"[\d]+(?:[.,]\d+)?", text)
    if m:
        return float(m.group().replace(",", "."))
    return None


# ──────────────────────────────────────────
# Camada 2 – LLM (Ollama)
# ──────────────────────────────────────────

_SYSTEM_PROMPT = """Você é um especialista em análise de licitações públicas brasileiras.
Sua tarefa é verificar se um produto atende a um requisito técnico de um edital.
Responda APENAS com JSON válido no seguinte formato:
{"score": <float 0.0 a 1.0>, "reasoning": "<explicação concisa em português>"}
- score 1.0 = atende completamente
- score 0.5 = atende parcialmente ou dados insuficientes
- score 0.0 = não atende"""

def _llm_score(
    product: Product,
    req: Requirement,
    context: str,
) -> tuple[float, str]:
    """
    Chama o Ollama para avaliar o requisito.
    Retorna (score, reasoning).
    """
    user_msg = f"""
## Produto
Modelo: {product.model}
Especificações: {json.dumps(product.data, ensure_ascii=False, indent=2)}

## Requisito do Edital
Atributo : {req.attribute}
Requisito: {req.raw_value}

## Trechos relevantes do edital (contexto RAG)
{context or "Nenhum trecho encontrado."}

Avalie se o produto atende ao requisito e retorne o JSON solicitado.
"""

    try:
        response = _ollama_client.chat(
            model    = LLM_MODEL,
            messages = [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
            options={"temperature": 0.1},
        )
        raw = response["message"]["content"].strip()

        # Tenta extrair JSON mesmo que o modelo coloque texto em volta
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
            score     = max(0.0, min(1.0, float(data.get("score", 0.5))))
            reasoning = str(data.get("reasoning", ""))
            return score, reasoning

    except Exception as e:
        logger.warning(f"[LLM] Erro ao avaliar '{req.attribute}': {e}")

    return 0.5, "Não foi possível obter avaliação do LLM."


# ──────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────

def _score_to_status(score: float) -> MatchStatus:
    if score >= 0.75:
        return MatchStatus.ATENDE
    elif score >= 0.45:
        return MatchStatus.VERIFICAR
    return MatchStatus.NAO_ATENDE


def _generate_summary(product: Product, details: list[MatchDetail], overall: float) -> str:
    atende     = sum(1 for d in details if d.status == MatchStatus.ATENDE)
    nao_atende = sum(1 for d in details if d.status == MatchStatus.NAO_ATENDE)
    verificar  = sum(1 for d in details if d.status == MatchStatus.VERIFICAR)
    return (
        f"{product.model}: score geral {overall:.0%} | "
        f"✅ {atende} atende · ⚠️ {verificar} verificar · ❌ {nao_atende} não atende"
    )