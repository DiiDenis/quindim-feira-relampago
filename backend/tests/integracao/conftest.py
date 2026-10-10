import os
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.mongo import ConexaoMongo, criar_conexao_mongo


@pytest.fixture(scope="session")
def url_api() -> str:
    return os.environ.get("API_URL", "http://api:8000").rstrip("/")


@pytest.fixture(scope="session")
def cliente_http(url_api: str) -> Iterator[httpx.Client]:
    cliente = httpx.Client(base_url=url_api, timeout=5.0)
    try:
        resposta = cliente.get("/healthz")
        resposta.raise_for_status()
    except httpx.HTTPError as erro:
        cliente.close()
        pytest.fail(
            f"API indisponível para os testes em {url_api}: {type(erro).__name__}.",
            pytrace=False,
        )

    yield cliente
    cliente.close()


@pytest.fixture(scope="session")
def conexao_mongo() -> Iterator[ConexaoMongo]:
    uri = os.environ.get("MONGO_URI", "mongodb://mongo:27017")
    nome_banco = os.environ.get("MONGO_BANCO", "quindim")
    conexao = criar_conexao_mongo(uri, nome_banco)
    try:
        conexao.cliente.admin.command("ping")
    except PyMongoError as erro:
        conexao.cliente.close()
        pytest.fail(
            f"MongoDB indisponível para os testes: {type(erro).__name__}.",
            pytrace=False,
        )

    yield conexao
    conexao.cliente.close()


@pytest.fixture(scope="session")
def banco_mongo(conexao_mongo: ConexaoMongo) -> Database[dict[str, Any]]:
    return conexao_mongo.banco


@pytest.fixture
def documento_feira(banco_mongo: Database[dict[str, Any]]) -> dict[str, Any]:
    documento = banco_mongo["feiras"].find_one({"_id": "principal"})
    if documento is None:
        pytest.fail("Seed real ausente: feiras/principal não foi encontrado.", pytrace=False)
    return documento


@pytest.fixture(scope="session")
def token_admin() -> str:
    token = os.environ.get("ADMIN_TOKEN", "").strip()
    if not token:
        pytest.fail("ADMIN_TOKEN não foi definido para os testes.", pytrace=False)
    return token
