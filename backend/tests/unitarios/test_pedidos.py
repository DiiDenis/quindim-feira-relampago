from copy import deepcopy
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from app.pedidos import criar_resposta_pedido, montar_pedido

AGORA = datetime(2026, 10, 10, 18, 30, tzinfo=UTC)
ID_PEDIDO = "68e91f682eaeb2123b830010"


def criar_reserva(*itens: tuple[str, int, int]) -> dict[str, Any]:
    return {
        "id": "68e91f682eaeb2123b830001",
        "cliente_id": "cliente-pedido",
        "status": "ativa",
        "itens": [
            {"sku": sku, "quantidade": quantidade, "preco_centavos": preco}
            for sku, quantidade, preco in itens
        ],
        "criado_em": AGORA - timedelta(minutes=1),
        "expira_em": AGORA + timedelta(minutes=14),
    }


def test_monta_exemplo_completo_do_contrato() -> None:
    reserva = criar_reserva(
        ("QND-001", 1, 3990),
        ("QND-002", 1, 2990),
        ("QND-003", 1, 1995),
    )

    pedido = montar_pedido(reserva, ID_PEDIDO, AGORA)

    assert pedido == {
        "id": ID_PEDIDO,
        "reserva_id": reserva["id"],
        "cliente_id": "cliente-pedido",
        "status": "aguardando_pagamento",
        "linhas": [
            {
                "sku": "QND-001",
                "quantidade": 1,
                "preco_centavos": 3990,
                "valor_centavos": 3990,
                "desconto_centavos": 399,
                "liquido_centavos": 3591,
            },
            {
                "sku": "QND-002",
                "quantidade": 1,
                "preco_centavos": 2990,
                "valor_centavos": 2990,
                "desconto_centavos": 299,
                "liquido_centavos": 2691,
            },
            {
                "sku": "QND-003",
                "quantidade": 1,
                "preco_centavos": 1995,
                "valor_centavos": 1995,
                "desconto_centavos": 200,
                "liquido_centavos": 1795,
            },
        ],
        "subtotal_centavos": 8975,
        "desconto_centavos": 898,
        "total_centavos": 8077,
        "criado_em": AGORA,
        "pago_em": None,
    }


def test_faixa_de_desconto_depende_da_soma_das_unidades() -> None:
    reserva = criar_reserva(("QND-003", 3, 1995))

    pedido = montar_pedido(reserva, ID_PEDIDO, AGORA)

    assert len(pedido["linhas"]) == 1
    assert pedido["subtotal_centavos"] == 5985
    assert pedido["desconto_centavos"] == 599
    assert pedido["total_centavos"] == 5386
    assert pedido["linhas"][0]["desconto_centavos"] == 599


def test_saida_pydantic_remove_internos_e_serializa_utc_sem_alterar_dinheiro() -> None:
    reserva = criar_reserva(("SKU-PRECO-DA-RESERVA", 3, 345))
    pedido = montar_pedido(
        reserva,
        ID_PEDIDO,
        datetime(2026, 10, 10, 15, 30, tzinfo=timezone(timedelta(hours=-3))),
    )
    pedido["campo_interno"] = "nao-publicar"
    pedido["linhas"][0]["campo_interno"] = "nao-publicar"

    resposta = criar_resposta_pedido(pedido).model_dump(mode="json")

    assert set(resposta) == {
        "id",
        "reserva_id",
        "cliente_id",
        "status",
        "linhas",
        "subtotal_centavos",
        "desconto_centavos",
        "total_centavos",
        "criado_em",
        "pago_em",
    }
    assert "campo_interno" not in resposta["linhas"][0]
    assert resposta["criado_em"] == "2026-10-10T18:30:00Z"
    assert resposta["pago_em"] is None

    campos_monetarios = [
        resposta["subtotal_centavos"],
        resposta["desconto_centavos"],
        resposta["total_centavos"],
        resposta["linhas"][0]["preco_centavos"],
        resposta["linhas"][0]["valor_centavos"],
        resposta["linhas"][0]["desconto_centavos"],
        resposta["linhas"][0]["liquido_centavos"],
    ]
    assert all(
        isinstance(valor, int) and not isinstance(valor, bool) for valor in campos_monetarios
    )


@pytest.mark.parametrize(
    ("campo", "valor", "mensagem"),
    [
        ("subtotal_centavos", 9999, "subtotal do pedido"),
        ("desconto_centavos", 0, "desconto do pedido"),
        ("total_centavos", 9999, "total do pedido"),
    ],
)
def test_saida_rejeita_totais_de_cabecalho_incoerentes(
    campo: str,
    valor: int,
    mensagem: str,
) -> None:
    pedido = montar_pedido(criar_reserva(("QND-001", 3, 1000)), ID_PEDIDO, AGORA)
    pedido_invalido = deepcopy(pedido)
    pedido_invalido[campo] = valor

    with pytest.raises(ValidationError, match=mensagem):
        criar_resposta_pedido(pedido_invalido)


def test_saida_rejeita_totais_de_linha_incoerentes() -> None:
    pedido = montar_pedido(criar_reserva(("QND-001", 1, 1000)), ID_PEDIDO, AGORA)
    pedido["linhas"][0]["liquido_centavos"] = 999

    with pytest.raises(ValidationError, match="líquido da linha"):
        criar_resposta_pedido(pedido)


def test_rejeita_hora_sem_fuso() -> None:
    reserva = criar_reserva(("QND-001", 1, 1000))

    with pytest.raises(ValueError, match="fuso UTC"):
        montar_pedido(reserva, ID_PEDIDO, datetime(2026, 10, 10, 18, 30))
