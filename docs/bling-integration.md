# Integração Bling API v3

Esta primeira etapa integra o backend ao Bling para:

- criar um pedido de venda;
- gerar uma NF-e a partir de um pedido de venda;
- criar uma NF-e diretamente;
- enviar uma NF-e já criada para autorização na Sefaz.

## Configuração da infraestrutura

1. Gere `BLING_CREDENTIALS_ENCRYPTION_KEY` conforme `.env.bling.example` e salve-a
   no cofre de segredos do ambiente. Não troque essa chave sem antes rotacionar os
   dados cifrados.
2. Execute a migration `20260924_01`.
3. No aplicativo criado no Bling, habilite os escopos de pedidos de venda e notas
   fiscais e cadastre `https://SEU_DOMINIO/api/integrations/bling/oauth/callback`
   como URL de redirecionamento.
4. Um administrador acessa **Integrações > Bling ERP**, informa Client ID e Client
   Secret e conclui a autorização no Bling.

O Client Secret, access token e refresh token são protegidos com Fernet e armazenados
em uma linha exclusiva por tenant. A tabela também possui Row-Level Security. O
backend solicita JWT (`enable-jwt: 1`), renova o token após `401` e persiste a rotação
do `refresh_token` antes de repetir a operação.

## Rotas internas

Todas as rotas exigem autenticação no sistema. Operações de escrita aceitam os
papéis `admin` e `editor`; o status da configuração é restrito a `admin`.

| Método | Rota | Operação no Bling |
| --- | --- | --- |
| `GET` | `/integrations/bling/status` | Estado da conexão da empresa |
| `PUT` | `/integrations/bling/credentials` | Salva credenciais cifradas; somente admin |
| `DELETE` | `/integrations/bling/credentials` | Remove credenciais e tokens; somente admin |
| `POST` | `/integrations/bling/oauth/start` | Inicia OAuth com state descartável; somente admin |
| `GET` | `/integrations/bling/oauth/callback` | Valida state e grava os tokens do tenant |
| `POST` | `/integrations/bling/sales-orders` | `POST /pedidos/vendas` |
| `POST` | `/integrations/bling/sales-orders/{id}/invoice` | `POST /pedidos/vendas/{id}/gerar-nfe` |
| `POST` | `/integrations/bling/invoices` | `POST /nfe` |
| `POST` | `/integrations/bling/invoices/{id}/authorize?sendEmail=false` | `POST /nfe/{id}/enviar` |

### Exemplo de pedido de venda

```json
{
  "data": "2026-09-24",
  "dataSaida": "2026-09-24",
  "dataPrevista": "2026-09-25",
  "contato": {"id": 12345678},
  "itens": [
    {
      "descricao": "Produto de exemplo",
      "quantidade": 2,
      "valor": 99.9,
      "valorLista": 99.9,
      "produto": {"id": 87654321}
    }
  ],
  "parcelas": []
}
```

Na tela `/integracoes/bling`, o usuário preenche contato, produto, quantidade e
valor, cria o pedido e então gera a NF-e vinculada. Criar a nota não a autoriza:
o envio à Sefaz é uma operação separada, mostra uma confirmação explícita e pode
opcionalmente solicitar o envio de e-mail após a emissão.

Referência: <https://developer.bling.com.br/referencia>
