from uuid import UUID

from app.seed import criar_estado_inicial

CATALOGO_ESPERADO = [
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


def test_cria_estado_inicial_com_catalogo_exato() -> None:
    estado = criar_estado_inicial()

    assert estado["_id"] == "principal"
    assert UUID(estado["geracao"]).version == 4
    assert estado["versao"] == 0
    assert estado["livros"] == CATALOGO_ESPERADO
    assert estado["reservas"] == []
    assert estado["pedidos"] == []
    assert estado["eventos"] == []


def test_cria_estados_com_geracoes_e_listas_independentes() -> None:
    primeiro = criar_estado_inicial()
    segundo = criar_estado_inicial()

    primeiro["livros"][0]["disponivel"] = 0
    primeiro["reservas"].append({"id": "reserva-de-teste"})

    assert primeiro["geracao"] != segundo["geracao"]
    assert segundo["livros"] == CATALOGO_ESPERADO
    assert segundo["reservas"] == []
