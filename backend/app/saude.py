"""Endpoint de saúde da API e do MongoDB."""

from typing import Literal, cast

from flask import Blueprint, Response, current_app, jsonify
from pydantic import BaseModel
from pymongo.errors import PyMongoError

from .erros import criar_resposta_erro
from .mongo import ConexaoMongo

bp = Blueprint("saude", __name__)


class RespostaSaude(BaseModel):
    """Resposta pública quando todas as dependências estão acessíveis."""

    status: Literal["ok"]


@bp.get("/healthz")
def consultar_saude() -> tuple[Response, int] | Response:
    """Confirma a comunicação real com o MongoDB."""
    conexao = cast(ConexaoMongo, current_app.extensions["mongo"])
    try:
        conexao.cliente.admin.command("ping")
    except PyMongoError:
        return criar_resposta_erro(
            503,
            "servico_indisponivel",
            "Serviço temporariamente indisponível.",
        )

    resposta = RespostaSaude(status="ok")
    return jsonify(resposta.model_dump(mode="json"))
