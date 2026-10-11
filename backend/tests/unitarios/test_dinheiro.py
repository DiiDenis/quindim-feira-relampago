from typing import Any

import pytest

from app.dinheiro import calcular_desconto


@pytest.mark.parametrize(
    ("subtotal_centavos", "total_unidades", "desconto_esperado"),
    [
        (1000, 1, 0),
        (1000, 2, 0),
        (1000, 3, 100),
        (1000, 4, 100),
        (1000, 5, 150),
        (0, 5, 0),
        (344, 3, 34),
        (345, 3, 35),
        (346, 3, 35),
        (8975, 3, 898),
    ],
)
def test_calcula_desconto_progressivo_com_arredondamento_comercial(
    subtotal_centavos: int,
    total_unidades: int,
    desconto_esperado: int,
) -> None:
    desconto = calcular_desconto(subtotal_centavos, total_unidades)

    assert desconto == desconto_esperado
    assert isinstance(desconto, int)


@pytest.mark.parametrize(
    ("subtotal_centavos", "total_unidades", "mensagem"),
    [
        (-1, 1, "subtotal em centavos não pode ser negativo"),
        (100, 0, "total de unidades deve ser positivo"),
        (100, -1, "total de unidades deve ser positivo"),
    ],
)
def test_rejeita_valores_internos_impossiveis(
    subtotal_centavos: int,
    total_unidades: int,
    mensagem: str,
) -> None:
    with pytest.raises(ValueError, match=mensagem):
        calcular_desconto(subtotal_centavos, total_unidades)


@pytest.mark.parametrize(
    ("subtotal_centavos", "total_unidades", "mensagem"),
    [
        (100.0, 1, "subtotal em centavos deve ser um inteiro"),
        ("100", 1, "subtotal em centavos deve ser um inteiro"),
        (True, 1, "subtotal em centavos deve ser um inteiro"),
        (100, 1.0, "total de unidades deve ser um inteiro"),
        (100, "1", "total de unidades deve ser um inteiro"),
        (100, True, "total de unidades deve ser um inteiro"),
    ],
)
def test_rejeita_tipos_que_nao_sao_inteiros(
    subtotal_centavos: Any,
    total_unidades: Any,
    mensagem: str,
) -> None:
    with pytest.raises(TypeError, match=mensagem):
        calcular_desconto(subtotal_centavos, total_unidades)
