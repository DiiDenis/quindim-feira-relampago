"""Conexão síncrona com o MongoDB mantida pela instância da aplicação."""

from dataclasses import dataclass
from datetime import UTC
from typing import Any

from pymongo import MongoClient
from pymongo.database import Database

TEMPO_SELECAO_SERVIDOR_MS = 2_000


@dataclass(slots=True)
class ConexaoMongo:
    """Cliente com pool e banco usados durante a vida do processo."""

    cliente: MongoClient[dict[str, Any]]
    banco: Database[dict[str, Any]]


def criar_conexao_mongo(uri: str, nome_banco: str) -> ConexaoMongo:
    """Cria um cliente lazy, com seleção finita e datas conscientes de UTC."""
    cliente: MongoClient[dict[str, Any]] = MongoClient(
        uri,
        connect=False,
        serverSelectionTimeoutMS=TEMPO_SELECAO_SERVIDOR_MS,
        tz_aware=True,
        tzinfo=UTC,
    )
    return ConexaoMongo(cliente=cliente, banco=cliente[nome_banco])
