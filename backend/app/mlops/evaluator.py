# =============================================================================
#
# CONCEITO: Por que avaliar além do score do LLM?
#
# O LLM te dá um score (ex: 0.87), mas isso não diz se o SISTEMA está
# funcionando bem. O evaluator responde perguntas como:
#
#   → Os scores estão bem distribuídos ou todo mundo fica em 0.5? (clustering)
#   → Requisitos específicos estão sistematicamente com score baixo?
#   → O sistema está muito confiante (todos ATENDE) ou muito incerto?
#   → A distribuição de hoje está diferente da de ontem? (drift de resultados)
#
# VOCABULÁRIO MLOPS:
#   - Precision:    dos que o modelo disse ATENDE, quantos realmente atendem?
#   - Recall:       dos que realmente atendem, quantos o modelo encontrou?
#   - F1-Score:     média harmônica entre precision e recall (número único de qualidade)
#   - Distribuição: como os scores estão espalhados (histograma)
#   - Baseline:     resultado mínimo aceitável para comparar novos runs
#
# ATENÇÃO: Aqui não temos ground truth (verdade absoluta definida por humanos).
# Por isso calculamos métricas que não dependem de labels verdadeiros,
# como distribuição, consistência e cobertura.
# Quando usuários validarem resultados, adicionamos precision/recall real.
#
# ==============================


import statistics
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class MatchingEvaluator:
    '''
    Calcula metriscas de qualidade dos resultados de matching

    Nao precisa de 'verdade absoluta' para funcionar 
    Usa os proprios resultados para detectar padroes problemáticos

    - Threholds do sistema (devem bater com matching_engine.py)
      Definidos aqui como constantes para facilitar ajuste futuro    
    '''
    THRESHOLD_ATENDE    = 0.75   # score >= 0.75 → ATENDE
    THRESHOLD_VERIFICAR = 0.45   # score >= 0.45 → VERIFICAR
                                    # score <  0.45 → NÃO ATENDE
    def avaliar_distribuicao(self, resultados: list[dict]) -> dict:
        ''' 
        Analisa como os scores estao distribuidos

        Uma distribuição saudavel tem:
          - Poucos resultados em torno de 0.45~0.55 (zona de incerteza)
          - Maioria claramente acima de 0.75 ou abaixo de 0.45
          - Desvio padrao razoavel (nao todos iguais)
        
          Retorna um dict com metricas de distribuição
        '''
        if not resultados:
            return {'erro' : 'Nenhm rsultado para avaliar'}
        scores = [r.get('score_geral', 0) for r in resultados]
        total = len(scores)

        #Estatisticas basicas
        media = statistics.mean(scores)
        mediana = statistics.median(scores)


        #Desvio padrao mede o quanto os scores variam
        # Desvio baixo(< 0.1): todos scores parecidos - sistema pode estar sem discriminacao
        # Desvio alto(> 0.3): scores muito espalhados - sistema pode estar inconsistente
        desvio_padrao = statistics.stdev(scores) if len(scores) > 1 else 0

        # Produtos com score entre os dois thresholds estão na "zona cinza"
        # Muitos produtos aqui = o sistema está confuso com os requisitos
        zona_incerteza = [
            s for s in scores
            if self.THRESHOLD_VERIFICAR <= s < self.THRESHOLD_ATENDE
        ]
        pct_incerteza = len(zona_incerteza) / total * 100

        #Alerta de qualidade 
        #Regras simples que sinalizam problemas no sistema
        alertas = []
        if pct_incerteza > 40:
            alertas.append(
                f'Alerta: {pct_incerteza:.1f}% dos produtos estão na zona de incerteza (entre {self.THRESHOLD_VERIFICAR} e {self.THRESHOLD_ATENDE})'
            )
        if desvio_padrao < 0.5:
            alertas.append(
                f'Alerta: Desvio padrão baixo ({desvio_padrao:.3f}) - os scores estão muito parecidos, o sistema pode não estar discriminando bem os requisitos'
            )
        
        if media > 0.9:
            alertas.append(
                f'Alerta: Média muito alta ({media:.3f}) - o sistema pode estar superestimando os matches'
            )

        resultado = {
            "total_produtos":    total,
            "score_media":       round(media, 4),
            "score_mediana":     round(mediana, 4),
            "desvio_padrao":     round(desvio_padrao, 4),
            "score_maximo":      round(max(scores), 4),
            "score_minimo":      round(min(scores), 4),
            "pct_zona_incerteza": round(pct_incerteza, 2),
            "alertas":           alertas,
        }

        for alerta in alertas:
            logger.warning(f'Evaluator: {alerta}')
        
        return resultado
    
    def avaliar_cobertura_requisitos(self, resultados: list[dict]) -> dict:
        '''
        Verifica se requisitos especificos estao sistematicamente com score baixo.

        Isso detecta GAPS no catalogo de produtos.
        Exemplo : Se 'budget poe' sempre tem score 0.2, proavelmente nenhum produto
        no catalogo tem essa informação bem documentado.

        Retorna ranking de requisitors piores com score medios
        '''

        if not resultados:
            return {'erro' : 'Nenhum resultado para avaliar'}
        # Agrupa scores por requisito
        scores_por_requisito : dict[str, list[float]] = {}
        for produto in resultados:
            for detalhe in produto.get('detalhes', []):
                req = detalhe.get('requisito')
                score = detalhe.get('score', 0)
                if req not in scores_por_requisito:
                    scores_por_requisito[req] = []
                scores_por_requisito[req].append(score)

        if not scores_por_requisito:
            return {'erro' : 'Nenhum detalhe de requisito encontrado nos resultados'}
        
        # Calcula score médio por requisito e ordena do pior para o melhor
        media_por_requisito = {
            req : statistics.mean(scores)
            for req, scores in scores_por_requisito.items()
        }
        #Ordena 
        ranking = sorted(media_por_requisito.items(), key=lambda x: x[1]) # do pior para o melhor

        #requisitos com score medio abaixo de 0.5 sao considerados problematicos
        requisitos_problematicos = [
            {'requisito':req, 'score_medio': round(score, 4)}
            for req, score in media_por_requisito.items()
            if score < 0.5
        ]
        
        if requisitos_problematicos:
            logger.warning(
                f"[Evaluator] {len(requisitos_problematicos)} requisitos com score médio < 0.5: "
                f"{[r['requisito'] for r in requisitos_problematicos]}"
            )

        return {
            "total_requisitos_avaliados": len(media_por_requisito),
            "requisitos_problematicos":   requisitos_problematicos,
            "ranking_completo": [
                {"requisito": req, "score_medio": score}
                for req, score in ranking
            ],
        }
    
    def gerar_relatorio_completo(
            self,
            edital_id : str,
            resultados: list[dict],
            tenant_id : Optional[str] = None,
    ) -> dict:
        """
        Executa todas as avaliações e retorna um relatório consolidado.

        Este é o método que o matching_engine.py vai chamar ao final.
        Integra com o tracker para logar as métricas no MLflow.

        Args:
            edital_id:  ID do edital avaliado
            resultados: lista de resultados do matching
            tenant_id:  ID da empresa (opcional)

        Returns:
            Dict com todas as métricas consolidadas.
        """
        distribuicao =self.avaliar_distribuicao(resultados)
        cobertura = self.avaliar_cobertura_requisitos(resultados)
        relatorio = {
            "edital_id": edital_id,
            "tenant_id": tenant_id,
            "distribuicao": distribuicao,
            "cobertura_requisitos": cobertura,
            #saude geral, numero unica que resume a saude do matching
            #Formula : penaliza zona de incerteza e requisitos problematicos
            'saude_geral' : self._calcular_saude(distribuicao),
        }
        logger.info(
            f'Evaluator: Relatório completo para edital {edital_id} gerado com sucesso. '
            f'alertas = {len(distribuicao.get("alertas", [])) + len(cobertura.get("requisitos_problematicos", []))}'
        )
        return relatorio
    
    def _calcular_saude(self, distribuicao: dict) -> int:
        """
        Calcula um score de "saúde" do sistema de 0 a 100.

        Não é uma métrica científica — é um indicador rápido para o dashboard.
        Fórmula:
          - Começa em 100
          - Perde pontos por % de incerteza
          - Perde pontos por desvio padrão muito baixo
          - Perde pontos por cada alerta
        """
        if 'erro' in distribuicao:
            return 0  # Se não tem dados para avaliar, saúde é zero
        
        saude = 100
        #Penzaliza zona de incerteza (max -30 pontos)
        pct_incerteza = distribuicao.get('pct_zona_incerteza', 0)
        saude -= min(pct_incerteza * 0.75, 30) # cada 1% de incerteza penaliza 0.75 pontos, até max 30 pontos

        #Penzalia desvio padrao baixo
        desvio = distribuicao.get('desvio_padrao', 0)
        if desvio < 0.1:
            saude -= 20  # desvio muito baixo penaliza 20 pontos
        elif desvio < 0.15:
            saude -= 10  # desvio baixo penaliza 10 pontos

        #Penaliza alertas (10 pontos cada)
        n_alertas = len(distribuicao.get('alertas', []))
        saude -= n_alertas * 10

        return max(0, int(saude))