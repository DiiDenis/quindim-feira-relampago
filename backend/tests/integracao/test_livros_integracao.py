from typing import Any

import httpx
import pytest
from pymongo.database import Database

pytestmark = [pytest.mark.integracao, pytest.mark.negocio]

LIVROS_ESPERADOS = [
    {
        "sku": "QND-001",
        "titulo": "O Jardim de Dentro",
        "preco_centavos": 3990,
        "estoque": 10,
        "disponivel": 10,
    },
    {
        "sku": "QND-002",
        "titulo": "Bicho-Palavra",
        "preco_centavos": 2990,
        "estoque": 10,
        "disponivel": 10,
    },
    {
        "sku": "QND-003",
        "titulo": "A Casa que Anda",
        "preco_centavos": 1995,
        "estoque": 10,
        "disponivel": 10,
    },
    {
        "sku": "QND-004",
        "titulo": "Kit Primeira Leitura",
        "preco_centavos": 8990,
        "estoque": 3,
        "disponivel": 3,
    },
    {
        "sku": "QND-005",
        "titulo": "A Lua no Bolso — edição numerada",
        "preco_centavos": 12900,
        "estoque": 1,
        "disponivel": 1,
    },
]


def test_lista_catalogo_com_contrato_publico_exato(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
) -> None:
    estado_antes = banco_mongo["feiras"].find_one({"_id": "principal"})
    assert estado_antes is not None

    resposta = cliente_http.get("/v1/livros")

    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("application/json")
    assert resposta.json() == {"livros": LIVROS_ESPERADOS}
    for livro in resposta.json()["livros"]:
        assert set(livro) == {
            "sku",
            "titulo",
            "preco_centavos",
            "estoque",
            "disponivel",
        }
        assert type(livro["preco_centavos"]) is int
        assert type(livro["estoque"]) is int
        assert type(livro["disponivel"]) is int

    estado_depois = banco_mongo["feiras"].find_one({"_id": "principal"})
    assert estado_depois is not None
    assert estado_depois["geracao"] == estado_antes["geracao"]
    assert estado_depois["versao"] == estado_antes["versao"] + 1
