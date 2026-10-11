from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import pytest

from app.pagamentos import EventoPagamentoEntrada, processar_evento_pagamento
from app.pedidos import confirmar_reserva
from app.reservas import ReservaEntrada, reservar_itens
from app.seed import criar_estado_inicial

AGORA = datetime(2026, 10, 10, 18, 30, tzinfo=UTC)
ID_RESERVA = "68e91f682eaeb2123b830001"
ID_PEDIDO = "68e91f682eaeb2123b830010"


def preparar_pedido() -> dict[str, Any]:
    estado = criar_estado_inicial()
    entrada = ReservaEntrada.model_validate(
        {
            "cliente_id": "cliente-pagamento",
            "itens": [
                {"sku": "QND-001", "quantidade": 2},
                {"sku": "QND-005", "quantidade": 1},
            ],
        }
    )
    reservar_itens(estado, entrada, ID_RESERVA, AGORA, 900)
    confirmar_reserva(estado, ID_RESERVA, ID_PEDIDO, AGORA)
    return estado


def criar_evento(
    evento_id: str,
    tipo: Literal["pago", "recusado"],
    *,
    pedido_id: str = ID_PEDIDO,
    ocorrido_em: datetime = AGORA + timedelta(minutes=1),
) -> EventoPagamentoEntrada:
    return EventoPagamentoEntrada(
        evento_id=evento_id,
        pedido_id=pedido_id,
        tipo=tipo,
        ocorrido_em=ocorrido_em,
    )


def livro_por_sku(estado: dict[str, Any], sku: str) -> dict[str, Any]:
    return next(livro for livro in estado["livros"] if livro["sku"] == sku)


def conferir_invariantes(estado: dict[str, Any]) -> None:
    reservadas: Counter[str] = Counter()
    comprometidas: Counter[str] = Counter()
    for reserva in estado["reservas"]:
        if reserva["status"] == "ativa":
            for item in reserva["itens"]:
                reservadas[item["sku"]] += item["quantidade"]
    for pedido in estado["pedidos"]:
        if pedido["status"] in {"aguardando_pagamento", "pago"}:
            for linha in pedido["linhas"]:
                comprometidas[linha["sku"]] += linha["quantidade"]

    for livro in estado["livros"]:
        sku = livro["sku"]
        assert 0 <= livro["disponivel"] <= livro["estoque"]
        assert livro["estoque"] == (livro["disponivel"] + reservadas[sku] + comprometidas[sku])


def test_pagamento_aprovado_marca_pedido_sem_devolver_estoque() -> None:
    estado = preparar_pedido()
    disponibilidade_antes = [livro["disponivel"] for livro in estado["livros"]]
    evento = criar_evento("evt-pago", "pago")

    consumido = processar_evento_pagamento(estado, evento)

    assert consumido is True
    assert estado["eventos"] == [evento.model_dump()]
    assert estado["pedidos"][0]["status"] == "pago"
    assert estado["pedidos"][0]["pago_em"] == evento.ocorrido_em
    assert [livro["disponivel"] for livro in estado["livros"]] == disponibilidade_antes
    assert estado["reservas"][0]["status"] == "confirmada"
    conferir_invariantes(estado)


def test_pagamento_recusado_cancela_e_devolve_cada_unidade() -> None:
    estado = preparar_pedido()
    evento = criar_evento("evt-recusado", "recusado")

    consumido = processar_evento_pagamento(estado, evento)

    assert consumido is True
    assert estado["pedidos"][0]["status"] == "cancelado"
    assert estado["pedidos"][0]["pago_em"] is None
    assert livro_por_sku(estado, "QND-001")["disponivel"] == 10
    assert livro_por_sku(estado, "QND-005")["disponivel"] == 1
    assert estado["reservas"][0]["status"] == "confirmada"
    conferir_invariantes(estado)


def test_mesmo_evento_repetido_nao_eh_aplicado_novamente() -> None:
    estado = preparar_pedido()
    evento = criar_evento("evt-duplicado", "recusado")
    processar_evento_pagamento(estado, evento)
    estado_apos_primeiro = deepcopy(estado)

    consumido = processar_evento_pagamento(estado, evento)

    assert consumido is False
    assert estado == estado_apos_primeiro
    conferir_invariantes(estado)


def test_eventos_distintos_de_recusa_nao_devolvem_estoque_duas_vezes() -> None:
    estado = preparar_pedido()
    processar_evento_pagamento(estado, criar_evento("evt-recusa-1", "recusado"))

    consumido = processar_evento_pagamento(
        estado,
        criar_evento("evt-recusa-2", "recusado"),
    )

    assert consumido is True
    assert len(estado["eventos"]) == 2
    assert estado["pedidos"][0]["status"] == "cancelado"
    assert livro_por_sku(estado, "QND-001")["disponivel"] == 10
    assert livro_por_sku(estado, "QND-005")["disponivel"] == 1
    conferir_invariantes(estado)


def test_pedido_inexistente_ainda_consome_evento() -> None:
    estado = criar_estado_inicial()
    evento = criar_evento(
        "evt-pedido-inexistente",
        "pago",
        pedido_id="pedido-inexistente",
    )

    consumido = processar_evento_pagamento(estado, evento)

    assert consumido is True
    assert estado["eventos"] == [evento.model_dump()]
    assert estado["pedidos"] == []
    conferir_invariantes(estado)


def test_mesmo_id_com_conteudo_diferente_preserva_primeiro_evento() -> None:
    estado = preparar_pedido()
    primeiro = criar_evento("evt-conflitante", "pago")
    processar_evento_pagamento(estado, primeiro)
    estado_apos_primeiro = deepcopy(estado)
    conflitante = criar_evento(
        "evt-conflitante",
        "recusado",
        pedido_id="outro-pedido",
        ocorrido_em=AGORA - timedelta(days=1),
    )

    consumido = processar_evento_pagamento(estado, conflitante)

    assert consumido is False
    assert estado == estado_apos_primeiro
    assert estado["eventos"] == [primeiro.model_dump()]
    conferir_invariantes(estado)


@pytest.mark.parametrize("status_terminal", ["pago", "cancelado"])
@pytest.mark.parametrize("novo_tipo", ["pago", "recusado"])
def test_status_terminal_nao_muda_com_evento_posterior_ou_data_mais_antiga(
    status_terminal: Literal["pago", "cancelado"],
    novo_tipo: Literal["pago", "recusado"],
) -> None:
    estado = preparar_pedido()
    tipo_inicial: Literal["pago", "recusado"] = "pago" if status_terminal == "pago" else "recusado"
    processar_evento_pagamento(estado, criar_evento("evt-inicial", tipo_inicial))
    pedido_antes = deepcopy(estado["pedidos"][0])
    livros_antes = deepcopy(estado["livros"])

    consumido = processar_evento_pagamento(
        estado,
        criar_evento(
            "evt-posterior",
            novo_tipo,
            ocorrido_em=AGORA - timedelta(days=1),
        ),
    )

    assert consumido is True
    assert len(estado["eventos"]) == 2
    assert estado["pedidos"][0] == pedido_antes
    assert estado["livros"] == livros_antes
    assert estado["reservas"][0]["status"] == "confirmada"
    conferir_invariantes(estado)
