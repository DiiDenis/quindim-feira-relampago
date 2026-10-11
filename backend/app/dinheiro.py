"""Cálculos monetários do domínio usando somente centavos inteiros."""


def calcular_desconto(subtotal_centavos: int, total_unidades: int) -> int:
    """Calcula o desconto progressivo com arredondamento comercial."""
    if isinstance(subtotal_centavos, bool) or not isinstance(subtotal_centavos, int):
        raise TypeError("O subtotal em centavos deve ser um inteiro.")
    if subtotal_centavos < 0:
        raise ValueError("O subtotal em centavos não pode ser negativo.")
    if isinstance(total_unidades, bool) or not isinstance(total_unidades, int):
        raise TypeError("O total de unidades deve ser um inteiro.")
    if total_unidades < 1:
        raise ValueError("O total de unidades deve ser positivo.")

    if total_unidades <= 2:
        percentual = 0
    elif total_unidades <= 4:
        percentual = 10
    else:
        percentual = 15

    return (subtotal_centavos * percentual + 50) // 100
