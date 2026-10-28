# Hostinger teste — correção do cadastro

Tag comum: `products-hostinger-20261028-v4` para API, frontend e MLflow.
Branch: `codex/inteligencia-produtos-hostinger`.

O frontend em `8ba9c68` corrige o redirecionamento indevido das páginas públicas
quando a consulta inicial de sessão retorna 401. Cadastro, recuperação de senha
e página inicial permanecem acessíveis; páginas privadas continuam protegidas.
API e MLflow reutilizam as imagens testadas da v3 sob a tag v4.

As três imagens foram publicadas com autorização do usuário. Pull público,
digests e plataforma Linux amd64 foram verificados no Docker Hub:
[manifesto](products-hostinger-20261028-v4.json).

No painel, mantenha o projeto **servidor2**, suas credenciais e volumes.
Substitua todo o Compose pelo arquivo atual `deploy/products/compose.panel.yaml`.
Mantenha no ambiente:

```env
IMAGE_TAG=products-hostinger-20261028-v4
REGISTER_ENABLED=1
```

Reimplante e abra `/cadastro-tor-gestao-interna`. O painel usa apenas pull.
A publicação das imagens não executa a implantação na VPS.

Validação: 50 testes do frontend aprovados; navegador com resposta inicial 401
simulada confirmou páginas públicas abertas e redirecionamento de página privada.
Nenhuma conta foi criada na VPS durante essa verificação.
