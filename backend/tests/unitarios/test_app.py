from datetime import UTC

from flask import Flask

from app import criar_app
from app.config import Configuracao
from app.mongo import TEMPO_SELECAO_SERVIDOR_MS


def configuracao_de_teste() -> Configuracao:
    return Configuracao(
        mongo_uri="mongodb://127.0.0.1:1",
        mongo_banco="quindim_teste",
        admin_token="admin-de-teste",
        webhook_segredo="segredo-de-teste",
        reserva_ttl_segundos=900,
    )


def test_cria_aplicacao_sem_abrir_socket_do_mongo() -> None:
    app = criar_app(configuracao_de_teste())

    assert isinstance(app, Flask)
    assert app.config["MONGO_URI"] == "mongodb://127.0.0.1:1"
    assert app.config["RESERVA_TTL_SEGUNDOS"] == 900
    cliente = app.extensions["mongo"].cliente
    assert cliente.options.connect is False
    assert cliente.options.server_selection_timeout == TEMPO_SELECAO_SERVIDOR_MS / 1_000
    assert cliente.codec_options.tz_aware is True
    assert cliente.codec_options.tzinfo is UTC


def test_cria_instancias_independentes() -> None:
    primeira = criar_app(configuracao_de_teste())
    segunda = criar_app(configuracao_de_teste())

    primeira.config["MARCADOR_TESTE"] = "somente-na-primeira"

    assert primeira is not segunda
    assert primeira.extensions["mongo"].cliente is not segunda.extensions["mongo"].cliente
    assert "MARCADOR_TESTE" not in segunda.config


def test_factory_nao_inicia_servidor(monkeypatch) -> None:
    def falhar_se_executar_run(*args, **kwargs) -> None:
        raise AssertionError("Flask.run não deveria ser chamado pela factory")

    monkeypatch.setattr(Flask, "run", falhar_se_executar_run)

    app = criar_app(configuracao_de_teste())

    assert isinstance(app, Flask)
