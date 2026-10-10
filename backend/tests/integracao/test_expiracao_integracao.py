import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier, BrokenBarrierError
from time import monotonic, sleep
from typing import Any

import httpx
import pytest
from pymongo.database import Database

from app.banco import ler_snapshot_feira

pytestmark = [pytest.mark.integracao, pytest.mark.negocio]

TOTAL_REQUISICOES = 20
TIMEOUT_SEGUNDOS = 10.0


def criar_reserva_qnd005(cliente_http: httpx.Client, cliente_id: str) -> dict[str, Any]:
    resposta = cliente_http.post(
        "/v1/reservas",
        json={
            "cliente_id": cliente_id,
            "itens": [{"sku": "QND-005", "quantidade": 1}],
        },
    )
    assert resposta.status_code == 201
    return resposta.json()


def vencer_reserva(
    banco_mongo: Database[dict[str, Any]],
    id_reserva: str,
) -> None:
    colecao = banco_mongo["feiras"]
    agora = ler_snapshot_feira(colecao).agora
    resultado = colecao.update_one(
        {"_id": "principal", "reservas.id": id_reserva},
        {"$set": {"reservas.$.expira_em": agora - timedelta(seconds=1)}},
    )
    assert resultado.modified_count == 1


def obter_estado(banco_mongo: Database[dict[str, Any]]) -> dict[str, Any]:
    estado = banco_mongo["feiras"].find_one({"_id": "principal"})
    assert estado is not None
    return estado


def livro_por_sku(estado: dict[str, Any], sku: str) -> dict[str, Any]:
    return next(livro for livro in estado["livros"] if livro["sku"] == sku)


def test_get_livros_libera_estoque_vencido_imediatamente(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
) -> None:
    reserva = criar_reserva_qnd005(cliente_http, "cliente-catalogo")
    vencer_reserva(banco_mongo, reserva["id"])

    resposta = cliente_http.get("/v1/livros")

    assert resposta.status_code == 200
    livro = next(livro for livro in resposta.json()["livros"] if livro["sku"] == "QND-005")
    assert livro["disponivel"] == 1


def test_get_reserva_publica_status_expirado(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
) -> None:
    reserva = criar_reserva_qnd005(cliente_http, "cliente-consulta-expirada")
    vencer_reserva(banco_mongo, reserva["id"])

    resposta = cliente_http.get(f"/v1/reservas/{reserva['id']}")

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "expirada"


def test_nova_reserva_reutiliza_estoque_vencido_sem_rotina_periodica(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
) -> None:
    reserva_vencida = criar_reserva_qnd005(cliente_http, "cliente-reserva-vencida")
    vencer_reserva(banco_mongo, reserva_vencida["id"])

    nova_reserva = criar_reserva_qnd005(cliente_http, "cliente-nova-reserva")

    assert nova_reserva["status"] == "ativa"
    estado = obter_estado(banco_mongo)
    reservas_por_id = {reserva["id"]: reserva for reserva in estado["reservas"]}
    assert reservas_por_id[reserva_vencida["id"]]["status"] == "expirada"
    assert reservas_por_id[nova_reserva["id"]]["status"] == "ativa"
    assert livro_por_sku(estado, "QND-005")["disponivel"] == 0


def test_gets_simultaneos_devolvem_uma_vez_e_so_uma_nova_reserva_vence(
    cliente_http: httpx.Client,
    url_api: str,
    banco_mongo: Database[dict[str, Any]],
) -> None:
    reserva_vencida = criar_reserva_qnd005(cliente_http, "cliente-vinte-consultas")
    vencer_reserva(banco_mongo, reserva_vencida["id"])
    barreira_consultas = Barrier(TOTAL_REQUISICOES)

    def consultar_reserva(_indice: int) -> tuple[int, str]:
        try:
            barreira_consultas.wait(timeout=TIMEOUT_SEGUNDOS)
        except BrokenBarrierError as erro:
            raise AssertionError("A barreira das consultas expirou.") from erro
        with httpx.Client(base_url=url_api, timeout=TIMEOUT_SEGUNDOS) as cliente:
            resposta = cliente.get(f"/v1/reservas/{reserva_vencida['id']}")
        return resposta.status_code, resposta.json()["status"]

    with ThreadPoolExecutor(max_workers=TOTAL_REQUISICOES) as executor:
        consultas = list(executor.map(consultar_reserva, range(TOTAL_REQUISICOES)))

    assert consultas == [(200, "expirada")] * TOTAL_REQUISICOES
    estado_apos_consultas = obter_estado(banco_mongo)
    assert livro_por_sku(estado_apos_consultas, "QND-005")["disponivel"] == 1
    barreira_reservas = Barrier(TOTAL_REQUISICOES)

    def tentar_reservar(indice: int) -> int:
        try:
            barreira_reservas.wait(timeout=TIMEOUT_SEGUNDOS)
        except BrokenBarrierError as erro:
            raise AssertionError("A barreira das novas reservas expirou.") from erro
        with httpx.Client(base_url=url_api, timeout=TIMEOUT_SEGUNDOS) as cliente:
            resposta = cliente.post(
                "/v1/reservas",
                json={
                    "cliente_id": f"cliente-estoque-devolvido-{indice}",
                    "itens": [{"sku": "QND-005", "quantidade": 1}],
                },
            )
        return resposta.status_code

    with ThreadPoolExecutor(max_workers=TOTAL_REQUISICOES) as executor:
        reservas = list(executor.map(tentar_reservar, range(TOTAL_REQUISICOES)))

    assert Counter(reservas) == Counter({201: 1, 409: 19})
    estado_final = obter_estado(banco_mongo)
    livro = livro_por_sku(estado_final, "QND-005")
    reservas_ativas = [
        reserva for reserva in estado_final["reservas"] if reserva["status"] == "ativa"
    ]
    assert livro["disponivel"] == 0
    assert len(estado_final["reservas"]) == 2
    assert len(reservas_ativas) == 1
    assert (
        livro["disponivel"]
        + sum(
            item["quantidade"]
            for reserva in reservas_ativas
            for item in reserva["itens"]
            if item["sku"] == "QND-005"
        )
        == livro["estoque"]
    )


def test_ttl_real_configurado_na_api(
    cliente_http: httpx.Client,
) -> None:
    ttl_esperado = int(os.environ.get("TTL_ESPERADO_SEGUNDOS", "900"))
    reserva = criar_reserva_qnd005(cliente_http, "cliente-ttl-real")
    criado_em = datetime.fromisoformat(reserva["criado_em"].replace("Z", "+00:00"))
    expira_em = datetime.fromisoformat(reserva["expira_em"].replace("Z", "+00:00"))

    assert expira_em - criado_em == timedelta(seconds=ttl_esperado)

    resposta_antes = cliente_http.get(f"/v1/reservas/{reserva['id']}")
    assert resposta_antes.status_code == 200
    assert resposta_antes.json()["status"] == "ativa"

    if ttl_esperado > 5:
        return

    inicio = monotonic()
    limite_espera = ttl_esperado + 5
    while True:
        resposta_depois = cliente_http.get(f"/v1/reservas/{reserva['id']}")
        assert resposta_depois.status_code == 200
        if resposta_depois.json()["status"] == "expirada":
            break
        assert monotonic() - inicio < limite_espera, (
            f"A reserva não expirou em até {limite_espera} segundos."
        )
        sleep(0.05)

    livros = cliente_http.get("/v1/livros")
    assert livros.status_code == 200
    qnd005 = next(livro for livro in livros.json()["livros"] if livro["sku"] == "QND-005")
    assert qnd005["disponivel"] == 1
