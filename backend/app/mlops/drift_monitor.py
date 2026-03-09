'''
Drift = os dados mudarem e o modelo nao sabe disso

O DriftMonitor detecta isso ANTES que vire problema.

TIPOS DE DRIFT QUE MONITORAMOS:

1. Embedding Drift (Data Drift) :
    Os vetores gerados hoje estao diferentes do de 3 meses atras?
    Detectado comparando distribuição estatística dos embeddings

2. Score Drift (Prediction Drift)):
    Os scores de matching estao mudando ao longo do tempo ?
    Ex: Media caindo de 0.8 para 0.65 em 2 meses = algo mudou

3. Feature Drift:
    Os resiquistos dos editais estao pedindo coisas novas ?
    EX: 'wi-fi 7' aparecendo nos editais mas nao no catalogo

FERRAMENTA :  Evidently AI
    Open Source, gera relatiorios HTML bonitos e metricas detalhadas
    Compara um 'dataset de referencia' (passado) com 'dataset atual' (presente).

VOCABULÁRIO MLOPS:
    - Reference dataset: dados do passado (baseline confiável)
    - Current dataset : dados de agora (o que queremos avaliar)
    - p-value : probabilidade estatistica de que a mudança é real (nao ruido)
    - KS test : Kolmogorov-Smirnov test, compara distribuições de 2 datasets (score drift)
    - Wasserstein distance : mede a diferença entre 2 distribuições (embedding drift)


'''
import os 
import json
import logging
import statistics
from datetime import datetime
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

#Evidently tem imports pesados - fazemos lazy import para nao travar a inicializacao da API se o evidently nao estiver instalado
try:
    import pandas as pd
    from evidently.report import Report
    from evidently.metric_preset import DataDriftPreset, DataQualityPreset
    from evidently.metrics import ColumnDriftMetric
    EVIDENTLY_DISPONIVEL = True
except ImportError:
    EVIDENTLY_DISPONIVEL = False
    logger.warning("Evidently AI nao encontrado. DriftMonitor nao funcionará. Instale com 'pip install evidently' para habilitar.")

class DriftMonitor:
    '''
    Monitora mudanças nos dados e resultados ao longo do tempo

    Persiste historico de embeddings e scores em JSON local.
    Quando acumular dados suficientes, gera relatorios de drift

    Integra com MLFLOW (via tracker.py) para logar alertas 
    '''
    def __init__(self, storage_path: str = '/data/drift_history'):
        '''
        Args : 
            storage_path : onde salvar o historico de embeddings e scores.
                Deve ser um volume persistente no docker
        '''
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)

        #Arquivos de historico para cada tipo de drift
        self.embedding_history_file = self.storage_path / 'embedding_history.json'
        self.score_history_file = self.storage_path / 'score_history.json'
        logger.info(f"DriftMonitor inicializado. Historico salvo em {self.storage_path}")

    def registrar_embeddings(self, edital_id: str, embeddings:list[list[float]], tenant_id : Optional[str] = None):
        """
        Salva uma amostra dos embeddings gerados para este edital.

        Não salvamos TODOS os embeddings (seria enorme).
        Salvamos estatísticas da distribuição: média, std, min, max por dimensão.
        Isso é suficiente para detectar drift com Evidently.

        Args:
            edital_id:  ID do edital
            embeddings: lista de vetores (cada vetor tem 768 dimensões — nomic-embed-text)
            tenant_id:  ID da empresa
        """
        if not embeddings:
            logger.warning(f"DriftMonitor: Nenhum embedding para registrar no edital {edital_id}")
            return
        #calula estatisticas reumidas
        #Para detectar o drift precisamos saber : a distribuição mudou ?
        # As estatisticas por dimensao capturam isso com muito menos espaço

        n_dims = len(embeddings[0])
        #Para cada dimensao, calcula a media entre entre todos os chunks do edital -> resultando no embedding medio
        media_por_dim = []
        for dim in range(n_dims):
            valores_dim = [emb[dim] for emb in embeddings]
            media_por_dim.append(statistics.mean(valores_dim))

        #Estatisticas globais do embedding( resumo de todas as dimensoes)
        entrada = {
            "timestamp":       datetime.utcnow().isoformat(),
            "edital_id":       str(edital_id),
            "tenant_id":       str(tenant_id) if tenant_id else None,
            "n_produtos":      len(scores),
            "score_medio":     round(statistics.mean(scores), 4),
            "score_mediana":   round(statistics.median(scores), 4),
            "score_std":       round(statistics.stdev(scores) if len(scores) > 1 else 0, 4),
            "score_min":       round(min(scores), 4),
            "score_max":       round(max(scores), 4),
            # Distribuição por status
            "pct_atende":      round(sum(1 for r in resultados if r.get("status_geral") == "ATENDE") / len(resultados) * 100, 2),
            "pct_verificar":   round(sum(1 for r in resultados if r.get("status_geral") == "VERIFICAR") / len(resultados) * 100, 2),
            "pct_nao_atende":  round(sum(1 for r in resultados if r.get("status_geral") == "NÃO ATENDE") / len(resultados) * 100, 2),
        }

        self._append_to_history(self.scores_history_file, entrada)
        logger.debug(f"[DriftMonitor] Scores registrados | edital={edital_id} | score_medio={entrada['score_medio']}")

    # =========================================================================
    # DETECÇÃO DE DRIFT
    # =========================================================================

    def detectar_drift_scores(self, janela_runs: int = 10) -> dict:
        """
        Compara os últimos N runs com os N anteriores para detectar drift nos scores.

        Estratégia simples (sem Evidently):
          - Pega os últimos `janela_runs` resultados → dataset atual
          - Pega os `janela_runs` anteriores → dataset de referência
          - Compara médias e desvia padrões
          - Se a diferença for > threshold, emite alerta

        Args:
            janela_runs: quantos runs usar em cada janela de comparação

        Returns:
            Dict com resultado da análise de drift.
        """
        historico = self._load_history(self.scores_history_file)

        # Precisamos de pelo menos 2x janela_runs para comparar
        if len(historico) < janela_runs * 2:
            return {
                "status": "dados_insuficientes",
                "mensagem": f"Precisamos de {janela_runs * 2} runs. Temos {len(historico)}.",
                "drift_detectado": False,
            }

        # Divide em referência (passado) e atual (presente)
        referencia = historico[-janela_runs*2 : -janela_runs]  # runs do passado
        atual      = historico[-janela_runs:]                   # runs recentes

        # Extrai scores médios de cada janela
        scores_ref   = [r["score_medio"] for r in referencia]
        scores_atual = [r["score_medio"] for r in atual]

        media_ref   = statistics.mean(scores_ref)
        media_atual = statistics.mean(scores_atual)

        # Variação absoluta na média
        delta = abs(media_atual - media_ref)

        # THRESHOLD: se a média caiu mais de 0.10 pontos = drift significativo
        # Este valor pode ser ajustado conforme o sistema amadurece
        THRESHOLD_DRIFT = 0.10

        drift_detectado = delta > THRESHOLD_DRIFT
        direcao = "↓ queda" if media_atual < media_ref else "↑ melhora"

        resultado = {
            "status":           "drift_detectado" if drift_detectado else "estavel",
            "drift_detectado":  drift_detectado,
            "media_referencia": round(media_ref, 4),
            "media_atual":      round(media_atual, 4),
            "delta":            round(delta, 4),
            "direcao":          direcao,
            "janela_runs":      janela_runs,
            "alerta": (
                f"⚠️  Score médio mudou {delta:.3f} pontos ({direcao}). "
                f"Referência: {media_ref:.3f} → Atual: {media_atual:.3f}. "
                "Considere revisar o prompt do LLM ou verificar mudanças nos editais."
            ) if drift_detectado else None
        }

        if drift_detectado:
            logger.warning(f"[DriftMonitor] DRIFT DETECTADO | {resultado['alerta']}")
        else:
            logger.info(f"[DriftMonitor] Scores estáveis | delta={delta:.4f}")

        return resultado

    def gerar_relatorio_evidently(
        self,
        output_path: str = "/data/drift_reports",
    ) -> Optional[str]:
        """
        Gera relatório HTML completo de drift usando o Evidently.

        O relatório é um arquivo HTML interativo — abra no navegador.
        Inclui gráficos de distribuição, testes estatísticos e alertas visuais.

        Só executa se o Evidently estiver instalado e houver dados suficientes.

        Returns:
            Caminho do arquivo HTML gerado, ou None se não foi possível gerar.
        """
        if not EVIDENTLY_DISPONIVEL:
            logger.warning("[DriftMonitor] Evidently não disponível. Skipping relatório HTML.")
            return None

        historico = self._load_history(self.scores_history_file)

        if len(historico) < 20:
            logger.info(f"[DriftMonitor] Dados insuficientes para Evidently ({len(historico)} < 20 runs)")
            return None

        # Converte histórico para DataFrame (formato que o Evidently espera)
        df = pd.DataFrame(historico)
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        # Divide em referência e atual
        metade = len(df) // 2
        df_referencia = df.iloc[:metade].copy()
        df_atual      = df.iloc[metade:].copy()

        # Cria relatório Evidently com preset de drift
        # DataDriftPreset detecta automaticamente drift em todas as colunas numéricas
        report = Report(metrics=[
            DataDriftPreset(),      # drift em todas as features
            DataQualityPreset(),    # qualidade dos dados (nulos, outliers, etc.)
            ColumnDriftMetric(column_name="score_medio"),   # drift específico nos scores
        ])

        report.run(
            reference_data=df_referencia,
            current_data=df_atual,
        )

        # Salva relatório HTML
        Path(output_path).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_file = f"{output_path}/drift_report_{timestamp}.html"

        report.save_html(output_file)
        logger.info(f"[DriftMonitor] Relatório Evidently gerado: {output_file}")

        return output_file

    # =========================================================================
    # HELPERS INTERNOS
    # =========================================================================

    def _append_to_history(self, filepath: Path, entrada: dict):
        """
        Adiciona uma entrada ao arquivo de histórico JSON.
        Cria o arquivo se não existir.
        """
        historico = self._load_history(filepath)
        historico.append(entrada)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(historico, f, ensure_ascii=False, indent=2)

    def _load_history(self, filepath: Path) -> list:
        """
        Carrega o histórico de um arquivo JSON.
        Retorna lista vazia se o arquivo não existir.
        """
        if not filepath.exists():
            return []

        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
