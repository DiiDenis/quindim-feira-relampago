from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
from bson import ObjectId
from pymongo.database import Database

pytestmark = [pytest.mark.integracao, pytest.mark.negocio]


def obter_estado(banco_mongo: Database[dict[str, Any]]) -> dict[str, Any]:
    estado = banco_mongo["feiras"].find_one({"_id": "principal"})
    assert estado is not None
    return estado


def livro_por_sku(estado: dict[str, Any], sku: str) -> dict[str, Any]:
    return next(livro for livro in estado["livros"] if livro["sku"] == sku)


def interpretar_data_utc(valor: str) -> datetime:
    assert valor.endswith("Z")
    return datetime.fromisoformat(valor.replace("Z", "+00:00"))


def test_cria_reserva_e_persiste_cesta_inteira(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
) -> None:
    resposta = cliente_http.post(
        "/v1/reservas",
        json={
            "cliente_id": "cliente-http",
            "itens": [
                {"sku": "QND-001", "quantidade": 2},
                {"sku": "QND-004", "quantidade": 1},
            ],
        },
    )

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert set(corpo) == {
        "id",
        "cliente_id",
        "status",
        "itens",
        "criado_em",
        "expira_em",
    }
    assert ObjectId.is_valid(corpo["id"])
    assert corpo["cliente_id"] == "cliente-http"
    assert corpo["status"] == "ativa"
    assert corpo["itens"] == [
        {"sku": "QND-001", "quantidade": 2, "preco_centavos": 3990},
        {"sku": "QND-004", "quantidade": 1, "preco_centavos": 8990},
    ]
    criado_em = interpretar_data_utc(corpo["criado_em"])
    expira_em = interpretar_data_utc(corpo["expira_em"])
    assert expira_em - criado_em == timedelta(seconds=900)

    estado = obter_estado(banco_mongo)
    assert estado["versao"] == 1
    assert livro_por_sku(estado, "QND-001")["disponivel"] == 8
    assert livro_por_sku(estado, "QND-004")["disponivel"] == 2
    assert len(estado["reservas"]) == 1
    assert estado["reservas"][0]["id"] == corpo["id"]
    assert estado["reservas"][0]["criado_em"] == criado_em
    assert estado["reservas"][0]["expira_em"] == expira_em


def test_entrada_invalida_nao_modifica_estado(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
) -> None:
    estado_antes = obter_estado(banco_mongo)

    resposta = cliente_http.post(
        "/v1/reservas",
        json={
            "cliente_id": "cliente-http",
            "itens": [
                {
                    "sku": "QND-001",
                    "quantidade": 1,
                    "preco_centavos": 1,
                }
            ],
        },
    )

    assert resposta.status_code == 400
    assert resposta.json()["erro"]["codigo"] == "requisicao_invalida"
    assert obter_estado(banco_mongo) == estado_antes


def test_sku_desconhecido_retorna_404_sem_criar_reserva(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
) -> None:
    estado_antes = obter_estado(banco_mongo)

    resposta = cliente_http.post(
        "/v1/reservas",
        json={
            "cliente_id": "cliente-http",
            "itens": [{"sku": "SKU-INEXISTENTE", "quantidade": 1}],
        },
    )

    assert resposta.status_code == 404
    assert resposta.json() == {
        "erro": {
            "codigo": "nao_encontrado",
            "mensagem": "Livro não encontrado.",
            "detalhes": {},
        }
    }
    assert obter_estado(banco_mongo) == estado_antes


def test_segundo_item_sem_estoque_nao_reserva_o_primeiro(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
) -> None:
    resultado = banco_mongo["feiras"].update_one(
        {"_id": "principal"},
        {"$set": {"livros.4.disponivel": 0}},
    )
    assert resultado.modified_count == 1
    estado_antes = deepcopy(obter_estado(banco_mongo))

    resposta = cliente_http.post(
        "/v1/reservas",
        json={
            "cliente_id": "cliente-http",
            "itens": [
                {"sku": "QND-001", "quantidade": 3},
                {"sku": "QND-005", "quantidade": 1},
            ],
        },
    )

    assert resposta.status_code == 409
    assert resposta.json() == {
        "erro": {
            "codigo": "estoque_insuficiente",
            "mensagem": "Estoque insuficiente.",
            "detalhes": {"skus": ["QND-005"]},
        }
    }
    assert obter_estado(banco_mongo) == estado_antes
