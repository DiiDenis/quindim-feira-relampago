import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { formatarCentavos } from './moeda.ts'

describe('formatarCentavos', () => {
  it('apresenta os valores do catálogo em reais', () => {
    assert.equal(formatarCentavos(3990), 'R$ 39,90')
    assert.equal(formatarCentavos(1995), 'R$ 19,95')
    assert.equal(formatarCentavos(12900), 'R$ 129,00')
    assert.equal(formatarCentavos(0), 'R$ 0,00')
  })

  it('rejeita valores que perderiam precisão', () => {
    assert.throws(
      () => formatarCentavos(Number.MAX_SAFE_INTEGER + 1),
      /inteiro seguro/,
    )
    assert.throws(() => formatarCentavos(19.95), /inteiro seguro/)
  })
})
