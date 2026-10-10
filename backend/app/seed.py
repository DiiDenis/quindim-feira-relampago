"""Catálogo fixo e comando idempotente de inicialização da feira."""

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from .config import Configuracao
from .mongo import criar_conexao_mongo

ID_FEIRA = "principal"
COLECAO_FEIRAS = "feiras"


@dataclass(frozen=True, slots=True)
class LivroSeed:
    """Definição imutável de um livro do catálogo inicial."""

    sku: str
    titulo: str
    preco_centavos: int
    estoque: int


CATALOGO_INICIAL = (
    LivroSeed("QND-001", "O Jardim de Dentro", 3990, 10),
    LivroSeed("QND-002", "Bicho-Palavra", 2990, 10),
    LivroSeed("QND-003", "A Casa que Anda", 1995, 10),
    LivroSeed("QND-004", "Kit Primeira Leitura", 8990, 3),
    LivroSeed("QND-005", "A Lua no Bolso — edição numerada", 12900, 1),
)


def criar_estado_inicial() -> dict[str, Any]:
    """Cria um agregado novo, sem compartilhar estruturas mutáveis."""
    return {
        "_id": ID_FEIRA,
        "geracao": str(uuid4()),
        "versao": 0,
        "livros": [
            {
                "sku": livro.sku,
                "titulo": livro.titulo,
                "preco_centavos": livro.preco_centavos,
                "estoque": livro.estoque,
                "disponivel": livro.estoque,
            }
            for livro in CATALOGO_INICIAL
        ],
        "reservas": [],
        "pedidos": [],
        "eventos": [],
    }


def aplicar_seed(banco: Database[dict[str, Any]]) -> bool:
    """Insere o agregado somente quando ele ainda não existe."""
    feiras = banco[COLECAO_FEIRAS]
    try:
        resultado = feiras.update_one(
            {"_id": ID_FEIRA},
            {"$setOnInsert": criar_estado_inicial()},
            upsert=True,
        )
    except DuplicateKeyError:
        if feiras.find_one({"_id": ID_FEIRA}, {"_id": 1}) is None:
            raise
        return False
    return resultado.upserted_id is not None


def main() -> None:
    """Aplica o seed com cliente próprio e fecha o pool ao terminar."""
    configuracao = Configuracao.do_ambiente()
    conexao = criar_conexao_mongo(configuracao.mongo_uri, configuracao.mongo_banco)
    try:
        criado = aplicar_seed(conexao.banco)
    finally:
        conexao.cliente.close()

    if criado:
        print("Catálogo inicial criado.")
    else:
        print("Catálogo existente preservado.")


if __name__ == "__main__":
    main()
