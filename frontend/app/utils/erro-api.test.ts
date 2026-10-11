import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { lerErroApi } from './erro-api.ts'

describe('lerErroApi', () => {
  it('extrai status e mensagem do envelope público', () => {
    assert.deepEqual(lerErroApi({
      status: 409,
      data: {
        erro: {
          codigo: 'estoque_insuficiente',
          mensagem: 'Estoque insuficiente.',
          detalhes: { skus: ['QND-001'] },
        },
      },
    }), {
      status: 409,
      resposta: {
        erro: {
          codigo: 'estoque_insuficiente',
          mensagem: 'Estoque insuficiente.',
          detalhes: { skus: ['QND-001'] },
        },
      },
    })
  })

  it('mantém desconhecido seguro quando não há envelope válido', () => {
    assert.deepEqual(lerErroApi(new Error('falha de rede')), {})
    assert.deepEqual(lerErroApi({ statusCode: 502, data: 'html' }), {
      status: 502,
    })
  })
})
