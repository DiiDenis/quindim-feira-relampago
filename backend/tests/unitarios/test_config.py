import pytest

from app.config import Configuracao

VARIAVEIS = (
    "MONGO_URI",
    "MONGO_BANCO",
    "ADMIN_TOKEN",
    "WEBHOOK_SEGREDO",
    "RESERVA_TTL_SEGUNDOS",
)


def preparar_ambiente_minimo(monkeypatch: pytest.MonkeyPatch) -> None:
    for nome in VARIAVEIS:
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setenv("ADMIN_TOKEN", "admin-de-teste")
    monkeypatch.setenv("WEBHOOK_SEGREDO", "segredo-de-teste")


def test_carrega_configuracao_padrao(monkeypatch: pytest.MonkeyPatch) -> None:
    preparar_ambiente_minimo(monkeypatch)

    configuracao = Configuracao.do_ambiente()

    assert configuracao.mongo_uri == "mongodb://localhost:27017"
    assert configuracao.mongo_banco == "quindim"
    assert configuracao.admin_token == "admin-de-teste"
    assert configuracao.webhook_segredo == "segredo-de-teste"
    assert configuracao.reserva_ttl_segundos == 900


def test_carrega_configuracao_customizada(monkeypatch: pytest.MonkeyPatch) -> None:
    preparar_ambiente_minimo(monkeypatch)
    monkeypatch.setenv("MONGO_URI", "mongodb://mongo:27017")
    monkeypatch.setenv("MONGO_BANCO", "feira_teste")
    monkeypatch.setenv("RESERVA_TTL_SEGUNDOS", "30")

    configuracao = Configuracao.do_ambiente()

    assert configuracao.mongo_uri == "mongodb://mongo:27017"
    assert configuracao.mongo_banco == "feira_teste"
    assert configuracao.reserva_ttl_segundos == 30


@pytest.mark.parametrize("valor", ["", "0", "-1", "1.5", "true", "false"])
def test_rejeita_ttl_invalido(monkeypatch: pytest.MonkeyPatch, valor: str) -> None:
    preparar_ambiente_minimo(monkeypatch)
    monkeypatch.setenv("RESERVA_TTL_SEGUNDOS", valor)

    with pytest.raises(ValueError, match="RESERVA_TTL_SEGUNDOS deve ser um inteiro positivo"):
        Configuracao.do_ambiente()


@pytest.mark.parametrize("nome", ["ADMIN_TOKEN", "WEBHOOK_SEGREDO"])
def test_exige_segredos_no_ambiente(monkeypatch: pytest.MonkeyPatch, nome: str) -> None:
    preparar_ambiente_minimo(monkeypatch)
    monkeypatch.delenv(nome)

    with pytest.raises(ValueError, match=f"{nome} deve ser definida"):
        Configuracao.do_ambiente()


@pytest.mark.parametrize("nome", ["ADMIN_TOKEN", "WEBHOOK_SEGREDO"])
def test_rejeita_segredos_vazios(monkeypatch: pytest.MonkeyPatch, nome: str) -> None:
    preparar_ambiente_minimo(monkeypatch)
    monkeypatch.setenv(nome, "   ")

    with pytest.raises(ValueError, match=f"{nome} não pode ser vazia"):
        Configuracao.do_ambiente()
