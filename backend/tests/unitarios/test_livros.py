from datetime import UTC, datetime
from typing import Any

from app import criar_app
from app.banco import CAMPO_AGORA_MONGO
from app.config import Configuracao


class ColecaoComCatalogoInvalido:
    def __init__(self) -> None:
        self.escritas = 0

    def aggregate(self, _pipeline: list[dict[str, Any]]):
        return iter(
            [
                {
                    "_id": "principal",
                    "geracao": "geracao-de-teste",
                    "versao": 0,
                    "livros": [
                        {
                            "sku": "QND-001",
                            "titulo": "O Jardim de Dentro",
                            "preco_centavos": True,
                            "estoque": 10,
                            "disponivel": 10,
                        }
                    ],
                    "reservas": [],
                    "pedidos": [],
                    "eventos": [],
                    CAMPO_AGORA_MONGO: datetime.now(UTC),
                }
            ]
        )

    def replace_one(self, _filtro: dict[str, Any], _candidato: dict[str, Any]):
        self.escritas += 1
        raise AssertionError("Saída inválida não deveria ser persistida")


class BancoComCatalogoInvalido:
    def __init__(self, colecao: ColecaoComCatalogoInvalido) -> None:
        self.colecao = colecao

    def __getitem__(self, nome: str) -> ColecaoComCatalogoInvalido:
        assert nome == "feiras"
        return self.colecao


class ConexaoComCatalogoInvalido:
    def __init__(self, colecao: ColecaoComCatalogoInvalido) -> None:
        self.banco = BancoComCatalogoInvalido(colecao)


def test_catalogo_invalido_nao_vira_resposta_publica() -> None:
    app = criar_app(
        Configuracao(
            mongo_uri="mongodb://127.0.0.1:1",
            mongo_banco="quindim_teste",
            admin_token="admin-de-teste",
            webhook_segredo="segredo-de-teste",
            reserva_ttl_segundos=900,
        )
    )
    colecao = ColecaoComCatalogoInvalido()
    app.extensions["mongo"] = ConexaoComCatalogoInvalido(colecao)

    resposta = app.test_client().get("/v1/livros")

    assert resposta.status_code == 500
    assert resposta.get_json()["erro"]["codigo"] == "erro_interno"
    assert colecao.escritas == 0
