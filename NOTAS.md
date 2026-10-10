# Notas

## Decisões

- Manter o kit de planejamento fora deste repositório, na pasta irmã `../kit-quindim`.
- Preservar um histórico Git pequeno e verdadeiro, com revisão antes de cada commit.
- Manter o repositório remoto privado durante o desenvolvimento.

### Modelo de consistência proposto

Estas são decisões nossas para atender o contrato; não são escolhas aprovadas pela empresa.

- Usar um único documento agregado na coleção `feiras`, com `_id: "principal"`, `geracao`, `versao`, livros, reservas, pedidos e eventos processados.
- Alterar em uma única escrita tudo o que precisa permanecer consistente: disponibilidade e reserva; confirmação e pedido; evento, estado do pedido e eventual devolução.
- Aplicar CAS por `geracao + versao`: ler o estado, calcular uma cópia e salvar apenas se ambos ainda coincidirem. Em conflito, reler e recalcular; não reaproveitar o snapshot antigo.
- Obter a hora do MongoDB com `$$NOW` e incluir a fronteira temporal no filtro de escrita. Na igualdade `agora == expira_em`, a reserva já venceu.
- Normalizar reservas expiradas durante as requisições relevantes, sem depender de tarefa periódica. Mesmo quando a operação terminar em erro de negócio, a liberação já calculada precisa ser persistida uma única vez.
- Trocar `geracao` no reset para impedir que uma escrita iniciada antes dele sobrescreva o novo seed, mesmo que o número de versão se repita.
- Manter `estoque` como capacidade física fixa e variar `disponivel`. Depois de normalizar expirações: `estoque = disponivel + reservas_ativas + pedidos_aguardando_ou_pagos`.

Limitações conhecidas: o documento único concentra contenção, cresce com reservas/pedidos/eventos, custa mais para ler e regravar e está sujeito ao limite BSON de 16 MiB. Consultas podem precisar publicar expirações e incrementar a versão. É uma solução deliberada para a feira pequena e para MongoDB standalone, não uma arquitetura de escala ilimitada.

### Ambiguidades e critérios adotados

As decisões abaixo são propostas nossas e deverão ser confirmadas por testes; não foram atribuídas a Daniel.

| Evidência ou lacuna | Decisão e justificativa | Teste ou limite futuro |
|---|---|---|
| Prazo principal em 15/10/2026 às 9h, mas um parágrafo menciona dia 29 | Seguir 15/10 às 9h, por ser o prazo explícito e repetido no início | Planejar entrega e tag para esse instante |
| RN-03 diz 15 minutos, mas o exemplo mostra 10 | Usar 900 segundos por padrão; `RESERVA_TTL_SEGUNDOS` governa | Testar padrão e TTL curto configurado |
| Reserva e pedido dos exemplos têm itens diferentes | Tratar como exemplos independentes de formato; pedido real copia sua reserva | Teste encadeado confere SKUs, quantidades e preços |
| Regra geral pede JSON, enquanto reset responde 204 | A regra específica vence: reset sem corpo | Conferir status 204 e corpo vazio |
| Mesmo SKU pode aparecer mais de uma vez na entrada | Consolidar quantidades preservando a primeira posição; total por SKU não pode passar de 3 | Testar soma válida e tentativa de burlar o limite |
| SKU desconhecido não tem tratamento específico | Responder 404 `nao_encontrado`, sem alteração parcial | Testar estado antes e depois |
| Campos extras não são descritos | Rejeitar entrada com 400 e nunca expor campos internos na saída | Testes de validação de entrada e saída |
| `cliente_id` e `evento_id` vazios não são definidos | Rejeitar vazios; aceitar identificadores não vazios sem inventar cadastro ou login | Testar vazio, tipos errados e valor válido |
| ID malformado de pedido em webhook autenticado conflita com 404 genérico | Tratar como pedido inexistente e responder 200, pois a regra específica do webhook prevalece | Testar HMAC válido e ausência de criação de pedido |
| Mesmo `evento_id` pode reaparecer com outro conteúdo | A primeira ocorrência autenticada e válida consome o ID; repetições não reaplicam | Testar payload conflitante e estado inalterado |
| Data de webhook sem fuso não é definida | Responder 400; aceitar data com fuso e normalizar para UTC/Z | Testar ausência de fuso e conversão de offset |
| Confirmação repetida depois de pedido pago ou cancelado | Retornar o mesmo pedido em seu estado atual com HTTP 200 | Testar ambos os estados finais |
| Endpoint de confirmação é descrito como sem corpo | Rejeitar corpo não vazio com 400 | Testar corpo vazio e conteúdo indevido |
| Relação entre `estoque` e `disponivel` não traz equação | `estoque` permanece a capacidade inicial; `disponivel` varia conforme o invariante acima | Recalcular o invariante de uma leitura persistida |

## Diário

### 09/10/2026

- O repositório vazio foi criado manualmente no GitHub e clonado por HTTPS.
- A estrutura local foi corrigida depois que o primeiro clone criou uma pasta duplicada.
- Foram preparados apenas os arquivos iniciais do projeto; a aplicação ainda não foi implementada.
- O PDF original foi comparado com o contrato, o plano arquitetural e a matriz de aceite do kit.
- A IA ajudou a organizar requisitos, decisões e ambiguidades; nenhum código de aplicação ou teste foi produzido nesta etapa.
- O Python instalado no Windows era 3.14.8; para respeitar o contrato foi usado o Python 3.12.14 do runtime local do Codex.
- Como `uv` não estava instalado e o motor do Docker não estava ativo, `uv` 0.13.0 foi instalado somente em um ambiente virtual temporário, sem instalação global.
- O lockfile real foi gerado e sincronizado; imports e ferramentas foram verificados. Ainda não existem testes de negócio.
- A primeira tentativa de conferir o lock e importar `app` foi executada pela IA na raiz do repositório e falhou por diretório incorreto; os comandos foram repetidos em `backend` e passaram.
- Na primeira coleta dos testes da factory, o `pytest.exe` no Windows não encontrou o pacote `app`; a raiz de `backend` foi declarada no `pythonpath` do pytest e a suíte foi repetida.
- A factory Flask e a configuração foram verificadas por 15 testes unitários; importar `app` sem variáveis de ambiente não iniciou servidor nem tentou acessar MongoDB.
- O Compose foi validado e subiu MongoDB 8.3.11 standalone, sem porta no host, e a API com Gunicorn 23.0.0 e quatro workers síncronos.
- O target Docker de testes foi construído separadamente e os 15 testes unitários passaram também no contêiner Linux com Python 3.12.

### 10/10/2026

- A aplicação passou a criar um cliente PyMongo por instância Flask, sem conexão antecipada, com timeout finito e leitura de datas em UTC.
- O endpoint `/healthz` foi verificado por HTTP contra o MongoDB real; os 16 testes unitários e o teste de integração passaram.
- O MongoDB somente deste projeto foi interrompido para confirmar o erro 503 genérico e depois restaurado; Mongo e API voltaram ao estado saudável.
- A primeira tentativa da IA de agrupar a interrupção e a restauração em um comando foi rejeitada pela política de execução; os passos foram repetidos separadamente.
- A primeira coleta da suíte completa falhou porque os testes unitário e de integração tinham o mesmo nome de módulo; o arquivo de integração foi renomeado antes da repetição.
- O catálogo inicial passou a ser criado antes do Gunicorn e foi preservado ao reiniciar somente a API.
- O seed foi executado repetidamente em um banco isolado; manteve um único documento e não desfez uma alteração controlada. O banco de verificação foi removido ao final.
- Os testes de seed cobriram o catálogo exato, estruturas independentes, repetição e oito inicializações concorrentes; a suíte no contêiner passou com 21 testes.
- A primeira checagem de estilo da etapa encontrou uma linha longa; a primeira quebra manual ainda divergiu do formatador e a segunda correção passou.
- A API passou a responder erros esperados e inesperados no mesmo envelope JSON; falhas internas mantêm HTTP 500 e detalhes técnicos somente no log.
- Foram adicionados helpers para IDs ObjectId estritos e datas com fuso normalizadas em UTC/Z sem descartar a fração de segundo.
- A suíte passou com 33 testes unitários e 36 testes no contêiner; uma chamada real via Gunicorn confirmou 404 JSON para rota inexistente.
- A primeira checagem de formato pediu reorganização de duas chamadas nos testes; o Ruff aplicou a correção antes da repetição.
- O profile de teste passou a executar pytest contra `api` e `mongo` pelos nomes da rede Compose, com fixtures HTTP, Mongo e token administrativo vindo do ambiente.
- `docker compose run --rm testes` passou com 33 verificações unitárias e quatro de integração; saúde e seed foram conferidos através da API/Gunicorn e do MongoDB reais.
- URLs deliberadamente inválidas produziram erros explícitos de API e Mongo, sem transformar ausência de serviço em teste pulado.
- O primeiro runner reutilizou uma imagem Compose antiga e não encontrou os testes; `pull_policy: build` foi adicionado e a repetição reconstruiu a imagem correta.
- `docker compose up` manteve somente MongoDB e API em execução; o serviço de testes permaneceu fora do ambiente normal.
- O reset administrativo passou a autenticar o token antes de acessar a feira e a substituir o agregado inteiro, com uma geração nova, em uma única escrita.
- Testes reais confirmaram respostas 401 e 204 sem corpo, recomposição exata do catálogo e isolamento dos cenários de negócio por reset restrito à rede do Compose.
