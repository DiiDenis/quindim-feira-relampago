from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from pymongo.errors import AutoReconnect

from app.banco import CAMPO_AGORA_MONGO, executar_com_cas


class ColecaoComFalhaDeRede:
    def __init__(self) -> None:
        self.leituras = 0
        self.escritas = 0

    def aggregate(self, _pipeline: list[dict[str, Any]]):
        self.leituras += 1
        return iter(
            [
                {
                    "_id": "principal",
                    "geracao": "geracao-inicial",
                    "versao": 0,
                    "livros": [],
                    "reservas": [],
                    "eventos": [],
                    CAMPO_AGORA_MONGO: datetime.now(UTC),
                }
            ]
        )

    def replace_one(self, _filtro: dict[str, Any], _candidato: dict[str, Any]):
        self.escritas += 1
        raise AutoReconnect("falha controlada")


class BancoComFalhaDeRede:
    def __init__(self, colecao: ColecaoComFalhaDeRede) -> None:
        self.colecao = colecao

    def __getitem__(self, nome: str) -> ColecaoComFalhaDeRede:
        assert nome == "feiras"
        return self.colecao


def test_falha_de_rede_na_escrita_nao_reexecuta_operacao() -> None:
    colecao = ColecaoComFalhaDeRede()
    banco = BancoComFalhaDeRede(colecao)
    execucoes = 0

    def operacao(candidato: dict[str, Any], _agora: datetime) -> None:
        nonlocal execucoes
        execucoes += 1
        candidato["eventos"].append("evento-de-teste")

    with pytest.raises(AutoReconnect, match="falha controlada"):
        executar_com_cas(banco, operacao)  # type: ignore[arg-type]

    assert execucoes == 1
    assert colecao.leituras == 1
    assert colecao.escritas == 1


@pytest.mark.parametrize(
    ("prazo_original", "prazo_candidato", "prazo_esperado"),
    [
        (timedelta(minutes=10), timedelta(minutes=5), timedelta(minutes=5)),
        (timedelta(minutes=5), timedelta(minutes=10), timedelta(minutes=5)),
    ],
)
def test_filtro_temporal_preserva_original_e_inclui_nova_reserva(
    prazo_original: timedelta,
    prazo_candidato: timedelta,
    prazo_esperado: timedelta,
) -> None:
    agora = datetime(2026, 10, 10, 15, 0, tzinfo=UTC)
    documento = {
        "_id": "principal",
        "geracao": "geracao-inicial",
        "versao": 0,
        "livros": [],
        "reservas": [
            {
                "id": "original",
                "status": "ativa",
                "itens": [],
                "expira_em": agora + prazo_original,
            }
        ],
        "eventos": [],
    }

    class ColecaoCapturaFiltro:
        def __init__(self) -> None:
            self.filtro: dict[str, Any] | None = None

        def aggregate(self, _pipeline: list[dict[str, Any]]):
            snapshot = deepcopy(documento)
            snapshot[CAMPO_AGORA_MONGO] = agora
            return iter([snapshot])

        def replace_one(self, filtro: dict[str, Any], _candidato: dict[str, Any]):
            self.filtro = filtro
            return SimpleNamespace(matched_count=1)

    colecao = ColecaoCapturaFiltro()
    banco = BancoComFalhaDeRede(colecao)  # type: ignore[arg-type]

    def operacao(estado: dict[str, Any], _agora: datetime) -> None:
        estado["reservas"][0]["status"] = "confirmada"
        estado["reservas"].append(
            {
                "id": "nova",
                "status": "ativa",
                "itens": [],
                "expira_em": agora + prazo_candidato,
            }
        )

    executar_com_cas(banco, operacao)  # type: ignore[arg-type]

    assert colecao.filtro is not None
    assert colecao.filtro["$expr"] == {"$lt": ["$$NOW", agora + prazo_esperado]}
