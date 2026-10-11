import type { ItemReservaEntrada, Livro } from '../types/api.ts'

export function construirItensReserva(
  livros: Livro[],
  quantidades: Record<string, number>,
): ItemReservaEntrada[] {
  return livros.flatMap((livro) => {
    const quantidade = quantidades[livro.sku] ?? 0

    return quantidade > 0
      ? [{ sku: livro.sku, quantidade }]
      : []
  })
}
