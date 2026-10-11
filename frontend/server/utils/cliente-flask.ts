import { useRuntimeConfig } from '#imports'
import { $fetch } from 'ofetch'
import {
  setResponseHeader,
  setResponseStatus,
  type H3Event,
} from 'h3'

type MetodoHttp = 'GET' | 'POST'

export type CorpoJson = Record<string, unknown>

interface OpcoesRequisicao {
  metodo: MetodoHttp
  corpo?: CorpoJson
}

interface ErroPublico {
  erro: {
    codigo: string
    mensagem: string
    detalhes: Record<string, never>
  }
}

const erroIndisponibilidade: ErroPublico = {
  erro: {
    codigo: 'servico_indisponivel',
    mensagem: 'Não foi possível comunicar com o serviço da feira.',
    detalhes: {},
  },
}

export async function requisitarFlask(
  evento: H3Event,
  caminho: string,
  opcoes: OpcoesRequisicao,
): Promise<unknown> {
  const configuracao = useRuntimeConfig(evento)

  setResponseHeader(evento, 'cache-control', 'no-store')
  setResponseHeader(evento, 'content-type', 'application/json; charset=utf-8')

  try {
    const resposta = await $fetch.raw(caminho, {
      baseURL: configuracao.apiBase,
      method: opcoes.metodo,
      body: opcoes.corpo,
      ignoreResponseError: true,
      retry: 0,
    })

    setResponseStatus(evento, resposta.status)
    return resposta._data
  }
  catch {
    setResponseStatus(evento, 502)
    return erroIndisponibilidade
  }
}
