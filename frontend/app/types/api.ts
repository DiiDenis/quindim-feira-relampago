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
