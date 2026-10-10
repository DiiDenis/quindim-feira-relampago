from typing import Any

import pytest

from app import criar_app
from app.config import Configuracao


class BancoProibido:
    def __getitem__(self, _nome: str) -> None:
        raise AssertionError("O estado da feira foi acessado antes da autenticação")


class ConexaoProibida:
    banco = BancoProibido()


class ColecaoFalsa:
    def __init__(self) -> None:
        self.substituicoes: list[tuple[dict[str, Any], dict[str, Any], bool]] = []

    def replace_one(
        self,
        filtro: dict[str, Any],
        substituto: dict[str, Any],
        *,
        upsert: bool,
    ) -> None:
        self.substituicoes.append((filtro, substituto, upsert))


class BancoFalso:
    def __init__(self, colecao: ColecaoFalsa) -> None:
        self.colecao = colecao

    def __getitem__(self, nome: str) -> ColecaoFalsa:
        assert nome == "feiras"
        return self.colecao


class ConexaoFalsa:
    def __init__(self, colecao: ColecaoFalsa) -> None:
        self.banco = BancoFalso(colecao)


@pytest.fixture
def app_admin():
    app = criar_app(
        Configuracao(
            mongo_uri="mongodb://127.0.0.1:1",
            mongo_banco="quindim_teste",
            admin_token="admin-de-teste",
            webhook_segredo="segredo-de-teste",
            reserva_ttl_segundos=900,
        )
    )
    app.config["TESTING"] = True
    return app


@pytest.mark.parametrize("token", [None, "token-incorreto", "não-é-o-token"])
def test_reset_recusa_token_invalido_sem_acessar_estado(app_admin, token: str | None) -> None:
    app_admin.extensions["mongo"] = ConexaoProibida()
    headers = {} if token is None else {"X-Admin-Token": token}

    resposta = app_admin.test_client().post("/v1/admin/reset", headers=headers)

    assert resposta.status_code == 401
    assert resposta.get_json() == {
        "erro": {
            "codigo": "nao_autorizado",
            "mensagem": "Token administrativo inválido.",
            "detalhes": {},
        }
    }
    assert b"admin-de-teste" not in resposta.data


def test_reset_substitui_agregado_inteiro_com_nova_geracao(app_admin) -> None:
    colecao = ColecaoFalsa()
    app_admin.extensions["mongo"] = ConexaoFalsa(colecao)
    cliente = app_admin.test_client()

    primeira = cliente.post(
        "/v1/admin/reset",
        headers={"X-Admin-Token": "admin-de-teste"},
    )
    segunda = cliente.post(
        "/v1/admin/reset",
        headers={"X-Admin-Token": "admin-de-teste"},
    )

    assert primeira.status_code == segunda.status_code == 204
    assert primeira.data == segunda.data == b""
    assert len(colecao.substituicoes) == 2
    filtro, primeiro_estado, upsert = colecao.substituicoes[0]
    assert filtro == {"_id": "principal"}
    assert upsert is True
    assert primeiro_estado["reservas"] == []
    assert primeiro_estado["pedidos"] == []
    assert primeiro_estado["eventos"] == []
    assert primeiro_estado["geracao"] != colecao.substituicoes[1][1]["geracao"]
