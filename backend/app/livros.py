"""Consulta pública do catálogo de livros."""

from datetime import datetime
from typing import Any, cast

from flask import Blueprint, Response, current_app, jsonify
from pydantic import BaseModel, ConfigDict

from .banco import executar_com_cas
from .mongo import ConexaoMongo

bp = Blueprint("livros", __name__, url_prefix="/v1")

CAMPOS_PUBLICOS_LIVRO = (
    "sku",
    "titulo",
    "preco_centavos",
    "estoque",
    "disponivel",
)


class LivroSaida(BaseModel):
    """Livro no formato exposto pela API."""

    model_config = ConfigDict(extra="forbid", strict=True)

    sku: str
    titulo: str
    preco_centavos: int
    estoque: int
    disponivel: int


class RespostaLivros(BaseModel):
    """Envelope público da listagem do catálogo."""

    model_config = ConfigDict(extra="forbid", strict=True)

    livros: list[LivroSaida]


def criar_resposta_livros(
    estado: dict[str, Any],
    _agora: datetime,
) -> RespostaLivros:
    """Seleciona campos públicos e valida o DTO ainda dentro da tentativa CAS."""
    livros_publicos = [
        {campo: livro[campo] for campo in CAMPOS_PUBLICOS_LIVRO} for livro in estado["livros"]
    ]
    return RespostaLivros.model_validate({"livros": livros_publicos})


@bp.get("/livros")
def listar_livros() -> Response:
    """Lista o catálogo pelo caminho comum de leitura e normalização."""
    conexao = cast(ConexaoMongo, current_app.extensions["mongo"])
    resposta = executar_com_cas(conexao.banco, criar_resposta_livros)
    return jsonify(resposta.model_dump(mode="json"))
