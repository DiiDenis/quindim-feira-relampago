<script setup lang="ts">
import type { RespostaLivros } from '~/types/api'
import { formatarCentavos } from '~/utils/moeda'

const titulo = 'Feira Relâmpago'

const {
  data: respostaCatalogo,
  error: erroCatalogo,
} = await useFetch<RespostaLivros>('/api/livros', {
  key: 'catalogo-livros',
})

const livros = computed(() => respostaCatalogo.value?.livros ?? [])
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
              <p class="livro-card__disponibilidade">
                {{ livro.disponivel }}
                {{ livro.disponivel === 1 ? 'disponível' : 'disponíveis' }}
              </p>
            </template>
          </UCard>
        </section>
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
}
</style>
