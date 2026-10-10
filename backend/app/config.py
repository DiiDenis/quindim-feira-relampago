"""Leitura e validação das configurações da aplicação."""

from dataclasses import dataclass
from os import environ

TTL_PADRAO_SEGUNDOS = 900


@dataclass(frozen=True, slots=True)
class Configuracao:
    """Configuração imutável carregada das variáveis de ambiente."""

    mongo_uri: str
    mongo_banco: str
    admin_token: str
    webhook_segredo: str
    reserva_ttl_segundos: int

    @classmethod
    def do_ambiente(cls) -> "Configuracao":
        """Carrega a configuração sem acessar serviços externos."""
        return cls(
            mongo_uri=_ler_texto("MONGO_URI", padrao="mongodb://localhost:27017"),
            mongo_banco=_ler_texto("MONGO_BANCO", padrao="quindim"),
            admin_token=_ler_texto("ADMIN_TOKEN"),
            webhook_segredo=_ler_texto("WEBHOOK_SEGREDO"),
            reserva_ttl_segundos=_ler_ttl(),
        )


def _ler_texto(nome: str, *, padrao: str | None = None) -> str:
    valor = environ.get(nome)
    if valor is None:
        if padrao is not None:
            return padrao
        raise ValueError(f"Configuração inválida: {nome} deve ser definida.")

    valor_limpo = valor.strip()
    if not valor_limpo:
        raise ValueError(f"Configuração inválida: {nome} não pode ser vazia.")
    return valor_limpo


def _ler_ttl() -> int:
    valor = environ.get("RESERVA_TTL_SEGUNDOS")
    if valor is None:
        return TTL_PADRAO_SEGUNDOS

    try:
        ttl = int(valor)
    except ValueError as erro:
        raise ValueError(
            "Configuração inválida: RESERVA_TTL_SEGUNDOS deve ser um inteiro positivo."
        ) from erro

    if ttl <= 0:
        raise ValueError(
            "Configuração inválida: RESERVA_TTL_SEGUNDOS deve ser um inteiro positivo."
        )
    return ttl
