import os

import pytest

from app import criar_app
from app.config import Configuracao

pytestmark = [
    pytest.mark.integracao,
    pytest.mark.skipif(
        os.environ.get("EXECUTAR_TESTES_INTEGRACAO") != "1",
        reason="requer MongoDB real e EXECUTAR_TESTES_INTEGRACAO=1",
    ),
]


def test_healthz_confirma_mongo_real() -> None:
    configuracao = Configuracao(
        mongo_uri=os.environ["MONGO_URI"],
        mongo_banco=os.environ.get("MONGO_BANCO", "quindim_teste"),
        admin_token="admin-de-teste",
        webhook_segredo="segredo-de-teste",
        reserva_ttl_segundos=900,
    )
    app = criar_app(configuracao)

    try:
        resposta = app.test_client().get("/healthz")
    finally:
        app.extensions["mongo"].cliente.close()

    assert resposta.status_code == 200
    assert resposta.get_json() == {"status": "ok"}
