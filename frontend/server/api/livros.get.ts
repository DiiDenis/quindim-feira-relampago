import { defineEventHandler } from 'h3'

import { listarLivros } from '../services/feira'

export default defineEventHandler(evento => listarLivros(evento))
