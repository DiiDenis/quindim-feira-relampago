from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.expiracao import expirar_reservas
from app.seed import criar_estado_inicial

EXPIRA_EM = datetime(2026, 10, 10, 16, 0, tzinfo=UTC)


def livro_por_sku(estado: dict[str, Any], sku: str) -> dict[str, Any]:
    return next(livro for livro in estado["livros"] if livro["sku"] == sku)


def registrar_reserva(
    estado: dict[str, Any],
    id_reserva: str,
    status: str,
    expira_em: datetime,
    *itens: tuple[str, int],
) -> dict[str, Any]:
    itens_reserva = []
    for sku, quantidade in itens:
        livro = livro_por_sku(estado, sku)
        if status != "expirada":
            livro["disponivel"] -= quantidade
        itens_reserva.append(
            {
                "sku": sku,
                "quantidade": quantidade,
                "preco_centavos": livro["preco_centavos"],
            }
        )

    reserva = {
        "id": id_reserva,
        "cliente_id": f"cliente-{id_reserva}",
        "status": status,
        "itens": itens_reserva,
        "criado_em": expira_em - timedelta(minutes=15),
        "expira_em": expira_em,
    }
    estado["reservas"].append(reserva)
    return reserva


@pytest.mark.parametrize(
    ("agora", "status_esperado", "disponivel_001", "disponivel_005"),
    [
        (EXPIRA_EM - timedelta(microseconds=1), "ativa", 8, 0),
        (EXPIRA_EM, "expirada", 10, 1),
        (EXPIRA_EM + timedelta(microseconds=1), "expirada", 10, 1),
    ],
)
def test_expira_na_igualdade_e_depois_mas_nao_antes(
    agora: datetime,
    status_esperado: str,
    disponivel_001: int,
    disponivel_005: int,
) -> None:
    estado = criar_estado_inicial()
    estoques_antes = {livro["sku"]: livro["estoque"] for livro in estado["livros"]}
    reserva = registrar_reserva(
        estado,
        "fronteira",
        "ativa",
        EXPIRA_EM,
        ("QND-001", 2),
        ("QND-005", 1),
    )

    expirar_reservas(estado, agora)

    assert reserva["status"] == status_esperado
    assert livro_por_sku(estado, "QND-001")["disponivel"] == disponivel_001
    assert livro_por_sku(estado, "QND-005")["disponivel"] == disponivel_005
    assert {livro["sku"]: livro["estoque"] for livro in estado["livros"]} == estoques_antes


def test_segunda_execucao_nao_devolve_estoque_novamente() -> None:
    estado = criar_estado_inicial()
    registrar_reserva(
        estado,
        "idempotente",
        "ativa",
        EXPIRA_EM,
        ("QND-001", 2),
        ("QND-003", 1),
    )

    expirar_reservas(estado, EXPIRA_EM)
    estado_depois_da_primeira = deepcopy(estado)
    expirar_reservas(estado, EXPIRA_EM + timedelta(hours=1))

    assert estado == estado_depois_da_primeira


def test_expira_somente_ativas_e_preserva_capacidade_total() -> None:
    estado = criar_estado_inicial()
    reserva_ativa = registrar_reserva(
        estado,
        "ativa-vencida",
        "ativa",
        EXPIRA_EM - timedelta(seconds=1),
        ("QND-001", 2),
        ("QND-002", 1),
    )
    reserva_confirmada = registrar_reserva(
        estado,
        "confirmada-vencida",
        "confirmada",
        EXPIRA_EM - timedelta(minutes=1),
        ("QND-001", 3),
        ("QND-002", 1),
    )
    reserva_expirada = registrar_reserva(
        estado,
        "ja-expirada",
        "expirada",
        EXPIRA_EM - timedelta(minutes=2),
        ("QND-001", 1),
        ("QND-002", 1),
    )

    expirar_reservas(estado, EXPIRA_EM)

    assert reserva_ativa["status"] == "expirada"
    assert reserva_confirmada["status"] == "confirmada"
    assert reserva_expirada["status"] == "expirada"
    for livro in estado["livros"]:
        quantidade_alocada = sum(
            item["quantidade"]
            for reserva in estado["reservas"]
            if reserva["status"] in {"ativa", "confirmada"}
            for item in reserva["itens"]
            if item["sku"] == livro["sku"]
        )
        assert livro["disponivel"] + quantidade_alocada == livro["estoque"]


def test_rejeita_agora_sem_fuso() -> None:
    estado = criar_estado_inicial()

    with pytest.raises(ValueError, match="fuso UTC"):
        expirar_reservas(estado, datetime(2026, 10, 10, 16, 0))
