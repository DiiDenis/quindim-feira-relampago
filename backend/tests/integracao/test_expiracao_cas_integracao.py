from copy import deepcopy
from datetime import datetime, timedelta
from time import monotonic, sleep
from typing import Any

import httpx
import pytest
from pymongo.database import Database

from app.banco import executar_com_cas, ler_snapshot_feira, tentar_substituir_snapshot

pytestmark = [pytest.mark.integracao, pytest.mark.negocio]


def livro_por_sku(estado: dict[str, Any], sku: str) -> dict[str, Any]:
    return next(livro for livro in estado["livros"] if livro["sku"] == sku)


def criar_reserva(
    cliente_http: httpx.Client,
    cliente_id: str,
    sku: str,
    quantidade: int,
) -> dict[str, Any]:
    resposta = cliente_http.post(
        "/v1/reservas",
        json={
            "cliente_id": cliente_id,
            "itens": [{"sku": sku, "quantidade": quantidade}],
        },
    )
    assert resposta.status_code == 201
    return resposta.json()


def test_filtro_temporal_recusa_snapshot_que_venceu_sem_outro_escritor(
    banco_mongo: Database[dict[str, Any]],
) -> None:
    colecao = banco_mongo["feiras"]
    agora_inicial = ler_snapshot_feira(colecao).agora
    limite_temporal = agora_inicial + timedelta(seconds=1)
    resultado = colecao.update_one(
        {"_id": "principal"},
        {
            "$set": {
                "livros.4.disponivel": 0,
                "reservas": [
                    {
                        "id": "reserva-no-limite",
                        "cliente_id": "cliente-limite",
                        "status": "ativa",
                        "itens": [
                            {
                                "sku": "QND-005",
                                "quantidade": 1,
                                "preco_centavos": 12900,
                            }
                        ],
                        "criado_em": agora_inicial,
                        "expira_em": limite_temporal,
                    }
                ],
            }
        },
    )
    assert resultado.modified_count == 1

    snapshot_antigo = ler_snapshot_feira(colecao)
    assert snapshot_antigo.agora < limite_temporal
    candidato_antigo = deepcopy(snapshot_antigo.estado)
    candidato_antigo["eventos"].append("nao-deve-ser-salvo")

    espera_iniciada = monotonic()
    while ler_snapshot_feira(colecao).agora < limite_temporal:
        assert monotonic() - espera_iniciada < 3
        sleep(0.01)

    assert (
        tentar_substituir_snapshot(
            colecao,
            snapshot_antigo,
            candidato_antigo,
            limite_temporal,
        )
        is False
    )
    estado_final = colecao.find_one({"_id": "principal"})
    assert estado_final is not None
    assert estado_final["versao"] == snapshot_antigo.estado["versao"]
    assert estado_final["eventos"] == []


def test_cas_rele_hora_e_expira_depois_de_perder_filtro_temporal(
    banco_mongo: Database[dict[str, Any]],
) -> None:
    colecao = banco_mongo["feiras"]
    agora_inicial = ler_snapshot_feira(colecao).agora
    limite_temporal = agora_inicial + timedelta(seconds=1)
    resultado = colecao.update_one(
        {"_id": "principal"},
        {
            "$set": {
                "livros.4.disponivel": 0,
                "reservas": [
                    {
                        "id": "reserva-para-retry",
                        "cliente_id": "cliente-retry",
                        "status": "ativa",
                        "itens": [
                            {
                                "sku": "QND-005",
                                "quantidade": 1,
                                "preco_centavos": 12900,
                            }
                        ],
                        "criado_em": agora_inicial,
                        "expira_em": limite_temporal,
                    }
                ],
            }
        },
    )
    assert resultado.modified_count == 1
    horas_observadas: list[datetime] = []

    def operacao(estado: dict[str, Any], agora: datetime) -> str:
        horas_observadas.append(agora)
        if len(horas_observadas) == 1:
            segundos_ate_vencer = (limite_temporal - agora).total_seconds()
            sleep(max(segundos_ate_vencer + 0.05, 0.05))
        return estado["reservas"][0]["status"]

    status = executar_com_cas(banco_mongo, operacao)

    assert status == "expirada"
    assert len(horas_observadas) == 2
    assert horas_observadas[0] < limite_temporal <= horas_observadas[1]
    estado_final = colecao.find_one({"_id": "principal"})
    assert estado_final is not None
    assert estado_final["reservas"][0]["status"] == "expirada"
    assert livro_por_sku(estado_final, "QND-005")["disponivel"] == 1
    assert estado_final["versao"] == 1


def test_erro_de_estoque_preserva_expiracao_no_mesmo_cas(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
) -> None:
    reserva_a_expirar = criar_reserva(
        cliente_http,
        "cliente-expirado",
        "QND-001",
        2,
    )
    reserva_que_mantem_estoque = criar_reserva(
        cliente_http,
        "cliente-ativo",
        "QND-005",
        1,
    )
    colecao = banco_mongo["feiras"]
    agora = ler_snapshot_feira(colecao).agora
    resultado = colecao.update_one(
        {"_id": "principal", "reservas.id": reserva_a_expirar["id"]},
        {"$set": {"reservas.$.expira_em": agora - timedelta(seconds=1)}},
    )
    assert resultado.modified_count == 1

    resposta = cliente_http.post(
        "/v1/reservas",
        json={
            "cliente_id": "cliente-sem-estoque",
            "itens": [{"sku": "QND-005", "quantidade": 1}],
        },
    )

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "estoque_insuficiente"
    estado_final = colecao.find_one({"_id": "principal"})
    assert estado_final is not None
    reservas_por_id = {reserva["id"]: reserva for reserva in estado_final["reservas"]}
    assert reservas_por_id[reserva_a_expirar["id"]]["status"] == "expirada"
    assert reservas_por_id[reserva_que_mantem_estoque["id"]]["status"] == "ativa"
    assert len(estado_final["reservas"]) == 2
    assert livro_por_sku(estado_final, "QND-001")["disponivel"] == 10
    assert livro_por_sku(estado_final, "QND-005")["disponivel"] == 0
    assert estado_final["versao"] == 3
