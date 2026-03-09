'''
Experiment tracking

Imagine que voce testou o matching com llama3 hoje e amanha quer testar com o mistral.
Como voce sabe qual foi melhor ? Sem tracking nao temos como saber

O mlflow resolve isso. Cada execução do matching vira um 'run' registrado
com todos os parametros usados e as metricas resultantes.

Vocabulario MLOPS:
- Experiment: grupo de runs relacionados (ex: "edital-matching")
- Run: uma execução específica com parâmetros + métricas logadas
- Parameter: configuração usada (ex: modelo LLM, peso do score)
- Metric: resultado mensurável (ex: score médio, tempo de execução)
- Artifact: arquivo gerado (ex: relatório PDF, CSV de resultados)
- Tag: metadado livre (ex: edital_id, tenant_id)]

'''

import time

from llama_cpp import Optional 
import mlflow
import logging
import os
logger = logging.getLogger(__name__)

class MatchingTracker:
    '''
    Responsavel por registrar cada execução do pipeline no mlflow
    
    Como usar : 
    tracker = MatchingTracker()
    with tracker.start_run(edital_id="123"):
        tracker.log_params(...)
        tracker.log_metrics(...)
    '''
    def __init__(self, experiment_name: str = 'edital_matching'):
        '''
        Inicializaa o tracker apontando para o servidor do mlflow.
        
        O MLflow precisa saber ONDE salvar os dados.
        A URI pode ser:
          - "http://localhost:5000"     → servidor MLflow rodando em Docker
          - "./mlruns"                  → pasta local (sem servidor, bom pra dev)
          - "postgresql://..."          → banco de dados (produção)

        Aqui usamos variável de ambiente MLFLOW_TRACKING_URI com fallback local.
        
        
        '''
        tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
        mlflow.set_tracking_uri(tracking_uri)
        #O experiment agrupa todos os runs relacionados
        # S nao existir o mlflow cria automaticamente
        mlflow.set_experiment(experiment_name)
        self.expertiment_name = experiment_name
        logger.info(f"MLflow tracking URI set to: {tracking_uri}")
        
    def start_run(self, edital_id: str, tenant_id : Optional[str] = None, run_name: Optioonal[str] = None):
        '''
        Abre um novo 'run' no mlflow para registrar essa execução
        
        Um run é como uma linha numa planilha de experimentos
        Cada run tem um ID unico, um timestamp, parametros, metricas e artefatos
        
        Args:
            edital_id: ID do edital sendo processado (usamos como tag)
            tenant_id: ID do tenant (opcional, mas útil para multi-tenant)
            run_name: nome legível para o run (opcional)
            
        Return: 
        COontext maneger do MLFLOW - use com 'with tracker.start_rum((...))
        '''
        
        #Tags sao metadados extras que aparecem na ui do mlflow
        #Uteis para fitlrar runs por empresa, versao, ambiente 
        tags = {
            'edital_id': str(edital_id),
            'ambiente' : 'desenvolvimenmto', #Trocar para produção quando for para o ar
        }
        
        if tenant_id:
            tags['tenant_id'] = str(tenant_id) # quando auth/multi-tentat estiver pronto
        
        if not run_name:
            run_name = f'Mathing-edital - {edital_id}'
        logger.info(f'Starting MLflow run: {run_name} with tags: {tags}')
        
        #mlflow.start_run() retorna um context manager
        # Tudo que for logado dentro do 'with' fica associado a este run
        return mlflow.start_run(run_name = run_name, tags = tags)
    
    def log_params(self,params: dict):
        ''' 
        Loga os parametros usados nesta execução
        
        Paratros sao as configuração - nao mudam durante o run
        Exemplos : qual modelo llm foi usado, qual threshold de score,
        qual versao do prompt, quantos chunks foram gerados
        
        IMPORTANTE : mlflow.log_params() aceita dict com strigs e numeros
        Nao coloque objetos complexos aqui - serialize para string ou log como artefato
        '''
        #garante que todos os valores sao serializaveis (string ou numeros)
        safe_params = {k:str(v) for k, v in params.items()}
        mlflow.log_params(safe_params)
        logger.debug(f"Logged parameters: {safe_params}")
        
    def log_metrics(self, metrics: dict, step: Optional[int] = None):
        """
        Loga as MÉTRICAS resultado da execução.

        Métricas são os resultados — números que medem qualidade ou performance.
        Exemplos: score médio, % de produtos que ATENDE, tempo total.

        O parâmetro `step` permite logar métricas ao longo do tempo.
        Exemplo: score após processar chunk 1, 2, 3... → forma um gráfico.

        Se step=None, loga apenas o valor final (mais comum).
        """
        mlflow.log_metrics(metrics, step = step)
        logger.debug(f"Logged metrics: {metrics} at step: {step}")
        
    
    def log_artifact(self, local_path: str):
        """
        Loga um ARQUIVO como artefato do run.

        Artefatos são arquivos gerados durante a execução.
        Exemplos: relatório PDF, CSV de resultados, gráfico de distribuição de scores.

        O MLflow copia o arquivo para seu servidor e mantém versionado.
        """
        mlflow.log_artifact(local_path)
        logger.info(f"[MLflow] Artefato logado: {local_path}")
        
    def log_matching_run(self, edital_id: str, resultados : list[dict], llm_model : str = 'phi3', embed_model: str = 'nomic-embed-text', score_weight_heuristic: float =0.3,
                         score_weight_llm: float = 0.7, tenant_id: Optional[str] = None):
        '''
        Método principal - loga um run completo de matching de uma so vez
        
        Este é o metodo que o matching_engiene.py vai chamar ao terminar.
        Recebe os resultados brutos e extrai automaticamente todas as metrics.
        
        Args:
            edital_id: ID do edital processado (usamos como tag)
            resultados: lista de dicts com os resultados do matching (modelo, heuristica, score final, etc)
            llm_model: nome do modelo LLM usado (parametro)
            embed_model: nome do modelo de embedding usado (parametro)
            score_weight_heuristic: peso da heuristica no score final (parametro)
            score_weight_llm: peso do LLM no score final (parametro)
            tenant_id: ID do tenant (opcional, mas útil para multi-tenant)
            
            Estrutura esperada de cada item em `resultados`:
            {
                "modelo": "Switch XS-1920-12HPX",
                "score_geral": 0.87,
                "status_geral": "ATENDE",
                "detalhes": [
                    {
                        "requisito": "Portas RJ45",
                        "score": 0.95,
                        "status": "ATENDE"
                    }, ...
                ]
            }
        
        '''
        inicio = time.time()
        with self.start_run(edital_id = edital_id, tenant_id = tenant_id):
            #Parametros - o que voce configurou para esse run
            self.log_params({
                'llm_model': llm_model,
                'embed_model': embed_model,
                'score_weight_heuristic': score_weight_heuristic,
                'score_weight_llm': score_weight_llm,
                'num_resultados': len(resultados),
            })
            
            #Metricas - os resultados mensuraveis do run
            if resultados:
                scores = [r.get('score_geral', 0 ) for r in resultados]
                #Contagem por status - revela a saude do matching
                # Muitos 'verificar' = sistema incerto - precisa melhorar
                total = len(resultados)
                n_atende = sum(1 for r in resultados if r.get('status_geral') == 'ATENDE')
                n_nao_atende = sum(1 for r in resultados if r.get('status_geral') == 'NAO_ATENDE')
                n_verificar = sum(1 for r in resultados if r.get('status_geral') == 'VERIFICAR')
                
                tempo_total = time.time() - inicio
                self.log_metrics({
                    # Scores de qualidade
                    "score_medio":  round(sum(scores) / total, 4),
                    "score_maximo": round(max(scores), 4),
                    "score_minimo": round(min(scores), 4),

                    # Distribuição de status (em %)
                    "pct_atende":     round(n_atende / total * 100, 2),
                    "pct_verificar":  round(n_verificar / total * 100, 2),
                    "pct_nao_atende": round(n_nao_atende / total * 100, 2),

                    # Performance
                    "tempo_execucao_segundos": round(tempo_total, 2),
                    "produtos_por_segundo": round(total / tempo_total, 2) if tempo_total > 0 else 0,
                })

                logger.info(
                    f"[MLflow] Run logado | edital={edital_id} | "
                    f"score_medio={sum(scores)/total:.2f} | "
                    f"ATENDE={n_atende} | VERIFICAR={n_verificar} | NÃO ATENDE={n_nao_atende}"
                )
            else:
                logger.warning("[MLflow] Nenhum resultado para logar")