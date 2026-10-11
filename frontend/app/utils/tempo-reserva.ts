export function calcularSegundosRestantes(
  expiraEm: string,
  instanteAtualMs: number,
): number {
  const expiracaoMs = Date.parse(expiraEm)

  if (!Number.isFinite(expiracaoMs) || !Number.isFinite(instanteAtualMs)) {
    throw new TypeError('A expiração e o instante atual devem ser válidos.')
  }

  return Math.max(0, Math.ceil((expiracaoMs - instanteAtualMs) / 1000))
}

export function formatarDuracao(segundosTotais: number): string {
  if (!Number.isSafeInteger(segundosTotais) || segundosTotais < 0) {
    throw new TypeError('A duração deve ser um inteiro não negativo.')
  }

  const minutos = Math.floor(segundosTotais / 60)
  const segundos = segundosTotais % 60
  return `${minutos.toString().padStart(2, '0')}:${segundos.toString().padStart(2, '0')}`
}
