from typing import Any

import httpx
import pytest
from pymongo.database import Database

pytestmark = [pytest.mark.integracao, pytest.mark.negocio]

LIVROS_INICIAIS = [
    {
        "sku": "QND-001",
        "titulo": "O Jardim de Dentro",
        "preco_centavos": 3990,
        "estoque": 10,
        "disponivel": 10,
    },
    {
        "sku": "QND-002",
        "titulo": "Bicho-Palavra",
        "preco_centavos": 2990,
        "estoque": 10,
        "disponivel": 10,
    },
    {
        "sku": "QND-003",
        "titulo": "A Casa que Anda",
        "preco_centavos": 1995,
        "estoque": 10,
        "disponivel": 10,
    },
    {
        "sku": "QND-004",
        "titulo": "Kit Primeira Leitura",
        "preco_centavos": 8990,
        "estoque": 3,
        "disponivel": 3,
    },
    {
        "sku": "QND-005",
        "titulo": "A Lua no Bolso — edição numerada",
        "preco_centavos": 12900,
        "estoque": 1,
        "disponivel": 1,
    },
]


def _obter_estado(banco_mongo: Database[dict[str, Any]]) -> dict[str, Any]:
    estado = banco_mongo["feiras"].find_one({"_id": "principal"})
    assert estado is not None
    return estado


def _assert_estado_inicial(estado: dict[str, Any]) -> None:
    assert estado["versao"] == 0
    assert estado["livros"] == LIVROS_INICIAIS
    assert estado["reservas"] == []
    assert estado["pedidos"] == []
    assert estado["eventos"] == []


def test_reset_sem_autenticacao_nao_altera_estado(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
    token_admin: str,
) -> None:
    estado_antes = _obter_estado(banco_mongo)

    sem_token = cliente_http.post("/v1/admin/reset")
    token_incorreto = cliente_http.post(
        "/v1/admin/reset",
        headers={"X-Admin-Token": "token-incorreto"},
    )

    for resposta in (sem_token, token_incorreto):
        assert resposta.status_code == 401
        assert resposta.json() == {
            "erro": {
                "codigo": "nao_autorizado",
                "mensagem": "Token administrativo inválido.",
                "detalhes": {},
            }
        }
        assert token_admin not in resposta.text
    assert _obter_estado(banco_mongo) == estado_antes


def test_reset_autorizado_recompoe_estado_em_um_snapshot(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
    token_admin: str,
) -> None:
    estado_antes = _obter_estado(banco_mongo)
    resultado = banco_mongo["feiras"].update_one(
        {"_id": "principal"},
        {
            "$set": {
                "livros.0.disponivel": 2,
                "reservas": [{"id": "reserva-antiga"}],
                "pedidos": [{"id": "pedido-antigo"}],
                "eventos": ["evento-antigo"],
            }
        },
    )
    assert resultado.modified_count == 1

    resposta = cliente_http.post(
        "/v1/admin/reset",
        headers={"X-Admin-Token": token_admin},
    )

    assert resposta.status_code == 204
    assert resposta.content == b""
    assert token_admin not in resposta.text
    estado_resetado = _obter_estado(banco_mongo)
    assert banco_mongo["feiras"].count_documents({}) == 1
    assert estado_resetado["geracao"] != estado_antes["geracao"]
    _assert_estado_inicial(estado_resetado)


def test_dois_resets_autorizados_mantem_estado_valido(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
    token_admin: str,
) -> None:
    respostas = []
    geracoes = []
    for _ in range(2):
        respostas.append(
            cliente_http.post(
                "/v1/admin/reset",
                headers={"X-Admin-Token": token_admin},
            )
        )
        estado = _obter_estado(banco_mongo)
        geracoes.append(estado["geracao"])
        _assert_estado_inicial(estado)

    assert all(resposta.status_code == 204 for resposta in respostas)
    assert all(resposta.content == b"" for resposta in respostas)
    assert geracoes[0] != geracoes[1]
    assert banco_mongo["feiras"].count_documents({}) == 1
