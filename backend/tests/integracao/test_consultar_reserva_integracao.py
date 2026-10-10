from typing import Any

import httpx
import pytest
from pymongo.database import Database

pytestmark = [pytest.mark.integracao, pytest.mark.negocio]


def criar_reserva(cliente_http: httpx.Client) -> dict[str, Any]:
    resposta = cliente_http.post(
        "/v1/reservas",
        json={
            "cliente_id": "cliente-consulta",
            "itens": [
                {"sku": "QND-002", "quantidade": 1},
                {"sku": "QND-003", "quantidade": 2},
            ],
        },
    )
    assert resposta.status_code == 201
    return resposta.json()


def test_consulta_reserva_com_mesmo_contrato_da_criacao(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
) -> None:
    reserva_criada = criar_reserva(cliente_http)
    resultado = banco_mongo["feiras"].update_one(
        {"_id": "principal", "reservas.id": reserva_criada["id"]},
        {"$set": {"reservas.$.pedido_id": "interno-nao-publico"}},
    )
    assert resultado.modified_count == 1

    resposta = cliente_http.get(f"/v1/reservas/{reserva_criada['id']}")

    assert resposta.status_code == 200
    reserva_consultada = resposta.json()
    assert set(reserva_consultada) == {
        "id",
        "cliente_id",
        "status",
        "itens",
        "criado_em",
        "expira_em",
    }
    assert reserva_consultada == reserva_criada
    assert "pedido_id" not in reserva_consultada


@pytest.mark.parametrize("id_reserva", ["nao-e-id", "f" * 24])
def test_consulta_id_invalido_ou_inexistente_retorna_404(
    cliente_http: httpx.Client,
    id_reserva: str,
) -> None:
    resposta = cliente_http.get(f"/v1/reservas/{id_reserva}")

    assert resposta.status_code == 404
    assert resposta.json() == {
        "erro": {
            "codigo": "nao_encontrado",
            "mensagem": "Recurso não encontrado.",
            "detalhes": {},
        }
    }
