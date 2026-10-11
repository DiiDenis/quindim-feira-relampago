from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier, BrokenBarrierError
from time import monotonic, sleep
from typing import Any

import httpx
import pytest
from bson import ObjectId
from pymongo.database import Database

from app.banco import executar_com_cas, ler_snapshot_feira
from app.erros import ErroNegocio
from app.pedidos import confirmar_reserva

pytestmark = [pytest.mark.integracao, pytest.mark.negocio]

TOTAL_REQUISICOES = 20
TIMEOUT_SEGUNDOS = 10.0


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
        json={"cliente_id": "cliente-corrida", "itens": itens},
    )
    assert resposta.status_code == 201
    return resposta.json()


def definir_expiracao(
    banco_mongo: Database[dict[str, Any]],
    id_reserva: str,
    expira_em: datetime,
) -> None:
    resultado = banco_mongo["feiras"].update_one(
        {"_id": "principal", "reservas.id": id_reserva},
        {"$set": {"reservas.$.expira_em": expira_em}},
    )
    assert resultado.modified_count == 1


def esperar_hora_mongo(
    banco_mongo: Database[dict[str, Any]],
    instante: datetime,
) -> None:
    inicio = monotonic()
    while ler_snapshot_feira(banco_mongo["feiras"]).agora < instante:
        assert monotonic() - inicio < 5, "A espera pela hora do MongoDB expirou."
        sleep(0.005)


def conferir_invariantes(estado: dict[str, Any]) -> None:
    reservadas: Counter[str] = Counter()
    vendidas: Counter[str] = Counter()
    for reserva in estado["reservas"]:
        if reserva["status"] == "ativa":
            for item in reserva["itens"]:
                reservadas[item["sku"]] += item["quantidade"]
    for pedido in estado["pedidos"]:
        if pedido["status"] in {"aguardando_pagamento", "pago"}:
            for linha in pedido["linhas"]:
                vendidas[linha["sku"]] += linha["quantidade"]

    for livro in estado["livros"]:
        sku = livro["sku"]
        assert livro["estoque"] == (livro["disponivel"] + reservadas[sku] + vendidas[sku])


def confirmar_simultaneamente(
    url_api: str,
    id_reserva: str,
) -> list[tuple[int, dict[str, Any]]]:
    barreira = Barrier(TOTAL_REQUISICOES)

    def confirmar(indice: int) -> tuple[int, dict[str, Any]]:
        try:
            barreira.wait(timeout=TIMEOUT_SEGUNDOS)
        except BrokenBarrierError as erro:
            raise AssertionError("A barreira das confirmações expirou.") from erro

        try:
            with httpx.Client(
                base_url=url_api,
                timeout=httpx.Timeout(TIMEOUT_SEGUNDOS),
            ) as cliente:
                resposta = cliente.post(f"/v1/reservas/{id_reserva}/confirmar")
        except httpx.RequestError as erro:
            raise AssertionError(
                f"A confirmação concorrente {indice} falhou: {type(erro).__name__}."
            ) from erro
        return resposta.status_code, resposta.json()

    with ThreadPoolExecutor(max_workers=TOTAL_REQUISICOES) as executor:
        return list(executor.map(confirmar, range(TOTAL_REQUISICOES)))


def test_vinte_confirmacoes_simultaneas_devolvem_o_mesmo_pedido(
    cliente_http: httpx.Client,
    url_api: str,
    banco_mongo: Database[dict[str, Any]],
) -> None:
    servidor_mongo = banco_mongo.client.admin.command("hello")
    assert "setName" not in servidor_mongo
    reserva = criar_reserva(
        cliente_http,
        [{"sku": "QND-001", "quantidade": 2}],
    )
    estado_reservado = obter_estado(banco_mongo)
    disponibilidade_reservada = {
        livro["sku"]: livro["disponivel"] for livro in estado_reservado["livros"]
    }

    resultados = confirmar_simultaneamente(url_api, reserva["id"])

    assert Counter(status for status, _corpo in resultados) == Counter({200: 19, 201: 1})
    corpos = [corpo for _status, corpo in resultados]
    assert all(corpo == corpos[0] for corpo in corpos)
    assert ObjectId.is_valid(corpos[0]["id"])
    estado = obter_estado(banco_mongo)
    assert len(estado["pedidos"]) == 1
    assert len(estado["reservas"]) == 1
    assert estado["reservas"][0]["status"] == "confirmada"
    assert estado["reservas"][0]["pedido_id"] == corpos[0]["id"]
    assert {livro["sku"]: livro["disponivel"] for livro in estado["livros"]} == (
        disponibilidade_reservada
    )
    conferir_invariantes(estado)


def test_confirmacao_repetida_depois_do_prazo_antigo_nao_expira(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
) -> None:
    reserva = criar_reserva(
        cliente_http,
        [{"sku": "QND-005", "quantidade": 1}],
    )
    limite = ler_snapshot_feira(banco_mongo["feiras"]).agora + timedelta(seconds=0.3)
    definir_expiracao(banco_mongo, reserva["id"], limite)
    primeira = cliente_http.post(f"/v1/reservas/{reserva['id']}/confirmar")
    assert primeira.status_code == 201
    esperar_hora_mongo(banco_mongo, limite)

    repeticao = cliente_http.post(f"/v1/reservas/{reserva['id']}/confirmar")

    assert repeticao.status_code == 200
    assert repeticao.json() == primeira.json()
    estado = obter_estado(banco_mongo)
    assert len(estado["pedidos"]) == 1
    assert estado["reservas"][0]["status"] == "confirmada"
    assert livro_por_sku(estado, "QND-005")["disponivel"] == 0
    conferir_invariantes(estado)


def test_confirmacao_iniciada_antes_do_prazo_nao_publica_depois_de_vencer(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
) -> None:
    reserva = criar_reserva(
        cliente_http,
        [{"sku": "QND-005", "quantidade": 1}],
    )
    limite = ler_snapshot_feira(banco_mongo["feiras"]).agora + timedelta(seconds=1)
    definir_expiracao(banco_mongo, reserva["id"], limite)
    id_pedido = str(ObjectId())
    horas_observadas: list[datetime] = []

    def confirmar_e_pausar(estado: dict[str, Any], agora: datetime) -> None:
        horas_observadas.append(agora)
        confirmar_reserva(estado, reserva["id"], id_pedido, agora)
        if len(horas_observadas) == 1:
            segundos_ate_vencer = (limite - agora).total_seconds()
            sleep(max(segundos_ate_vencer + 0.05, 0.05))

    with pytest.raises(ErroNegocio) as erro:
        executar_com_cas(banco_mongo, confirmar_e_pausar)

    assert erro.value.status_http == 410
    assert erro.value.codigo == "reserva_expirada"
    assert len(horas_observadas) == 2
    assert horas_observadas[0] < limite <= horas_observadas[1]
    estado = obter_estado(banco_mongo)
    assert estado["pedidos"] == []
    assert estado["reservas"][0]["status"] == "expirada"
    assert livro_por_sku(estado, "QND-005")["disponivel"] == 1
    conferir_invariantes(estado)


@pytest.mark.parametrize("rodada", range(3))
def test_corrida_entre_confirmacao_e_leitura_que_expira_preserva_invariantes(
    cliente_http: httpx.Client,
    url_api: str,
    banco_mongo: Database[dict[str, Any]],
    rodada: int,
) -> None:
    reserva = criar_reserva(
        cliente_http,
        [{"sku": "QND-005", "quantidade": 1}],
    )
    limite = ler_snapshot_feira(banco_mongo["feiras"]).agora + timedelta(seconds=0.5)
    definir_expiracao(banco_mongo, reserva["id"], limite)
    barreira = Barrier(2)

    def fazer_requisicao(caminho: str, instante: datetime) -> httpx.Response:
        try:
            barreira.wait(timeout=TIMEOUT_SEGUNDOS)
        except BrokenBarrierError as erro:
            raise AssertionError("A barreira da corrida temporal expirou.") from erro
        esperar_hora_mongo(banco_mongo, instante)
        with httpx.Client(
            base_url=url_api,
            timeout=httpx.Timeout(TIMEOUT_SEGUNDOS),
        ) as cliente:
            return cliente.request("POST" if caminho.endswith("confirmar") else "GET", caminho)

    with ThreadPoolExecutor(max_workers=2) as executor:
        tentativa_confirmar = executor.submit(
            fazer_requisicao,
            f"/v1/reservas/{reserva['id']}/confirmar",
            limite - timedelta(milliseconds=10),
        )
        leitura = executor.submit(
            fazer_requisicao,
            f"/v1/reservas/{reserva['id']}",
            limite,
        )
        resposta_confirmar = tentativa_confirmar.result(timeout=TIMEOUT_SEGUNDOS)
        resposta_leitura = leitura.result(timeout=TIMEOUT_SEGUNDOS)

    assert resposta_leitura.status_code == 200
    estado = obter_estado(banco_mongo)
    conferir_invariantes(estado)
    if estado["pedidos"]:
        assert resposta_confirmar.status_code == 201, f"Falha na rodada {rodada}."
        assert estado["reservas"][0]["status"] == "confirmada"
        assert resposta_leitura.json()["status"] == "confirmada"
        assert livro_por_sku(estado, "QND-005")["disponivel"] == 0
    else:
        assert resposta_confirmar.status_code == 410, f"Falha na rodada {rodada}."
        assert resposta_confirmar.json()["erro"]["codigo"] == "reserva_expirada"
        assert estado["reservas"][0]["status"] == "expirada"
        assert resposta_leitura.json()["status"] == "expirada"
        assert livro_por_sku(estado, "QND-005")["disponivel"] == 1
