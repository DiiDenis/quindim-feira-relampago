import logging

from flask import Flask, request
from pydantic import BaseModel, ConfigDict, Field

from app import criar_app
from app.config import Configuracao
from app.erros import ErroNegocio, validar_entrada
from app.formatos import interpretar_id_recurso


class EntradaTeste(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantidade: int = Field(gt=0, strict=True)


class SaidaTeste(BaseModel):
    quantidade: int


def criar_app_de_teste() -> Flask:
    app = criar_app(
        Configuracao(
            mongo_uri="mongodb://127.0.0.1:1",
            mongo_banco="quindim_teste",
            admin_token="admin-de-teste",
            webhook_segredo="segredo-de-teste",
            reserva_ttl_segundos=900,
        )
    )

    @app.post("/teste/entrada")
    def receber_entrada():
        entrada = validar_entrada(EntradaTeste, request.get_json())
        return {"quantidade": entrada.quantidade}

    @app.get("/teste/recurso/<identificador>")
    def consultar_recurso(identificador: str):
        interpretar_id_recurso(identificador)
        return {"encontrado": True}

    @app.get("/teste/erro-negocio")
    def falhar_com_erro_negocio():
        raise ErroNegocio(
            409,
            "estoque_insuficiente",
            "Estoque insuficiente.",
            {"skus": ["QND-005"]},
        )

    @app.get("/teste/erro-inesperado")
    def falhar_inesperadamente():
        raise RuntimeError("detalhe técnico secreto")

    @app.get("/teste/saida-invalida")
    def produzir_saida_invalida():
        SaidaTeste.model_validate({"quantidade": "não é inteiro"})
        return {"inalcancavel": True}

    return app


def test_json_malformado_retorna_400_sem_html() -> None:
    resposta = (
        criar_app_de_teste()
        .test_client()
        .post(
            "/teste/entrada",
            data='{"quantidade":',
            content_type="application/json",
        )
    )

    assert resposta.status_code == 400
    assert resposta.content_type == "application/json"
    assert resposta.get_json() == {
        "erro": {
            "codigo": "requisicao_invalida",
            "mensagem": "Corpo JSON inválido.",
            "detalhes": {},
        }
    }


def test_validacao_de_entrada_retorna_detalhes_serializaveis() -> None:
    resposta = (
        criar_app_de_teste()
        .test_client()
        .post(
            "/teste/entrada",
            json={"quantidade": -1},
        )
    )

    assert resposta.status_code == 400
    corpo = resposta.get_json()
    assert corpo["erro"]["codigo"] == "requisicao_invalida"
    assert corpo["erro"]["detalhes"]["campos"] == [
        {
            "campo": "quantidade",
            "mensagem": "Input should be greater than 0",
            "tipo": "greater_than",
        }
    ]
    assert "ctx" not in resposta.get_data(as_text=True)
    assert "input" not in resposta.get_data(as_text=True)


def test_rota_desconhecida_retorna_404_sem_html() -> None:
    resposta = criar_app_de_teste().test_client().get("/rota-inexistente")

    assert resposta.status_code == 404
    assert resposta.content_type == "application/json"
    assert resposta.get_json() == {
        "erro": {
            "codigo": "nao_encontrado",
            "mensagem": "Recurso não encontrado.",
            "detalhes": {},
        }
    }


def test_id_invalido_em_rota_retorna_404() -> None:
    resposta = criar_app_de_teste().test_client().get("/teste/recurso/id-invalido")

    assert resposta.status_code == 404
    assert resposta.get_json()["erro"]["codigo"] == "nao_encontrado"


def test_erro_de_negocio_preserva_status_codigo_e_detalhes() -> None:
    resposta = criar_app_de_teste().test_client().get("/teste/erro-negocio")

    assert resposta.status_code == 409
    assert resposta.get_json() == {
        "erro": {
            "codigo": "estoque_insuficiente",
            "mensagem": "Estoque insuficiente.",
            "detalhes": {"skus": ["QND-005"]},
        }
    }


def test_erro_inesperado_retorna_500_generico_e_registra_excecao(caplog) -> None:
    app = criar_app_de_teste()

    with caplog.at_level(logging.ERROR, logger=app.logger.name):
        resposta = app.test_client().get("/teste/erro-inesperado")

    assert resposta.status_code == 500
    assert resposta.get_json() == {
        "erro": {
            "codigo": "erro_interno",
            "mensagem": "Erro interno do servidor.",
            "detalhes": {},
        }
    }
    assert "detalhe técnico secreto" not in resposta.get_data(as_text=True)
    assert any(registro.exc_info is not None for registro in caplog.records)


def test_erro_de_validacao_de_saida_continua_500() -> None:
    resposta = criar_app_de_teste().test_client().get("/teste/saida-invalida")

    assert resposta.status_code == 500
    assert resposta.get_json()["erro"]["codigo"] == "erro_interno"
