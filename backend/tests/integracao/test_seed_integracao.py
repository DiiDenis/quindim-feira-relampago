import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from app.mongo import criar_conexao_mongo
from app.seed import aplicar_seed

pytestmark = [
    pytest.mark.integracao,
    pytest.mark.skipif(
        os.environ.get("EXECUTAR_TESTES_INTEGRACAO") != "1",
        reason="requer MongoDB real e EXECUTAR_TESTES_INTEGRACAO=1",
    ),
]


def test_seed_repetido_preserva_estado_existente() -> None:
    nome_banco = f"quindim_teste_seed_{uuid4().hex}"
    conexao = criar_conexao_mongo(os.environ["MONGO_URI"], nome_banco)
    feiras = conexao.banco["feiras"]

    try:
        assert aplicar_seed(conexao.banco) is True
        estado_original = feiras.find_one({"_id": "principal"})
        assert aplicar_seed(conexao.banco) is False
        assert feiras.count_documents({}) == 1

        resultado = feiras.update_one(
            {"_id": "principal"},
            {"$set": {"livros.0.disponivel": 7}},
        )
        assert resultado.modified_count == 1
        assert aplicar_seed(conexao.banco) is False

        estado_preservado = feiras.find_one({"_id": "principal"})
        assert estado_original is not None
        assert estado_preservado is not None
        assert estado_preservado["geracao"] == estado_original["geracao"]
        assert estado_preservado["livros"][0]["disponivel"] == 7
        assert [
            (livro["titulo"], livro["preco_centavos"]) for livro in estado_preservado["livros"]
        ] == [
            ("O Jardim de Dentro", 3990),
            ("Bicho-Palavra", 2990),
            ("A Casa que Anda", 1995),
            ("Kit Primeira Leitura", 8990),
            ("A Lua no Bolso — edição numerada", 12900),
        ]
    finally:
        conexao.cliente.drop_database(nome_banco)
        conexao.cliente.close()


def test_seed_concorrente_cria_um_unico_documento() -> None:
    nome_banco = f"quindim_teste_seed_corrida_{uuid4().hex}"
    conexao = criar_conexao_mongo(os.environ["MONGO_URI"], nome_banco)

    try:
        with ThreadPoolExecutor(max_workers=8) as executor:
            resultados = list(executor.map(lambda _: aplicar_seed(conexao.banco), range(8)))

        assert resultados.count(True) == 1
        assert resultados.count(False) == 7
        assert conexao.banco["feiras"].count_documents({}) == 1
    finally:
        conexao.cliente.drop_database(nome_banco)
        conexao.cliente.close()
