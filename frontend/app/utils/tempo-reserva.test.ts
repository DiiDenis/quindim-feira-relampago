import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
  calcularSegundosRestantes,
  formatarDuracao,
} from './tempo-reserva.ts'

describe('contador de reserva', () => {
  it('recalcula pelo prazo absoluto sem acumular atraso dos ticks', () => {
    const expiraEm = '2026-10-10T12:15:00Z'

    assert.equal(
      calcularSegundosRestantes(expiraEm, Date.parse('2026-10-10T12:00:00Z')),
      900,
    )
    assert.equal(
      calcularSegundosRestantes(expiraEm, Date.parse('2026-10-10T12:14:59.250Z')),
      1,
    )
    assert.equal(
      calcularSegundosRestantes(expiraEm, Date.parse(expiraEm)),
      0,
    )
  })

  it('formata minutos e segundos', () => {
    assert.equal(formatarDuracao(900), '15:00')
    assert.equal(formatarDuracao(5), '00:05')
    assert.equal(formatarDuracao(0), '00:00')
  })
})
