import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import type { Livro } from '../types/api.ts'
import { construirItensReserva } from './reserva.ts'

const livros: Livro[] = [
  {
    sku: 'QND-001',
    titulo: 'Livro um',
    preco_centavos: 3990,
    estoque: 10,
    disponivel: 10,
  },
  {
    sku: 'QND-002',
    titulo: 'Livro dois',
    preco_centavos: 2990,
    estoque: 10,
    disponivel: 10,
  },
]

describe('construirItensReserva', () => {
  it('envia somente SKU e quantidade positiva na ordem do catálogo', () => {
    assert.deepEqual(
      construirItensReserva(livros, { 'QND-001': 2, 'QND-002': 0 }),
      [{ sku: 'QND-001', quantidade: 2 }],
    )
  })

  it('devolve lista vazia quando não há seleção', () => {
    assert.deepEqual(construirItensReserva(livros, {}), [])
  })
})
