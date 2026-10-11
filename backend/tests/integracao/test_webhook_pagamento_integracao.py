import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from pymongo.database import Database

from app.banco import ler_snapshot_feira
from app.pagamentos import calcular_assinatura

pytestmark = [pytest.mark.integracao, pytest.mark.negocio]


def obter_estado(banco_mongo: Database[dict[str, Any]]) -> dict[str, Any]:
    estado = banco_mongo["feiras"].find_one({"_id": "principal"})
    assert estado is not None
    return estado


def livro_por_sku(estado: dict[str, Any], sku: str) -> dict[str, Any]:
    return next(livro for livro in estado["livros"] if livro["sku"] == sku)


def criar_pedido(
    cliente_http: httpx.Client,
    itens: list[dict[str, Any]],
) -> dict[str, Any]:
    reserva = cliente_http.post(
        "/v1/reservas",
        json={"cliente_id": "cliente-webhook", "itens": itens},
    )
    assert reserva.status_code == 201
    confirmacao = cliente_http.post(f"/v1/reservas/{reserva.json()['id']}/confirmar")
    assert confirmacao.status_code == 201
    return confirmacao.json()


def corpo_evento(**alteracoes: Any) -> dict[str, Any]:
    evento = {
        "evento_id": "evt-http-001",
        "pedido_id": "pedido-inexistente",
        "tipo": "pago",
        "ocorrido_em": "2026-10-10T15:45:00-03:00",
    }
    evento.update(alteracoes)
    return evento


def serializar_evento(evento: dict[str, Any]) -> bytes:
    return json.dumps(evento, ensure_ascii=False, separators=(",", ":")).encode()


def enviar_evento(
    cliente_http: httpx.Client,
    segredo_webhook: str,
    evento: dict[str, Any],
    *,
    assinatura: str | None = None,
) -> httpx.Response:
    corpo = serializar_evento(evento)
    assinatura_efetiva = assinatura or calcular_assinatura(corpo, segredo_webhook)
    return cliente_http.post(
        "/v1/webhooks/pagamento",
        content=corpo,
        headers={
            "Content-Type": "application/json",
            "X-Assinatura": assinatura_efetiva,
        },
    )


@pytest.mark.parametrize("assinatura", [None, "0" * 64])
def test_assinatura_invalida_nao_acessa_nem_normaliza_estado(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
    assinatura: str | None,
) -> None:
    reserva = cliente_http.post(
        "/v1/reservas",
        json={
            "cliente_id": "cliente-expiracao-incidental",
            "itens": [{"sku": "QND-005", "quantidade": 1}],
        },
    )
    assert reserva.status_code == 201
    colecao = banco_mongo["feiras"]
    agora = ler_snapshot_feira(colecao).agora
    resultado = colecao.update_one(
        {"_id": "principal", "reservas.id": reserva.json()["id"]},
        {"$set": {"reservas.$.expira_em": agora - timedelta(seconds=1)}},
    )
    assert resultado.modified_count == 1
    estado_antes = deepcopy(obter_estado(banco_mongo))
    corpo = serializar_evento(corpo_evento())
    headers = {"Content-Type": "application/json"}
    if assinatura is not None:
        headers["X-Assinatura"] = assinatura

    resposta = cliente_http.post(
        "/v1/webhooks/pagamento",
        content=corpo,
        headers=headers,
    )

    assert resposta.status_code == 401
    assert resposta.json()["erro"]["codigo"] == "nao_autorizado"
    assert obter_estado(banco_mongo) == estado_antes


def test_corpo_invalido_com_assinatura_valida_retorna_400_sem_alterar_estado(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
    segredo_webhook: str,
) -> None:
    estado_antes = deepcopy(obter_estado(banco_mongo))

    resposta = enviar_evento(
        cliente_http,
        segredo_webhook,
        corpo_evento(tipo="pendente"),
    )

    assert resposta.status_code == 400
    assert resposta.json()["erro"]["codigo"] == "requisicao_invalida"
    assert obter_estado(banco_mongo) == estado_antes


def test_webhook_pago_normaliza_data_e_responde_recebido_em_repeticoes(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
    segredo_webhook: str,
) -> None:
    pedido = criar_pedido(
        cliente_http,
        [{"sku": "QND-005", "quantidade": 1}],
    )
    evento = corpo_evento(pedido_id=pedido["id"])

    primeira = enviar_evento(cliente_http, segredo_webhook, evento)
    repeticao = enviar_evento(cliente_http, segredo_webhook, evento)

    assert primeira.status_code == repeticao.status_code == 200
    assert primeira.json() == repeticao.json() == {"recebido": True}
    estado = obter_estado(banco_mongo)
    assert len(estado["eventos"]) == 1
    assert estado["pedidos"][0]["status"] == "pago"
    assert estado["pedidos"][0]["pago_em"] == datetime(2026, 10, 10, 18, 45, tzinfo=UTC)
    assert livro_por_sku(estado, "QND-005")["disponivel"] == 0

    sem_efeito = enviar_evento(
        cliente_http,
        segredo_webhook,
        corpo_evento(
            evento_id="evt-http-sem-efeito",
            pedido_id=pedido["id"],
            tipo="recusado",
        ),
    )
    assert sem_efeito.status_code == 200
    assert sem_efeito.json() == {"recebido": True}
    estado_terminal = obter_estado(banco_mongo)
    assert len(estado_terminal["eventos"]) == 2
    assert estado_terminal["pedidos"][0]["status"] == "pago"
    assert estado_terminal["pedidos"][0]["pago_em"] == datetime(2026, 10, 10, 18, 45, tzinfo=UTC)
    assert livro_por_sku(estado_terminal, "QND-005")["disponivel"] == 0


def test_webhook_recusado_cancela_e_devolve_estoque(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
    segredo_webhook: str,
) -> None:
    pedido = criar_pedido(
        cliente_http,
        [
            {"sku": "QND-001", "quantidade": 2},
            {"sku": "QND-005", "quantidade": 1},
        ],
    )

    resposta = enviar_evento(
        cliente_http,
        segredo_webhook,
        corpo_evento(pedido_id=pedido["id"], tipo="recusado"),
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"recebido": True}
    estado = obter_estado(banco_mongo)
    assert estado["pedidos"][0]["status"] == "cancelado"
    assert estado["pedidos"][0]["pago_em"] is None
    assert estado["reservas"][0]["status"] == "confirmada"
    assert livro_por_sku(estado, "QND-001")["disponivel"] == 10
    assert livro_por_sku(estado, "QND-005")["disponivel"] == 1


def test_webhook_de_pedido_inexistente_responde_recebido_e_registra_evento(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
    segredo_webhook: str,
) -> None:
    evento = corpo_evento(pedido_id="nao-precisa-ser-object-id")

    resposta = enviar_evento(cliente_http, segredo_webhook, evento)

    assert resposta.status_code == 200
    assert resposta.json() == {"recebido": True}
    estado = obter_estado(banco_mongo)
    assert estado["pedidos"] == []
    assert len(estado["eventos"]) == 1
    assert estado["eventos"][0]["evento_id"] == evento["evento_id"]
