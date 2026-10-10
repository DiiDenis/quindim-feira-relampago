from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from typing import Any

import httpx
import pytest
from pymongo.database import Database

from app.banco import (
    CAMPO_AGORA_MONGO,
    executar_com_cas,
    ler_snapshot_feira,
    tentar_substituir_snapshot,
)

pytestmark = [pytest.mark.integracao, pytest.mark.negocio]


def test_conflito_cas_descarta_candidato_e_recalcula(
    banco_mongo: Database[dict[str, Any]],
) -> None:
    barreira = Barrier(2)

    def executar(candidato_id: str) -> tuple[str, int, datetime]:
        def operacao(estado: dict[str, Any], agora: datetime) -> tuple[str, int, datetime]:
            if estado["versao"] == 0:
                barreira.wait(timeout=5)
            estado["eventos"].append(candidato_id)
            return candidato_id, estado["versao"], agora

        return executar_com_cas(banco_mongo, operacao)

    with ThreadPoolExecutor(max_workers=2) as executor:
        resultados = list(executor.map(executar, ("primeiro", "segundo")))

    estado_final = banco_mongo["feiras"].find_one({"_id": "principal"})
    assert estado_final is not None
    assert sorted(resultado[0] for resultado in resultados) == ["primeiro", "segundo"]
    assert sorted(resultado[1] for resultado in resultados) == [0, 1]
    assert sorted(estado_final["eventos"]) == ["primeiro", "segundo"]
    assert estado_final["versao"] == 2
    assert CAMPO_AGORA_MONGO not in estado_final
    assert all(resultado[2].tzinfo is UTC for resultado in resultados)


def test_snapshot_anterior_ao_reset_nao_sobrescreve_nova_geracao(
    cliente_http: httpx.Client,
    banco_mongo: Database[dict[str, Any]],
    token_admin: str,
) -> None:
    colecao = banco_mongo["feiras"]
    snapshot_antigo = ler_snapshot_feira(colecao)
    candidato_antigo = snapshot_antigo.estado.copy()
    candidato_antigo["eventos"] = ["nao-deve-ser-salvo"]

    resposta = cliente_http.post(
        "/v1/admin/reset",
        headers={"X-Admin-Token": token_admin},
    )
    assert resposta.status_code == 204

    assert tentar_substituir_snapshot(colecao, snapshot_antigo, candidato_antigo) is False
    estado_atual = colecao.find_one({"_id": "principal"})
    assert estado_atual is not None
    assert estado_atual["geracao"] != snapshot_antigo.estado["geracao"]
    assert estado_atual["versao"] == 0
    assert estado_atual["eventos"] == []
    assert CAMPO_AGORA_MONGO not in estado_atual
