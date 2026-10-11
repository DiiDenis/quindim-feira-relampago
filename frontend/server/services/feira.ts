import type { H3Event } from 'h3'

import {
  requisitarFlask,
  type CorpoJson,
} from '../utils/cliente-flask'

function segmentoSeguro(id: string): string {
  return encodeURIComponent(id)
}

export function listarLivros(evento: H3Event): Promise<unknown> {
  return requisitarFlask(evento, '/v1/livros', { metodo: 'GET' })
}

export function criarReserva(
  evento: H3Event,
  corpo: CorpoJson,
): Promise<unknown> {
  return requisitarFlask(evento, '/v1/reservas', {
    metodo: 'POST',
    corpo,
  })
}

export function consultarReserva(
  evento: H3Event,
  idReserva: string,
): Promise<unknown> {
  return requisitarFlask(
    evento,
    `/v1/reservas/${segmentoSeguro(idReserva)}`,
    { metodo: 'GET' },
  )
}

export function confirmarReserva(
  evento: H3Event,
  idReserva: string,
): Promise<unknown> {
  return requisitarFlask(
    evento,
    `/v1/reservas/${segmentoSeguro(idReserva)}/confirmar`,
    { metodo: 'POST' },
  )
}

export function consultarPedido(
  evento: H3Event,
  idPedido: string,
): Promise<unknown> {
  return requisitarFlask(
    evento,
    `/v1/pedidos/${segmentoSeguro(idPedido)}`,
    { metodo: 'GET' },
  )
}
