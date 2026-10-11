import hashlib
import hmac
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, BrokenBarrierError
from typing import Any

import httpx
import pytest
from pymongo.database import Database

pytestmark = [pytest.mark.integracao, pytest.mark.negocio]

TOTAL_REQUISICOES = 20
TIMEOUT_SEGUNDOS = 10.0


def obter_estado(banco_mongo: Database[dict[str, Any]]) -> dict[str, Any]:
    estado = banco_mongo["feiras"].find_one({"_id": "principal"})
    assert estado is not None
    return estado


def livro_por_sku(estado: dict[str, Any], sku: str) -> dict[str, Any]:
    return next(livro for livro in estado["livros"] if livro["sku"] == sku)


def criar_pedido_ultima_unidade(cliente_http: httpx.Client) -> dict[str, Any]:
    reserva = cliente_http.post(
        "/v1/reservas",
        json={
            "cliente_id": "cliente-pagamento-concorrente",
            "itens": [{"sku": "QND-005", "quantidade": 1}],
        },
    )
    assert reserva.status_code == 201
    confirmacao = cliente_http.post(f"/v1/reservas/{reserva.json()['id']}/confirmar")
    assert confirmacao.status_code == 201
    return confirmacao.json()


def criar_evento(evento_id: str, pedido_id: str, tipo: str) -> dict[str, str]:
    return {
        "evento_id": evento_id,
        "pedido_id": pedido_id,
        "tipo": tipo,
        "ocorrido_em": "2026-10-10T18:45:00Z",
    }


def serializar_e_assinar(
    evento: dict[str, str],
    segredo: str,
) -> tuple[bytes, str]:
    corpo = json.dumps(evento, separators=(",", ":")).encode()
    assinatura = hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
    return corpo, assinatura


def postar_evento(
    cliente: httpx.Client,
    evento: dict[str, str],
    segredo: str,
) -> httpx.Response:
    corpo, assinatura = serializar_e_assinar(evento, segredo)
    return cliente.post(
        "/v1/webhooks/pagamento",
        content=corpo,
        headers={"Content-Type": "application/json", "X-Assinatura": assinatura},
    )


def enviar_eventos_simultaneos(
    url_api: str,
    segredo: str,
    eventos: list[dict[str, str]],
) -> list[tuple[int, dict[str, Any]]]:
    barreira = Barrier(len(eventos))

    def enviar(evento: dict[str, str]) -> tuple[int, dict[str, Any]]:
        try:
            barreira.wait(timeout=TIMEOUT_SEGUNDOS)
        except BrokenBarrierError as erro:
            raise AssertionError("A barreira dos webhooks expirou.") from erro
        try:
            with httpx.Client(
                base_url=url_api,
                timeout=httpx.Timeout(TIMEOUT_SEGUNDOS),
            ) as cliente:
                resposta = postar_evento(cliente, evento, segredo)
        except httpx.RequestError as erro:
            raise AssertionError(
                f"O webhook {evento['evento_id']} falhou: {type(erro).__name__}."
            ) from erro
        return resposta.status_code, resposta.json()

    with ThreadPoolExecutor(max_workers=len(eventos)) as executor:
        return list(executor.map(enviar, eventos))


def conferir_respostas_recebidas(resultados: list[tuple[int, dict[str, Any]]]) -> None:
    assert Counter(status for status, _corpo in resultados) == Counter({200: len(resultados)})
    assert all(corpo == {"recebido": True} for _status, corpo in resultados)


def conferir_invariantes(estado: dict[str, Any]) -> None:
    reservadas: Counter[str] = Counter()
    comprometidas: Counter[str] = Counter()
    for reserva in estado["reservas"]:
        if reserva["status"] == "ativa":
            for item in reserva["itens"]:
                reservadas[item["sku"]] += item["quantidade"]
    for pedido in estado["pedidos"]:
        if pedido["status"] in {"aguardando_pagamento", "pago"}:
            for linha in pedido["linhas"]:
                comprometidas[linha["sku"]] += linha["quantidade"]

    for livro in estado["livros"]:
        sku = livro["sku"]
        assert 0 <= livro["disponivel"] <= livro["estoque"]
        assert livro["estoque"] == (livro["disponivel"] + reservadas[sku] + comprometidas[sku])


def test_vinte_entregas_do_mesmo_evento_devolvem_uma_vez(
    cliente_http: httpx.Client,
    url_api: str,
    banco_mongo: Database[dict[str, Any]],
    segredo_webhook: str,
) -> None:
    pedido = criar_pedido_ultima_unidade(cliente_http)
    evento = criar_evento("evt-recusa-repetido", pedido["id"], "recusado")

    resultados = enviar_eventos_simultaneos(
        url_api,
        segredo_webhook,
        [evento] * TOTAL_REQUISICOES,
    )

    conferir_respostas_recebidas(resultados)
    estado = obter_estado(banco_mongo)
    assert len(estado["eventos"]) == 1
    assert estado["eventos"][0]["evento_id"] == evento["evento_id"]
    assert estado["pedidos"][0]["status"] == "cancelado"
    assert livro_por_sku(estado, "QND-005")["disponivel"] == 1
    conferir_invariantes(estado)


def test_vinte_eventos_distintos_de_recusa_nao_multiplicam_devolucao(
    cliente_http: httpx.Client,
    url_api: str,
    banco_mongo: Database[dict[str, Any]],
    segredo_webhook: str,
) -> None:
    pedido = criar_pedido_ultima_unidade(cliente_http)
    eventos = [
        criar_evento(f"evt-recusa-{indice:02d}", pedido["id"], "recusado")
        for indice in range(TOTAL_REQUISICOES)
    ]

    resultados = enviar_eventos_simultaneos(url_api, segredo_webhook, eventos)

    conferir_respostas_recebidas(resultados)
    estado = obter_estado(banco_mongo)
    assert len(estado["eventos"]) == TOTAL_REQUISICOES
    assert {evento["evento_id"] for evento in estado["eventos"]} == {
        evento["evento_id"] for evento in eventos
    }
    assert estado["pedidos"][0]["status"] == "cancelado"
    assert livro_por_sku(estado, "QND-005")["disponivel"] == 1
    conferir_invariantes(estado)


@pytest.mark.parametrize("rodada", range(5))
def test_pago_e_recusado_simultaneos_terminam_em_um_estado_coerente(
    cliente_http: httpx.Client,
    url_api: str,
    banco_mongo: Database[dict[str, Any]],
    segredo_webhook: str,
    rodada: int,
) -> None:
    pedido = criar_pedido_ultima_unidade(cliente_http)
    eventos = [
        criar_evento(f"evt-pago-{rodada}", pedido["id"], "pago"),
        criar_evento(f"evt-recusado-{rodada}", pedido["id"], "recusado"),
    ]

    resultados = enviar_eventos_simultaneos(url_api, segredo_webhook, eventos)

    conferir_respostas_recebidas(resultados)
    estado = obter_estado(banco_mongo)
    assert len(estado["eventos"]) == 2
    pedido_final = estado["pedidos"][0]
    disponivel = livro_por_sku(estado, "QND-005")["disponivel"]
    if pedido_final["status"] == "pago":
        assert pedido_final["pago_em"] is not None
        assert disponivel == 0
    else:
        assert pedido_final["status"] == "cancelado", f"Falha na rodada {rodada}."
        assert pedido_final["pago_em"] is None
        assert disponivel == 1
    conferir_invariantes(estado)


@pytest.mark.parametrize("rodada", range(5))
def test_recusa_e_nova_reserva_simultaneas_preservam_estoque(
    cliente_http: httpx.Client,
    url_api: str,
    banco_mongo: Database[dict[str, Any]],
    segredo_webhook: str,
    rodada: int,
) -> None:
    pedido = criar_pedido_ultima_unidade(cliente_http)
    evento = criar_evento(f"evt-libera-{rodada}", pedido["id"], "recusado")
    barreira = Barrier(2)

    def aguardar_barreira() -> None:
        try:
            barreira.wait(timeout=TIMEOUT_SEGUNDOS)
        except BrokenBarrierError as erro:
            raise AssertionError("A barreira da recusa e reserva expirou.") from erro

    def recusar() -> httpx.Response:
        aguardar_barreira()
        with httpx.Client(base_url=url_api, timeout=TIMEOUT_SEGUNDOS) as cliente:
            return postar_evento(cliente, evento, segredo_webhook)

    def reservar() -> httpx.Response:
        aguardar_barreira()
        with httpx.Client(base_url=url_api, timeout=TIMEOUT_SEGUNDOS) as cliente:
            return cliente.post(
                "/v1/reservas",
                json={
                    "cliente_id": f"cliente-nova-reserva-{rodada}",
                    "itens": [{"sku": "QND-005", "quantidade": 1}],
                },
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futuro_recusa = executor.submit(recusar)
        futuro_reserva = executor.submit(reservar)
        resposta_recusa = futuro_recusa.result(timeout=TIMEOUT_SEGUNDOS)
        resposta_reserva = futuro_reserva.result(timeout=TIMEOUT_SEGUNDOS)

    assert resposta_recusa.status_code == 200
    assert resposta_recusa.json() == {"recebido": True}
    assert resposta_reserva.status_code in {201, 409}
    estado = obter_estado(banco_mongo)
    assert len(estado["eventos"]) == 1
    assert estado["pedidos"][0]["status"] == "cancelado"
    if resposta_reserva.status_code == 201:
        assert len(estado["reservas"]) == 2
        assert estado["reservas"][1]["status"] == "ativa"
        assert livro_por_sku(estado, "QND-005")["disponivel"] == 0
    else:
        assert resposta_reserva.json()["erro"]["codigo"] == "estoque_insuficiente"
        assert len(estado["reservas"]) == 1, f"Falha na rodada {rodada}."
        assert livro_por_sku(estado, "QND-005")["disponivel"] == 1
    conferir_invariantes(estado)
