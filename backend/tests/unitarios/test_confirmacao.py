from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.erros import ErroNegocio
from app.expiracao import expirar_reservas
from app.pedidos import confirmar_reserva
from app.reservas import ReservaEntrada, reservar_itens
from app.seed import criar_estado_inicial

AGORA = datetime(2026, 10, 10, 18, 30, tzinfo=UTC)
ID_RESERVA = "68e91f682eaeb2123b830001"
ID_PEDIDO = "68e91f682eaeb2123b830010"


def preparar_reserva(
    estado: dict[str, Any],
    *itens: tuple[str, int],
) -> dict[str, Any]:
    entrada = ReservaEntrada.model_validate(
        {
            "cliente_id": "cliente-confirmacao",
            "itens": [{"sku": sku, "quantidade": quantidade} for sku, quantidade in itens],
        }
    )
    return reservar_itens(estado, entrada, ID_RESERVA, AGORA, 900)


def livro_por_sku(estado: dict[str, Any], sku: str) -> dict[str, Any]:
    return next(livro for livro in estado["livros"] if livro["sku"] == sku)


def test_confirma_reserva_ativa_sem_debitar_estoque_novamente() -> None:
    estado = criar_estado_inicial()
    reserva = preparar_reserva(estado, ("QND-001", 2), ("QND-003", 1))
    disponibilidade_antes = {livro["sku"]: livro["disponivel"] for livro in estado["livros"]}

    pedido, criado = confirmar_reserva(estado, ID_RESERVA, ID_PEDIDO, AGORA)

    assert criado is True
    assert pedido["id"] == ID_PEDIDO
    assert estado["pedidos"] == [pedido]
    assert reserva["status"] == "confirmada"
    assert reserva["pedido_id"] == ID_PEDIDO
    assert {livro["sku"]: livro["disponivel"] for livro in estado["livros"]} == (
        disponibilidade_antes
    )
    assert livro_por_sku(estado, "QND-001")["disponivel"] == 8
    assert livro_por_sku(estado, "QND-003")["disponivel"] == 9


def test_confirmacao_repetida_devolve_mesmo_pedido_apos_prazo_original() -> None:
    estado = criar_estado_inicial()
    preparar_reserva(estado, ("QND-005", 1))
    pedido_criado, criado = confirmar_reserva(estado, ID_RESERVA, ID_PEDIDO, AGORA)
    estado_apos_primeira = deepcopy(estado)

    pedido_repetido, criado_na_repeticao = confirmar_reserva(
        estado,
        ID_RESERVA,
        "id-que-nao-deve-ser-usado",
        AGORA + timedelta(hours=1),
    )

    assert criado is True
    assert criado_na_repeticao is False
    assert pedido_repetido == pedido_criado
    assert pedido_repetido["id"] == ID_PEDIDO
    assert estado == estado_apos_primeira
    assert len(estado["pedidos"]) == 1
    assert livro_por_sku(estado, "QND-005")["disponivel"] == 0


def test_reserva_expirada_retorna_410_sem_criar_pedido() -> None:
    estado = criar_estado_inicial()
    reserva = preparar_reserva(estado, ("QND-001", 2))
    expirar_reservas(estado, reserva["expira_em"])
    estado_antes = deepcopy(estado)

    with pytest.raises(ErroNegocio) as captura:
        confirmar_reserva(estado, ID_RESERVA, ID_PEDIDO, reserva["expira_em"])

    assert captura.value.status_http == 410
    assert captura.value.codigo == "reserva_expirada"
    assert estado == estado_antes
    assert estado["pedidos"] == []
    assert livro_por_sku(estado, "QND-001")["disponivel"] == 10


def test_reserva_inexistente_retorna_404_sem_alterar_estado() -> None:
    estado = criar_estado_inicial()
    estado_antes = deepcopy(estado)

    with pytest.raises(ErroNegocio) as captura:
        confirmar_reserva(estado, "reserva-inexistente", ID_PEDIDO, AGORA)

    assert captura.value.status_http == 404
    assert captura.value.codigo == "nao_encontrado"
    assert estado == estado_antes


@pytest.mark.parametrize("corrupcao", ["sem_vinculo", "pedido_inexistente"])
def test_reserva_confirmada_corrompida_nao_inventa_outro_pedido(corrupcao: str) -> None:
    estado = criar_estado_inicial()
    reserva = preparar_reserva(estado, ("QND-001", 1))
    confirmar_reserva(estado, ID_RESERVA, ID_PEDIDO, AGORA)
    if corrupcao == "sem_vinculo":
        del reserva["pedido_id"]
    else:
        reserva["pedido_id"] = "pedido-inexistente"
    estado_antes = deepcopy(estado)

    with pytest.raises(RuntimeError, match="sem pedido vinculado válido"):
        confirmar_reserva(
            estado,
            ID_RESERVA,
            "novo-pedido-indevido",
            AGORA + timedelta(minutes=1),
        )

    assert estado == estado_antes
    assert len(estado["pedidos"]) == 1


def test_confirmacao_preserva_invariante_de_estoque() -> None:
    estado = criar_estado_inicial()
    preparar_reserva(estado, ("QND-001", 2), ("QND-005", 1))

    confirmar_reserva(estado, ID_RESERVA, ID_PEDIDO, AGORA)

    for livro in estado["livros"]:
        unidades_em_pedidos = sum(
            linha["quantidade"]
            for pedido in estado["pedidos"]
            if pedido["status"] in {"aguardando_pagamento", "pago"}
            for linha in pedido["linhas"]
            if linha["sku"] == livro["sku"]
        )
        assert livro["disponivel"] + unidades_em_pedidos == livro["estoque"]
