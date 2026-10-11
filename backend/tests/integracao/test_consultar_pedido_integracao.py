from typing import Any

import httpx
import pytest
from pymongo.database import Database

pytestmark = [pytest.mark.integracao, pytest.mark.negocio]


def criar_e_confirmar_pedido(cliente_http: httpx.Client) -> dict[str, Any]:
    reserva = cliente_http.post(
        "/v1/reservas",
        json={
            "cliente_id": "cliente-consulta-pedido",
            "itens": [
                {"sku": "QND-001", "quantidade": 1},
                {"sku": "QND-002", "quantidade": 1},
                {"sku": "QND-003", "quantidade": 1},
            ],
        },
    )
    assert reserva.status_code == 201
    confirmacao = cliente_http.post(f"/v1/reservas/{reserva.json()['id']}/confirmar")
    assert confirmacao.status_code == 201
    return confirmacao.json()


def test_consulta_reproduz_contrato_completo_da_confirmacao(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
) -> None:
    pedido_criado = criar_e_confirmar_pedido(cliente_http)
    resultado = banco_mongo["feiras"].update_one(
        {"_id": "principal", "pedidos.id": pedido_criado["id"]},
        {
            "$set": {
                "pedidos.$.campo_interno": "nao-publicar",
                "pedidos.0.linhas.0.campo_interno": "nao-publicar",
            }
        },
    )
    assert resultado.modified_count == 1

    resposta = cliente_http.get(f"/v1/pedidos/{pedido_criado['id']}")

    assert resposta.status_code == 200
    pedido_consultado = resposta.json()
    assert pedido_consultado == pedido_criado
    assert set(pedido_consultado) == {
        "id",
        "reserva_id",
        "cliente_id",
        "status",
        "linhas",
        "subtotal_centavos",
        "desconto_centavos",
        "total_centavos",
        "criado_em",
        "pago_em",
    }
    assert set(pedido_consultado["linhas"][0]) == {
        "sku",
        "quantidade",
        "preco_centavos",
        "valor_centavos",
        "desconto_centavos",
        "liquido_centavos",
    }
    assert pedido_consultado["linhas"] == [
        {
            "sku": "QND-001",
            "quantidade": 1,
            "preco_centavos": 3990,
            "valor_centavos": 3990,
            "desconto_centavos": 399,
            "liquido_centavos": 3591,
        },
        {
            "sku": "QND-002",
            "quantidade": 1,
            "preco_centavos": 2990,
            "valor_centavos": 2990,
            "desconto_centavos": 299,
            "liquido_centavos": 2691,
        },
        {
            "sku": "QND-003",
            "quantidade": 1,
            "preco_centavos": 1995,
            "valor_centavos": 1995,
            "desconto_centavos": 200,
            "liquido_centavos": 1795,
        },
    ]
    assert pedido_consultado["subtotal_centavos"] == 8975
    assert pedido_consultado["desconto_centavos"] == 898
    assert pedido_consultado["total_centavos"] == 8077
    assert pedido_consultado["pago_em"] is None
    assert pedido_consultado["criado_em"].endswith("Z")
    assert "campo_interno" not in pedido_consultado
    assert "campo_interno" not in pedido_consultado["linhas"][0]

    estado = banco_mongo["feiras"].find_one({"_id": "principal"})
    assert estado is not None
    pedido_persistido = estado["pedidos"][0]
    assert pedido_persistido["id"] == pedido_consultado["id"]
    assert pedido_persistido["subtotal_centavos"] == pedido_consultado["subtotal_centavos"]
    assert pedido_persistido["desconto_centavos"] == pedido_consultado["desconto_centavos"]
    assert pedido_persistido["total_centavos"] == pedido_consultado["total_centavos"]


@pytest.mark.parametrize("id_pedido", ["nao-e-id", "f" * 24])
def test_consulta_id_invalido_ou_inexistente_retorna_404(
    cliente_http: httpx.Client,
    id_pedido: str,
) -> None:
    resposta = cliente_http.get(f"/v1/pedidos/{id_pedido}")

    assert resposta.status_code == 404
    assert resposta.json() == {
        "erro": {
            "codigo": "nao_encontrado",
            "mensagem": "Recurso não encontrado.",
            "detalhes": {},
        }
    }
