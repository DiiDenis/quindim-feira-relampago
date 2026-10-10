# Contrato operacional — Feira Relâmpago

Este documento resume o enunciado original para orientar implementação e testes. Ele não acrescenta requisitos nem transforma decisões de engenharia em exigências da empresa. Em caso de divergência, o PDF original prevalece; nossas decisões e ambiguidades ficam em `NOTAS.md`.

## Entrega e stack obrigatória

- Enviar o link do repositório em 13/10/2026, mesmo incompleto. Entrega principal em 15/10/2026 às 9h, horário de Brasília; commit final da `main` marcado com a tag `entrega`. Não é necessário hospedar.
- Backend: Python 3.12 síncrono, Flask 3, PyMongo puro, Pydantic 2 na entrada e na saída, pytest, Ruff e uv ou Poetry com lockfile. Escolheremos uv.
- Banco: imagem oficial `mongo:8`, instância standalone padrão, sem ODM e sem configuração de cluster.
- Execução: Docker Compose; API servida por Gunicorn com quatro workers.
- Frontend: Nuxt 4, Vue 3, `<script setup lang="ts">` e Nuxt UI 4, com SSR.
- Código de domínio e commits em português. O histórico deve ser real, com mudanças pequenas, testes junto do código e push em cada dia trabalhado; 25–50 commits é referência, não meta artificial. Não reescrever o histórico enviado.
- IA é permitida, mas o candidato precisa entender cada linha entregue. `README.md` deve ser curto; `NOTAS.md` registra decisões, ambiguidades, limitações e diário real, incluindo ajuda e erros da IA.
- Após a entrega haverá apresentação de aproximadamente 45 minutos e uma pequena alteração ao vivo.

## Regras de negócio

- **RN-01 — Dinheiro:** valores monetários são inteiros em centavos no banco, na API e nos cálculos; nenhum `float` participa das contas.
- **RN-02 — Catálogo:** catálogo fixo do seed; cada livro mantém `estoque` físico e `disponivel` para reserva.
- **RN-03 — Reserva:** um ou mais SKUs, no máximo três unidades por SKU e operação tudo ou nada. TTL padrão de 15 minutos, configurável por `RESERVA_TTL_SEGUNDOS`.
- **RN-04 — Concorrência:** `disponivel` nunca fica negativo e a soma reservada/vendida nunca supera `estoque`, mesmo com requisições simultâneas e quatro processos.
- **RN-05 — Expiração:** em `expira_em` a reserva já está expirada. A próxima consulta de livros ou nova reserva libera as unidades, exatamente uma vez, sem depender de rotina periódica.
- **RN-06 — Confirmação:** reserva ativa gera no máximo um pedido `aguardando_pagamento`. Chamadas repetidas ou simultâneas devolvem o mesmo pedido.
- **RN-07 — Desconto:** pelo total de unidades: 1–2 = 0%; 3–4 = 10%; 5 ou mais = 15%. Aplicar ao subtotal com arredondamento comercial para centavos.
- **RN-08 — Rateio:** desconto proporcional ao valor de cada linha; distribuir centavos restantes pelos maiores restos e, no empate, pela ordem original.
- **RN-09 — Pagamento:** somente webhook altera pedido. `pago` e `cancelado` são finais; recusa libera estoque uma vez; `evento_id` não é aplicado duas vezes.
- **RN-10 — Datas:** persistir em UTC e responder em ISO 8601 UTC com sufixo `Z`.

Exemplo monetário obrigatório: valores `[3990, 2990, 1995]`, subtotal `8975`, desconto total `898`, rateio `[399, 299, 200]` e total líquido `8077`.

## Contrato HTTP

Base da API: `/v1`. As respostas são JSON, exceto o reset `204` sem corpo. Nenhum erro pode expor HTML, stack trace ou dados internos.

| Método e caminho | Entrada principal | Sucesso |
|---|---|---|
| `GET /healthz` | — | `200 {"status":"ok"}` somente com MongoDB acessível |
| `GET /v1/livros` | — | `200` com os cinco livros e disponibilidade já normalizada |
| `POST /v1/reservas` | `cliente_id` e lista `itens[{sku, quantidade}]` | `201` com a reserva criada |
| `GET /v1/reservas/{id}` | ID no caminho | `200` com status verdadeiro no instante da consulta |
| `POST /v1/reservas/{id}/confirmar` | sem corpo | `201` ao criar; repetições retornam o mesmo pedido com `200` |
| `GET /v1/pedidos/{id}` | ID no caminho | `200` com o pedido completo |
| `POST /v1/webhooks/pagamento` | evento JSON e `X-Assinatura` | `200 {"recebido":true}` para aceito, duplicado, sem efeito ou pedido inexistente |
| `POST /v1/admin/reset` | `X-Admin-Token` | `204` sem corpo; restaura o seed e remove reservas, pedidos e eventos |

### Formatos principais

- Livro: `sku`, `titulo`, `preco_centavos`, `estoque`, `disponivel`.
- Reserva: `id`, `cliente_id`, `status`, `itens[{sku, quantidade, preco_centavos}]`, `criado_em`, `expira_em`.
- Status da reserva: `ativa`, `confirmada`, `expirada`.
- Pedido: `id`, `reserva_id`, `cliente_id`, `status`, `linhas`, `subtotal_centavos`, `desconto_centavos`, `total_centavos`, `criado_em`, `pago_em`.
- Linha do pedido: `sku`, `quantidade`, `preco_centavos`, `valor_centavos`, `desconto_centavos`, `liquido_centavos`.
- Status do pedido: `aguardando_pagamento`, `pago`, `cancelado`.
- Webhook: `evento_id`, `pedido_id`, `tipo` (`pago` ou `recusado`) e `ocorrido_em`.

### Erros

Envelope:

```json
{"erro":{"codigo":"estoque_insuficiente","mensagem":"Texto legível.","detalhes":{}}}
```

| HTTP | `codigo` | Situação |
|---:|---|---|
| 400 | `requisicao_invalida` | Corpo ou parâmetros fora do contrato |
| 401 | `nao_autorizado` | Token administrativo ou assinatura inválidos/ausentes |
| 404 | `nao_encontrado` | Recurso inexistente, inclusive ID malformado |
| 409 | `estoque_insuficiente` | `detalhes.skus` lista os SKUs sem quantidade suficiente |
| 410 | `reserva_expirada` | Tentativa de confirmar reserva expirada |

### Assinatura do webhook

`X-Assinatura` é o HMAC-SHA256 hexadecimal dos bytes do corpo bruto, usando `WEBHOOK_SEGREDO`. Assinatura ausente ou inválida responde 401 e não processa nada. `pago_em` recebe `ocorrido_em` do evento que efetivou o pagamento.

Vetor de referência, sem espaços nem quebra de linha:

```text
segredo: segredo-de-exemplo
corpo: {"evento_id":"evt_0001","pedido_id":"66f0c2a1e4b0a1b2c3d4e5f7","tipo":"pago","ocorrido_em":"2026-10-01T12:00:00Z"}
assinatura: bcb4b6f50d0ad32b6e2988d50fca256a72fd31196164ea4c210214966da968d7
```

## Seed exato

| SKU | Título | `preco_centavos` | `estoque` |
|---|---|---:|---:|
| QND-001 | O Jardim de Dentro | 3990 | 10 |
| QND-002 | Bicho-Palavra | 2990 | 10 |
| QND-003 | A Casa que Anda | 1995 | 10 |
| QND-004 | Kit Primeira Leitura | 8990 | 3 |
| QND-005 | A Lua no Bolso — edição numerada | 12900 | 1 |

`disponivel` começa igual a `estoque`.

## Frontend, execução e testes

- Uma página: catálogo, quantidades, reserva, contagem regressiva, confirmação e pedido com desconto por linha; erros claros e moeda brasileira.
- O navegador chama somente rotas `server/api` do Nuxt; a URL do Flask e os segredos ficam no servidor.
- SSR permanece ligado e sem avisos de hidratação.
- Um clone limpo deve subir MongoDB, API na porta 8000 e frontend na porta 3000 com `docker compose up --build`, após copiar `.env.example` para `.env`.
- Testes obrigatórios: unidade para desconto/rateio e integração concorrente contra MongoDB real; os comandos ficam no README quando forem executados.
- Prioridade: catálogo/reserva/confirmação concorrentes; expiração; dinheiro; webhook; frontend.
