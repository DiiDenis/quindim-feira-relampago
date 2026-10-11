"""Validação da entrada autenticada de pagamentos."""

import hashlib
import hmac
import re
from collections import Counter
from datetime import UTC, datetime
from typing import Any, Literal, cast

from flask import Blueprint, Response, current_app, jsonify, request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .banco import executar_com_cas
from .erros import ErroNegocio, validar_entrada
from .mongo import ConexaoMongo

PADRAO_ASSINATURA = re.compile(r"[0-9a-fA-F]{64}\Z")
bp = Blueprint("pagamentos", __name__, url_prefix="/v1")


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


class WebhookPagamentoSaida(BaseModel):
    """Confirma o recebimento sem revelar o efeito interno do evento."""

    model_config = ConfigDict(extra="forbid", strict=True)

    recebido: Literal[True]


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


def processar_evento_pagamento(
    estado: dict[str, Any],
    evento: EventoPagamentoEntrada,
) -> bool:
    """Consome um evento uma vez e aplica somente uma transição válida."""
    if any(item["evento_id"] == evento.evento_id for item in estado["eventos"]):
        return False

    pedido = next(
        (item for item in estado["pedidos"] if item["id"] == evento.pedido_id),
        None,
    )
    if pedido is not None and pedido["status"] not in {
        "aguardando_pagamento",
        "pago",
        "cancelado",
    }:
        raise RuntimeError("Pedido com status interno desconhecido.")

    livros_por_sku = {livro["sku"]: livro for livro in estado["livros"]}
    devolucoes: Counter[str] = Counter()
    if (
        pedido is not None
        and pedido["status"] == "aguardando_pagamento"
        and evento.tipo == "recusado"
    ):
        for linha in pedido["linhas"]:
            devolucoes[linha["sku"]] += linha["quantidade"]
        for sku, quantidade in devolucoes.items():
            livro = livros_por_sku.get(sku)
            if livro is None or livro["disponivel"] + quantidade > livro["estoque"]:
                raise RuntimeError("Pedido viola a capacidade interna do estoque.")

    estado["eventos"].append(evento.model_dump())
    if pedido is None or pedido["status"] in {"pago", "cancelado"}:
        return True

    if evento.tipo == "pago":
        pedido["status"] = "pago"
        pedido["pago_em"] = evento.ocorrido_em
        return True

    pedido["status"] = "cancelado"
    for sku, quantidade in devolucoes.items():
        livros_por_sku[sku]["disponivel"] += quantidade
    return True


@bp.post("/webhooks/pagamento")
def receber_webhook_pagamento() -> tuple[Response, int]:
    """Autentica os bytes antes de validar e aplicar o evento via CAS."""
    corpo = request.get_data(cache=True)
    segredo = cast(str, current_app.config["WEBHOOK_SEGREDO"])
    if not assinatura_valida(corpo, request.headers.get("X-Assinatura"), segredo):
        raise ErroNegocio(
            401,
            "nao_autorizado",
            "Assinatura do webhook inválida.",
        )

    evento = validar_entrada(EventoPagamentoEntrada, request.get_json())
    conexao = cast(ConexaoMongo, current_app.extensions["mongo"])

    def executar(estado: dict[str, Any], _agora: datetime) -> WebhookPagamentoSaida:
        processar_evento_pagamento(estado, evento)
        return WebhookPagamentoSaida(recebido=True)

    resposta = executar_com_cas(conexao.banco, executar)
    return jsonify(resposta.model_dump(mode="json")), 200
