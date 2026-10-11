import hashlib
import hmac
import json
import re
from datetime import UTC, datetime

import httpx
import pytest
from playwright.sync_api import Page, expect
from pymongo.database import Database

TITULOS = [
    "O Jardim de Dentro",
    "Bicho-Palavra",
    "A Casa que Anda",
    "Kit Primeira Leitura",
    "A Lua no Bolso — edição numerada",
]
PRECOS = ["R$ 39,90", "R$ 29,90", "R$ 19,95", "R$ 89,90", "R$ 129,00"]


def abrir_pagina(pagina: Page, url_frontend: str) -> None:
    resposta = pagina.goto(url_frontend, wait_until="networkidle")
    assert resposta is not None
    assert resposta.status == 200
    expect(pagina.get_by_role("heading", name="Feira Relâmpago")).to_be_visible()


@pytest.mark.navegador
def test_catalogo_ssr_e_fluxo_pago_com_rateio_exato(
    pagina: Page,
    url_frontend: str,
    cliente_api: httpx.Client,
    segredo_webhook: str,
    banco_mongo: Database[dict],
) -> None:
    html_inicial = httpx.get(url_frontend, timeout=10.0).text
    for texto in [*TITULOS, *PRECOS]:
        assert texto in html_inicial
    assert "http://api:8000" not in html_inicial
    assert segredo_webhook not in html_inicial

    abrir_pagina(pagina, url_frontend)
    quantidades = pagina.get_by_label("Quantidade")
    for indice in range(3):
        quantidades.nth(indice).fill("1")

    pagina.get_by_role("button", name="Criar reserva").click()
    expect(pagina.get_by_text("ativa", exact=True)).to_be_visible()
    expect(pagina.get_by_text("9 disponíveis", exact=True)).to_have_count(3)

    contador = pagina.locator(".reserva-card__contador")
    primeiro_valor = contador.inner_text()
    assert re.fullmatch(r"\d{2}:\d{2}", primeiro_valor)
    pagina.wait_for_timeout(1_250)
    assert contador.inner_text() != primeiro_valor

    pagina.get_by_role("button", name="Confirmar reserva").click()
    expect(pagina.get_by_text("confirmada", exact=True)).to_be_visible()
    expect(pagina.get_by_text("aguardando pagamento", exact=True)).to_be_visible()
    expect(pagina.get_by_text("R$ 3,99", exact=True)).to_be_visible()
    expect(pagina.get_by_text("R$ 2,99", exact=True)).to_be_visible()
    expect(pagina.get_by_text("R$ 2,00", exact=True)).to_be_visible()
    expect(pagina.get_by_text("R$ 89,75", exact=True)).to_be_visible()
    expect(pagina.get_by_text("R$ 8,98", exact=True)).to_be_visible()
    expect(pagina.get_by_text("R$ 80,77", exact=True)).to_be_visible()

    id_pedido = pagina.locator(".pedido-card__id").inner_text()
    corpo = json.dumps(
        {
            "evento_id": "evt_navegador_pago",
            "pedido_id": id_pedido,
            "tipo": "pago",
            "ocorrido_em": "2026-10-10T12:00:00Z",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    assinatura = hmac.new(segredo_webhook.encode(), corpo, hashlib.sha256).hexdigest()
    resposta_webhook = cliente_api.post(
        "/v1/webhooks/pagamento",
        content=corpo,
        headers={
            "Content-Type": "application/json",
            "X-Assinatura": assinatura,
        },
    )
    assert resposta_webhook.status_code == 200
    assert resposta_webhook.json() == {"recebido": True}

    pagina.get_by_role("button", name="Atualizar status").click()
    expect(pagina.get_by_text("pago", exact=True)).to_be_visible()
    expect(pagina.get_by_text("2026-10-10T12:00:00Z", exact=True)).to_be_visible()

    feira = banco_mongo["feiras"].find_one({"_id": "principal"})
    assert feira is not None
    assert len(feira["reservas"]) == 1
    assert len(feira["pedidos"]) == 1
    assert feira["pedidos"][0]["subtotal_centavos"] == 8975
    assert feira["pedidos"][0]["desconto_centavos"] == 898
    assert feira["pedidos"][0]["total_centavos"] == 8077
    assert [linha["desconto_centavos"] for linha in feira["pedidos"][0]["linhas"]] == [
        399,
        299,
        200,
    ]


@pytest.mark.navegador
def test_interface_trata_estoque_concorrente_com_409(
    pagina: Page,
    url_frontend: str,
    cliente_api: httpx.Client,
) -> None:
    abrir_pagina(pagina, url_frontend)
    resposta_concorrente = cliente_api.post(
        "/v1/reservas",
        json={
            "cliente_id": "concorrente",
            "itens": [{"sku": "QND-005", "quantidade": 1}],
        },
    )
    assert resposta_concorrente.status_code == 201

    pagina.get_by_label("Quantidade").nth(4).fill("1")
    pagina.get_by_role("button", name="Criar reserva").click()

    mensagem_estoque = pagina.get_by_text(
        "O estoque mudou enquanto você escolhia.",
        exact=False,
    )
    expect(mensagem_estoque).to_be_visible()
    expect(pagina.get_by_text("0 disponíveis", exact=True)).to_be_visible()
    assert pagina.get_by_label("Quantidade").nth(4).input_value() == "0"
    expect(pagina.get_by_role("button", name="Criar reserva")).to_be_disabled()


@pytest.mark.navegador
def test_interface_trata_confirmacao_expirada_com_410(
    pagina: Page,
    url_frontend: str,
    banco_mongo: Database[dict],
) -> None:
    abrir_pagina(pagina, url_frontend)
    pagina.get_by_label("Quantidade").nth(0).fill("1")
    pagina.get_by_role("button", name="Criar reserva").click()
    expect(pagina.get_by_text("ativa", exact=True)).to_be_visible()

    id_reserva = pagina.locator(".reserva-card__valor").nth(0).inner_text()
    resultado = banco_mongo["feiras"].update_one(
        {"_id": "principal", "reservas.id": id_reserva},
        {"$set": {"reservas.$[reserva].expira_em": datetime(1970, 1, 1, tzinfo=UTC)}},
        array_filters=[{"reserva.id": id_reserva}],
    )
    assert resultado.modified_count == 1

    pagina.get_by_role("button", name="Confirmar reserva").click()

    mensagem_expiracao = pagina.get_by_text(
        "A reserva expirou antes da confirmação.",
        exact=False,
    )
    expect(mensagem_expiracao).to_be_visible()
    expect(pagina.get_by_text("expirada", exact=True)).to_be_visible()
    expect(pagina.get_by_text("10 disponíveis", exact=True)).to_have_count(3)
    expect(pagina.get_by_text("Você pode iniciar uma nova seleção.", exact=False)).to_be_visible()
    assert pagina.get_by_role("heading", name="Pedido").count() == 0
