"""Leitura e escrita otimista do agregado da feira."""

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from pymongo.collection import Collection
from pymongo.database import Database

from .erros import ErroNegocio
from .expiracao import expirar_reservas
from .seed import COLECAO_FEIRAS, ID_FEIRA

CAMPO_AGORA_MONGO = "_agora_mongo"
SEM_RESULTADO = object()


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
    limite_temporal: datetime | None = None,
) -> bool:
    """Substitui somente se versão, geração e prazo ainda forem válidos."""
    candidato["_id"] = snapshot.estado["_id"]
    candidato["geracao"] = snapshot.estado["geracao"]
    candidato["versao"] = snapshot.estado["versao"] + 1
    filtro: dict[str, Any] = {
        "_id": snapshot.estado["_id"],
        "geracao": snapshot.estado["geracao"],
        "versao": snapshot.estado["versao"],
    }
    if limite_temporal is not None:
        if limite_temporal.tzinfo is None or limite_temporal.utcoffset() is None:
            raise ValueError("O limite temporal deve informar o fuso UTC.")
        filtro["$expr"] = {
            "$lt": ["$$NOW", limite_temporal.astimezone(UTC)],
        }
    resultado = colecao.replace_one(
        filtro,
        candidato,
    )
    return resultado.matched_count == 1


def menor_prazo_ativo_futuro(
    estado: dict[str, Any],
    agora: datetime,
) -> datetime | None:
    """Obtém o primeiro prazo ativo que ainda não venceu no snapshot."""
    prazos: list[datetime] = []
    for reserva in estado["reservas"]:
        if reserva["status"] != "ativa":
            continue
        expira_em = reserva["expira_em"]
        if expira_em.tzinfo is None or expira_em.utcoffset() is None:
            raise ValueError("A expiração da reserva deve informar o fuso UTC.")
        expira_em_utc = expira_em.astimezone(UTC)
        if expira_em_utc > agora:
            prazos.append(expira_em_utc)
    return min(prazos, default=None)


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
        limite_original = menor_prazo_ativo_futuro(snapshot.estado, snapshot.agora)
        estado_normalizado = deepcopy(snapshot.estado)
        expirar_reservas(estado_normalizado, snapshot.agora)
        houve_expiracao = estado_normalizado != snapshot.estado
        candidato = deepcopy(estado_normalizado)

        erro_negocio: ErroNegocio | None = None
        resultado: Resultado | object = SEM_RESULTADO
        try:
            resultado = operacao(candidato, snapshot.agora)
        except ErroNegocio as erro:
            erro_negocio = erro
            candidato = estado_normalizado

        if erro_negocio is not None and not houve_expiracao and limite_original is None:
            raise erro_negocio

        limite_candidato = menor_prazo_ativo_futuro(candidato, snapshot.agora)
        limites = [limite for limite in (limite_original, limite_candidato) if limite is not None]
        limite_temporal = min(limites, default=None)
        if tentar_substituir_snapshot(
            colecao,
            snapshot,
            candidato,
            limite_temporal,
        ):
            if erro_negocio is not None:
                raise erro_negocio
            return cast(Resultado, resultado)
