# Correções dos fluxos de inteligência, download, match e ficha técnica

A inteligência de mercado usa `GET /crm/intelligence/notices`, uma leitura autenticada dos editais/itens da empresa com relações necessárias e valores JSON seguros. Evita serializar todo o cadastro comercial, anexos e relações do CRUD genérico. A leitura reconhece `raw_payload._raw_input.caracteristicas_bi`, `bi_features` e as folhas BI dos formatos de JSON usados no CRM.

O relatório comercial e seu detalhamento de demanda usam os itens operacionais atuais, sem aguardar o worker analítico ou gravar snapshots a cada consulta. O catálogo também entra na relação produtos × demanda diretamente. Histórico de resultados, preços externos, modelos e predições continua usando as fontes analíticas correspondentes. Nenhum vínculo de catálogo é convertido em confirmação técnica. Quantidade/referência alteradas no CRM aparecem no próximo relatório. Falhas de consultas auxiliares não apagam o relatório principal.

O download por item usa o endpoint autenticado existente com `?download=true` e `Content-Disposition: attachment`, disparado por um link nativo. Foi verificado pelo evento de download do navegador e pela leitura do arquivo salvo em Downloads. A mudança evita depender de um clique em Blob depois de uma chamada assíncrona no Safari.

A categoria do produto passa pela identidade técnica; marca/aba `tp_link` não vira tipo de produto. A classificação considera o substantivo principal, preservando a distinção entre fonte para switch e switch acompanhado de cabo/fonte. Marca aparece em sua própria linha de filtro. Foram adicionados pontos explícitos de camada, tipo, portas Ethernet, expansão, velocidade de uplink, VLAN, bivolt, MDI/MDIX, controle de fluxo e rack. Pontos sem mapeamento continuam em linhas individuais, com associação manual, texto original e revisão pendente. Os filtros continuam progressivos e independentes das exigências do edital.

A ficha do catálogo mostra característica, valor, unidade e origem em uma tabela visível. Registros antigos em texto ganham uma visão de compatibilidade com fatos explícitos do próprio produto: portas, camada e dados de transceiver como alcance/taxa/fibra/conector. A visão preenche ausências e preserva atributos existentes, inclusive aliases. O editor salva a ficha quando o usuário solicita. Os requisitos do edital permanecem no item do edital/match. Extrações de documentos com aplicabilidade incerta ficam separadas e recolhidas, sem virar capacidades confirmadas do produto ou filtros automaticamente.

Fonte do CRM reproduzível: patches anteriores seguidos de `docs/crm-repairs-source.patch`, aplicados pelo `scripts/sync-bid-buddy.mjs` a um checkout limpo da fonte privada. O repositório privado não foi publicado.

Validações: testes unitários de identidade, parsers e compatibilidade; testes HTTP em `qa/test_crm_repairs.py` mais regressão de match/sugestões/documentos; testes das páginas de inteligência e de suas bibliotecas; build embarcado e imagens locais; navegador com carregamento das duas inteligências, filtro progressivo, download real e ficha técnica. Os testes HTTP usam empresas de QA e preservam os dados da empresa demonstrativa.

A reprodução e a validação foram feitas no Docker local. As imagens da Hostinger precisam receber esta versão para aplicar as correções em produção.
