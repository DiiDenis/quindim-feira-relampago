"""Conversões compartilhadas de identificadores e datas públicas."""

import re
from datetime import UTC, datetime

from bson import ObjectId

from .erros import ErroNegocio

PADRAO_OBJECT_ID = re.compile(r"[0-9a-fA-F]{24}\Z")


def interpretar_id_recurso(valor: str) -> ObjectId:
    """Converte um ID hexadecimal ou responde como recurso inexistente."""
    if PADRAO_OBJECT_ID.fullmatch(valor) is None:
        raise ErroNegocio(
            404,
            "nao_encontrado",
            "Recurso não encontrado.",
        )
    return ObjectId(valor)


def serializar_data_utc(valor: datetime) -> str:
    """Normaliza uma data consciente de fuso e termina a saída em Z."""
    if valor.tzinfo is None or valor.utcoffset() is None:
        raise ValueError("A data deve informar o fuso horário.")
    return valor.astimezone(UTC).isoformat().replace("+00:00", "Z")
