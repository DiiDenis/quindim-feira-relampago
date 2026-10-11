import type { RespostaErro } from '../types/api.ts'

interface ErroApiLido {
  status?: number
  resposta?: RespostaErro
}

function ehRegistro(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === 'object' && valor !== null
}

export function lerErroApi(erro: unknown): ErroApiLido {
  if (!ehRegistro(erro)) {
    return {}
  }

  const status = typeof erro.status === 'number'
    ? erro.status
    : typeof erro.statusCode === 'number'
      ? erro.statusCode
      : undefined
  const resultadoSemEnvelope: ErroApiLido = status === undefined
    ? {}
    : { status }

  if (!ehRegistro(erro.data) || !ehRegistro(erro.data.erro)) {
    return resultadoSemEnvelope
  }

  const detalhe = erro.data.erro

  if (
    typeof detalhe.codigo !== 'string'
    || typeof detalhe.mensagem !== 'string'
  ) {
    return resultadoSemEnvelope
  }

  return {
    status,
    resposta: {
      erro: {
        codigo: detalhe.codigo,
        mensagem: detalhe.mensagem,
        detalhes: ehRegistro(detalhe.detalhes) ? detalhe.detalhes : {},
      },
    },
  }
}
