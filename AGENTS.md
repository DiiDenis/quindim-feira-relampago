# Feira Relâmpago — instruções para o agente

## Escopo e precedência

Implemente somente a etapa solicitada. Leia este arquivo, `docs/CONTRATO.md`, `NOTAS.md`, `git status` e o diff antes de agir. O PDF original prevalece sobre o roteiro; divergências devem ser expostas, não corrigidas silenciosamente. O kit externo `../kit-quindim` contém o planejamento; um clone da entrega deve funcionar sem ele.

Stack fixa: Python 3.12 síncrono, Flask 3, MongoDB 8 standalone, PyMongo puro, Pydantic 2, pytest, Ruff, uv com uv.lock; Nuxt 4, Vue 3, TypeScript e Nuxt UI 4; Docker Compose e Gunicorn com quatro workers síncronos. Não use async/await no Python, ODM, SQL, replica set ou trava em memória para garantir consistência.

## Forma de trabalhar

- Uma mudança pequena por vez, acompanhada dos seus testes. Não implemente etapas futuras.
- Prefira funções e módulos pequenos. Classes de validação Pydantic são apropriadas; não crie interfaces, repositories abstratos ou camadas sem necessidade concreta.
- Dinheiro: inteiro em centavos; nunca float, round() bancário ou cálculo monetário no navegador com fração decimal.
- Domínio e mensagens de commit em português. Termos das bibliotecas permanecem como são.
- Use o CAS documentado em NOTAS.md para mudanças de estoque/reservas/pedidos/eventos. Não grave esses estados em operações separadas que deixem janelas de inconsistência.
- Segurança: segredos somente no servidor; não publique .env, tokens ou dados pessoais. Não crie autenticação de cliente, pagamento real ou extras fora do enunciado.
- E-books, capturas, relatórios extensos e material de estudo ficam FORA deste repositório, em `../quindim-estudos`.

## Verificação e Git

Não diga que testou algo sem executar. Mostre o comando, o resultado real e qualquer impedimento. Teste que não rodou não é teste aprovado. Falha deve ser investigada; não remova assert, ignore cenário, substitua MongoDB por mock nem altere o contrato para conseguir verde.

Antes de um commit: teste a mudança, rode Ruff quando aplicável, confira `git diff --check`, `git diff --stat` e o diff completo. Mostre os arquivos alterados e PARE para minha revisão. Aguarde a frase `Revisei. Pode commitar.`. Após a aprovação, adicione somente os arquivos desta etapa, faça um commit em português e dê push normal. Não avance sozinho para outro prompt.

Não invente commits, datas, estudos, tropeços ou autoria. Nunca use squash, rebase para arrumar histórico, amend em commit enviado, force push ou commit vazio para bater meta. Nunca apague mudanças existentes. Se a etapa precisar ser dividida, explique antes e proponha subtarefas pequenas, sem simular dias de trabalho.

README curto. NOTAS.md tem `Decisões` e `Diário`; o diário registra apenas fatos ocorridos. Não escreva que Denis estudou ou entendeu algo sem confirmação. Descreva ajuda e erros reais da IA sem eufemismos.

## Resposta de encerramento por etapa

No máximo cerca de 180 palavras, fora comandos e de um exemplo com até 8 linhas. Use:

**Feito:** o que mudou e em quais arquivos.
**Padrão e motivo:** nome simples; quando não houver padrão formal, diga isso.
**Python ↔ JS/TS:** uma equivalência útil; indique os limites da analogia.
**Sem equivalente direto:** somente se necessário, em uma ou duas frases.
**Verificado:** comandos e resultados reais; liste pendências sem escondê-las.
**Olhe no diff:** um trecho concreto para eu revisar.
**Entendimento:** uma pergunta curta, sem responder por mim.
**Commit sugerido:** uma frase em português. Aguardar minha aprovação.

Não dê aula longa, não responda com o arquivo inteiro e não trate sintaxe Python como se fosse JavaScript traduzido literalmente. Corrigir meu entendimento é tão importante quanto fazer os testes passarem.
