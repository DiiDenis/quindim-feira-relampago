"""Erros públicos da API e seus handlers Flask."""

from typing import Any

from flask import Flask, Response, current_app, jsonify
from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError
from werkzeug.exceptions import BadRequest, NotFound, UnsupportedMediaType


class DetalheErro(BaseModel):
    """Conteúdo público de um erro da API."""

    model_config = ConfigDict(extra="forbid", strict=True)

    codigo: str
    mensagem: str
    detalhes: dict[str, JsonValue] = Field(default_factory=dict)


class RespostaErro(BaseModel):
    """Envelope público comum a todos os erros."""

    model_config = ConfigDict(extra="forbid", strict=True)

    erro: DetalheErro


class ErroNegocio(Exception):
    """Falha esperada com status e código HTTP controlados."""

    def __init__(
        self,
        status_http: int,
        codigo: str,
        mensagem: str,
        detalhes: dict[str, JsonValue] | None = None,
    ) -> None:
        super().__init__(mensagem)
        self.status_http = status_http
        self.codigo = codigo
        self.mensagem = mensagem
        self.detalhes = detalhes or {}


def validar_entrada[ModeloEntrada: BaseModel](
    modelo: type[ModeloEntrada], dados: Any
) -> ModeloEntrada:
    """Valida entrada Pydantic e converte somente essa falha em HTTP 400."""
    try:
        return modelo.model_validate(dados)
    except ValidationError as erro:
        campos: list[dict[str, JsonValue]] = []
        for item in erro.errors(
            include_url=False,
            include_context=False,
            include_input=False,
        ):
            campos.append(
                {
                    "campo": ".".join(str(parte) for parte in item["loc"]),
                    "mensagem": item["msg"],
                    "tipo": item["type"],
                }
            )
        raise ErroNegocio(
            400,
            "requisicao_invalida",
            "Dados da requisição são inválidos.",
            {"campos": campos},
        ) from erro


def criar_resposta_erro(
    status_http: int,
    codigo: str,
    mensagem: str,
    detalhes: dict[str, JsonValue] | None = None,
) -> tuple[Response, int]:
    """Serializa o envelope através do modelo Pydantic de saída."""
    resposta = RespostaErro(
        erro=DetalheErro(
            codigo=codigo,
            mensagem=mensagem,
            detalhes=detalhes or {},
        )
    )
    return jsonify(resposta.model_dump(mode="json")), status_http


def registrar_handlers_erros(app: Flask) -> None:
    """Registra respostas JSON sem esconder falhas inesperadas do log."""

    @app.errorhandler(ErroNegocio)
    def tratar_erro_negocio(erro: ErroNegocio) -> tuple[Response, int]:
        return criar_resposta_erro(
            erro.status_http,
            erro.codigo,
            erro.mensagem,
            erro.detalhes,
        )

    @app.errorhandler(BadRequest)
    @app.errorhandler(UnsupportedMediaType)
    def tratar_requisicao_invalida(_erro: Exception) -> tuple[Response, int]:
        return criar_resposta_erro(
            400,
            "requisicao_invalida",
            "Corpo JSON inválido.",
        )

    @app.errorhandler(NotFound)
    def tratar_nao_encontrado(_erro: NotFound) -> tuple[Response, int]:
        return criar_resposta_erro(
            404,
            "nao_encontrado",
            "Recurso não encontrado.",
        )

    @app.errorhandler(Exception)
    def tratar_erro_inesperado(_erro: Exception) -> tuple[Response, int]:
        current_app.logger.exception("Erro inesperado durante a requisição")
        return criar_resposta_erro(
            500,
            "erro_interno",
            "Erro interno do servidor.",
        )
