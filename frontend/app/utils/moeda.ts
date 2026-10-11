export function formatarCentavos(valorCentavos: number): string {
  if (!Number.isSafeInteger(valorCentavos)) {
    throw new TypeError('O valor em centavos deve ser um inteiro seguro.')
  }

  const valor = BigInt(valorCentavos)
  const sinal = valor < 0n ? '-' : ''
  const valorAbsoluto = valor < 0n ? -valor : valor
  const reais = valorAbsoluto / 100n
  const centavos = valorAbsoluto % 100n

  return `R$ ${sinal}${reais.toLocaleString('pt-BR')},${centavos.toString().padStart(2, '0')}`
}
