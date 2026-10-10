"""Operações administrativas protegidas da feira."""

from hmac import compare_digest
from typing import cast

from flask import Blueprint, Response, current_app, request

from .erros import ErroNegocio
from .mongo import ConexaoMongo
from .seed import COLECAO_FEIRAS, ID_FEIRA, criar_estado_inicial

bp = Blueprint("admin", __name__, url_prefix="/v1/admin")


@bp.post("/reset")
def resetar_feira() -> Response:
    """Restaura todo o agregado com uma geração nova em uma única escrita."""
    token_recebido = request.headers.get("X-Admin-Token")
    token_esperado = cast(str, current_app.config["ADMIN_TOKEN"])
    if token_recebido is None or not compare_digest(
        token_recebido.encode(), token_esperado.encode()
    ):
        raise ErroNegocio(
            401,
            "nao_autorizado",
            "Token administrativo inválido.",
        )

    conexao = cast(ConexaoMongo, current_app.extensions["mongo"])
    conexao.banco[COLECAO_FEIRAS].replace_one(
        {"_id": ID_FEIRA},
        criar_estado_inicial(),
        upsert=True,
    )
    return Response(status=204)
