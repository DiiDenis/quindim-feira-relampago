import { defineEventHandler, readBody } from 'h3'

import { criarReserva } from '../services/feira'
import type { CorpoJson } from '../utils/cliente-flask'

export default defineEventHandler(async (evento) => {
  const corpo = await readBody<CorpoJson>(evento)
  return criarReserva(evento, corpo)
})
