# Identidade do frontend: produto, cliente e operação

## Princípio

O sistema é um produto SaaS multi-tenant. A identidade visual da plataforma não pertence a um cliente específico.

A hierarquia apresentada ao usuário deve ser:

1. **Produto:** Edital Matcher (nome provisório e configurável).
2. **Cliente/tenant:** empresa que contratou a plataforma, como a Tor Tecnologias.
3. **Operação:** dados, catálogo, códigos, documentos e processos particulares do cliente.

Assim, a TOR pode aparecer como o ambiente ativo e em recursos próprios (`ID TOR`, `PN TOR`, templates e datasheets), sem ocupar o lugar de fabricante ou proprietário da plataforma.

## Aplicação no frontend

- A rota pública `/` apresenta a landing page do produto e conduz ao acesso em `/login`.
- Login, título do navegador, navegação, rodapé e cabeçalho identificam o produto.
- O cartão **Ambiente de trabalho** identifica o tenant autenticado.
- Termos específicos de um cliente permanecem apenas nos fluxos que realmente pertencem a ele.
- Nome, descrição e textos principais do produto vêm do perfil de mercado, evitando marca espalhada em componentes.
- Preferências locais usam chaves neutras e preservam migração de chaves legadas.

## Próximas etapas

1. Tornar logo, cores e nome do produto configuráveis sem rebuild.
2. Criar perfil visual opcional por tenant para co-branding (`Edital Matcher para Tor Tecnologias`).
3. Classificar textos específicos da TOR em configuração de tenant ou módulo, em vez de constantes de interface.
4. Definir o nome comercial e a identidade visual definitivos do produto.
5. Evoluir a landing page com conteúdo comercial definitivo, onboarding e área de planos.

## Regra para novas telas

Antes de adicionar uma marca ou nome de empresa, classifique o conteúdo:

- pertence à plataforma: usar identidade do produto;
- pertence à organização autenticada: usar dados do tenant;
- pertence a um processo particular: usar configuração ou dados do módulo.
