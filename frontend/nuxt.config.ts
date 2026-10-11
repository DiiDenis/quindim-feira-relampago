export default defineNuxtConfig({
  modules: ['@nuxt/ui'],
  css: ['~/assets/css/main.css'],
  runtimeConfig: {
    apiBase: '',
  },
  ssr: true,
  vite: {
    css: {
      preprocessorOptions: {
        scss: {
          additionalData: [
            '@use "~/assets/scss/tokens" as *;',
            '@use "~/assets/scss/breakpoints" as *;',
          ].join('\n'),
        },
      },
    },
  },
})
