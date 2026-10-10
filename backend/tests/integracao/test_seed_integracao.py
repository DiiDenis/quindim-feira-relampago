from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from app.mongo import ConexaoMongo
from app.seed import aplicar_seed

pytestmark = pytest.mark.integracao


def test_seed_repetido_preserva_estado_existente(conexao_mongo: ConexaoMongo) -> None:
    nome_banco = f"quindim_teste_seed_{uuid4().hex}"
    banco = conexao_mongo.cliente[nome_banco]
    feiras = banco["feiras"]

    try:
        assert aplicar_seed(banco) is True
        estado_original = feiras.find_one({"_id": "principal"})
        assert aplicar_seed(banco) is False
        assert feiras.count_documents({}) == 1

        resultado = feiras.update_one(
            {"_id": "principal"},
            {"$set": {"livros.0.disponivel": 7}},
        )
        assert resultado.modified_count == 1
        assert aplicar_seed(banco) is False

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
        conexao_mongo.cliente.drop_database(nome_banco)


def test_seed_concorrente_cria_um_unico_documento(conexao_mongo: ConexaoMongo) -> None:
    nome_banco = f"quindim_teste_seed_corrida_{uuid4().hex}"
    banco = conexao_mongo.cliente[nome_banco]

    try:
        with ThreadPoolExecutor(max_workers=8) as executor:
            resultados = list(executor.map(lambda _: aplicar_seed(banco), range(8)))

        assert resultados.count(True) == 1
        assert resultados.count(False) == 7
        assert banco["feiras"].count_documents({}) == 1
    finally:
        conexao_mongo.cliente.drop_database(nome_banco)
