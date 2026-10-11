<script setup lang="ts">
const titulo = 'Feira Relâmpago'
</script>

<template>
  <UApp>
    <main class="pagina-inicial">
      <UContainer class="pagina-inicial__container">
        <UCard class="pagina-inicial__card">
          <template #header>
            <UBadge
              class="pagina-inicial__status"
              color="primary"
              variant="soft"
            >
              Ambiente preparado
            </UBadge>
          </template>

          <h1 class="pagina-inicial__titulo">
            {{ titulo }}
          </h1>
          <p class="pagina-inicial__descricao">
            A base Nuxt está pronta para receber o fluxo da feira.
          </p>
        </UCard>
      </UContainer>
    </main>
  </UApp>
</template>

<style scoped lang="scss">
.pagina-inicial {
  align-items: center;
  background: $cor-fundo;
  display: flex;
  min-height: 100vh;
  padding-block: $espaco-xl;

  &__container {
    width: 100%;

    @include breakpoint(md) {
      max-width: $largura-conteudo;
    }
  }

  &__card {
    border-radius: $raio-lg;
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
}
</style>
