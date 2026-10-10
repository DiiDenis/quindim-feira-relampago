"""Entrada e regras de negócio de reservas."""

from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Self, cast

from bson import ObjectId
from flask import Blueprint, Response, current_app, jsonify, request
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from .banco import executar_com_cas
from .erros import ErroNegocio, validar_entrada
from .formatos import serializar_data_utc
from .mongo import ConexaoMongo

bp = Blueprint("reservas", __name__, url_prefix="/v1")


class ItemReservaEntrada(BaseModel):
    """Item solicitado pelo cliente antes de consultar o catálogo."""

    model_config = ConfigDict(extra="forbid", strict=True)

    sku: str
    quantidade: int = Field(ge=1, le=3, strict=True)

    @field_validator("sku")
    @classmethod
    def rejeitar_sku_vazio(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("SKU não pode ser vazio.")
        return valor


def consolidar_itens_repetidos(
    itens: list[ItemReservaEntrada],
) -> list[ItemReservaEntrada]:
    """Soma SKUs repetidos mantendo a posição da primeira ocorrência."""
    consolidados: list[ItemReservaEntrada] = []
    posicao_por_sku: dict[str, int] = {}

    for item in itens:
        posicao = posicao_por_sku.get(item.sku)
        if posicao is None:
            posicao_por_sku[item.sku] = len(consolidados)
            consolidados.append(item)
            continue

        quantidade_total = consolidados[posicao].quantidade + item.quantidade
        if quantidade_total > 3:
            raise ValueError(f"Quantidade total do SKU {item.sku} não pode passar de 3.")
        consolidados[posicao] = consolidados[posicao].model_copy(
            update={"quantidade": quantidade_total}
        )

    return consolidados


class ReservaEntrada(BaseModel):
    """Corpo aceito para solicitar uma reserva."""

    model_config = ConfigDict(extra="forbid", strict=True)

    cliente_id: str
    itens: list[ItemReservaEntrada] = Field(min_length=1)

    @field_validator("cliente_id")
    @classmethod
    def rejeitar_cliente_vazio(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("cliente_id não pode ser vazio.")
        return valor

    @model_validator(mode="after")
    def normalizar_skus_repetidos(self) -> Self:
        self.itens = consolidar_itens_repetidos(self.itens)
        return self


class ItemReservaSaida(BaseModel):
    """Item da reserva no contrato público."""

    model_config = ConfigDict(extra="forbid", strict=True)

    sku: str
    quantidade: int
    preco_centavos: int


class ReservaSaida(BaseModel):
    """Reserva serializada sem campos internos do agregado."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str
    cliente_id: str
    status: Literal["ativa", "confirmada", "expirada"]
    itens: list[ItemReservaSaida]
    criado_em: datetime
    expira_em: datetime

    @field_serializer("criado_em", "expira_em")
    def serializar_datas(self, valor: datetime) -> str:
        return serializar_data_utc(valor)


def validar_e_normalizar_entrada_reserva(dados: Any) -> ReservaEntrada:
    """Valida o corpo e devolve SKUs consolidados para a futura regra de domínio."""
    return ReservaEntrada.model_validate(dados)


def reservar_itens(
    estado: dict[str, Any],
    entrada: ReservaEntrada,
    id_reserva: str,
    agora: datetime,
    ttl_segundos: int,
) -> dict[str, Any]:
    """Reserva a cesta inteira somente quando todos os itens podem ser atendidos."""
    if agora.tzinfo is None or agora.utcoffset() is None:
        raise ValueError("A hora da reserva deve informar o fuso UTC.")
    agora_utc = agora.astimezone(UTC)
    livros_por_sku = {livro["sku"]: livro for livro in estado["livros"]}

    skus_desconhecidos = [item.sku for item in entrada.itens if item.sku not in livros_por_sku]
    if skus_desconhecidos:
        raise ErroNegocio(
            404,
            "nao_encontrado",
            "Livro não encontrado.",
        )

    skus_insuficientes = [
        item.sku
        for item in entrada.itens
        if livros_por_sku[item.sku]["disponivel"] < item.quantidade
    ]
    if skus_insuficientes:
        raise ErroNegocio(
            409,
            "estoque_insuficiente",
            "Estoque insuficiente.",
            {"skus": skus_insuficientes},
        )

    itens_reservados = [
        {
            "sku": item.sku,
            "quantidade": item.quantidade,
            "preco_centavos": livros_por_sku[item.sku]["preco_centavos"],
        }
        for item in entrada.itens
    ]
    for item in entrada.itens:
        livros_por_sku[item.sku]["disponivel"] -= item.quantidade

    reserva = {
        "id": id_reserva,
        "cliente_id": entrada.cliente_id,
        "status": "ativa",
        "itens": itens_reservados,
        "criado_em": agora_utc,
        "expira_em": agora_utc + timedelta(seconds=ttl_segundos),
    }
    estado["reservas"].append(reserva)
    return reserva


def criar_resposta_reserva(reserva: dict[str, Any]) -> ReservaSaida:
    """Seleciona e valida somente os campos públicos da reserva."""
    return ReservaSaida.model_validate(
        {
            "id": reserva["id"],
            "cliente_id": reserva["cliente_id"],
            "status": reserva["status"],
            "itens": [
                {
                    "sku": item["sku"],
                    "quantidade": item["quantidade"],
                    "preco_centavos": item["preco_centavos"],
                }
                for item in reserva["itens"]
            ],
            "criado_em": reserva["criado_em"],
            "expira_em": reserva["expira_em"],
        }
    )


@bp.post("/reservas")
def criar_reserva() -> tuple[Response, int]:
    """Valida e publica uma reserva somente depois da escrita CAS vencer."""
    entrada = validar_entrada(ReservaEntrada, request.get_json())
    id_reserva = str(ObjectId())
    conexao = cast(ConexaoMongo, current_app.extensions["mongo"])
    ttl_segundos = cast(int, current_app.config["RESERVA_TTL_SEGUNDOS"])

    def executar(estado: dict[str, Any], agora: datetime) -> ReservaSaida:
        return criar_resposta_reserva(
            reservar_itens(
                estado,
                entrada,
                id_reserva,
                agora,
                ttl_segundos,
            )
        )

    resposta = executar_com_cas(conexao.banco, executar)
    return jsonify(resposta.model_dump(mode="json")), 201
