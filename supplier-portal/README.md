# TorTecDash

Página independente com dados reais e acesso revogável por fornecedor. Não contém dados empresariais no repositório. Cada consulta lê o recorte autorizado da API; o CRM alimenta a base analítica pelo worker. O navegador atualiza a cada cinco minutos enquanto a aba estiver visível e permite atualização manual.

No Vercel, importe este repositório, crie o projeto `tortecdash` e selecione **Root Directory: supplier-portal**, framework **Other**, sem build command. Confirme o endereço do portal em `vercel.json` antes de publicar. O proxy expõe somente a apresentação compartilhada. É necessário atualizar a API do portal e aplicar a migração `20261010_03` antes de usar os links reais.

No CRM, em Inteligência → apresentação para fornecedor, selecione fornecedor, fonte e filtros; informe a URL efetivamente publicada, gere o link e compartilhe. O token fica no fragmento da URL, é válido por até 30 dias e pode ser revogado pelo CRM. Qualquer pessoa com esse link pode consultar o recorte até a revogação ou expiração. Não use um token de login do CRM nesta página.

Os produtos usam os fornecedores canônicos do catálogo, após normalização da base. Custos internos, margens, estoque, documentos, clientes e outros fornecedores são excluídos da resposta pública. Valores de referência não representam compras ou receita. Unidades mistas e valores desconhecidos permanecem indisponíveis. A simulação de crescimento é hipotética.

Validação local: `npm test`; `npm run dev` usa o portal Docker em `127.0.0.1:3088` e abre a página em `127.0.0.1:3733`. Nenhum servidor local é acessível externamente.
