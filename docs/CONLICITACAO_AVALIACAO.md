# Avaliação da API ConLicitação (semana de teste)

Tudo roda em **Integrações → ConLicitação → Avaliação da API (dados reais)**, só para administradores, pela VPS (IP autorizado).

## Rotas usadas (documentação oficial)

| Tela | Rota RagMatch | Rota ConLicitação |
|---|---|---|
| Filtros | `GET /integrations/conlicitacao/lab/filters` | `GET /api/filtros` |
| Boletins do filtro | `GET …/lab/filters/{id}/bulletins` | `GET /api/filtro/{id}/boletins?page&per_page&order` |
| Abrir boletim + qualidade | `GET …/lab/bulletins/{id}` | `GET /api/boletim/{id}` |
| Rastrear licitação | `GET …/lab/biddings/{id}/trace` | `/api/filtros` + `/api/filtro/{id}/boletins` + N× `/api/boletim/{id}` + `/api/monitored_biddings` |
| Baixar documento | `GET …/lab/bulletins/{b}/tenders/{t}/documents/{i}` | `GET /api/boletim/{id}` (link novo) + `GET /boletim_web/public/api/download?auth=…` |
| Usuários | `GET …/lab/users` | `GET /api/users` |
| Licitações monitoradas | `GET …/lab/monitored` | `GET /api/monitored_biddings?page&per_page&trading_status` |
| Chat | `GET …/lab/monitored/{id}/messages` | `GET /api/monitored_biddings/messages?bidding_id&page&per_page` |
| Ativar/desativar chat | `POST …/monitoring/start`, `DELETE …/monitoring/{id}?user_id` | `POST /api/monitored_biddings/add`, `DELETE /api/monitored_biddings/{id}?user_id` |

## Roteiro de testes

1. **Cobertura do filtro:** abra os boletins de 2 ou 3 dias e veja quantas licitações chegam por turno e quantas são do seu segmento (use a busca: `switch`, `rede`, `telecom`, `informática`).
2. **Qualidade dos dados:** confira a tabela de preenchimento. Os pontos críticos são `valor_estimado`, `documento`, `item` e as datas. A API manda `0.0` e `""` quando não sabe.
3. **Documentos:** baixe editais de várias licitações. Compare com o portal: no site a 19399420 mostra "Ver arquivos (10)". Veja quantos vêm pela API.
4. **Rastreio (ex.: 19399420):** veja em quantos boletins ela reaparece, o que muda entre eles (situação, datas) e se aparecem acompanhamentos.
5. **Acompanhamentos:** veja se a extração automática de vencedor, CNPJ e valor da `sintese` funciona. É o dado mais valioso para inteligência competitiva.
6. **Chat:** ative o monitoramento de uma licitação com `has_electronic_trading` em portal suportado, deixe "Atualizar a cada 30 s" ligado durante a sessão e anote o **atraso de detecção** de cada mensagem nova.
7. **Desempenho:** anote o tempo de resposta dos boletins. Acima de 10 s fica vermelho; o timeout do boletim é `CONLICITACAO_BULLETIN_TIMEOUT_SECONDS` (padrão 60).

## Critérios para decidir

- Percentual de licitações relevantes por boletim e se o filtro pode ser ajustado (só o suporte da ConLicitação altera filtros).
- Documentos realmente baixáveis pela API (o link vale 24 h).
- Acompanhamentos com vencedor e valor utilizáveis.
- Atraso do chat aceitável para reagir durante a disputa.
- Sem erros 429 ou 5xx durante a semana.
