from typing import Any

import pytest
from pydantic import ValidationError

from app.reservas import validar_e_normalizar_entrada_reserva


def corpo_reserva(quantidade: Any = 1) -> dict[str, Any]:
    return {
        "cliente_id": "cliente-001",
        "itens": [{"sku": "QND-001", "quantidade": quantidade}],
    }


@pytest.mark.parametrize("quantidade", [0, -1, 4, 1.0, "1", True, False])
def test_rejeita_quantidade_fora_do_contrato(quantidade: Any) -> None:
    with pytest.raises(ValidationError):
        validar_e_normalizar_entrada_reserva(corpo_reserva(quantidade))


@pytest.mark.parametrize(
    "corpo",
    [
        {"cliente_id": "cliente-001", "itens": []},
        {"cliente_id": "", "itens": [{"sku": "QND-001", "quantidade": 1}]},
        {"cliente_id": "   ", "itens": [{"sku": "QND-001", "quantidade": 1}]},
        {"cliente_id": 123, "itens": [{"sku": "QND-001", "quantidade": 1}]},
        {"cliente_id": "cliente-001", "itens": [{"sku": "", "quantidade": 1}]},
        {"cliente_id": "cliente-001", "itens": [{"sku": "   ", "quantidade": 1}]},
        {"cliente_id": "cliente-001", "itens": [{"sku": 123, "quantidade": 1}]},
    ],
)
def test_rejeita_lista_vazia_e_identificadores_invalidos(corpo: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        validar_e_normalizar_entrada_reserva(corpo)


@pytest.mark.parametrize(
    "corpo",
    [
        {
            "cliente_id": "cliente-001",
            "itens": [{"sku": "QND-001", "quantidade": 1}],
            "campo_extra": "não permitido",
        },
        {
            "cliente_id": "cliente-001",
            "itens": [
                {
                    "sku": "QND-001",
                    "quantidade": 1,
                    "campo_extra": "não permitido",
                }
            ],
        },
    ],
)
def test_rejeita_campos_extras_no_corpo_e_nos_itens(corpo: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        validar_e_normalizar_entrada_reserva(corpo)


def test_consolida_skus_repetidos_preservando_primeira_posicao() -> None:
    entrada = validar_e_normalizar_entrada_reserva(
        {
            "cliente_id": "cliente-001",
            "itens": [
                {"sku": "QND-002", "quantidade": 1},
                {"sku": "QND-001", "quantidade": 2},
                {"sku": "QND-002", "quantidade": 2},
                {"sku": "SKU-DESCONHECIDO", "quantidade": 1},
            ],
        }
    )

    assert [item.model_dump() for item in entrada.itens] == [
        {"sku": "QND-002", "quantidade": 3},
        {"sku": "QND-001", "quantidade": 2},
        {"sku": "SKU-DESCONHECIDO", "quantidade": 1},
    ]


def test_rejeita_soma_de_duplicatas_acima_do_limite() -> None:
    with pytest.raises(ValidationError, match="não pode passar de 3"):
        validar_e_normalizar_entrada_reserva(
            {
                "cliente_id": "cliente-001",
                "itens": [
                    {"sku": "QND-001", "quantidade": 2},
                    {"sku": "QND-001", "quantidade": 2},
                ],
            }
        )
