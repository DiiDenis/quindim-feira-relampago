import hashlib
import hmac
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from pymongo.database import Database

from app.banco import ler_snapshot_feira

pytestmark = [pytest.mark.integracao, pytest.mark.negocio]

SEGREDO_PDF = "segredo-de-exemplo"
CORPO_PDF = (
    b'{"evento_id":"evt_0001","pedido_id":"66f0c2a1e4b0a1b2c3d4e5f7",'
    b'"tipo":"pago","ocorrido_em":"2026-10-01T12:00:00Z"}'
)
ASSINATURA_PDF = "bcb4b6f50d0ad32b6e2988d50fca256a72fd31196164ea4c210214966da968d7"


def obter_estado(banco_mongo: Database[dict[str, Any]]) -> dict[str, Any]:
    estado = banco_mongo["feiras"].find_one({"_id": "principal"})
    assert estado is not None
    return estado


def livro_por_sku(estado: dict[str, Any], sku: str) -> dict[str, Any]:
    return next(livro for livro in estado["livros"] if livro["sku"] == sku)


def criar_pedido(
    cliente_http: httpx.Client,
    itens: list[dict[str, Any]],
) -> dict[str, Any]:
    reserva = cliente_http.post(
        "/v1/reservas",
        json={"cliente_id": "cliente-webhook", "itens": itens},
    )
    assert reserva.status_code == 201
    confirmacao = cliente_http.post(f"/v1/reservas/{reserva.json()['id']}/confirmar")
    assert confirmacao.status_code == 201
    return confirmacao.json()


def corpo_evento(**alteracoes: Any) -> dict[str, Any]:
    evento = {
        "evento_id": "evt-http-001",
        "pedido_id": "pedido-inexistente",
        "tipo": "pago",
        "ocorrido_em": "2026-10-10T15:45:00-03:00",
    }
    evento.update(alteracoes)
    return evento


def serializar_evento(evento: dict[str, Any]) -> bytes:
    return json.dumps(evento, ensure_ascii=False, separators=(",", ":")).encode()


def assinar_com_biblioteca_padrao(corpo: bytes, segredo: str) -> str:
    return hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()


def enviar_evento(
    cliente_http: httpx.Client,
    segredo_webhook: str,
    evento: dict[str, Any],
    *,
    assinatura: str | None = None,
) -> httpx.Response:
    corpo = serializar_evento(evento)
    assinatura_efetiva = assinatura or assinar_com_biblioteca_padrao(corpo, segredo_webhook)
    return cliente_http.post(
        "/v1/webhooks/pagamento",
        content=corpo,
        headers={
            "Content-Type": "application/json",
            "X-Assinatura": assinatura_efetiva,
        },
    )


@pytest.mark.parametrize("assinatura", [None, "0" * 64])
def test_assinatura_invalida_nao_acessa_nem_normaliza_estado(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
    assinatura: str | None,
) -> None:
    reserva = cliente_http.post(
        "/v1/reservas",
        json={
            "cliente_id": "cliente-expiracao-incidental",
            "itens": [{"sku": "QND-005", "quantidade": 1}],
        },
    )
    assert reserva.status_code == 201
    colecao = banco_mongo["feiras"]
    agora = ler_snapshot_feira(colecao).agora
    resultado = colecao.update_one(
        {"_id": "principal", "reservas.id": reserva.json()["id"]},
        {"$set": {"reservas.$.expira_em": agora - timedelta(seconds=1)}},
    )
    assert resultado.modified_count == 1
    estado_antes = deepcopy(obter_estado(banco_mongo))
    corpo = serializar_evento(corpo_evento())
    headers = {"Content-Type": "application/json"}
    if assinatura is not None:
        headers["X-Assinatura"] = assinatura

    resposta = cliente_http.post(
        "/v1/webhooks/pagamento",
        content=corpo,
        headers=headers,
    )

    assert resposta.status_code == 401
    assert resposta.json()["erro"]["codigo"] == "nao_autorizado"
    assert obter_estado(banco_mongo) == estado_antes


def test_vetor_do_pdf_eh_aceito_pelo_endpoint_real(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
    segredo_webhook: str,
) -> None:
    assert len(CORPO_PDF) == 114
    assert segredo_webhook == SEGREDO_PDF
    assert assinar_com_biblioteca_padrao(CORPO_PDF, segredo_webhook) == ASSINATURA_PDF

    resposta = cliente_http.post(
        "/v1/webhooks/pagamento",
        content=CORPO_PDF,
        headers={"Content-Type": "application/json", "X-Assinatura": ASSINATURA_PDF},
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"recebido": True}
    estado = obter_estado(banco_mongo)
    assert estado["pedidos"] == []
    assert len(estado["eventos"]) == 1
    assert estado["eventos"][0] == {
        "evento_id": "evt_0001",
        "pedido_id": "66f0c2a1e4b0a1b2c3d4e5f7",
        "tipo": "pago",
        "ocorrido_em": datetime(2026, 10, 1, 12, tzinfo=UTC),
    }


def test_json_malformado_autenticado_retorna_400_json_sem_alterar_estado(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
    segredo_webhook: str,
) -> None:
    corpo = b'{"evento_id":'
    assinatura = assinar_com_biblioteca_padrao(corpo, segredo_webhook)
    estado_antes = deepcopy(obter_estado(banco_mongo))

    resposta = cliente_http.post(
        "/v1/webhooks/pagamento",
        content=corpo,
        headers={"Content-Type": "application/json", "X-Assinatura": assinatura},
    )

    assert resposta.status_code == 400
    assert resposta.headers["content-type"].startswith("application/json")
    assert resposta.json()["erro"]["codigo"] == "requisicao_invalida"
    assert b"<html" not in resposta.content.lower()
    assert obter_estado(banco_mongo) == estado_antes


@pytest.mark.parametrize(
    "alteracoes",
    [
        {"tipo": "pendente"},
        {"ocorrido_em": "2026-10-10T18:45:00"},
    ],
)
def test_payload_invalido_com_assinatura_valida_retorna_400_sem_alterar_estado(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
    segredo_webhook: str,
    alteracoes: dict[str, Any],
) -> None:
    estado_antes = deepcopy(obter_estado(banco_mongo))

    resposta = enviar_evento(
        cliente_http,
        segredo_webhook,
        corpo_evento(**alteracoes),
    )

    assert resposta.status_code == 400
    assert resposta.json()["erro"]["codigo"] == "requisicao_invalida"
    assert b"<html" not in resposta.content.lower()
    assert obter_estado(banco_mongo) == estado_antes


def test_webhook_pago_normaliza_data_e_responde_recebido_em_repeticoes(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
    segredo_webhook: str,
) -> None:
    pedido = criar_pedido(
        cliente_http,
        [{"sku": "QND-005", "quantidade": 1}],
    )
    evento = corpo_evento(pedido_id=pedido["id"])

    primeira = enviar_evento(cliente_http, segredo_webhook, evento)
    repeticao = enviar_evento(cliente_http, segredo_webhook, evento)

    assert primeira.status_code == repeticao.status_code == 200
    assert primeira.json() == repeticao.json() == {"recebido": True}
    estado = obter_estado(banco_mongo)
    assert len(estado["eventos"]) == 1
    assert estado["pedidos"][0]["status"] == "pago"
    assert estado["pedidos"][0]["pago_em"] == datetime(2026, 10, 10, 18, 45, tzinfo=UTC)
    assert livro_por_sku(estado, "QND-005")["disponivel"] == 0
    consulta = cliente_http.get(f"/v1/pedidos/{pedido['id']}")
    assert consulta.status_code == 200
    assert consulta.json()["pago_em"] == "2026-10-10T18:45:00Z"

    sem_efeito = enviar_evento(
        cliente_http,
        segredo_webhook,
        corpo_evento(
            evento_id="evt-http-sem-efeito",
            pedido_id=pedido["id"],
            tipo="recusado",
        ),
    )
    assert sem_efeito.status_code == 200
    assert sem_efeito.json() == {"recebido": True}
    estado_terminal = obter_estado(banco_mongo)
    assert len(estado_terminal["eventos"]) == 2
    assert estado_terminal["pedidos"][0]["status"] == "pago"
    assert estado_terminal["pedidos"][0]["pago_em"] == datetime(2026, 10, 10, 18, 45, tzinfo=UTC)
    assert livro_por_sku(estado_terminal, "QND-005")["disponivel"] == 0


def test_webhook_recusado_cancela_e_devolve_estoque(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
    segredo_webhook: str,
) -> None:
    pedido = criar_pedido(
        cliente_http,
        [
            {"sku": "QND-001", "quantidade": 2},
            {"sku": "QND-005", "quantidade": 1},
        ],
    )

    resposta = enviar_evento(
        cliente_http,
        segredo_webhook,
        corpo_evento(pedido_id=pedido["id"], tipo="recusado"),
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"recebido": True}
    estado = obter_estado(banco_mongo)
    assert estado["pedidos"][0]["status"] == "cancelado"
    assert estado["pedidos"][0]["pago_em"] is None
    assert estado["reservas"][0]["status"] == "confirmada"
    assert livro_por_sku(estado, "QND-001")["disponivel"] == 10
    assert livro_por_sku(estado, "QND-005")["disponivel"] == 1


@pytest.mark.parametrize("pedido_id", ["f" * 24, "nao-eh-object-id"])
def test_webhook_de_pedido_inexistente_responde_recebido_e_registra_evento(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
    segredo_webhook: str,
    pedido_id: str,
) -> None:
    evento = corpo_evento(pedido_id=pedido_id)

    resposta = enviar_evento(cliente_http, segredo_webhook, evento)

    assert resposta.status_code == 200
    assert resposta.json() == {"recebido": True}
    estado = obter_estado(banco_mongo)
    assert estado["pedidos"] == []
    assert len(estado["eventos"]) == 1
    assert estado["eventos"][0]["evento_id"] == evento["evento_id"]


def test_mesmo_evento_id_com_payload_diferente_preserva_primeiro_efeito(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
    segredo_webhook: str,
) -> None:
    pedido = criar_pedido(
        cliente_http,
        [{"sku": "QND-005", "quantidade": 1}],
    )
    primeiro = corpo_evento(evento_id="evt-conflitante", pedido_id=pedido["id"])
    conflitante = corpo_evento(
        evento_id="evt-conflitante",
        pedido_id=pedido["id"],
        tipo="recusado",
        ocorrido_em="2026-10-09T10:00:00Z",
    )

    resposta_inicial = enviar_evento(cliente_http, segredo_webhook, primeiro)
    resposta_conflitante = enviar_evento(cliente_http, segredo_webhook, conflitante)

    assert resposta_inicial.status_code == resposta_conflitante.status_code == 200
    assert resposta_inicial.json() == resposta_conflitante.json() == {"recebido": True}
    estado = obter_estado(banco_mongo)
    assert len(estado["eventos"]) == 1
    assert estado["eventos"][0]["tipo"] == "pago"
    assert estado["pedidos"][0]["status"] == "pago"
    assert estado["pedidos"][0]["pago_em"] == datetime(2026, 10, 10, 18, 45, tzinfo=UTC)
    assert livro_por_sku(estado, "QND-005")["disponivel"] == 0


@pytest.mark.parametrize(
    ("primeiro_tipo", "segundo_tipo", "status_final"),
    [
        ("pago", "recusado", "pago"),
        ("recusado", "pago", "cancelado"),
    ],
)
def test_eventos_fora_de_ordem_preservam_estado_terminal_e_confirmacao_idempotente(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
    segredo_webhook: str,
    primeiro_tipo: str,
    segundo_tipo: str,
    status_final: str,
) -> None:
    pedido = criar_pedido(
        cliente_http,
        [{"sku": "QND-005", "quantidade": 1}],
    )
    primeiro = corpo_evento(
        evento_id="evt-mais-novo",
        pedido_id=pedido["id"],
        tipo=primeiro_tipo,
        ocorrido_em="2026-10-10T18:45:00Z",
    )
    segundo = corpo_evento(
        evento_id="evt-mais-antigo",
        pedido_id=pedido["id"],
        tipo=segundo_tipo,
        ocorrido_em="2026-10-09T18:45:00Z",
    )

    primeira = enviar_evento(cliente_http, segredo_webhook, primeiro)
    segunda = enviar_evento(cliente_http, segredo_webhook, segundo)
    pedido_atual = cliente_http.get(f"/v1/pedidos/{pedido['id']}")
    reconfirmacao = cliente_http.post(f"/v1/reservas/{pedido['reserva_id']}/confirmar")

    assert primeira.status_code == segunda.status_code == 200
    assert primeira.json() == segunda.json() == {"recebido": True}
    assert pedido_atual.status_code == 200
    assert pedido_atual.json()["status"] == status_final
    assert reconfirmacao.status_code == 200
    assert reconfirmacao.json() == pedido_atual.json()
    estado = obter_estado(banco_mongo)
    assert len(estado["pedidos"]) == 1
    assert len(estado["eventos"]) == 2
    assert estado["reservas"][0]["status"] == "confirmada"
    assert estado["pedidos"][0]["status"] == status_final
    if status_final == "pago":
        assert estado["pedidos"][0]["pago_em"] == datetime(2026, 10, 10, 18, 45, tzinfo=UTC)
        assert livro_por_sku(estado, "QND-005")["disponivel"] == 0
    else:
        assert estado["pedidos"][0]["pago_em"] is None
        assert livro_por_sku(estado, "QND-005")["disponivel"] == 1
        nova_reserva = cliente_http.post(
            "/v1/reservas",
            json={
                "cliente_id": "cliente-apos-recusa",
                "itens": [{"sku": "QND-005", "quantidade": 1}],
            },
        )
        assert nova_reserva.status_code == 201
        estado_reutilizado = obter_estado(banco_mongo)
        assert livro_por_sku(estado_reutilizado, "QND-005")["disponivel"] == 0
        assert len(estado_reutilizado["reservas"]) == 2
