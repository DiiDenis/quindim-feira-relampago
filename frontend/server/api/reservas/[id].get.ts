import { defineEventHandler, getRouterParam } from 'h3'

import { consultarReserva } from '../../services/feira'

export default defineEventHandler((evento) => {
  const idReserva = getRouterParam(evento, 'id') ?? ''
  return consultarReserva(evento, idReserva)
})
