from datetime import UTC, datetime
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
