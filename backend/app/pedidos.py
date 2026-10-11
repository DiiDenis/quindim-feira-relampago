"""Composição e contrato público dos pedidos."""

from datetime import UTC, datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from .dinheiro import calcular_desconto, ratear_desconto
from .erros import ErroNegocio
from .formatos import serializar_data_utc
from .reservas import encontrar_reserva


class LinhaPedidoSaida(BaseModel):
    """Linha pública com seus valores monetários conferidos."""

    model_config = ConfigDict(extra="forbid", strict=True)

    sku: str
    quantidade: int = Field(ge=1)
    preco_centavos: int = Field(ge=0)
    valor_centavos: int = Field(ge=0)
    desconto_centavos: int = Field(ge=0)
    liquido_centavos: int = Field(ge=0)

    @model_validator(mode="after")
    def conferir_totais(self) -> Self:
        if self.valor_centavos != self.quantidade * self.preco_centavos:
            raise ValueError("O valor da linha não corresponde à quantidade e ao preço.")
        if self.desconto_centavos > self.valor_centavos:
            raise ValueError("O desconto da linha não pode superar seu valor.")
        if self.liquido_centavos != self.valor_centavos - self.desconto_centavos:
            raise ValueError("O líquido da linha não corresponde ao valor menos o desconto.")
        return self


class PedidoSaida(BaseModel):
    """Pedido público com totais coerentes com suas linhas."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str
    reserva_id: str
    cliente_id: str
    status: Literal["aguardando_pagamento", "pago", "cancelado"]
    linhas: list[LinhaPedidoSaida] = Field(min_length=1)
    subtotal_centavos: int = Field(ge=0)
    desconto_centavos: int = Field(ge=0)
    total_centavos: int = Field(ge=0)
    criado_em: datetime
    pago_em: datetime | None

    @model_validator(mode="after")
    def conferir_totais(self) -> Self:
        if self.subtotal_centavos != sum(linha.valor_centavos for linha in self.linhas):
            raise ValueError("O subtotal do pedido não corresponde às linhas.")
        if self.desconto_centavos != sum(linha.desconto_centavos for linha in self.linhas):
            raise ValueError("O desconto do pedido não corresponde às linhas.")
        if self.total_centavos != sum(linha.liquido_centavos for linha in self.linhas):
            raise ValueError("O total do pedido não corresponde às linhas.")
        if self.total_centavos != self.subtotal_centavos - self.desconto_centavos:
            raise ValueError("O total do pedido não corresponde ao subtotal menos o desconto.")
        return self

    @field_serializer("criado_em", "pago_em")
    def serializar_datas(self, valor: datetime | None) -> str | None:
        return None if valor is None else serializar_data_utc(valor)


def montar_pedido(
    reserva: dict[str, Any],
    id_pedido: str,
    agora: datetime,
) -> dict[str, Any]:
    """Monta um pedido usando somente preços e quantidades da reserva."""
    if agora.tzinfo is None or agora.utcoffset() is None:
        raise ValueError("A hora do pedido deve informar o fuso UTC.")

    valores_linhas = [item["quantidade"] * item["preco_centavos"] for item in reserva["itens"]]
    subtotal_centavos = sum(valores_linhas)
    total_unidades = sum(item["quantidade"] for item in reserva["itens"])
    desconto_centavos = calcular_desconto(subtotal_centavos, total_unidades)
    descontos_linhas = ratear_desconto(valores_linhas, desconto_centavos)
    linhas = [
        {
            "sku": item["sku"],
            "quantidade": item["quantidade"],
            "preco_centavos": item["preco_centavos"],
            "valor_centavos": valor,
            "desconto_centavos": desconto,
            "liquido_centavos": valor - desconto,
        }
        for item, valor, desconto in zip(
            reserva["itens"],
            valores_linhas,
            descontos_linhas,
            strict=True,
        )
    ]

    pedido = {
        "id": id_pedido,
        "reserva_id": reserva["id"],
        "cliente_id": reserva["cliente_id"],
        "status": "aguardando_pagamento",
        "linhas": linhas,
        "subtotal_centavos": subtotal_centavos,
        "desconto_centavos": desconto_centavos,
        "total_centavos": subtotal_centavos - desconto_centavos,
        "criado_em": agora.astimezone(UTC),
        "pago_em": None,
    }
    criar_resposta_pedido(pedido)
    return pedido


def criar_resposta_pedido(pedido: dict[str, Any]) -> PedidoSaida:
    """Seleciona e valida somente os campos públicos do pedido."""
    return PedidoSaida.model_validate(
        {
            "id": pedido["id"],
            "reserva_id": pedido["reserva_id"],
            "cliente_id": pedido["cliente_id"],
            "status": pedido["status"],
            "linhas": [
                {
                    "sku": linha["sku"],
                    "quantidade": linha["quantidade"],
                    "preco_centavos": linha["preco_centavos"],
                    "valor_centavos": linha["valor_centavos"],
                    "desconto_centavos": linha["desconto_centavos"],
                    "liquido_centavos": linha["liquido_centavos"],
                }
                for linha in pedido["linhas"]
            ],
            "subtotal_centavos": pedido["subtotal_centavos"],
            "desconto_centavos": pedido["desconto_centavos"],
            "total_centavos": pedido["total_centavos"],
            "criado_em": pedido["criado_em"],
            "pago_em": pedido["pago_em"],
        }
    )


def confirmar_reserva(
    estado: dict[str, Any],
    id_reserva: str,
    id_novo_pedido: str,
    agora: datetime,
) -> tuple[dict[str, Any], bool]:
    """Confirma uma reserva uma única vez e indica se criou o pedido."""
    reserva = encontrar_reserva(estado, id_reserva)
    if reserva["status"] == "expirada":
        raise ErroNegocio(
            410,
            "reserva_expirada",
            "A reserva está expirada.",
        )

    if reserva["status"] == "confirmada":
        id_pedido = reserva.get("pedido_id")
        if not isinstance(id_pedido, str) or not id_pedido:
            raise RuntimeError("Reserva confirmada sem pedido vinculado válido.")
        pedido = next(
            (pedido for pedido in estado["pedidos"] if pedido["id"] == id_pedido),
            None,
        )
        if pedido is None:
            raise RuntimeError("Reserva confirmada sem pedido vinculado válido.")
        return pedido, False

    if reserva["status"] != "ativa":
        raise RuntimeError("Reserva com status interno desconhecido.")

    pedido = montar_pedido(reserva, id_novo_pedido, agora)
    estado["pedidos"].append(pedido)
    reserva["status"] = "confirmada"
    reserva["pedido_id"] = pedido["id"]
    return pedido, True
