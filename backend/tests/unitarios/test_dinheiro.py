from typing import Any

import pytest

from app.dinheiro import calcular_desconto, ratear_desconto


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


@pytest.mark.parametrize(
    ("valores_linhas", "desconto_total", "rateio_esperado"),
    [
        ([3990, 2990, 1995], 898, [399, 299, 200]),
        ([15, 15, 15], 5, [2, 2, 1]),
        ([3990, 2990, 1995], 0, [0, 0, 0]),
        ([500], 123, [123]),
        ([1995, 3990, 2990], 898, [200, 399, 299]),
        ([100, 200], 3, [1, 2]),
        ([1, 1], 1, [1, 0]),
        ([25, 25, 50], 7, [2, 2, 3]),
    ],
)
def test_rateia_desconto_total_sem_perder_centavos_ou_ordem(
    valores_linhas: list[int],
    desconto_total: int,
    rateio_esperado: list[int],
) -> None:
    rateio = ratear_desconto(valores_linhas, desconto_total)

    assert rateio == rateio_esperado
    assert sum(rateio) == desconto_total
    assert all(
        0 <= desconto <= valor for desconto, valor in zip(rateio, valores_linhas, strict=True)
    )


@pytest.mark.parametrize(
    ("valores_linhas", "desconto_total", "tipo_erro", "mensagem"),
    [
        ([], 0, ValueError, "ao menos uma linha"),
        ([0], 0, ValueError, "valores das linhas devem ser positivos"),
        ([-1, 100], 10, ValueError, "valores das linhas devem ser positivos"),
        ([100], -1, ValueError, "entre zero e o subtotal"),
        ([100], 101, ValueError, "entre zero e o subtotal"),
        ([100.0], 10, TypeError, "valores das linhas devem ser inteiros"),
        ([True], 1, TypeError, "valores das linhas devem ser inteiros"),
        ([100], 10.0, TypeError, "desconto total deve ser um inteiro"),
        ([100], True, TypeError, "desconto total deve ser um inteiro"),
    ],
)
def test_rateio_rejeita_entradas_internas_impossiveis(
    valores_linhas: Any,
    desconto_total: Any,
    tipo_erro: type[Exception],
    mensagem: str,
) -> None:
    with pytest.raises(tipo_erro, match=mensagem):
        ratear_desconto(valores_linhas, desconto_total)
