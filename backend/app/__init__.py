"""Aplicação da Feira Relâmpago."""

from flask import Flask

from .config import Configuracao


def criar_app(configuracao: Configuracao | None = None) -> Flask:
    """Cria uma instância Flask sem iniciar servidor ou conexão com banco."""
    configuracao_efetiva = configuracao or Configuracao.do_ambiente()
    app = Flask(__name__)
    app.config.from_mapping(
        MONGO_URI=configuracao_efetiva.mongo_uri,
        MONGO_BANCO=configuracao_efetiva.mongo_banco,
        ADMIN_TOKEN=configuracao_efetiva.admin_token,
        WEBHOOK_SEGREDO=configuracao_efetiva.webhook_segredo,
        RESERVA_TTL_SEGUNDOS=configuracao_efetiva.reserva_ttl_segundos,
    )
    return app
