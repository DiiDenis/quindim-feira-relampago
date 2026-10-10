"""Leitura e escrita otimista do agregado da feira."""

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pymongo.collection import Collection
from pymongo.database import Database

from .seed import COLECAO_FEIRAS, ID_FEIRA

CAMPO_AGORA_MONGO = "_agora_mongo"


@dataclass(frozen=True, slots=True)
class SnapshotFeira:
    """Estado observado junto da hora fornecida pelo MongoDB."""

    estado: dict[str, Any]
    agora: datetime


def ler_snapshot_feira(colecao: Collection[dict[str, Any]]) -> SnapshotFeira:
    """Lê o agregado e acrescenta a hora do servidor apenas ao resultado."""
    documento = next(
        colecao.aggregate(
            [
                {"$match": {"_id": ID_FEIRA}},
                {"$set": {CAMPO_AGORA_MONGO: "$$NOW"}},
            ]
        ),
        None,
    )
    if documento is None:
        raise RuntimeError("Estado da feira não encontrado.")

    agora = documento.pop(CAMPO_AGORA_MONGO)
    if not isinstance(agora, datetime) or agora.tzinfo is None:
        raise RuntimeError("MongoDB retornou uma hora sem fuso UTC.")
    return SnapshotFeira(estado=documento, agora=agora.astimezone(UTC))


def tentar_substituir_snapshot(
    colecao: Collection[dict[str, Any]],
    snapshot: SnapshotFeira,
    candidato: dict[str, Any],
) -> bool:
    """Substitui o agregado somente se geração e versão ainda forem as lidas."""
    candidato["_id"] = snapshot.estado["_id"]
    candidato["geracao"] = snapshot.estado["geracao"]
    candidato["versao"] = snapshot.estado["versao"] + 1
    resultado = colecao.replace_one(
        {
            "_id": snapshot.estado["_id"],
            "geracao": snapshot.estado["geracao"],
            "versao": snapshot.estado["versao"],
        },
        candidato,
    )
    return resultado.matched_count == 1


def executar_com_cas[Resultado](
    banco: Database[dict[str, Any]],
    operacao: Callable[[dict[str, Any], datetime], Resultado],
) -> Resultado:
    """Repete leitura e cálculo puros até sua escrita vencer o CAS.

    A operação pode ser executada novamente e, por isso, não deve fazer I/O nem
    produzir efeitos externos. Erros do MongoDB são propagados: somente
    ``matched_count == 0`` representa um conflito que deve ser recalculado.
    """
    colecao = banco[COLECAO_FEIRAS]
    while True:
        snapshot = ler_snapshot_feira(colecao)
        candidato = deepcopy(snapshot.estado)
        resultado = operacao(candidato, snapshot.agora)
        if tentar_substituir_snapshot(colecao, snapshot, candidato):
            return resultado
