"""Regra pura de expiração das reservas no estado da feira."""

from datetime import UTC, datetime
from typing import Any


def expirar_reservas(estado: dict[str, Any], agora: datetime) -> None:
    """Expira reservas ativas vencidas e devolve suas unidades uma única vez."""
    if agora.tzinfo is None or agora.utcoffset() is None:
        raise ValueError("A hora da expiração deve informar o fuso UTC.")

    agora_utc = agora.astimezone(UTC)
    livros_por_sku = {livro["sku"]: livro for livro in estado["livros"]}

    for reserva in estado["reservas"]:
        if reserva["status"] != "ativa":
            continue

        expira_em = reserva["expira_em"]
        if expira_em.tzinfo is None or expira_em.utcoffset() is None:
            raise ValueError("A expiração da reserva deve informar o fuso UTC.")
        if expira_em.astimezone(UTC) > agora_utc:
            continue

        for item in reserva["itens"]:
            livros_por_sku[item["sku"]]["disponivel"] += item["quantidade"]
        reserva["status"] = "expirada"
