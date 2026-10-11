import pytest
from pydantic import BaseModel

from app import criar_app
from app.config import Configuracao
from app.erros import DetalheErro, RespostaErro
from app.livros import LivroSaida, RespostaLivros
from app.pagamentos import WebhookPagamentoSaida
from app.pedidos import LinhaPedidoSaida, PedidoSaida
from app.reservas import ItemReservaSaida, ReservaSaida
from app.saude import RespostaSaude


def configuracao_de_teste() -> Configuracao:
    return Configuracao(
        mongo_uri="mongodb://127.0.0.1:1",
        mongo_banco="quindim_teste",
        admin_token="admin-de-teste",
        webhook_segredo="segredo-de-teste",
        reserva_ttl_segundos=900,
    )


def test_aplicacao_publica_exatamente_as_oito_rotas_do_contrato() -> None:
    app = criar_app(configuracao_de_teste())
    rotas = {
        (metodo, regra.rule)
        for regra in app.url_map.iter_rules()
        if regra.endpoint != "static"
        for metodo in regra.methods
        if metodo in {"GET", "POST"}
    }

    assert rotas == {
        ("GET", "/healthz"),
        ("GET", "/v1/livros"),
        ("POST", "/v1/reservas"),
        ("GET", "/v1/reservas/<id_reserva>"),
        ("POST", "/v1/reservas/<id_reserva>/confirmar"),
        ("GET", "/v1/pedidos/<id_pedido>"),
        ("POST", "/v1/webhooks/pagamento"),
        ("POST", "/v1/admin/reset"),
    }


@pytest.mark.parametrize(
    "modelo",
    [
        RespostaSaude,
        LivroSaida,
        RespostaLivros,
        ItemReservaSaida,
        ReservaSaida,
        LinhaPedidoSaida,
        PedidoSaida,
        WebhookPagamentoSaida,
        DetalheErro,
        RespostaErro,
    ],
)
def test_modelos_publicos_rejeitam_campos_extras_e_conversoes(
    modelo: type[BaseModel],
) -> None:
    assert modelo.model_config["extra"] == "forbid"
    assert modelo.model_config["strict"] is True
