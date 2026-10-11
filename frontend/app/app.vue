<script setup lang="ts">
import type {
  Livro,
  Pedido,
  Reserva,
  RespostaLivros,
} from '~/types/api'
import { lerErroApi } from '~/utils/erro-api'
import { formatarCentavos } from '~/utils/moeda'
import { construirItensReserva } from '~/utils/reserva'
import {
  calcularSegundosRestantes,
  formatarDuracao,
} from '~/utils/tempo-reserva'

const titulo = 'Feira Relâmpago'

const {
  data: respostaCatalogo,
  error: erroCatalogo,
  refresh: atualizarCatalogo,
  status: statusCatalogo,
} = await useFetch<RespostaLivros>('/api/livros', {
  key: 'catalogo-livros',
})

const livros = computed(() => respostaCatalogo.value?.livros ?? [])
const clienteId = ref('cli_demo')
const quantidades = reactive<Record<string, number>>({})
const reserva = ref<Reserva | null>(null)
const pedido = ref<Pedido | null>(null)
const enviandoReserva = ref(false)
const consultandoReserva = ref(false)
const confirmandoReserva = ref(false)
const atualizandoPedido = ref(false)
const repetindoCatalogo = ref(false)
const mensagemErro = ref('')
const instanteAtualMs = ref<number | null>(null)
let paginaMontada = false
let intervaloContador: ReturnType<typeof setInterval> | undefined

const itensSelecionados = computed(() => construirItensReserva(
  livros.value,
  quantidades,
))

const selecaoLiberada = computed(() => (
  reserva.value === null || reserva.value.status === 'expirada'
))

const podeReservar = computed(() => (
  selecaoLiberada.value
  && clienteId.value.trim().length > 0
  && itensSelecionados.value.length > 0
  && !enviandoReserva.value
))

const segundosRestantes = computed(() => {
  if (
    reserva.value?.status !== 'ativa'
    || instanteAtualMs.value === null
  ) {
    return null
  }

  return calcularSegundosRestantes(
    reserva.value.expira_em,
    instanteAtualMs.value,
  )
})

const contadorReserva = computed(() => {
  if (reserva.value?.status === 'expirada') {
    return '00:00'
  }

  return segundosRestantes.value === null
    ? '--:--'
    : formatarDuracao(segundosRestantes.value)
})

const podeConfirmar = computed(() => (
  reserva.value?.status === 'ativa'
  && !confirmandoReserva.value
))

function maximoSelecionavel(livro: Livro): number {
  return Math.min(3, livro.disponivel)
}

function definirQuantidade(
  livro: Livro,
  valorRecebido: unknown,
): void {
  const valor = Number(valorRecebido)
  const quantidade = Number.isFinite(valor) ? Math.trunc(valor) : 0
  quantidades[livro.sku] = Math.max(
    0,
    Math.min(maximoSelecionavel(livro), quantidade),
  )
}

function ajustarQuantidadesAoCatalogo(): void {
  livros.value.forEach((livro) => {
    definirQuantidade(livro, quantidades[livro.sku] ?? 0)
  })
}

function pararContador(): void {
  if (intervaloContador !== undefined) {
    clearInterval(intervaloContador)
    intervaloContador = undefined
  }
}

async function consultarReservaAoVencer(idReserva: string): Promise<void> {
  if (consultandoReserva.value || reserva.value?.id !== idReserva) {
    return
  }

  pararContador()
  consultandoReserva.value = true

  try {
    const reservaAtualizada = await $fetch<Reserva>(
      `/api/reservas/${encodeURIComponent(idReserva)}`,
      { retry: 0 },
    )

    if (reserva.value?.id === idReserva) {
      reserva.value = reservaAtualizada
      await atualizarCatalogo()
      ajustarQuantidadesAoCatalogo()
    }
  }
  catch (erro: unknown) {
    const erroApi = lerErroApi(erro)
    mensagemErro.value = erroApi.resposta?.erro.mensagem
      ?? 'Não foi possível atualizar o estado da reserva.'
  }
  finally {
    consultandoReserva.value = false
  }
}

function atualizarRelogio(): void {
  instanteAtualMs.value = Date.now()

  if (segundosRestantes.value === 0 && reserva.value?.status === 'ativa') {
    void consultarReservaAoVencer(reserva.value.id)
  }
}

function iniciarContadorDaReserva(): void {
  pararContador()
  instanteAtualMs.value = null

  if (!paginaMontada || reserva.value?.status !== 'ativa') {
    return
  }

  atualizarRelogio()

  if (segundosRestantes.value !== 0) {
    intervaloContador = setInterval(atualizarRelogio, 250)
  }
}

watch(
  () => [
    reserva.value?.id,
    reserva.value?.status,
    reserva.value?.expira_em,
  ],
  iniciarContadorDaReserva,
)

onMounted(() => {
  paginaMontada = true
  iniciarContadorDaReserva()
})

onUnmounted(() => {
  paginaMontada = false
  pararContador()
})

async function criarReserva(): Promise<void> {
  if (!podeReservar.value) {
    return
  }

  enviandoReserva.value = true
  mensagemErro.value = ''

  try {
    const novaReserva = await $fetch<Reserva>('/api/reservas', {
      method: 'POST',
      body: {
        cliente_id: clienteId.value.trim(),
        itens: itensSelecionados.value,
      },
      retry: 0,
    })

    reserva.value = novaReserva
    pedido.value = null
    Object.keys(quantidades).forEach(sku => quantidades[sku] = 0)
    await atualizarCatalogo()
  }
  catch (erro: unknown) {
    const erroApi = lerErroApi(erro)
    mensagemErro.value = erroApi.status === 409
      ? 'O estoque mudou enquanto você escolhia. Confira as quantidades disponíveis.'
      : erroApi.resposta?.erro.mensagem
        ?? 'Não foi possível criar a reserva agora.'

    if (erroApi.status === 409) {
      await atualizarCatalogo()
      ajustarQuantidadesAoCatalogo()
    }
  }
  finally {
    enviandoReserva.value = false
  }
}

async function tentarCatalogoNovamente(): Promise<void> {
  if (repetindoCatalogo.value) {
    return
  }

  repetindoCatalogo.value = true

  try {
    await atualizarCatalogo()
  }
  finally {
    repetindoCatalogo.value = false
  }
}

async function atualizarReservaPeloServidor(idReserva: string): Promise<void> {
  reserva.value = await $fetch<Reserva>(
    `/api/reservas/${encodeURIComponent(idReserva)}`,
    { retry: 0 },
  )
  await atualizarCatalogo()
  ajustarQuantidadesAoCatalogo()
}

async function confirmarReserva(): Promise<void> {
  if (!podeConfirmar.value || reserva.value === null) {
    return
  }

  const idReserva = reserva.value.id
  confirmandoReserva.value = true
  mensagemErro.value = ''

  try {
    pedido.value = await $fetch<Pedido>(
      `/api/reservas/${encodeURIComponent(idReserva)}/confirmar`,
      {
        method: 'POST',
        retry: 0,
      },
    )
    await atualizarReservaPeloServidor(idReserva)
  }
  catch (erro: unknown) {
    const erroApi = lerErroApi(erro)

    if (erroApi.status === 410) {
      await atualizarReservaPeloServidor(idReserva)
      mensagemErro.value = 'A reserva expirou antes da confirmação. O estoque foi atualizado.'
    }
    else {
      mensagemErro.value = erroApi.resposta?.erro.mensagem
        ?? 'Não foi possível confirmar a reserva.'
    }
  }
  finally {
    confirmandoReserva.value = false
  }
}

async function atualizarStatusPedido(): Promise<void> {
  if (pedido.value === null || atualizandoPedido.value) {
    return
  }

  atualizandoPedido.value = true
  mensagemErro.value = ''

  try {
    pedido.value = await $fetch<Pedido>(
      `/api/pedidos/${encodeURIComponent(pedido.value.id)}`,
      { retry: 0 },
    )
  }
  catch (erro: unknown) {
    const erroApi = lerErroApi(erro)
    mensagemErro.value = erroApi.resposta?.erro.mensagem
      ?? 'Não foi possível atualizar o pedido.'
  }
  finally {
    atualizandoPedido.value = false
  }
}
</script>

<template>
  <UApp>
    <main class="pagina-inicial">
      <UContainer class="pagina-inicial__container">
        <header class="pagina-inicial__cabecalho">
          <UBadge
            class="pagina-inicial__status"
            color="primary"
            variant="soft"
          >
            Catálogo
          </UBadge>
          <h1 class="pagina-inicial__titulo">
            {{ titulo }}
          </h1>
          <p class="pagina-inicial__descricao">
            Escolha entre os livros disponíveis nesta edição.
          </p>
        </header>

        <UAlert
          v-if="statusCatalogo === 'pending' && livros.length === 0"
          class="pagina-inicial__carregando"
          color="neutral"
          description="Buscando os livros disponíveis."
          title="Carregando catálogo"
          variant="soft"
        />

        <div
          v-else-if="erroCatalogo && livros.length === 0"
          class="pagina-inicial__erro"
        >
          <UAlert
            class="pagina-inicial__erro-alerta"
            color="error"
            description="Não foi possível carregar o catálogo agora."
            title="Catálogo indisponível"
            variant="soft"
          />
          <UButton
            class="pagina-inicial__erro-botao"
            color="neutral"
            :disabled="repetindoCatalogo"
            :loading="repetindoCatalogo"
            variant="soft"
            @click="tentarCatalogoNovamente"
          >
            Tentar novamente
          </UButton>
        </div>

        <section
          v-else
          class="pagina-inicial__catalogo"
          aria-label="Livros disponíveis"
        >
          <UCard
            v-for="livro in livros"
            :key="livro.sku"
            class="livro-card"
          >
            <template #header>
              <UBadge
                class="livro-card__sku"
                color="neutral"
                variant="soft"
              >
                {{ livro.sku }}
              </UBadge>
            </template>

            <h2 class="livro-card__titulo">
              {{ livro.titulo }}
            </h2>
            <p class="livro-card__preco">
              {{ formatarCentavos(livro.preco_centavos) }}
            </p>

            <template #footer>
              <div class="livro-card__rodape">
                <p class="livro-card__disponibilidade">
                  {{ livro.disponivel }}
                  {{ livro.disponivel === 1 ? 'disponível' : 'disponíveis' }}
                </p>
                <label
                  class="livro-card__quantidade-label"
                  :for="`quantidade-${livro.sku}`"
                >
                  Quantidade
                </label>
                <UInput
                  :id="`quantidade-${livro.sku}`"
                  class="livro-card__quantidade"
                  :disabled="livro.disponivel === 0 || enviandoReserva || !selecaoLiberada"
                  :max="maximoSelecionavel(livro)"
                  min="0"
                  :model-value="quantidades[livro.sku] ?? 0"
                  type="number"
                  @update:model-value="definirQuantidade(livro, $event)"
                />
              </div>
            </template>
          </UCard>
        </section>

        <form
          v-if="!erroCatalogo || livros.length > 0"
          class="reserva-form"
          @submit.prevent="criarReserva"
        >
          <UFormField
            class="reserva-form__campo"
            label="Identificação do cliente"
            name="cliente-id"
          >
            <UInput
              v-model="clienteId"
              class="reserva-form__cliente"
              :disabled="enviandoReserva || !selecaoLiberada"
              placeholder="cli_demo"
            />
          </UFormField>

          <UButton
            class="reserva-form__botao"
            :disabled="!podeReservar"
            :loading="enviandoReserva"
            type="submit"
          >
            Criar reserva
          </UButton>
        </form>

        <UAlert
          v-if="mensagemErro"
          class="pagina-inicial__retorno"
          color="error"
          :description="mensagemErro"
          title="A operação não pôde ser concluída"
          variant="soft"
        />

        <UCard
          v-if="reserva"
          class="reserva-card"
        >
          <template #header>
            <div class="reserva-card__cabecalho">
              <h2 class="reserva-card__titulo">
                Reserva
              </h2>
              <UBadge
                class="reserva-card__status"
                :color="reserva.status === 'ativa' ? 'success' : 'neutral'"
                variant="soft"
              >
                {{ reserva.status }}
              </UBadge>
            </div>
          </template>

          <dl class="reserva-card__dados">
            <div class="reserva-card__dado">
              <dt class="reserva-card__rotulo">
                Identificador
              </dt>
              <dd class="reserva-card__valor">
                {{ reserva.id }}
              </dd>
            </div>
            <div class="reserva-card__dado">
              <dt class="reserva-card__rotulo">
                Cliente
              </dt>
              <dd class="reserva-card__valor">
                {{ reserva.cliente_id }}
              </dd>
            </div>
            <div class="reserva-card__dado">
              <dt class="reserva-card__rotulo">
                Expira em
              </dt>
              <dd class="reserva-card__valor">
                <time :datetime="reserva.expira_em">
                  {{ reserva.expira_em }}
                </time>
              </dd>
            </div>
          </dl>

          <ul class="reserva-card__itens">
            <li
              v-for="item in reserva.itens"
              :key="item.sku"
              class="reserva-card__item"
            >
              <span class="reserva-card__item-sku">{{ item.sku }}</span>
              <span class="reserva-card__item-quantidade">
                {{ item.quantidade }} × {{ formatarCentavos(item.preco_centavos) }}
              </span>
            </li>
          </ul>

          <template #footer>
            <div class="reserva-card__acoes">
              <div
                v-if="reserva.status === 'ativa'"
                class="reserva-card__prazo"
              >
                <span class="reserva-card__prazo-label">Tempo restante</span>
                <strong
                  class="reserva-card__contador"
                  aria-live="polite"
                >
                  {{ contadorReserva }}
                </strong>
                <span
                  v-if="consultandoReserva"
                  class="reserva-card__consulta"
                >
                  Verificando estado no servidor…
                </span>
              </div>
              <p
                v-else-if="reserva.status === 'confirmada'"
                class="reserva-card__confirmada"
              >
                Esta reserva já gerou um pedido.
              </p>
              <p
                v-else
                class="reserva-card__expirada"
              >
                Prazo encerrado. Você pode iniciar uma nova seleção.
              </p>

              <UButton
                v-if="reserva.status === 'ativa'"
                class="reserva-card__confirmar"
                :disabled="!podeConfirmar"
                :loading="confirmandoReserva"
                @click="confirmarReserva"
              >
                Confirmar reserva
              </UButton>
            </div>
          </template>
        </UCard>

        <UCard
          v-if="pedido"
          class="pedido-card"
        >
          <template #header>
            <div class="pedido-card__cabecalho">
              <div class="pedido-card__identificacao">
                <h2 class="pedido-card__titulo">
                  Pedido
                </h2>
                <p class="pedido-card__id">
                  {{ pedido.id }}
                </p>
              </div>
              <UBadge
                class="pedido-card__status"
                :color="pedido.status === 'pago' ? 'success' : pedido.status === 'cancelado' ? 'error' : 'warning'"
                variant="soft"
              >
                {{ pedido.status.replace('_', ' ') }}
              </UBadge>
            </div>
          </template>

          <div class="pedido-card__tabela-container">
            <table class="pedido-card__tabela">
              <thead class="pedido-card__tabela-cabecalho">
                <tr class="pedido-card__linha-cabecalho">
                  <th class="pedido-card__celula-cabecalho">SKU</th>
                  <th class="pedido-card__celula-cabecalho">Qtd.</th>
                  <th class="pedido-card__celula-cabecalho">Preço</th>
                  <th class="pedido-card__celula-cabecalho">Valor</th>
                  <th class="pedido-card__celula-cabecalho">Desconto</th>
                  <th class="pedido-card__celula-cabecalho">Líquido</th>
                </tr>
              </thead>
              <tbody class="pedido-card__tabela-corpo">
                <tr
                  v-for="linha in pedido.linhas"
                  :key="linha.sku"
                  class="pedido-card__linha"
                >
                  <td class="pedido-card__celula pedido-card__celula--sku">
                    {{ linha.sku }}
                  </td>
                  <td class="pedido-card__celula">
                    {{ linha.quantidade }}
                  </td>
                  <td class="pedido-card__celula">
                    {{ formatarCentavos(linha.preco_centavos) }}
                  </td>
                  <td class="pedido-card__celula">
                    {{ formatarCentavos(linha.valor_centavos) }}
                  </td>
                  <td class="pedido-card__celula">
                    {{ formatarCentavos(linha.desconto_centavos) }}
                  </td>
                  <td class="pedido-card__celula">
                    {{ formatarCentavos(linha.liquido_centavos) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <dl class="pedido-card__totais">
            <div class="pedido-card__total-linha">
              <dt class="pedido-card__total-rotulo">Subtotal</dt>
              <dd class="pedido-card__total-valor">
                {{ formatarCentavos(pedido.subtotal_centavos) }}
              </dd>
            </div>
            <div class="pedido-card__total-linha">
              <dt class="pedido-card__total-rotulo">Desconto</dt>
              <dd class="pedido-card__total-valor">
                {{ formatarCentavos(pedido.desconto_centavos) }}
              </dd>
            </div>
            <div class="pedido-card__total-linha pedido-card__total-linha--destaque">
              <dt class="pedido-card__total-rotulo">Total</dt>
              <dd class="pedido-card__total-valor">
                {{ formatarCentavos(pedido.total_centavos) }}
              </dd>
            </div>
            <div
              v-if="pedido.pago_em"
              class="pedido-card__total-linha"
            >
              <dt class="pedido-card__total-rotulo">Pago em</dt>
              <dd class="pedido-card__total-valor">
                <time :datetime="pedido.pago_em">{{ pedido.pago_em }}</time>
              </dd>
            </div>
          </dl>

          <template #footer>
            <UButton
              class="pedido-card__atualizar"
              color="neutral"
              :disabled="atualizandoPedido"
              :loading="atualizandoPedido"
              variant="soft"
              @click="atualizarStatusPedido"
            >
              Atualizar status
            </UButton>
          </template>
        </UCard>
      </UContainer>
    </main>
  </UApp>
</template>

<style scoped lang="scss">
.pagina-inicial {
  background: $cor-fundo;
  min-height: 100vh;
  padding-block: $espaco-xl;

  &__container {
    width: 100%;

    @include breakpoint(md) {
      max-width: $largura-conteudo;
    }
  }

  &__cabecalho {
    margin-bottom: $espaco-xl;
  }

  &__status {
    font-weight: 600;
  }

  &__titulo {
    color: $cor-texto;
    font-size: $fonte-titulo;
    font-weight: 700;
    line-height: 1.15;
  }

  &__descricao {
    color: $cor-texto-suave;
    margin-top: $espaco-sm;
  }

  &__carregando,
  &__erro {
    border-radius: $raio-lg;
  }

  &__erro {
    display: grid;
    gap: $espaco-sm;
    justify-items: start;
  }

  &__erro-alerta {
    width: 100%;
  }

  &__erro-botao {
    justify-content: center;
  }

  &__catalogo {
    display: grid;
    gap: $espaco-md;

    @include breakpoint(sm) {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    @include breakpoint(lg) {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
  }

  &__retorno {
    margin-top: $espaco-md;
  }
}

.livro-card {
  border-radius: $raio-lg;

  &__sku {
    font-family: monospace;
  }

  &__titulo {
    color: $cor-texto;
    font-size: $fonte-subtitulo;
    font-weight: 700;
    line-height: 1.3;
  }

  &__preco {
    color: $cor-destaque;
    font-size: $fonte-preco;
    font-weight: 700;
    margin-top: $espaco-md;
  }

  &__disponibilidade {
    color: $cor-texto-suave;
    font-size: $fonte-pequena;
  }

  &__rodape {
    display: grid;
    gap: $espaco-xs;
  }

  &__quantidade-label {
    color: $cor-texto;
    font-size: $fonte-pequena;
    font-weight: 600;
  }

  &__quantidade {
    width: 6rem;
  }
}

.reserva-form {
  align-items: end;
  background: $cor-superficie;
  border-radius: $raio-lg;
  display: grid;
  gap: $espaco-md;
  margin-top: $espaco-xl;
  padding: $espaco-md;

  @include breakpoint(sm) {
    grid-template-columns: minmax(0, 1fr) auto;
  }

  &__campo {
    min-width: 0;
  }

  &__cliente {
    width: 100%;
  }

  &__botao {
    justify-content: center;
  }
}

.reserva-card {
  border-radius: $raio-lg;
  margin-top: $espaco-md;

  &__cabecalho {
    align-items: center;
    display: flex;
    justify-content: space-between;
  }

  &__titulo {
    color: $cor-texto;
    font-size: $fonte-subtitulo;
    font-weight: 700;
  }

  &__status {
    text-transform: capitalize;
  }

  &__dados {
    display: grid;
    gap: $espaco-sm;
  }

  &__dado {
    min-width: 0;
  }

  &__rotulo {
    color: $cor-texto-suave;
    font-size: $fonte-pequena;
  }

  &__valor {
    color: $cor-texto;
    overflow-wrap: anywhere;
  }

  &__itens {
    display: grid;
    gap: $espaco-xs;
    list-style: none;
    margin-top: $espaco-md;
    padding: 0;
  }

  &__item {
    display: flex;
    gap: $espaco-sm;
    justify-content: space-between;
  }

  &__item-sku {
    color: $cor-texto;
    font-family: monospace;
  }

  &__item-quantidade {
    color: $cor-texto-suave;
  }

  &__prazo {
    align-items: baseline;
    display: flex;
    flex-wrap: wrap;
    gap: $espaco-sm;
  }

  &__acoes {
    align-items: center;
    display: flex;
    flex-wrap: wrap;
    gap: $espaco-md;
    justify-content: space-between;
  }

  &__prazo-label {
    color: $cor-texto-suave;
  }

  &__contador {
    color: $cor-destaque;
    font-size: $fonte-preco;
    font-variant-numeric: tabular-nums;
  }

  &__consulta {
    color: $cor-texto-suave;
    font-size: $fonte-pequena;
  }

  &__confirmada,
  &__expirada {
    color: $cor-texto-suave;
  }

  &__confirmar {
    justify-content: center;
  }
}

.pedido-card {
  border-radius: $raio-lg;
  margin-top: $espaco-md;

  &__cabecalho {
    align-items: flex-start;
    display: flex;
    gap: $espaco-md;
    justify-content: space-between;
  }

  &__identificacao {
    min-width: 0;
  }

  &__titulo {
    color: $cor-texto;
    font-size: $fonte-subtitulo;
    font-weight: 700;
  }

  &__id {
    color: $cor-texto-suave;
    font-family: monospace;
    font-size: $fonte-pequena;
    overflow-wrap: anywhere;
  }

  &__status {
    flex: 0 0 auto;
    text-transform: capitalize;
  }

  &__tabela-container {
    overflow-x: auto;
  }

  &__tabela {
    border-collapse: collapse;
    color: $cor-texto;
    min-width: 44rem;
    width: 100%;
  }

  &__celula-cabecalho,
  &__celula {
    border-bottom: 1px solid $cor-borda;
    padding: $espaco-sm;
    text-align: right;
  }

  &__celula-cabecalho {
    color: $cor-texto-suave;
    font-size: $fonte-pequena;
    font-weight: 600;
  }

  &__celula-cabecalho:first-child,
  &__celula--sku {
    text-align: left;
  }

  &__celula--sku {
    font-family: monospace;
  }

  &__totais {
    display: grid;
    gap: $espaco-xs;
    margin-left: auto;
    margin-top: $espaco-md;
    max-width: 22rem;
  }

  &__total-linha {
    display: flex;
    gap: $espaco-md;
    justify-content: space-between;
  }

  &__total-linha--destaque {
    color: $cor-destaque;
    font-size: $fonte-preco;
    font-weight: 700;
  }

  &__total-rotulo {
    color: inherit;
  }

  &__total-valor {
    color: inherit;
    font-variant-numeric: tabular-nums;
    text-align: right;
  }

  &__atualizar {
    justify-content: center;
  }
}
</style>
