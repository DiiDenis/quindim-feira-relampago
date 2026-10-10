from pymongo.errors import ServerSelectionTimeoutError

from app import criar_app
from app.config import Configuracao


class AdministradorIndisponivel:
    def command(self, comando: str) -> None:
        assert comando == "ping"
        raise ServerSelectionTimeoutError("falha controlada")


class ClienteIndisponivel:
    def __init__(self) -> None:
        self.admin = AdministradorIndisponivel()
        self.fechamentos = 0

    def close(self) -> None:
        self.fechamentos += 1


def test_healthz_retorna_erro_generico_quando_mongo_falha() -> None:
    configuracao = Configuracao(
        mongo_uri="mongodb://127.0.0.1:1",
        mongo_banco="quindim_teste",
        admin_token="admin-de-teste",
        webhook_segredo="segredo-de-teste",
        reserva_ttl_segundos=900,
    )
    app = criar_app(configuracao)
    cliente_indisponivel = ClienteIndisponivel()
    app.extensions["mongo"].cliente = cliente_indisponivel

    resposta = app.test_client().get("/healthz")

    assert resposta.status_code == 503
    assert resposta.get_json() == {
        "erro": {
            "codigo": "servico_indisponivel",
            "mensagem": "Serviço temporariamente indisponível.",
            "detalhes": {},
        }
    }
    assert b"falha controlada" not in resposta.data
    assert cliente_indisponivel.fechamentos == 0
