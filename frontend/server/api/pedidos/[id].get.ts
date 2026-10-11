import { defineEventHandler, getRouterParam } from 'h3'

import { consultarPedido } from '../../services/feira'

export default defineEventHandler((evento) => {
  const idPedido = getRouterParam(evento, 'id') ?? ''
  return consultarPedido(evento, idPedido)
})
