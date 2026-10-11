from copy import deepcopy
from datetime import timedelta
from typing import Any

import httpx
import pytest
from bson import ObjectId
from pymongo.database import Database

from app.banco import ler_snapshot_feira

pytestmark = [pytest.mark.integracao, pytest.mark.negocio]


def obter_estado(banco_mongo: Database[dict[str, Any]]) -> dict[str, Any]:
    estado = banco_mongo["feiras"].find_one({"_id": "principal"})
    assert estado is not None
    return estado


def livro_por_sku(estado: dict[str, Any], sku: str) -> dict[str, Any]:
    return next(livro for livro in estado["livros"] if livro["sku"] == sku)


def criar_reserva(
    cliente_http: httpx.Client,
    itens: list[dict[str, Any]],
) -> dict[str, Any]:
    resposta = cliente_http.post(
        "/v1/reservas",
        json={"cliente_id": "cliente-confirmacao-http", "itens": itens},
    )
    assert resposta.status_code == 201
    return resposta.json()


def test_primeira_confirmacao_retorna_201_e_repeticao_o_mesmo_pedido_com_200(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
) -> None:
    reserva = criar_reserva(
        cliente_http,
        [
            {"sku": "QND-001", "quantidade": 1},
            {"sku": "QND-002", "quantidade": 1},
            {"sku": "QND-003", "quantidade": 1},
        ],
    )
    estado_reservado = obter_estado(banco_mongo)
    disponibilidade_reservada = {
        livro["sku"]: livro["disponivel"] for livro in estado_reservado["livros"]
    }

    primeira = cliente_http.post(f"/v1/reservas/{reserva['id']}/confirmar")

    assert primeira.status_code == 201
    pedido_publico = primeira.json()
    assert ObjectId.is_valid(pedido_publico["id"])
    assert pedido_publico["reserva_id"] == reserva["id"]
    assert pedido_publico["status"] == "aguardando_pagamento"
    assert pedido_publico["subtotal_centavos"] == 8975
    assert pedido_publico["desconto_centavos"] == 898
    assert pedido_publico["total_centavos"] == 8077
    assert pedido_publico["pago_em"] is None

    estado_confirmado = obter_estado(banco_mongo)
    assert len(estado_confirmado["pedidos"]) == 1
    pedido_persistido = estado_confirmado["pedidos"][0]
    assert pedido_persistido["id"] == pedido_publico["id"]
    assert pedido_persistido["reserva_id"] == pedido_publico["reserva_id"]
    assert pedido_persistido["linhas"] == pedido_publico["linhas"]
    assert pedido_persistido["subtotal_centavos"] == pedido_publico["subtotal_centavos"]
    assert pedido_persistido["desconto_centavos"] == pedido_publico["desconto_centavos"]
    assert pedido_persistido["total_centavos"] == pedido_publico["total_centavos"]
    reserva_persistida = estado_confirmado["reservas"][0]
    assert reserva_persistida["status"] == "confirmada"
    assert reserva_persistida["pedido_id"] == pedido_publico["id"]
    assert {livro["sku"]: livro["disponivel"] for livro in estado_confirmado["livros"]} == (
        disponibilidade_reservada
    )

    repeticao = cliente_http.post(f"/v1/reservas/{reserva['id']}/confirmar")

    assert repeticao.status_code == 200
    assert repeticao.json() == pedido_publico
    estado_repetido = obter_estado(banco_mongo)
    assert estado_repetido["pedidos"] == estado_confirmado["pedidos"]
    assert estado_repetido["reservas"] == estado_confirmado["reservas"]
    assert [livro["disponivel"] for livro in estado_repetido["livros"]] == [
        livro["disponivel"] for livro in estado_confirmado["livros"]
    ]


@pytest.mark.parametrize("id_reserva", ["nao-e-id", "f" * 24])
def test_confirmacao_de_id_invalido_ou_inexistente_retorna_404(
    cliente_http: httpx.Client,
    id_reserva: str,
) -> None:
    resposta = cliente_http.post(f"/v1/reservas/{id_reserva}/confirmar")

    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "nao_encontrado"


def test_confirmacao_rejeita_corpo_sem_modificar_estado(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
) -> None:
    reserva = criar_reserva(
        cliente_http,
        [{"sku": "QND-001", "quantidade": 1}],
    )
    estado_antes = deepcopy(obter_estado(banco_mongo))

    resposta = cliente_http.post(
        f"/v1/reservas/{reserva['id']}/confirmar",
        json={},
    )

    assert resposta.status_code == 400
    assert resposta.json()["erro"]["codigo"] == "requisicao_invalida"
    assert obter_estado(banco_mongo) == estado_antes


def test_confirmacao_expirada_retorna_410_e_persiste_liberacao(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
) -> None:
    reserva = criar_reserva(
        cliente_http,
        [{"sku": "QND-005", "quantidade": 1}],
    )
    colecao = banco_mongo["feiras"]
    agora = ler_snapshot_feira(colecao).agora
    resultado = colecao.update_one(
        {"_id": "principal", "reservas.id": reserva["id"]},
        {"$set": {"reservas.$.expira_em": agora - timedelta(seconds=1)}},
    )
    assert resultado.modified_count == 1

    resposta = cliente_http.post(f"/v1/reservas/{reserva['id']}/confirmar")

    assert resposta.status_code == 410
    assert resposta.json()["erro"]["codigo"] == "reserva_expirada"
    estado = obter_estado(banco_mongo)
    assert len(estado["pedidos"]) == 0
    assert estado["reservas"][0]["status"] == "expirada"
    assert livro_por_sku(estado, "QND-005")["disponivel"] == 1
