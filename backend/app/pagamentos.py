"""Validação da entrada autenticada de pagamentos."""

import hashlib
import hmac
import re
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PADRAO_ASSINATURA = re.compile(r"[0-9a-fA-F]{64}\Z")


class EventoPagamentoEntrada(BaseModel):
    """Evento recebido do provedor antes de alterar o pedido."""

    model_config = ConfigDict(extra="forbid")

    evento_id: str = Field(strict=True)
    pedido_id: str = Field(strict=True)
    tipo: Literal["pago", "recusado"]
    ocorrido_em: datetime

    @field_validator("evento_id", "pedido_id")
    @classmethod
    def rejeitar_identificador_vazio(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("O identificador não pode ser vazio.")
        return valor

    @field_validator("ocorrido_em")
    @classmethod
    def normalizar_data_utc(cls, valor: datetime) -> datetime:
        if valor.tzinfo is None or valor.utcoffset() is None:
            raise ValueError("ocorrido_em deve informar o fuso horário.")
        return valor.astimezone(UTC)


def validar_e_normalizar_evento_pagamento(dados: Any) -> EventoPagamentoEntrada:
    """Valida o contrato do evento sem interpretar pedido_id como ID de rota."""
    return EventoPagamentoEntrada.model_validate(dados)


def calcular_assinatura(corpo: bytes, segredo: str) -> str:
    """Calcula o HMAC-SHA256 hexadecimal dos bytes originais."""
    return hmac.new(
        segredo.encode("utf-8"),
        corpo,
        hashlib.sha256,
    ).hexdigest()


def assinatura_valida(corpo: bytes, assinatura: str | None, segredo: str) -> bool:
    """Valida formato e conteúdo da assinatura sem comparação vulnerável a tempo."""
    if assinatura is None or PADRAO_ASSINATURA.fullmatch(assinatura) is None:
        return False
    esperada = calcular_assinatura(corpo, segredo)
    return hmac.compare_digest(assinatura.lower(), esperada)
