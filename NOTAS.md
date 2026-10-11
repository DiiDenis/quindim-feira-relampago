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

Limitações conhecidas: o documento único concentra contenção, cresce com reservas/pedidos/eventos, custa mais para ler e regravar e está sujeito ao limite BSON de 16 MiB. Consultas podem precisar publicar expirações e incrementar a versão. O laço CAS não limita conflitos normais; timeouts de infraestrutura continuam possíveis e são propagados, não tratados como conflito. Os cenários concorrentes são finitos e não equivalem a benchmark, teste de carga ou prova de todas as intercalações possíveis. É uma solução deliberada para a feira pequena e para MongoDB standalone, não uma arquitetura de escala ilimitada.

O CAS protege geração e versão e também inclui no filtro do MongoDB a fronteira temporal relevante para cada operação. Essa proteção cobre as disputas modeladas e testadas neste projeto, mas não substitui teste de carga nem demonstra escalabilidade ilimitada.

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
- O mecanismo CAS passou a reler estado e hora do MongoDB após conflitos de geração ou versão, descartando o cálculo vencido antes de tentar novamente.
- Dois candidatos sincronizados contra o MongoDB real partiram da versão zero; um deles releu após perder o CAS, e o agregado terminou corretamente na versão dois.
- `GET /v1/livros` passou a publicar somente o DTO validado dos cinco livros, usando o caminho CAS que receberá a normalização de expiração.
- A primeira checagem de formato do catálogo pediu a compactação de uma compreensão; após o ajuste, a suíte com HTTP real passou com 49 testes.
- A entrada de reserva passou a rejeitar tipos, vazios, extras e quantidades fora do limite antes de qualquer acesso ao banco.
- A normalização de SKUs repetidos preservou a primeira posição e impediu somas acima de três; os 67 testes da suíte passaram no Docker.
- A regra de reserva passou a validar toda a cesta antes de alterar disponibilidade, preservando integralmente o estado quando há SKU inexistente ou estoque insuficiente.
- A reserva válida registra preços do estado e TTL em UTC, sem desconto; após ajustes de formatação em compreensões, os 71 testes passaram no Docker.
- `POST /v1/reservas` passou a validar a entrada, criar um ID, reservar a cesta inteira via CAS e responder 201 somente depois de persistir o novo estado no MongoDB.
- A primeira suíte completa revelou que o teste do seed reutilizava o estado alterado por outro cenário; ele passou a usar o reset de negócio e a repetição terminou com 75 testes aprovados.
- `GET /v1/reservas/{id}` passou a consultar o mesmo agregado via CAS e a reutilizar o contrato público da criação, sem expor campos internos da reserva.
- IDs malformados e IDs válidos inexistentes passaram a responder o mesmo erro 404 controlado, sem deixar a conversão de ObjectId escapar como falha interna.
- Testes HTTP com 20 chamadas simultâneas confirmaram no MongoDB standalone que apenas o estoque disponível é reservado e que cestas perdedoras não descontam outros itens.
- A disputa por dez unidades foi repetida em três rodadas contra os quatro workers; a suíte completa passou com 83 testes, sem timeout ou resposta 500.
- A primeira execução do teste concorrente usou por engano o preço 2590 para o QND-005; a expectativa foi corrigida para o valor 12900 do seed e os testes foram repetidos.
- A checagem de formato pediu parênteses na asserção longa da invariante; o trecho foi ajustado antes da revisão final.
- A regra pura de expiração passou a marcar reservas ativas vencidas e devolver todos os seus itens uma única vez, mantendo confirmadas e já expiradas intactas.
- Testes unitários cobriram antes, igualdade e depois do prazo, repetição e mistura de status; a suíte completa passou com 89 testes.
- O caminho CAS comum passou a expirar a cópia antes da operação e a exigir no filtro de escrita que a hora do Mongo ainda seja anterior ao menor prazo ativo relevante.
- O filtro considera reservas ativas do snapshot original e novas reservas candidatas; uma escrita real foi recusada ao cruzar o prazo mesmo sem outro escritor.
- Erros de negócio agora são adiados quando necessário para persistir uma expiração no mesmo CAS; um 409 real devolveu estoque vencido sem criar a reserva inválida.
- A primeira regressão elevou a versão em dois erros sem expiração e quebrou a expectativa de estado intacto; o CAS passou a gravar antes do erro somente quando há limpeza ou prazo ativo a proteger.
- A checagem de formato pediu a compactação de duas expressões; ambas foram ajustadas antes da revisão final.
- Um teste real confirmou que, ao perder pelo filtro temporal, o CAS relê a hora, expira a reserva e salva na segunda tentativa; a suíte completa passou com 94 testes.
- Testes HTTP reais confirmaram que consultas simultâneas devolvem o estoque vencido uma única vez e que somente uma nova reserva vence a disputa pela unidade liberada.
- A API foi recriada isoladamente com TTL de dois segundos; a reserva atravessou o relógio real, expirou sob demanda e a API foi restaurada ao padrão de 900 segundos.
- A primeira execução do TTL curto iniciou o runner apenas com o Compose padrão, que recriou a API com 900 segundos; a configuração curta foi aplicada também ao runner e o cenário passou na repetição.
- O desconto progressivo passou a ser calculado apenas com centavos e percentuais inteiros, incluindo arredondamento comercial e validação de valores internos impossíveis; a suíte completa passou com 118 testes.
- O desconto total passou a ser rateado proporcionalmente pelos maiores restos, com desempate pela ordem original; a suíte completa passou com 135 testes.
- A primeira checagem do rateio encontrou uma asserção longa e a segunda pediu a compactação do gerador; o trecho foi ajustado até lint e formato passarem juntos.
- A composição de pedidos passou a usar somente o snapshot da reserva, reaproveitando desconto e rateio para conferir valores de linha, subtotal, desconto e total líquido; a suíte completa passou com 143 testes.
- A primeira checagem de estilo dos pedidos encontrou uma asserção longa e a seguinte pediu a compactação de uma compreensão; os dois pontos foram ajustados antes da revisão.
- A confirmação de domínio passou a criar e vincular o pedido uma única vez, devolver o mesmo pedido nas repetições e preservar o estoque já retido; a suíte completa passou com 150 testes.
- A checagem de formato pediu a compactação de um dicionário no teste de confirmação; o trecho foi ajustado antes da revisão final.
- O endpoint de confirmação passou a publicar a transição pelo CAS: cria com 201, repete com 200, rejeita corpo e persiste a liberação antes do erro 410; a suíte completa passou com 155 testes.
- A consulta de pedido passou a reutilizar o mesmo DTO validado da confirmação, preservando linhas, centavos, datas e ocultando campos internos; a suíte completa passou com 158 testes.
- A primeira checagem de formato da consulta pediu a compactação de uma chamada HTTP; o ajuste foi aplicado antes da revisão.
- Vinte confirmações HTTP simultâneas contra quatro workers produziram um único pedido: uma resposta 201 e dezenove respostas 200 com o mesmo conteúdo; a suíte completa passou com 164 testes.
- Testes de fronteira confirmaram que uma tentativa iniciada antes do prazo não é publicada após vencê-lo e que a corrida com uma leitura termina somente em confirmação integral ou expiração integral.
- A primeira execução dos novos testes usou `Counter.update` com dicionários não hashable e consultou o nome errado do status em `ErroNegocio`; as duas verificações do teste foram corrigidas e os cenários passaram na repetição.
- A checagem de formato pediu a compactação da equação de invariante; o Ruff aplicou o ajuste antes da verificação final.
- A entrada de webhook passou a aceitar somente IDs não vazios, tipos pago/recusado e data com fuso normalizada para UTC, sem tratar `pedido_id` como ID de rota.
- O HMAC-SHA256 dos bytes originais foi conferido com o vetor fixo de 114 bytes do PDF; JSON equivalente com espaços exigiu outra assinatura, e a suíte completa passou com 181 testes.
- Eventos de pagamento passaram a ser consumidos globalmente pelo `evento_id`; pedidos aguardando mudam para pago ou cancelado, enquanto estados finais não são reabertos.
- A recusa devolve as unidades uma única vez no mesmo estado que registra o evento e cancela o pedido; pedido inexistente e eventos sem efeito também permanecem registrados para deduplicação.
- A primeira checagem de estilo pediu a união de duas condições e a de formato compactou duas expressões; após os ajustes, a suíte completa passou com 191 testes.
- `POST /v1/webhooks/pagamento` passou a autenticar o corpo bruto antes de interpretar JSON ou acessar o agregado, e aplica eventos válidos pelo mesmo CAS de reservas e pedidos.
- Um teste com reserva vencida confirmou que assinatura ausente ou inválida responde 401 sem alterar versão, status ou estoque; pago, recusado, duplicado, terminal e pedido inexistente respondem `recebido` conforme o contrato.
- A API foi reconstruída com os quatro workers para os testes HTTP; a suíte completa passou com 197 testes e a checagem de formato compactou uma asserção antes da verificação final.
- O contrato HTTP completo do webhook foi exercitado com HMAC calculado independentemente pela biblioteca padrão, incluindo o vetor fixo do PDF, JSON malformado, data sem fuso e IDs de pedido válidos ou malformados.
- Reentregas, payload conflitante com o mesmo `evento_id` e eventos fora de ordem preservaram estado terminal e `pago_em`; após recusa, uma nova reserva consumiu de fato a unidade devolvida.
- Confirmações repetidas depois de pagamento ou cancelamento devolveram o mesmo pedido atual sem criar outro; a suíte completa passou com 204 testes, e o Ruff pediu uma linha em branco no bloco de imports antes da verificação final.
- Vinte entregas simultâneas do mesmo evento de recusa retornaram 200, consumiram um único ID e devolveram a unidade uma vez; vinte IDs distintos também preservaram uma única devolução.
- Corridas entre pago/recusado e entre recusa/nova reserva foram repetidas em cinco rodadas cada; os testes aceitaram os vencedores possíveis e recalcularam a invariante diretamente do snapshot final.
- A suíte completa passou com 216 testes contra quatro workers e MongoDB real; a checagem de formato compactou duas asserções antes da verificação final.
- A auditoria final confirmou exatamente as oito rotas públicas do contrato e tornou também os modelos de saúde e erro estritos contra campos extras e conversões implícitas.
- A primeira tentativa de executar os testes direcionados usou por engano o serviço Compose `test`; o nome correto `testes` foi usado na repetição, que passou com 19 testes.
- Uma reserva confirmada e seu pedido foram consultados antes e depois de reiniciar somente a API; as respostas permaneceram idênticas, o contêiner do MongoDB não mudou e o Gunicorn voltou com quatro workers.
- O reset administrativo foi aplicado ao final da verificação de reinício. Esse cenário comprova persistência entre processos da API, mas não é teste de queda do host, durabilidade física nem teste de carga.
- Após a auditoria, a suíte completa passou com 227 testes; Ruff e a verificação de formatação passaram nos 49 arquivos Python.
- No checkpoint do backend, os targets `api` e `testes` foram reconstruídos sem cache; o ambiente executou Python 3.12.15, MongoDB 8.3.11 standalone sem `setName` e Gunicorn com um processo mestre e quatro workers.
- Os 36 testes unitários de dinheiro e os 69 testes de integração HTTP passaram separadamente, incluindo concorrência de reservas, confirmações, pagamentos e expiração.
- Uma execução isolada com TTL de dois segundos expirou e liberou uma reserva pelo relógio real; a API foi recriada depois com o padrão de 900 segundos, confirmado pelo mesmo teste.
- Os comandos documentados no README foram repetidos no checkpoint, e a suíte completa terminou com 227 testes aprovados.
- O frontend base foi criado com Nuxt 4.6.1, Vue 3.5.43, Nuxt UI 4.11.3 e TypeScript 5.9.3; o lock real foi gerado pelo npm e reproduzido com `npm ci` no Node 22.22.3 do Docker.
- Os estilos próprios adotam SCSS, BEM e breakpoints centralizados; Tailwind permanece somente como dependência interna do Nuxt UI, sem utilitários ou `@apply` no código da aplicação.
- A primeira tentativa de compilar o CSS global como SCSS fez o Sass interpretar os imports do Tailwind e falhou no bundle do servidor. Os imports exigidos pelo Nuxt UI foram isolados em CSS e os estilos próprios permaneceram em SCSS; typecheck e build passaram na repetição.
- O Compose passou a subir MongoDB, API e frontend saudável na porta 3000. O HTML servido contém o conteúdo inicial renderizado e não contém a URL interna da API.
- O `npm audit` registrou 15 alertas transitivos na árvore do Nuxt, incluindo dependências de ferramentas de desenvolvimento. `npm audit fix` não encontrou atualização compatível e a opção `--force` foi recusada porque propunha trocar Nuxt 4 por Nuxt 3.
- O BFF do Nuxt passou a expor somente as cinco rotas necessárias à interface e a montar no servidor os destinos fixos do Flask; não há proxy arbitrário, rota administrativa nem webhook no frontend.
- Chamadas HTTP reais pelo Nuxt preservaram os status 200, 201, 400 e 404 e seus JSONs. Com a API interrompida, o BFF respondeu 502 genérico sem URL interna ou stack; a API foi religada e voltou saudável.
- A primeira checagem de tipos do BFF encontrou o corpo `unknown` incompatível com o tipo aceito pelo `ofetch`. O corpo JSON foi tipado como objeto sem acrescentar validação de negócio, e typecheck e build passaram na repetição.
- O HTML público não expôs a URL interna nem o token administrativo. Depois da mudança, a suíte completa do backend continuou com 227 testes aprovados.
- O catálogo passou a ser buscado por `useFetch('/api/livros')` durante o SSR e renderizado com tipos públicos mínimos. O HTML inicial retornado pelo Nuxt continha os cinco títulos e os cinco preços, sem endereço do Flask.
- A apresentação de moeda converte centavos inteiros seguros para `BigInt`, separa reais e centavos por divisão e resto inteiros e aplica agrupamento `pt-BR`; testes cobriram 3990, 1995, 12900, zero e entradas inseguras.
- A primeira checagem de tipos dos testes não encontrou as declarações de `node:test` e `node:assert`; `@types/node` foi adicionado como dependência de desenvolvimento e teste, typecheck e build passaram na repetição.
- A página passou a montar a reserva somente com cliente, SKU e quantidades positivas, limitar visualmente cada item a três e à disponibilidade observada e impedir envio vazio ou repetido durante a requisição.
- Um envio real pela interface criou uma única reserva mesmo com clique duplo, zerou a seleção e atualizou o QND-001 de dez para nove disponíveis. A inspeção do estado confirmou uma reserva para `cli_demo` com uma unidade.
- Um conflito concorrente real no QND-005 devolveu 409 e atualizou catálogo e mensagem. O primeiro teste visual revelou que a quantidade antiga permanecia no campo após a disponibilidade cair a zero; a seleção passou a ser reconciliada com o catálogo e o cenário foi repetido com campo zerado e botão desabilitado.
- O reset administrativo recompôs o seed ao final dos cenários de interface.
- A reserva ativa passou a exibir itens, status, prazo ISO e um contador calculado a cada tick pela diferença para `expira_em`; o relógio só inicia após a montagem e o intervalo é limpo ao trocar de reserva ou desmontar a página.
- Com a API temporariamente executada com TTL de dois segundos, a interface mostrou `00:02`, consultou a reserva ao zerar, recebeu `expirada`, devolveu o QND-001 de nove para dez disponíveis e liberou uma nova seleção.
- A inspeção do console durante o cenário não encontrou avisos ou erros de hidratação. A API curta foi removida, a API padrão voltou saudável e o teste direcionado confirmou novamente o TTL padrão de 900 segundos.
- Testes unitários do contador cobriram o prazo absoluto, o instante exato da expiração e a formatação de 15:00, 00:05 e 00:00; a suíte frontend passou com seis testes.
- A interface passou a confirmar reservas sem corpo, bloquear clique repetido, consultar a reserva confirmada e apresentar o pedido retornado sem recalcular desconto ou rateio no navegador.
- O cenário real com QND-001, QND-002 e QND-003 mostrou subtotal 8975, desconto 898, total 8077 e rateio 399/299/200; o clique duplo terminou com uma reserva e um pedido no estado persistido.
- Um webhook assinado externamente marcou o pedido como pago. O botão de atualização trouxe `pago` e `pago_em` para a tela, enquanto o HTML público permaneceu sem segredo, nome do segredo ou URL interna da API.
- A fronteira 410 foi exercitada tornando o prazo de uma reserva de teste passado no MongoDB: a confirmação exibiu a expiração, recompôs a disponibilidade e liberou nova seleção. O reset recompôs o seed ao final.
- A primeira inspeção do snapshot usou por engano o nome `eventos_pagamento`; a coleção interna correta é `eventos`, e a repetição confirmou exatamente uma reserva, um pedido e um evento.
- A revisão funcional acrescentou estados explícitos de carregamento e falha do catálogo, com retentativa acessível. Com a API interrompida, o SSR mostrou a mensagem controlada; após religar a API, o botão recuperou os cinco livros sem recarregar a página.
- O narrowing de erros desconhecidos foi isolado em um helper sem `any` e testado para envelopes válidos, falha de rede e resposta sem JSON. A primeira expectativa encontrou `{status: undefined}`; o helper passou a omitir o campo ausente e os oito testes passaram.
- As ações de reserva, confirmação e atualização mantêm guardas contra repetição; campos da cesta permanecem bloqueados durante reserva ativa ou confirmada e são liberados somente após expiração informada pela API.
- A inspeção final não encontrou avisos no console, alteração em arquivos do backend nem serviço sem saúde no Compose.
