"""Aplicação da Feira Relâmpago."""

from flask import Flask

from .admin import bp as bp_admin
from .config import Configuracao
from .erros import registrar_handlers_erros
from .livros import bp as bp_livros
from .mongo import criar_conexao_mongo
from .reservas import bp as bp_reservas
from .saude import bp as bp_saude


def criar_app(configuracao: Configuracao | None = None) -> Flask:
    """Cria a aplicação e seu cliente MongoDB, sem abrir conexão antecipada."""
    configuracao_efetiva = configuracao or Configuracao.do_ambiente()
    app = Flask(__name__)
    app.config.from_mapping(
        MONGO_URI=configuracao_efetiva.mongo_uri,
        MONGO_BANCO=configuracao_efetiva.mongo_banco,
        ADMIN_TOKEN=configuracao_efetiva.admin_token,
        WEBHOOK_SEGREDO=configuracao_efetiva.webhook_segredo,
        RESERVA_TTL_SEGUNDOS=configuracao_efetiva.reserva_ttl_segundos,
    )
    registrar_handlers_erros(app)
    app.extensions["mongo"] = criar_conexao_mongo(
        configuracao_efetiva.mongo_uri,
        configuracao_efetiva.mongo_banco,
    )
    app.register_blueprint(bp_admin)
    app.register_blueprint(bp_livros)
    app.register_blueprint(bp_reservas)
    app.register_blueprint(bp_saude)
    return app
