'''
Conceito: O que é a orquestração de pipeline?

Hoje o pipeline roda assim (sicrono - trava API)
  POST /editais/upload -> OCR -> Chunk -> Embed -> salva -> retorna (processo que pode chegar a aprox 3min)

Com worker assicriono vamos ter um jog que roda em background

FERRAMENTE: Prefect
    Open source, retry autoamtico, logs centralizados, cada etapa do pipeline vira uma @task, o pipeline completo vira um @flow

Vocabulário MLOPS:
    - Flow : pipeline completo ( conjunto de tasks orquestradas)
    - Task: unidade atomica de trabalha (uma etapa do pipeline)
    - Run : Uma execução de um flow/task
    - State : Estado atual de uma run (pendente, em execução, falhou, concluída)
    - Retry: Re-execução automatica em caso de falha
    - Artifact : output de uma task que pode ser visualizada na UI

NOTA : Este worker esta preparado para Prefact mas podemos rodar sem ele
(modo sicrono / desenvolvimento)
'''
import logging
import time 
from typing import Optional

logger = logging.getLogger(__name__)
#Import do prefact
try:
    from prefect import flow, task
    from prefect.artifacts import create_markdown_artifact
    PREFECT_DISPONIVEL = True
    logger.info("[PipelineWorker] Prefect disponível — orquestração ativa")
except ImportError:
    # Decoradores dummy — a função roda normal, sem orquestração
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
    Orquestra o pipeline completo : OCR -> Chunk -> Embed -> Match -> MLFlow

    Prepara o terreno para o Job Orquestrador assicrono (proxima etapa).

    Hoje roda de forma sicrona - na proxima etapa, p endpoint vai retornar imediatamente um job_id e o worker roda em background
    '''
    def __init__(self):
        #Import locais para evitar circular imports
        from app.mlops import MatchingTracker, MatchingEvaluator, DriftMonitor
        self.tracker = MatchingTracker()
        self.evaluator = MatchingEvaluator()
        self.drift_monitor = DriftMonitor()

    
    @flow(name = 'Pipeline Edital', retries = 1, retry_delay_seconds = 30)
    def executar_pipeline_completo(self, edital_id: str, pdf_path : str, tenant_id : Optional[str] = None) -> dict:
        '''
        Flow principal - orquestra todo o processo de avaliação de um edital

        O decorador @flow faz o  Prefact:
            - Registrar este pipeline na UI
            - Rastrear cada execução, com logs e estados
            - Re-executar automaticamente em caso de falha (retries = 1)
            - Permitir cancelamento e monitoramento em tempo real

        Args:
            edital_id: ID do edital a ser processado
            pdf_path: Caminho para o arquivo PDF do edital
            tenant_id: ID da empresa (proxima etapa)
        
        Returns : Dict com resumo da execuçaõ e o status em cada etapa 
        '''

        logger.info(f"[PipelineWorker] Iniciando pipeline para edital {edital_id} (tenant: {tenant_id})")
        inicio_total = time.time()
        resultado = {
            'edital_id' : edital_id, 
            'etapas' : {},
            'sucesso' : False,
        }

        try:
            #Etapa 1 - OCR + PARSER
            #Converte PDF -> texto estruturado + chunks
            chunks, embeddings = self._etapa_ocr_e_chunk(
                edital_id = edital_id,
                pdf_path = pdf_path,
            )
            resultado['etapas']['ocr_chunk'] = {'status' : 'ok', 'n_chunks' : len(chunks)}

            #Etapa 2 - Embeddings
            #Gera e salva vetores no pgvector
            self._etapa_embeddings(
                edital_id = edital_id,
                chunks = chunks,
                embeddings = embeddings,
            )
            resultado['etapas']['embeddings'] = {'status':'ok', 'n_embeddings':len(embeddings)}

            #Registra embeddings no DriftMonitor(para detectar um drift futuro)
            self.drift_monitor.registrar_embeddings(
                edital_id = edital_id,
                embeddings = embeddings,
                tenant_id = tenant_id,
            )


            #Etapa 3 - MLFLOW
            #Logas metricas do pipeline (sem o matching ainda - esse é separado)
            self._logar_pipeline_metrics(
                edital_id = edital_id,
                n_chunks = len(chunks),
                tempo_total = time.time() - inicio_total,
                tenant_id = tenant_id,
            )
            resultado['sucesso'] = True
            resultado['tempo_total_segundos'] = round(time.time() - inicio_total, 2)
            logger.info(
                "Pipeline concluido | edital %s | chunks = %d | tempo: %s",
                edital_id, len(chunks), len(chunks), resultado
            )
        except Exception as e:
            logger.exception(f"Erro ao processar edital {edital_id}: {e}")
            resultado['etapas']['erro'] = str(e)
            raise #Re-lança para o prefact registrar como Failed e fazer retry automatico

        return resultado
    
    @flow(name = 'pipeline-matching', retries = 2, retry_delay_seconds = 10)
    def executar_matching_com_tracking(self, edital_id:str, resultados_matching: list[dict], llm_model: str = 'phi3', tenant_id : Optional[str] = None) -> dict:
        '''
        Flow para executar o matching e logar as metricas no MLflow via MatchingTracker

        Args:
            edital_id: ID do edital
            resultados_matching: Output bruto do matching (lista de produtos com detalhes e scores)
            llm_model: Nome do modelo LLM utilizado (para tracking)
            tenant_id: ID da empresa (para tracking)

        Returns:
            Relatório consolidado da avaliação, incluindo requisitos problemáticos e ranking completo

    )
        '''
        logger.info(f"[PipelineWorker] Iniciando etapa de matching com tracking para edital {edital_id} (tenant: {tenant_id})")

        #Logando no mlflow
        self.tracker.log_matching_run( edital_id = edital_id, resultados = resultados_matching, llm_model = llm_model,tenant_id = tenand_id)
        #Avalia a qualidade
        relatorio = self.evaluator.gerar_relatorio_completo(edital_id = edital_id, resultados = resultados_matching, tenant_id = tenant_id)
        #Registra scores para drift monitor
        self.drift_monitor.registrar_matching_scores(
            edital_id = edital_id,
            resultados = resultados_matching,
            tenant_id = tenant_id,
        )

        #Verifica drift
        # ── Verifica drift ────────────────────────────────────────────────────
        analise_drift = self.drift_monitor.detectar_drift_scores()
        if analise_drift.get("drift_detectado"):
            logger.warning(f"[PipelineWorker] {analise_drift['alerta']}")

        # ── Cria artifact no Prefect (se disponível) ──────────────────────────
        # Aparece na UI do Prefect como um relatório Markdown bonito
        if PREFECT_DISPONIVEL:
            saude = relatorio.get("saude_geral", 0)
            dist = relatorio.get("distribuicao", {})
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
            "analise_drift": analise_drift,
        }
    
    # ── Etapas do pipeline (OCR, Embeddings, MLFLOW) ──────────────────────────
    @task(name = 'OCR e Chunking', retries = 1)
    def _etapa_ocr_e_chunk(self, edital_id : str, pdf_path : str):
        '''
        Etapa 1 do pipeline: Faz OCR do PDF, extrai texto e gera chunks

        Args:
            edital_id: ID do edital (para logs)
            pdf_path: Caminho para o arquivo PDF

        Returns:
            Tuple (chunks, embeddings) onde:
                - chunks: lista de dicts com os chunks gerados
                - embeddings: lista de vetores de embedding correspondentes
        '''
        #Aqui a gente chama a função que já existe no matching_engine.py que faz OCR + Chunking
        #Mas poderia ser uma função totalmente separada, ou até um microserviço dedicado só para isso
        from app.pipeline.docling_parser import DoclingParser
        from app.pipeline.chunker import Chunker
        from app.pipeline.embedder import Embedder

        #ocr + extracao de texto estruturado
        parser = DoclingParser()
        texto = chunker.chunk(texto)

        #Divide em chunks
        chunker = Chunker()
        chunks = chunker.chunk(texto)

        #Gera embeddings
        embedder = Embedder()
        embeddings = embedder.embed_batch([c.text for c in chunks])

        return chunks, embeddings

    @task(name= 'salvar embeddings')
    def _etapa_embeddings(self, edital_id: str, chunks, embeddings):
        '''
        Task de persistencia dos embeddings no pgvector
        '''
        from app.vector.pgvector_store import PgVectorStore
        store = PgVectorStore()
        store.save_chunks(edital_id = edital_id, chunks = chunks, embeddings = embeddings)

    @taks(name = 'logar-pipeline-mlflow')
    def _logar_pipeline_metrics(
        self,
        edital_id : str,
        n_chunks : int,
        tempo_total : float,
        tenant_id : Optional[str],
    ):
        '''
        Task de logging no mlflow - registra metricas do pipeline (nao do matching)
        '''
        with self.tracker.start_run(edital_id = edital_id, tenant_id = tenant_id, run_name = f'Pipeline -- {edital_id}'):
            self.tracker.log_params({
                'etapa' : 'ingestao',
                'n_chunks' : n_chunks,
            })
            self.tracker.log_metrics({
                'tempo_pipeline_sgundos' : round(tempo_total,2),
                'chunks por segundo' : round(n_chunks / tempo_total,2) if tempo_total > 0 else 0,
            })

