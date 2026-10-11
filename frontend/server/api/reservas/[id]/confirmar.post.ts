import { defineEventHandler, getRouterParam } from 'h3'

import { confirmarReserva } from '../../../services/feira'

export default defineEventHandler((evento) => {
  const idReserva = getRouterParam(evento, 'id') ?? ''
  return confirmarReserva(evento, idReserva)
})
