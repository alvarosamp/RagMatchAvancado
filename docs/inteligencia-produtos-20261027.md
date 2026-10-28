# Inteligência de produtos — entrega de 27/10/2026

Disponível na seção **Inteligência de produtos** da página CRM
`/crm/inteligencia-mercado`. A implementação está no repositório `bid-buddy`.

## Decisões apoiadas

- Identificar combinações de especificações recorrentes para orientar o catálogo.
- Associar um modelo citado à marca cadastrada, conservando origem e ambiguidades.
- Identificar atributos faltantes ou divergentes antes de comparar produtos.
- Voltar ao edital/item que originou cada perfil e exportar o recorte analisado.

## Método

Perfis usam atributos documentados por categoria. Switches incluem portas,
velocidade de acesso, gerenciamento, PoE e uplinks. APs usam padrão Wi-Fi, bandas,
interface LAN e alimentação. Módulos usam formato, velocidade, meio e alcance.
DAC/AOC usam formato, velocidade, comprimento e topologia; DAC também inclui
tipo ativo/passivo. Patch cords separam conectores, meio, comprimento e,
conforme o meio declarado, fibra/polimento ou categoria de cobre/blindagem.

Conversões de comprimento e velocidade só acontecem quando a unidade está
explícita ou é determinada pelo nome do campo estruturado. Perfis com atributos
ausentes ficam separados dos preenchidos. A recorrência conta editais distintos
e conserva as linhas dos itens, inclusive cotas. Perfis são ordenados por editais,
itens e unidades conhecidas.

Quantidade e valor desconhecidos não são apresentados como observações de zero.
Cada total informa em quantos itens o dado está disponível. Uma ficha de perfil
preenchida não comprova cobertura de todos os requisitos do edital.

## Marca por modelo

O cruzamento usa códigos exatos de modelo/part number do catálogo da empresa.
Na descrição sem rótulo, o código precisa aparecer no início identificando o
produto. Referências e campos explícitos também são usados; códigos encontrados
apenas em padrões ou CATMAT não viram automaticamente modelos.

O trecho após "compatível com" é conservado como compatibilidade e excluído
da busca do produto solicitado. Não há consulta à internet, correspondência
aproximada nem alteração dos campos originais do item.

Estados possíveis: associação no catálogo, associação ambígua, marca divergente,
modelo sem marca associada e modelo não identificado. A associação não transforma
a marca do catálogo em marca exigida no edital. Catálogo indisponível gera aviso
e não impede a leitura dos perfis técnicos.

## Validação

- 28 testes de identidade, perfis, exportação, componentes e filtros aprovados.
- TypeScript e ESLint dos novos cálculos/componentes aprovados.
- Builds do CRM e frontend aprovados em Docker.
- Teste Chromium com catálogo e edital reais no PostgreSQL de QA aprovado:
  associação do módulo, exclusão do switch de compatibilidade, filtros e download
  JSON com quantidade, valor, origem e marca associada conferidos.
- Resultado visual conferido por captura da tela do ambiente de teste.

O ambiente é o projeto isolado `ragmatch-connectivity-qa`. Produção não foi
publicada. A análise usa o catálogo atual, não um histórico versionado das
associações. Enriquecimento por datasheets e verificação externa de fabricantes
permanecem fora desta entrega.

## Nomes curtos dos itens

Os cards, itens/resultados, comparação técnica e inteligência usam um nome curto
derivado de categoria e atributos documentados. Exemplo: `Switch · 24 Portas ·
Gigabit · PoE+`. Campos explícitos `nome_item`, `nome_curto` ou `item_name`, quando
presentes no JSON, têm prioridade. Não há inferência de marca/modelo a partir
de equipamentos de compatibilidade.

Essa é uma identificação de apresentação, sem nova coluna no banco. A descrição
completa continua no registro e na entrada do matching. Na inteligência e na
comparação, fica disponível em "Descrição completa do edital". A API de matching
também retorna categoria e atributos BI para compor o título.

Nesta alteração, passaram 15 testes de frontend, 7 de backend, TypeScript,
ESLint do gerador de nomes e compilação do CRM. O Docker não disponibilizou o
daemon após a tentativa de inicialização nesta sessão; o teste de navegador foi
ampliado para conferir os títulos, mas não foi reexecutado com esta alteração.
