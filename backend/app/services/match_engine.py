"""
services/matching_engine.py
────────────────────────────
Motor de matching em três camadas:

  1. Busca vetorial (RAG) → recupera trechos relevantes do edital
  2. Regras + heurísticas → score rápido por atributo
  3. LLM (Ollama)         → raciocínio fino e justificativa

Retorna MatchingResult com score 0-1 e reasoning do LLM.

─────────────────────────────────────────────────────────────
MLOps integrado (tracker + evaluator + drift monitor):
  - Cada batch de matching é rastreado como um run no MLflow
  - Ao final do batch, gera relatório de qualidade automático
  - DriftMonitor registra scores para detectar degradação futura

  IMPORTANTE: o MLOps nunca quebra o matching principal.
  Se qualquer módulo falhar, o sistema loga o erro e segue.
─────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

import os
import ollama
from sqlalchemy.orm import Session

_OLLAMA_HOST   = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
_ollama_client = ollama.Client(host=_OLLAMA_HOST)

from app.db.models import MatchingResult, MatchStatus, Product, Requirement
from app.vector.pgvector_store import search_similar
from app.logs.config import logger

# ─────────────────────────────────────────────────────────────────────────────
# MLOps — carregamento condicional (graceful degradation)
#
# Por que try/except aqui?
# O MLOps (MLflow, Evidently) são dependências "extras" — se o container subir
# sem elas instaladas, ou se o servidor MLflow estiver fora do ar, o matching
# deve continuar funcionando normalmente. Nunca deixamos uma ferramenta de
# observabilidade derrubar o sistema principal.
# ─────────────────────────────────────────────────────────────────────────────
try:
    from app.mlops.tracker import MatchingTracker
    from app.mlops.evaluator import MatchingEvaluator
    from app.mlops.drift_monitor import DriftMonitor

    # Singletons por processo — criados uma vez, reutilizados em todas as chamadas.
    # Evita reconectar ao MLflow a cada requisição HTTP.
    _tracker       = MatchingTracker(experiment_name="edital-matching")
    _evaluator     = MatchingEvaluator()
    _drift_monitor = DriftMonitor()

    MLOPS_ENABLED = True
    logger.info("[MatchingEngine] MLOps ativo — MLflow, Evaluator e DriftMonitor carregados")

except Exception as mlops_err:
    # Modo degradado: matching funciona, tracking desativado
    MLOPS_ENABLED = False
    logger.warning(f"[MatchingEngine] MLOps desativado (nao critico): {mlops_err}")


LLM_MODEL = "llama3"   # troque por qualquer modelo disponivel no seu Ollama


# ─────────────────────────────────────────────────────────────────────────────
# Tipos internos
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MatchDetail:
    """Resultado do matching para um par (produto, requisito)."""
    attribute:    str
    required:     str
    found:        str
    rule_score:   float   # 0.0 - 1.0  (score das heurísticas)
    llm_score:    float   # 0.0 - 1.0  (score do LLM)
    final_score:  float   # média ponderada: 30% regras + 70% LLM
    status:       MatchStatus
    reasoning:    str = ""


@dataclass
class MatchReport:
    """Relatório consolidado do matching para um produto inteiro."""
    product_model:  str
    edital_id:      int
    overall_score:  float
    status:         MatchStatus
    details:        list[MatchDetail] = field(default_factory=list)
    summary:        str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Função pública principal — produto único
# ─────────────────────────────────────────────────────────────────────────────

def run_matching(
    db: Session,
    product: Product,
    requirements: list[Requirement],
) -> MatchReport:
    """
    Executa o pipeline completo de matching para UM produto.

    Fluxo por requisito:
      1. RAG: busca chunks do edital relacionados ao requisito
      2. Heurística: comparação direta de valores
      3. LLM: raciocínio fino com contexto do edital
      4. Score final = 30% heurística + 70% LLM
      5. Persiste MatchingResult no banco

    Retorna MatchReport com score geral e detalhes por requisito.

    NOTA MLOps: o tracking MLflow acontece em match_all_products() (batch),
    não aqui — assim evitamos abrir/fechar um run por produto.
    """
    if not requirements:
        logger.warning(f"[Matching] Produto {product.model}: nenhum requisito para avaliar")
        return MatchReport(
            product_model=product.model,
            edital_id=0,
            overall_score=0.0,
            status=MatchStatus.VERIFICAR,
        )

    details: list[MatchDetail] = []

    for req in requirements:

        # ── Camada 1: RAG ─────────────────────────────────────────────────────
        # Busca os 4 chunks do edital mais similares ao requisito atual.
        # Esses trechos fornecem contexto real do edital para o LLM.
        context_chunks = search_similar(
            db,
            query     = f"{req.attribute} {req.raw_value}",
            edital_id = req.edital_id,
            top_k     = 4,
        )
        context_text = "\n---\n".join(c["text"] for c in context_chunks)

        # ── Camada 2: Heurísticas ─────────────────────────────────────────────
        # Score rápido por comparação direta de valores (sem LLM).
        # Roda em microsegundos — serve como sinal inicial para o LLM.
        rule_score = _rule_score(product.data, req)

        # ── Camada 3: LLM ─────────────────────────────────────────────────────
        # Avaliação com contexto completo: especificações do produto +
        # requisito do edital + trechos RAG. Retorna score + justificativa.
        llm_score, reasoning = _llm_score(product, req, context_text)

        # ── Score final ponderado ─────────────────────────────────────────────
        # Regras têm menos peso (30%) porque são comparações simplificadas.
        # LLM tem mais peso (70%) porque entende nuances e contexto.
        final_score = round(0.3 * rule_score + 0.7 * llm_score, 3)
        status      = _score_to_status(final_score)

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

        # ── Persiste no banco ─────────────────────────────────────────────────
        db.add(MatchingResult(
            product_id      = product.id,
            requirements_id = req.id,
            status          = status,
            score           = final_score,
            details         = detail.found,
            llm_reasoning   = reasoning,
        ))

    db.commit()

    overall = round(sum(d.final_score for d in details) / len(details), 3)
    status  = _score_to_status(overall)
    summary = _generate_summary(product, details, overall)

    return MatchReport(
        product_model = product.model,
        edital_id     = requirements[0].edital_id,
        overall_score = overall,
        status        = status,
        details       = details,
        summary       = summary,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Função pública batch — todos os produtos de um edital
# ─────────────────────────────────────────────────────────────────────────────

def match_all_products(
    db: Session,
    products: list[Product],
    requirements: list[Requirement],
    edital_id: int,
    tenant_id: str | None = None,
) -> list[MatchReport]:
    """
    Roda run_matching() para cada produto e aciona o MLOps ao final.

    Este é o ponto de entrada para o router /editais/{id}/match.
    Um único run MLflow representa o batch inteiro (N produtos x 1 edital).

    Args:
        db:           sessão do banco de dados
        products:     lista de produtos do catálogo a avaliar
        requirements: requisitos extraídos do edital
        edital_id:    ID do edital sendo avaliado
        tenant_id:    ID da empresa — usado quando Auth/Multi-tenant estiver pronto

    Returns:
        Lista de MatchReport ordenada por score decrescente (melhor primeiro).
    """
    inicio_batch = time.time()
    logger.info(
        f"[MatchingEngine] Iniciando batch | edital={edital_id} | "
        f"produtos={len(products)} | requisitos={len(requirements)}"
    )

    # ── Executa matching produto a produto ────────────────────────────────────
    reports: list[MatchReport] = []
    for product in products:
        report = run_matching(db=db, product=product, requirements=requirements)
        reports.append(report)

    # Ordena por score decrescente — melhor candidato no topo
    reports.sort(key=lambda r: r.overall_score, reverse=True)

    tempo_batch = round(time.time() - inicio_batch, 2)
    logger.info(
        f"[MatchingEngine] Batch concluido | tempo={tempo_batch}s | "
        f"melhor={reports[0].product_model if reports else 'N/A'} "
        f"score={reports[0].overall_score if reports else 0}"
    )

    # ── MLOps ─────────────────────────────────────────────────────────────────
    # Só executa se os módulos MLOps foram carregados com sucesso.
    # Encapsulado em função separada para manter este método limpo.
    if MLOPS_ENABLED and reports:
        _executar_mlops(
            reports     = reports,
            edital_id   = edital_id,
            tempo_batch = tempo_batch,
            tenant_id   = tenant_id,
        )

    return reports


# ─────────────────────────────────────────────────────────────────────────────
# MLOps — execução pós-batch
# ─────────────────────────────────────────────────────────────────────────────

def _executar_mlops(
    reports: list[MatchReport],
    edital_id: int,
    tempo_batch: float,
    tenant_id: str | None,
) -> None:
    """
    Executa todas as operações MLOps após o batch de matching.

    Separado em função própria por três motivos:
      1. Mantém match_all_products() limpo e legível
      2. Isola erros — um try/except centralizado cobre tudo
      3. Na próxima etapa (Job Orchestrator), esta função vai rodar
         de forma assíncrona sem bloquear a resposta HTTP

    Operações executadas:
      A) Converte MatchReports para o formato esperado pelos módulos MLOps
      B) Loga run no MLflow (parâmetros + métricas do batch inteiro)
      C) Avalia qualidade (distribuição de scores, gaps, saúde geral)
      D) Registra scores no DriftMonitor para histórico
      E) Verifica drift comparando com runs anteriores
    """
    try:
        # ── A) Conversão de formato ───────────────────────────────────────────
        # MatchReport é um dataclass interno. Os módulos MLOps esperam dicts
        # com campos padronizados. Fazemos a conversão aqui para não acoplar
        # os módulos MLOps aos tipos do matching engine.
        resultados_mlops = [
            {
                # Identificação do produto
                "modelo":       report.product_model,
                # Score geral (0.0 - 1.0)
                "score_geral":  report.overall_score,
                # Status em string: "ATENDE" / "VERIFICAR" / "NÃO ATENDE"
                "status_geral": report.status.value,
                # Detalhes por requisito (para o evaluator calcular gaps)
                "detalhes": [
                    {
                        "requisito": d.attribute,
                        "score":     d.final_score,
                        "status":    d.status.value,
                    }
                    for d in report.details
                ],
            }
            for report in reports
        ]

        # ── B) Loga run no MLflow ─────────────────────────────────────────────
        # Abre um run MLflow e registra:
        #   Parâmetros: modelo LLM, pesos da ponderação, total de produtos
        #   Métricas: score médio/min/max, distribuição ATENDE/VERIFICAR/NAO_ATENDE
        #   Tags: edital_id, tenant_id, ambiente
        _tracker.log_matching_run(
            edital_id  = str(edital_id),
            resultados = resultados_mlops,
            llm_model  = LLM_MODEL,
            tenant_id  = tenant_id,
            # Pesos usados na ponderação — logados como parâmetros para rastreabilidade
            score_weight_heuristic = 0.30,
            score_weight_llm       = 0.70,
        )

        # Loga tempo do batch como métrica separada (contexto de performance)
        import mlflow
        with mlflow.start_run(run_name=f"perf-batch-{edital_id}", nested=True):
            mlflow.log_metric("tempo_batch_segundos", tempo_batch)
            mlflow.log_metric("produtos_avaliados",   len(reports))

        # ── C) Avalia qualidade do batch ──────────────────────────────────────
        # Gera relatório com:
        #   - Distribuição dos scores (média, mediana, desvio padrão)
        #   - % de produtos na zona de incerteza (VERIFICAR)
        #   - Gaps por requisito (quais requisitos têm score sistematicamente baixo)
        #   - Score de "saúde geral" de 0 a 100
        relatorio = _evaluator.gerar_relatorio_completo(
            edital_id  = str(edital_id),
            resultados = resultados_mlops,
            tenant_id  = tenant_id,
        )

        # Loga saúde geral como métrica no MLflow
        with mlflow.start_run(run_name=f"qualidade-{edital_id}", nested=True):
            mlflow.log_metric("saude_geral", relatorio.get("saude_geral", 0))

        # Repassa alertas do evaluator para o log da aplicação
        alertas = relatorio.get("distribuicao", {}).get("alertas", [])
        for alerta in alertas:
            logger.warning(f"[MLOps/Evaluator] {alerta}")

        # Loga gaps de requisitos (requisitos com score médio abaixo de 0.5)
        problematicos = relatorio.get("cobertura", {}).get("requisitos_problematicos", [])
        if problematicos:
            logger.warning(
                f"[MLOps/Evaluator] {len(problematicos)} requisito(s) com score medio < 0.5: "
                f"{[r['requisito'] for r in problematicos]}"
            )

        # ── D) Registra no DriftMonitor ───────────────────────────────────────
        # Cada batch fica salvo em /data/drift_history/scores_history.json.
        # Com o tempo, esse histórico permite detectar degradação gradual:
        #   - O LLM ficou mais conservador depois de uma atualização?
        #   - Os editais estão pedindo requisitos que o catálogo não cobre?
        _drift_monitor.registrar_scores(
            edital_id  = str(edital_id),
            resultados = resultados_mlops,
            tenant_id  = tenant_id,
        )

        # ── E) Verifica drift acumulado ───────────────────────────────────────
        # Compara os 10 runs mais recentes com os 10 anteriores.
        # Se score médio caiu > 0.10 pontos → alerta no log.
        # Com mais dados (>20 runs), o Evidently gera relatório HTML completo.
        analise_drift = _drift_monitor.detectar_drift_scores(janela_runs=10)

        if analise_drift.get("drift_detectado"):
            logger.warning(
                f"[MLOps/Drift] DRIFT DETECTADO | {analise_drift.get('alerta')} | "
                f"edital={edital_id}"
            )
        else:
            logger.info(
                f"[MLOps/Drift] Scores estaveis | "
                f"delta={analise_drift.get('delta', 'N/A')} | "
                f"status={analise_drift.get('status')}"
            )

        # ── Resumo final no log ───────────────────────────────────────────────
        logger.info(
            f"[MLOps] Tracking completo | edital={edital_id} | "
            f"saude={relatorio.get('saude_geral')}/100 | "
            f"drift={analise_drift.get('status')} | "
            f"alertas={len(alertas)}"
        )

    except Exception as e:
        # MLOps NUNCA pode quebrar o matching principal.
        # O matching já foi salvo no banco — só o tracking falhou.
        # Loga o erro completo (com stack trace) e segue.
        logger.error(
            f"[MLOps] Erro no tracking (nao critico, matching ja salvo): {e}",
            exc_info=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Camada 1 – Heurísticas / Regras
# ─────────────────────────────────────────────────────────────────────────────

def _rule_score(specs: dict, req: Requirement) -> float:
    """
    Score rápido por comparação direta entre especificação e requisito.

    Retorna:
      1.0 → atende completamente
      0.5 → inconclusivo (sem dados ou comparação parcial)
      0.0 → não atende

    Estratégias (nesta ordem de prioridade):
      1. Sem dados → 0.5 (inconclusivo, não penaliza)
      2. Booleano  → compara "sim/yes/true/1"
      3. Numérico  → compara valores, aceita até 20% abaixo (score 0.5)
      4. Textual   → verifica se required está contido em actual ou vice-versa
    """
    key = req.attribute
    if not key or key not in specs:
        return 0.5   # sem dados no catálogo → inconclusivo

    actual   = str(specs[key]).strip().lower()
    required = str(req.parsed_value or req.raw_value or "").strip().lower()

    if not required:
        return 0.5   # requisito vazio → inconclusivo

    # ── Comparação booleana ───────────────────────────────────────────────────
    bool_yes = {"sim", "yes", "true", "1"}
    if required in bool_yes:
        return 1.0 if actual in bool_yes else 0.0

    # ── Comparação numérica ───────────────────────────────────────────────────
    # Exemplo: required="24", actual="24 portas" → extrai 24 de cada
    actual_num   = _extract_number(actual)
    required_num = _extract_number(required)
    if actual_num is not None and required_num is not None:
        if actual_num >= required_num:
            return 1.0
        elif actual_num >= required_num * 0.8:  # até 20% abaixo = parcial
            return 0.5
        return 0.0

    # ── Comparação textual ────────────────────────────────────────────────────
    # Verifica se o valor exigido está contido na especificação (ou vice-versa)
    return 1.0 if required in actual or actual in required else 0.0


def _extract_number(text: str) -> float | None:
    """
    Extrai o primeiro número de uma string.
    Exemplos: "24 portas" → 24.0 | "10Gbps" → 10.0 | "N/A" → None
    """
    m = re.search(r"[\d]+(?:[.,]\d+)?", text)
    if m:
        return float(m.group().replace(",", "."))
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Camada 2 – LLM (Ollama)
# ─────────────────────────────────────────────────────────────────────────────

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
    Chama o Ollama para avaliar o requisito com raciocínio em linguagem natural.

    Envia para o LLM:
      - Especificações completas do produto (JSON)
      - O requisito específico sendo avaliado
      - Trechos relevantes do edital (contexto RAG)

    Retorna (score: float, reasoning: str).
    Em caso de falha, retorna (0.5, mensagem de erro) — nunca lança exceção.
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
            options = {"temperature": 0.1},   # temperatura baixa = respostas mais determinísticas
        )
        raw = response["message"]["content"].strip()

        # Extrai JSON mesmo que o modelo coloque texto em volta
        # Exemplo: "Aqui está minha avaliação: {"score": 0.9, ...}"
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            data      = json.loads(match.group())
            score     = max(0.0, min(1.0, float(data.get("score", 0.5))))
            reasoning = str(data.get("reasoning", ""))
            return score, reasoning

        logger.warning(f"[LLM] Resposta sem JSON para '{req.attribute}': {raw[:100]}")

    except Exception as e:
        logger.warning(f"[LLM] Erro ao avaliar '{req.attribute}': {e}")

    # Fallback seguro — nunca lança exceção para cima
    return 0.5, "Não foi possível obter avaliação do LLM."


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _score_to_status(score: float) -> MatchStatus:
    """
    Converte score numérico para enum de status.

    Thresholds (definidos junto com o MatchingEvaluator — manter sincronizados):
      >= 0.75 → ATENDE
      >= 0.45 → VERIFICAR
       < 0.45 → NAO_ATENDE
    """
    if score >= 0.75:
        return MatchStatus.ATENDE
    elif score >= 0.45:
        return MatchStatus.VERIFICAR
    return MatchStatus.NAO_ATENDE


def _generate_summary(product: Product, details: list[MatchDetail], overall: float) -> str:
    """
    Gera linha de resumo legível para logs e relatórios.
    Exemplo: "Switch XS-2024: score geral 87% | ✅ 5 atende · ⚠️ 2 verificar · ❌ 1 não atende"
    """
    atende     = sum(1 for d in details if d.status == MatchStatus.ATENDE)
    nao_atende = sum(1 for d in details if d.status == MatchStatus.NAO_ATENDE)
    verificar  = sum(1 for d in details if d.status == MatchStatus.VERIFICAR)
    return (
        f"{product.model}: score geral {overall:.0%} | "
        f"✅ {atende} atende · ⚠️ {verificar} verificar · ❌ {nao_atende} não atende"
    )