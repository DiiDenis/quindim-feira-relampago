"""Modelos e normalização da entrada de reserva."""

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


def validar_e_normalizar_entrada_reserva(dados: Any) -> ReservaEntrada:
    """Valida o corpo e devolve SKUs consolidados para a futura regra de domínio."""
    return ReservaEntrada.model_validate(dados)
