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


def ratear_desconto(valores_linhas: list[int], desconto_total: int) -> list[int]:
    """Distribui o desconto pelos maiores restos e preserva a ordem das linhas."""
    if not valores_linhas:
        raise ValueError("O rateio exige ao menos uma linha.")
    if any(isinstance(valor, bool) or not isinstance(valor, int) for valor in valores_linhas):
        raise TypeError("Os valores das linhas devem ser inteiros.")
    if any(valor <= 0 for valor in valores_linhas):
        raise ValueError("Os valores das linhas devem ser positivos.")
    if isinstance(desconto_total, bool) or not isinstance(desconto_total, int):
        raise TypeError("O desconto total deve ser um inteiro.")

    subtotal = sum(valores_linhas)
    if desconto_total < 0 or desconto_total > subtotal:
        raise ValueError("O desconto total deve estar entre zero e o subtotal.")

    descontos: list[int] = []
    restos: list[int] = []
    for valor_linha in valores_linhas:
        base, resto = divmod(desconto_total * valor_linha, subtotal)
        descontos.append(base)
        restos.append(resto)

    centavos_restantes = desconto_total - sum(descontos)
    prioridade = sorted(range(len(valores_linhas)), key=lambda indice: (-restos[indice], indice))
    for indice in prioridade[:centavos_restantes]:
        descontos[indice] += 1

    return descontos
