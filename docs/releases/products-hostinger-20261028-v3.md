# Hostinger teste — imagens prontas para o painel

Tag comum: `products-hostinger-20261028-v3`. Branch exclusiva:
`codex/inteligencia-produtos-hostinger`. Fonte da aplicação em `7fc4355`, com o
ajuste de Host/porta validado em `8b458a3`. Inclui o relatório por marca e remove
a necessidade de `PUBLIC_ORIGIN`.

API, frontend e MLflow publicados nos repositórios `alvarocareli/ragmatch-api`,
`alvarocareli/ragmatch-frontend` e `alvarocareli/ragmatch-mlflow`. Digests e pull
anônimo verificados para Linux amd64: [manifesto](products-hostinger-20261028-v3.json).
O ENV, dados da aplicação e documentos enviados não integram as imagens.

No painel, preserve o projeto **servidor2** e suas credenciais/volumes. Substitua
somente o Compose por `deploy/products/compose.panel.yaml` e atualize:

```env
IMAGE_TAG=products-hostinger-20261028-v3
```

O painel precisa apenas baixar as imagens; não há `build` no Compose do painel.
A tentativa anterior baixou infraestrutura, mas pulou os builds e falhou ao criar
`migrate` sem a imagem local da API. Esta release publica as imagens para esse
fluxo observado. O envio ao Docker Hub foi explicitamente autorizado pelo usuário.

Validação local das imagens finais: stack saudável, readiness, login com cookie,
bloqueio CSRF de origem externa, importação JSON e leitura CRM usando a conta
restrita. A validação anterior do relatório por marca incluiu os downloads e a
gravação de motivos. Publicar a release não executa a implantação na Hostinger.
