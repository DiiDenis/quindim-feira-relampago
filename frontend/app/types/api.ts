export interface Livro {
  sku: string
  titulo: string
  preco_centavos: number
  estoque: number
  disponivel: number
}

export interface RespostaLivros {
  livros: Livro[]
}

export interface ItemReservaEntrada {
  sku: string
  quantidade: number
}

export interface ItemReserva extends ItemReservaEntrada {
  preco_centavos: number
}

export interface Reserva {
  id: string
  cliente_id: string
  status: 'ativa' | 'confirmada' | 'expirada'
  itens: ItemReserva[]
  criado_em: string
  expira_em: string
}

export interface RespostaErro {
  erro: {
    codigo: string
    mensagem: string
    detalhes: Record<string, unknown>
  }
}

export interface LinhaPedido {
  sku: string
  quantidade: number
  preco_centavos: number
  valor_centavos: number
  desconto_centavos: number
  liquido_centavos: number
}

export interface Pedido {
  id: string
  reserva_id: string
  cliente_id: string
  status: 'aguardando_pagamento' | 'pago' | 'cancelado'
  linhas: LinhaPedido[]
  subtotal_centavos: number
  desconto_centavos: number
  total_centavos: number
  criado_em: string
  pago_em: string | null
}
