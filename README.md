# Feira Relâmpago

Avaliação técnica do Clube Quindim para reserva concorrente de estoque, confirmação de pedidos e atualização de pagamentos.

A API usa Flask com quatro workers Gunicorn, MongoDB 8 standalone e um documento agregado protegido por CAS. A interface usa Nuxt/Vue com um BFF: o navegador chama somente o Nuxt, e o Nuxt encaminha as operações permitidas à API.

## Início rápido

Pré-requisito: Docker Desktop com Docker Compose ativo.

Crie o arquivo local de ambiente a partir do exemplo (`Copy-Item .env.example .env` no PowerShell ou `cp .env.example .env` em Bash). Depois execute, na raiz:

```bash
docker compose up -d --build
docker compose run --rm testes
docker compose --profile navegador run --rm testes-navegador
```

O primeiro comando cria o banco e o seed automaticamente e sobe toda a aplicação. O segundo executa os testes unitários e de integração/concorrência do backend. O terceiro monta a imagem separada do Chromium e testa o fluxo real pelo navegador.

- Interface: `http://localhost:3000`
- Saúde da API: `http://localhost:8000/healthz`
- Saúde do frontend: `http://localhost:3000/healthz`

Para encerrar sem apagar o banco local:

```bash
docker compose down
```

## Testes por grupo

Os comandos abaixo usam somente os serviços Docker do projeto:

```bash
# Regras isoladas
docker compose run --rm testes python -m pytest tests/unitarios -v

# API, MongoDB e concorrência real entre os quatro workers
docker compose run --rm testes python -m pytest tests/integracao -v

# Fluxo completo no Chromium
docker compose --profile navegador run --rm testes-navegador
```

Os testes de frontend sem navegador ficam em `frontend/app/utils/*.test.ts` e podem ser executados, com Node 22 disponível, por `cd frontend`, `npm ci` e `npm test`.

## Webhook de pagamento

O webhook recebe os bytes originais do JSON e confere a assinatura HMAC-SHA256 no header `X-Webhook-Signature`. O segredo fica somente entre os dois backends; ele não é enviado ao navegador.

O runner de integração simula eventos pagos, recusados, duplicados, fora de ordem e com assinatura inválida:

```bash
docker compose run --rm testes python -m pytest tests/integracao/test_webhook_pagamento_integracao.py -v
```

Esse comando cria o cenário necessário, assina o corpo e chama `POST /v1/webhooks/pagamento` pela rede interna do Compose.

## Reset administrativo

`POST /v1/admin/reset` é destrutivo: remove reservas, pedidos e eventos e recompõe o catálogo inicial. Use apenas em desenvolvimento/testes, com o token definido em `ADMIN_TOKEN`:

```bash
curl -i -X POST http://localhost:8000/v1/admin/reset \
  -H "X-Admin-Token: admin-local-de-exemplo"
```

Se você alterou o valor em `.env`, substitua também o token do exemplo. O contrato completo da API está em [`docs/CONTRATO.md`](docs/CONTRATO.md), e as decisões técnicas e verificações estão em [`NOTAS.md`](NOTAS.md).
