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


def disputar_reservas(
    url_api: str,
    itens: list[dict[str, Any]],
) -> list[tuple[int, dict[str, Any]]]:
    barreira = Barrier(TOTAL_REQUISICOES)

    def reservar(indice: int) -> tuple[int, dict[str, Any]]:
        try:
            barreira.wait(timeout=TIMEOUT_SEGUNDOS)
        except BrokenBarrierError as erro:
            raise AssertionError("A barreira das 20 requisições expirou.") from erro

        try:
            with httpx.Client(
                base_url=url_api,
                timeout=httpx.Timeout(TIMEOUT_SEGUNDOS),
            ) as cliente:
                resposta = cliente.post(
                    "/v1/reservas",
                    json={
                        "cliente_id": f"cliente-concorrente-{indice}",
                        "itens": itens,
                    },
                )
        except httpx.RequestError as erro:
            raise AssertionError(
                f"A requisição concorrente {indice} falhou: {type(erro).__name__}."
            ) from erro

        return resposta.status_code, resposta.json()

    with ThreadPoolExecutor(max_workers=TOTAL_REQUISICOES) as executor:
        return list(executor.map(reservar, range(TOTAL_REQUISICOES)))


def verificar_respostas(
    resultados: list[tuple[int, dict[str, Any]]],
    sucessos: int,
    conflitos: int,
) -> None:
    contagem = Counter(status for status, _corpo in resultados)
    assert contagem == Counter({201: sucessos, 409: conflitos})
    for status, corpo in resultados:
        if status == 409:
            assert corpo["erro"]["codigo"] == "estoque_insuficiente"


def test_vinte_clientes_disputam_ultima_unidade(
    url_api: str,
    banco_mongo: Database[dict[str, Any]],
) -> None:
    servidor_mongo = banco_mongo.client.admin.command("hello")
    assert "setName" not in servidor_mongo

    resultados = disputar_reservas(
        url_api,
        [{"sku": "QND-005", "quantidade": 1}],
    )

    verificar_respostas(resultados, sucessos=1, conflitos=19)
    estado = obter_estado(banco_mongo)
    assert livro_por_sku(estado, "QND-005")["disponivel"] == 0
    assert len(estado["reservas"]) == 1
    assert estado["reservas"][0]["itens"] == [
        {"sku": "QND-005", "quantidade": 1, "preco_centavos": 12900}
    ]


def test_cesta_perdedora_nao_desconta_primeiro_item(
    url_api: str,
    banco_mongo: Database[dict[str, Any]],
) -> None:
    resultados = disputar_reservas(
        url_api,
        [
            {"sku": "QND-001", "quantidade": 1},
            {"sku": "QND-005", "quantidade": 1},
        ],
    )

    verificar_respostas(resultados, sucessos=1, conflitos=19)
    estado = obter_estado(banco_mongo)
    assert livro_por_sku(estado, "QND-001")["disponivel"] == 9
    assert livro_por_sku(estado, "QND-005")["disponivel"] == 0
    assert len(estado["reservas"]) == 1
    assert [item["sku"] for item in estado["reservas"][0]["itens"]] == [
        "QND-001",
        "QND-005",
    ]


@pytest.mark.parametrize("rodada", range(3))
def test_vinte_clientes_disputam_dez_unidades_em_varias_rodadas(
    url_api: str,
    banco_mongo: Database[dict[str, Any]],
    rodada: int,
) -> None:
    resultados = disputar_reservas(
        url_api,
        [{"sku": "QND-001", "quantidade": 1}],
    )

    verificar_respostas(resultados, sucessos=10, conflitos=10)
    estado = obter_estado(banco_mongo)
    assert livro_por_sku(estado, "QND-001")["disponivel"] == 0
    assert len(estado["reservas"]) == 10
    assert (
        sum(
            item["quantidade"]
            for reserva in estado["reservas"]
            for item in reserva["itens"]
            if item["sku"] == "QND-001"
        )
        == 10
    ), f"Invariante violada na rodada {rodada}."
