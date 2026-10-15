# Publicação: validade da LPU e descrição do Match — 14/10/2026

As imagens da API, frontend, market-worker e MLflow foram publicadas no namespace
`alvarocareli` do Docker Hub, todas com a tag:

```
sha-1a130f889791ed87c52a1d2a2802ea6cb6a36c28
```

Código congelado no commit `1a130f889791ed87c52a1d2a2802ea6cb6a36c28`, plataforma
Linux amd64. Digests remotos conferidos contra as imagens locais testadas:
[manifesto](lpu-validity-20261014.json). [Variáveis de implantação](lpu-validity-20261014.env).

A release inclui os controles de validade e responsável na importação de LPU,
prévia de itens ausentes, avisos na entrada/dashboard, prorrogação e confirmação
para retirar produtos do catálogo ativo. Preços, informações e links da LPU antiga
continuam nos processos. O Match abre a descrição do item cadastrado, sem upload,
incluindo editais com data de disputa preenchida. A importação de JSONs e datasheets
da release anterior permanece incluída.

O frontend embarcado foi reconstruído na revisão privada fixada, com os patches
anteriores e `docs/crm-lpu-lifecycle-source.patch`. Conferidos 72 hashes de artefatos,
dois testes do formato de hash e três testes dos controles de LPU. Nas imagens finais,
passaram os cenários isolados de ciclo da LPU e descrição do Match, a configuração
Nginx e a CLI do worker. Conferidos head Alembic `20261014_01` e Compose de produção.
MLflow reaproveita a imagem anterior sem mudanças.

Para implantação, usar a nova tag nas variáveis existentes da Hostinger e aplicar
as migrações com o serviço migrate. Preservar configurações e volumes existentes.
O arquivo de variáveis contém apenas as referências da release e não substitui
credenciais. A publicação no Docker Hub não implanta a VPS.
