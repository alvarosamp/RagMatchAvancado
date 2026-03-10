'''
Conceito: O que é orquestração de pipeline?

Hoje o pipeline roda assim (síncrono - trava API):
  POST /editais/upload -> OCR -> Chunk -> Embed -> salva -> retorna (pode demorar ~3min)

Com worker assíncrono teremos um job que roda em background:
  POST /editais/upload -> retorna job_id (instantâneo)
                          ↓
                      [Worker roda em background]
                          OCR -> Chunk -> Embed -> salva
                          ↓
                   GET /jobs/{job_id}/status -> "concluido"

FERRAMENTA: Prefect
    Open source, retry automático, logs centralizados.
    Cada etapa do pipeline vira uma @task.
    O pipeline completo vira um @flow.

Vocabulário MLOps:
    - Flow:  pipeline completo (conjunto de tasks orquestradas)
    - Task:  unidade atômica de trabalho (uma etapa do pipeline)
    - Run:   uma execução de um flow/task
    - State: estado atual de um run (pendente, em execução, falhou, concluída)
    - Retry: re-execução automática em caso de falha
    - Artifact: output de uma task que pode ser visualizado na UI

NOTA: Este worker está preparado para Prefect mas roda SEM ele
(modo síncrono / desenvolvimento). O decorador @flow/@task é opcional.
'''

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Import do Prefect (opcional — cria decoradores dummy se não estiver instalado)
try:
    from prefect import flow, task
    from prefect.artifacts import create_markdown_artifact
    PREFECT_DISPONIVEL = True
    logger.info("[PipelineWorker] Prefect disponível — orquestração ativa")
except ImportError:
    # Decoradores dummy — a função roda normalmente, sem orquestração
    def flow(func=None, **kwargs):
        return func if func else lambda f: f

    def task(func=None, **kwargs):
        return func if func else lambda f: f

    def create_markdown_artifact(*args, **kwargs):
        pass

    PREFECT_DISPONIVEL = False
    logger.warning("[PipelineWorker] Prefect NÃO disponível — rodando sem orquestração")


class PipelineWorker:
    '''
    Orquestra o pipeline completo: OCR -> Chunk -> Embed -> Match -> MLflow.

    Prepara o terreno para o Job Orchestrator assíncrono (próxima etapa).
    Hoje roda de forma síncrona — na próxima etapa, o endpoint vai retornar
    imediatamente um job_id e o worker roda em background.
    '''

    def __init__(self):
        # Imports locais para evitar circular imports
        from app.mlops import MatchingTracker, MatchingEvaluator, DriftMonitor
        self.tracker       = MatchingTracker()
        self.evaluator     = MatchingEvaluator()
        self.drift_monitor = DriftMonitor()

    @flow(name='Pipeline Edital', retries=1, retry_delay_seconds=30)
    def executar_pipeline_completo(
        self,
        edital_id: str,
        pdf_path: str,
        tenant_id: Optional[str] = None,
    ) -> dict:
        '''
        Flow principal — orquestra todo o processo de ingestão de um edital.

        O decorador @flow faz o Prefect:
            - Registrar este pipeline na UI
            - Rastrear cada execução com logs e estados
            - Re-executar automaticamente em caso de falha (retries=1)
            - Permitir cancelamento e monitoramento em tempo real

        Args:
            edital_id: ID do edital a ser processado
            pdf_path:  Caminho para o arquivo PDF do edital
            tenant_id: ID da empresa (próxima etapa)

        Returns:
            Dict com resumo da execução e status em cada etapa
        '''
        logger.info(f"[PipelineWorker] Iniciando pipeline | edital={edital_id} | tenant={tenant_id}")
        inicio_total = time.time()

        resultado = {
            'edital_id': edital_id,
            'etapas':    {},
            'sucesso':   False,
        }

        try:
            # ── Etapa 1: OCR + Chunking ───────────────────────────────────────
            # Converte PDF → texto estruturado + chunks com embeddings
            chunks, embeddings = self._etapa_ocr_e_chunk(
                edital_id=edital_id,
                pdf_path=pdf_path,
            )
            resultado['etapas']['ocr_chunk'] = {'status': 'ok', 'n_chunks': len(chunks)}

            # ── Etapa 2: Salvar embeddings no pgvector ────────────────────────
            self._etapa_embeddings(
                edital_id=edital_id,
                chunks=chunks,
                embeddings=embeddings,
            )
            resultado['etapas']['embeddings'] = {'status': 'ok', 'n_embeddings': len(embeddings)}

            # Registra embeddings no DriftMonitor (para detectar drift futuro)
            self.drift_monitor.registrar_embeddings(
                edital_id=edital_id,
                embeddings=embeddings,
                tenant_id=tenant_id,
            )

            # ── Etapa 3: Loga métricas do pipeline no MLflow ──────────────────
            # (O matching é logado separadamente em executar_matching_com_tracking)
            self._logar_pipeline_metrics(
                edital_id=edital_id,
                n_chunks=len(chunks),
                tempo_total=time.time() - inicio_total,
                tenant_id=tenant_id,
            )

            resultado['sucesso'] = True
            resultado['tempo_total_segundos'] = round(time.time() - inicio_total, 2)

            logger.info(
                f"[PipelineWorker] Pipeline concluído | edital={edital_id} | "
                f"chunks={len(chunks)} | tempo={resultado['tempo_total_segundos']}s"
            )

        except Exception as e:
            logger.exception(f"[PipelineWorker] Erro ao processar edital {edital_id}: {e}")
            resultado['etapas']['erro'] = str(e)
            raise  # Re-lança para o Prefect registrar como FAILED e fazer retry

        return resultado

    @flow(name='pipeline-matching', retries=2, retry_delay_seconds=10)
    def executar_matching_com_tracking(
        self,
        edital_id: str,
        resultados_matching: list[dict],
        llm_model: str = 'llama3',
        tenant_id: Optional[str] = None,
    ) -> dict:
        '''
        Flow de matching — integra o resultado do matching com MLflow.

        Chamado pelo matching_engine.py depois que o matching terminar.
        Loga tudo no MLflow e gera relatório de avaliação.

        Args:
            edital_id:           ID do edital
            resultados_matching: saída do matching_engine.py
            llm_model:           modelo LLM usado
            tenant_id:           ID da empresa

        Returns:
            Dict com métricas e relatório de qualidade.
        '''
        logger.info(
            f"[PipelineWorker] Iniciando tracking do matching | "
            f"edital={edital_id} | tenant={tenant_id}"
        )

        # Loga no MLflow
        self.tracker.log_matching_run(
            edital_id=edital_id,
            resultados=resultados_matching,
            llm_model=llm_model,
            # BUG CORRIGIDO: era 'tenand_id' (typo) → correto: tenant_id
            tenant_id=tenant_id,
        )

        # Avalia qualidade do matching (distribuição, gaps, saúde geral)
        relatorio = self.evaluator.gerar_relatorio_completo(
            edital_id=edital_id,
            resultados=resultados_matching,
            tenant_id=tenant_id,
        )

        # Registra scores para o DriftMonitor (histórico para detecção futura)
        # BUG CORRIGIDO: era self.drift_monitor.registrar_matching_scores() (não existe)
        # Correto: self.drift_monitor.registrar_scores()
        self.drift_monitor.registrar_scores(
            edital_id=edital_id,
            resultados=resultados_matching,
            tenant_id=tenant_id,
        )

        # Verifica drift acumulado comparando com runs anteriores
        analise_drift = self.drift_monitor.detectar_drift_scores()
        if analise_drift.get("drift_detectado"):
            logger.warning(f"[PipelineWorker] DRIFT | {analise_drift['alerta']}")

        # Cria artifact no Prefect (aparece como relatório Markdown na UI)
        if PREFECT_DISPONIVEL:
            saude = relatorio.get("saude_geral", 0)
            dist  = relatorio.get("distribuicao", {})
            create_markdown_artifact(
                key=f"matching-report-edital-{edital_id}",
                markdown=f"""
## Relatório de Matching — Edital {edital_id}

**Saúde Geral:** {saude}/100

| Métrica | Valor |
|---------|-------|
| Score Médio | {dist.get('score_media', 'N/A')} |
| Desvio Padrão | {dist.get('desvio_padrao', 'N/A')} |
| Zona de Incerteza | {dist.get('pct_zona_incerteza', 'N/A')}% |

**Alertas:** {len(dist.get('alertas', []))} alerta(s)
**Drift:** {'⚠️ Detectado' if analise_drift.get('drift_detectado') else '✅ Estável'}
                """,
                description=f"Relatório de qualidade do matching para edital {edital_id}",
            )

        return {
            "relatorio_qualidade": relatorio,
            "analise_drift":       analise_drift,
        }

    # =========================================================================
    # TASKS INTERNAS (etapas do pipeline)
    # =========================================================================

    @task(name='OCR e Chunking', retries=1)
    def _etapa_ocr_e_chunk(self, edital_id: str, pdf_path: str):
        '''
        Task de OCR e chunking.
        O decorador @task faz o Prefect rastrear esta etapa individualmente.
        Se falhar, o Prefect re-executa só esta task (não o pipeline todo).
        '''
        from app.pipeline.docling_parser import DoclingParser
        from app.pipeline.chunker import Chunker
        from app.pipeline.embedder import Embedder

        # OCR + extração de texto estruturado
        parser = DoclingParser()
        # BUG CORRIGIDO: era texto = chunker.chunk(texto) antes de chunker ser criado
        # Ordem correta: parser → chunker → embedder
        texto = parser.parse(pdf_path)

        # Divide em chunks semânticos
        chunker = Chunker()
        chunks  = chunker.chunk(texto)

        # Gera embeddings para cada chunk
        embedder   = Embedder()
        embeddings = embedder.embed_batch([c.text for c in chunks])

        return chunks, embeddings

    @task(name='Salvar Embeddings')
    def _etapa_embeddings(self, edital_id: str, chunks, embeddings):
        '''
        Task de persistência dos embeddings no pgvector.
        '''
        from app.vector.pgvector_store import PgVectorStore
        store = PgVectorStore()
        store.save_chunks(edital_id=edital_id, chunks=chunks, embeddings=embeddings)

    # BUG CORRIGIDO: era @taks (typo) → correto: @task
    @task(name='Logar Pipeline MLflow')
    def _logar_pipeline_metrics(
        self,
        edital_id: str,
        n_chunks: int,
        tempo_total: float,
        tenant_id: Optional[str],
    ):
        '''
        Task de logging no MLflow — registra métricas do pipeline (não do matching).
        '''
        with self.tracker.start_run(
            edital_id=edital_id,
            tenant_id=tenant_id,
            run_name=f'Pipeline-{edital_id}',
        ):
            self.tracker.log_params({
                'etapa':    'ingestao',
                'n_chunks': n_chunks,
            })
            self.tracker.log_metrics({
                'tempo_pipeline_segundos': round(tempo_total, 2),
                'chunks_por_segundo':      round(n_chunks / tempo_total, 2) if tempo_total > 0 else 0,
            })