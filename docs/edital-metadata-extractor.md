# Extrator de metadados do edital

No CRM, abra um edital (inclusive na Triagem), clique **Extrair metadados**, escolha se deseja incluir o texto já extraído dos PDFs, clique **Gerar extração** e depois **Baixar JSON**. O arquivo pode ser anexado à conversa para análise dos dados reais.

Endpoint autenticado: `GET /crm/notices/{notice_id}/metadata-json`.
Parâmetros opcionais: `include_text=true` e `download=true`.

O contrato `tor.edital-metadata` versão 1.0.0 contém:

- identificação, etapa, órgão, portal, sessão, referências comerciais e riscos;
- todos os itens cadastrados, inclusive componentes de kits, com descrição, BI, condições comerciais e `raw_payload`;
- critérios técnicos na representação original, sem inventar requisitos;
- metadados dos documentos/checklists e referência ao arquivo anexado;
- JSON completo da análise vinculada, versão e hash da fonte;
- texto já armazenado, quando solicitado e disponível;
- diagnóstico de ausência de critérios ou análise vinculada.

A extração lê o banco com autenticação e filtros de tenant em edital, itens, documentos e análise. Não modifica a etapa, não chama IA, não baixa novos PDFs e não transmite o arquivo para terceiros. Documentos do checklist não garantem que o PDF do edital esteja anexado ou tenha sido extraído. O JSON original é preservado como dados; formatação textual original não é reconstruída.

Validação local: endpoint respondeu 200 com o edital disponível no compose isolado; download retornou attachment e ID inexistente retornou 404. O banco isolado só contém um edital sintético na etapa analysis, não os editais reais de Triagem da Hostinger. O exemplo em output/edital-metadata/metadados_edital_teste.json é identificado como teste.

Os builds do CRM e do frontend principal foram concluídos. A imagem de frontend instala as dependências com npm ci, sem usar o node_modules local inconsistente.
