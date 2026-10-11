<script setup lang="ts">
import type {
  Livro,
  Reserva,
  RespostaErro,
  RespostaLivros,
} from '~/types/api'
import { formatarCentavos } from '~/utils/moeda'
import { construirItensReserva } from '~/utils/reserva'

const titulo = 'Feira Relâmpago'

const {
  data: respostaCatalogo,
  error: erroCatalogo,
  refresh: atualizarCatalogo,
} = await useFetch<RespostaLivros>('/api/livros', {
  key: 'catalogo-livros',
})

const livros = computed(() => respostaCatalogo.value?.livros ?? [])
const clienteId = ref('cli_demo')
const quantidades = reactive<Record<string, number>>({})
const reserva = ref<Reserva | null>(null)
const enviandoReserva = ref(false)
const mensagemErro = ref('')

const itensSelecionados = computed(() => construirItensReserva(
  livros.value,
  quantidades,
))

const podeReservar = computed(() => (
  clienteId.value.trim().length > 0
  && itensSelecionados.value.length > 0
  && !enviandoReserva.value
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

function lerErroApi(erro: unknown): { status?: number, resposta?: RespostaErro } {
  if (typeof erro !== 'object' || erro === null) {
    return {}
  }

  const registro = erro as Record<string, unknown>
  const status = typeof registro.status === 'number'
    ? registro.status
    : undefined
  const resposta = registro.data

  if (typeof resposta !== 'object' || resposta === null || !('erro' in resposta)) {
    return { status }
  }

  return { status, resposta: resposta as RespostaErro }
}

async function criarReserva(): Promise<void> {
  if (!podeReservar.value) {
    return
  }

  enviandoReserva.value = true
  mensagemErro.value = ''

  try {
    reserva.value = await $fetch<Reserva>('/api/reservas', {
      method: 'POST',
      body: {
        cliente_id: clienteId.value.trim(),
        itens: itensSelecionados.value,
      },
      retry: 0,
    })

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
          v-if="erroCatalogo"
          class="pagina-inicial__erro"
          color="error"
          description="Não foi possível carregar o catálogo agora."
          title="Catálogo indisponível"
          variant="soft"
        />

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
                  :disabled="livro.disponivel === 0 || enviandoReserva"
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
              :disabled="enviandoReserva"
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
          title="Não foi possível reservar"
          variant="soft"
        />

        <UAlert
          v-if="reserva"
          class="pagina-inicial__retorno"
          color="success"
          :description="`Reserva ${reserva.id} criada para ${reserva.cliente_id}.`"
          title="Livros reservados"
          variant="soft"
        />
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

  &__erro {
    border-radius: $raio-lg;
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
</style>
