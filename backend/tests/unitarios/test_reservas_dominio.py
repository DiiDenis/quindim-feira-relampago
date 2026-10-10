from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.erros import ErroNegocio
from app.reservas import ReservaEntrada, reservar_itens, validar_e_normalizar_entrada_reserva
from app.seed import criar_estado_inicial

AGORA = datetime(2026, 10, 10, 15, 30, tzinfo=UTC)
ID_RESERVA = "68e91f682eaeb2123b830001"


def entrada_reserva(*itens: tuple[str, int]) -> ReservaEntrada:
    return validar_e_normalizar_entrada_reserva(
        {
            "cliente_id": "cliente-001",
            "itens": [{"sku": sku, "quantidade": quantidade} for sku, quantidade in itens],
        }
    )


def livro_por_sku(estado: dict[str, Any], sku: str) -> dict[str, Any]:
    return next(livro for livro in estado["livros"] if livro["sku"] == sku)


def test_reserva_cesta_completa_e_copia_precos_do_estado() -> None:
    estado = criar_estado_inicial()
    livro_por_sku(estado, "QND-001")["preco_centavos"] = 4123
    entrada = entrada_reserva(("QND-001", 2), ("QND-005", 1))

    reserva = reservar_itens(estado, entrada, ID_RESERVA, AGORA, 120)

    assert reserva == {
        "id": ID_RESERVA,
        "cliente_id": "cliente-001",
        "status": "ativa",
        "itens": [
            {"sku": "QND-001", "quantidade": 2, "preco_centavos": 4123},
            {"sku": "QND-005", "quantidade": 1, "preco_centavos": 12900},
        ],
        "criado_em": AGORA,
        "expira_em": AGORA + timedelta(seconds=120),
    }
    assert livro_por_sku(estado, "QND-001")["disponivel"] == 8
    assert livro_por_sku(estado, "QND-005")["disponivel"] == 0
    assert estado["reservas"] == [reserva]
    assert "desconto_centavos" not in reserva


def test_reune_todos_os_skus_sem_estoque_na_ordem_da_cesta() -> None:
    estado = criar_estado_inicial()
    livro_por_sku(estado, "QND-004")["disponivel"] = 1
    livro_por_sku(estado, "QND-002")["disponivel"] = 0
    estado_antes = deepcopy(estado)
    entrada = entrada_reserva(("QND-004", 2), ("QND-001", 1), ("QND-002", 3))

    with pytest.raises(ErroNegocio) as captura:
        reservar_itens(estado, entrada, ID_RESERVA, AGORA, 900)

    assert captura.value.status_http == 409
    assert captura.value.codigo == "estoque_insuficiente"
    assert captura.value.detalhes == {"skus": ["QND-004", "QND-002"]}
    assert estado == estado_antes


def test_sku_desconhecido_retorna_404_sem_alterar_estado() -> None:
    estado = criar_estado_inicial()
    livro_por_sku(estado, "QND-001")["disponivel"] = 0
    estado_antes = deepcopy(estado)
    entrada = entrada_reserva(("QND-001", 1), ("SKU-INEXISTENTE", 1))

    with pytest.raises(ErroNegocio) as captura:
        reservar_itens(estado, entrada, ID_RESERVA, AGORA, 900)

    assert captura.value.status_http == 404
    assert captura.value.codigo == "nao_encontrado"
    assert estado == estado_antes


def test_segundo_item_insuficiente_nao_desconta_o_primeiro() -> None:
    estado = criar_estado_inicial()
    livro_por_sku(estado, "QND-005")["disponivel"] = 0
    estado_antes = deepcopy(estado)
    entrada = entrada_reserva(("QND-001", 3), ("QND-005", 1))

    with pytest.raises(ErroNegocio, match="Estoque insuficiente"):
        reservar_itens(estado, entrada, ID_RESERVA, AGORA, 900)

    assert estado == estado_antes
