'''
Drift = os dados mudarem e o modelo nao sabe disso

O DriftMonitor detecta isso ANTES que vire problema.

TIPOS DE DRIFT QUE MONITORAMOS:

1. Embedding Drift (Data Drift):
    Os vetores gerados hoje estao diferentes do de 3 meses atras?
    Detectado comparando distribuição estatística dos embeddings

2. Score Drift (Prediction Drift):
    Os scores de matching estao mudando ao longo do tempo?
    Ex: Media caindo de 0.8 para 0.65 em 2 meses = algo mudou

3. Feature Drift:
    Os requisitos dos editais estao pedindo coisas novas?
    EX: 'wi-fi 7' aparecendo nos editais mas nao no catalogo

FERRAMENTA: Evidently AI
    Open Source, gera relatorios HTML bonitos e metricas detalhadas
    Compara um 'dataset de referencia' (passado) com 'dataset atual' (presente).

VOCABULARIO MLOPS:
    - Reference dataset: dados do passado (baseline confiável)
    - Current dataset: dados de agora (o que queremos avaliar)
    - p-value: probabilidade estatistica de que a mudança é real (nao ruido)
    - KS test: Kolmogorov-Smirnov, compara distribuições de 2 datasets (score drift)
    - Wasserstein distance: mede a diferença entre 2 distribuições (embedding drift)
'''

import os
import json
import logging
import statistics
from datetime import datetime
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Evidently tem imports pesados — lazy import para nao travar a API se nao estiver instalado
try:
    import pandas as pd
    from evidently.report import Report
    from evidently.metric_preset import DataDriftPreset, DataQualityPreset
    from evidently.metrics import ColumnDriftMetric
    EVIDENTLY_DISPONIVEL = True
except ImportError:
    EVIDENTLY_DISPONIVEL = False
    logger.warning(
        "Evidently AI nao encontrado. DriftMonitor nao funcionará completamente. "
        "Instale com 'pip install evidently' para habilitar relatórios HTML."
    )


class DriftMonitor:
    '''
    Monitora mudanças nos dados e resultados ao longo do tempo.

    Persiste historico de embeddings e scores em JSON local.
    Quando acumular dados suficientes, gera relatorios de drift.

    Integra com MLflow (via tracker.py) para logar alertas.
    '''

    def __init__(self, storage_path: str = '/data/drift_history'):
        '''
        Args:
            storage_path: onde salvar o historico de embeddings e scores.
                Deve ser um volume persistente no Docker.
        '''
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Arquivos de historico — um por tipo de dado monitorado
        self.embedding_history_file = self.storage_path / 'embedding_history.json'
        self.score_history_file     = self.storage_path / 'score_history.json'

        logger.info(f"DriftMonitor inicializado. Historico salvo em {self.storage_path}")

    # =========================================================================
    # REGISTRO DE DADOS
    # =========================================================================

    def registrar_embeddings(
        self,
        edital_id: str,
        embeddings: list[list[float]],
        tenant_id: Optional[str] = None,
    ):
        """
        Salva estatísticas dos embeddings gerados para este edital.

        Não salvamos TODOS os embeddings (seria enorme).
        Salvamos estatísticas da distribuição por dimensão.
        Isso é suficiente para detectar drift com Evidently.

        Args:
            edital_id:  ID do edital
            embeddings: lista de vetores (768 dimensões — nomic-embed-text)
            tenant_id:  ID da empresa
        """
        if not embeddings:
            logger.warning(f"DriftMonitor: Nenhum embedding para registrar no edital {edital_id}")
            return

        # Calcula estatísticas resumidas (não salva vetores brutos — muito pesado).
        # Para detectar drift, precisamos saber: "a distribuição mudou?"
        # As estatísticas por dimensão capturam isso com muito menos espaço.
        n_dims = len(embeddings[0])  # 768 para nomic-embed-text

        # Para cada dimensão, calcula a média entre todos os chunks do edital
        # → resulta no "embedding médio" representativo do edital
        media_por_dim = []
        for dim in range(n_dims):
            valores_dim = [emb[dim] for emb in embeddings]
            media_por_dim.append(statistics.mean(valores_dim))

        # Estatísticas globais (resumo de todas as dimensões)
        entrada = {
            "timestamp":    datetime.utcnow().isoformat(),
            "edital_id":    str(edital_id),
            "tenant_id":    str(tenant_id) if tenant_id else None,
            "n_chunks":     len(embeddings),
            "n_dimensoes":  n_dims,
            # Norm L2 médio — mede a "magnitude" dos vetores.
            # Se mudar muito, o modelo está gerando vetores em escala diferente.
            "norm_l2_medio": round(
                statistics.mean([
                    sum(x ** 2 for x in emb) ** 0.5
                    for emb in embeddings
                ]), 4
            ),
            # Média global (média das médias por dimensão)
            "media_global": round(statistics.mean(media_por_dim), 6),
            # Desvio padrão global
            "std_global":   round(
                statistics.stdev(media_por_dim) if len(media_por_dim) > 1 else 0.0, 6
            ),
        }

        # BUG CORRIGIDO: era self.scores_history_file (não existia).
        # Correto: self.embedding_history_file
        self._append_to_history(self.embedding_history_file, entrada)
        logger.debug(
            f"[DriftMonitor] Embeddings registrados | edital={edital_id} | chunks={len(embeddings)}"
        )

    def registrar_scores(
        self,
        edital_id: str,
        resultados: list[dict],
        tenant_id: Optional[str] = None,
    ):
        """
        Salva estatísticas dos scores de matching para histórico.

        Monitoramos se os scores estão mudando ao longo do tempo.
        Queda gradual = possível drift nos dados ou degradação do modelo.

        Args:
            edital_id:  ID do edital
            resultados: lista de resultados do matching
            tenant_id:  ID da empresa

        Estrutura esperada de cada item em resultados:
            {"modelo": "...", "score_geral": 0.87, "status_geral": "ATENDE", ...}
        """
        # BUG CORRIGIDO: este método estava FALTANDO no arquivo.
        # O corpo de registrar_scores havia sido colado por engano em registrar_embeddings.

        if not resultados:
            logger.warning(f"[DriftMonitor] Nenhum resultado para registrar | edital={edital_id}")
            return

        scores = [r.get("score_geral", 0) for r in resultados]

        entrada = {
            "timestamp":     datetime.utcnow().isoformat(),
            "edital_id":     str(edital_id),
            "tenant_id":     str(tenant_id) if tenant_id else None,
            "n_produtos":    len(scores),
            "score_medio":   round(statistics.mean(scores), 4),
            "score_mediana": round(statistics.median(scores), 4),
            "score_std":     round(statistics.stdev(scores) if len(scores) > 1 else 0, 4),
            "score_min":     round(min(scores), 4),
            "score_max":     round(max(scores), 4),
            # Distribuição por status
            "pct_atende":    round(
                sum(1 for r in resultados if r.get("status_geral") == "ATENDE")
                / len(resultados) * 100, 2
            ),
            "pct_verificar": round(
                sum(1 for r in resultados if r.get("status_geral") == "VERIFICAR")
                / len(resultados) * 100, 2
            ),
            "pct_nao_atende": round(
                sum(1 for r in resultados if r.get("status_geral") in ("NÃO ATENDE", "NAO_ATENDE"))
                / len(resultados) * 100, 2
            ),
        }

        self._append_to_history(self.score_history_file, entrada)
        logger.debug(
            f"[DriftMonitor] Scores registrados | edital={edital_id} | "
            f"score_medio={entrada['score_medio']}"
        )

    # =========================================================================
    # DETECÇÃO DE DRIFT
    # =========================================================================

    def detectar_drift_scores(self, janela_runs: int = 10) -> dict:
        """
        Compara os últimos N runs com os N anteriores para detectar drift nos scores.

        Estratégia simples (sem Evidently):
          - Pega os últimos `janela_runs` resultados → dataset atual
          - Pega os `janela_runs` anteriores         → dataset de referência
          - Compara médias
          - Se a diferença for > threshold, emite alerta

        Args:
            janela_runs: quantos runs usar em cada janela de comparação

        Returns:
            Dict com resultado da análise de drift.
        """
        # BUG CORRIGIDO: era self.scores_history_file (não existia).
        # Correto: self.score_history_file
        historico = self._load_history(self.score_history_file)

        # Precisamos de pelo menos 2x janela_runs para comparar
        if len(historico) < janela_runs * 2:
            return {
                "status":          "dados_insuficientes",
                "mensagem":        f"Precisamos de {janela_runs * 2} runs. Temos {len(historico)}.",
                "drift_detectado": False,
            }

        # Divide em referência (passado) e atual (presente)
        referencia = historico[-janela_runs * 2 : -janela_runs]  # runs do passado
        atual      = historico[-janela_runs:]                     # runs recentes

        scores_ref   = [r["score_medio"] for r in referencia]
        scores_atual = [r["score_medio"] for r in atual]

        media_ref   = statistics.mean(scores_ref)
        media_atual = statistics.mean(scores_atual)

        # Variação absoluta na média
        delta = abs(media_atual - media_ref)

        # THRESHOLD: se a média mudou mais de 0.10 pontos = drift significativo
        # Ajuste conforme o sistema amadurece com dados reais
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
                f"Score médio mudou {delta:.3f} pontos ({direcao}). "
                f"Referência: {media_ref:.3f} → Atual: {media_atual:.3f}. "
                "Considere revisar o prompt do LLM ou verificar mudanças nos editais."
            ) if drift_detectado else None,
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

        # BUG CORRIGIDO: era self.scores_history_file (não existia).
        historico = self._load_history(self.score_history_file)

        if len(historico) < 20:
            logger.info(
                f"[DriftMonitor] Dados insuficientes para Evidently ({len(historico)} < 20 runs)"
            )
            return None

        # Converte histórico para DataFrame (formato que o Evidently espera)
        df = pd.DataFrame(historico)
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        # Divide em referência (passado) e atual (presente)
        metade        = len(df) // 2
        df_referencia = df.iloc[:metade].copy()
        df_atual      = df.iloc[metade:].copy()

        # DataDriftPreset detecta drift automaticamente em todas as colunas numéricas
        report = Report(metrics=[
            DataDriftPreset(),
            DataQualityPreset(),
            ColumnDriftMetric(column_name="score_medio"),
        ])

        report.run(
            reference_data=df_referencia,
            current_data=df_atual,
        )

        # Salva relatório HTML
        Path(output_path).mkdir(parents=True, exist_ok=True)
        timestamp   = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
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