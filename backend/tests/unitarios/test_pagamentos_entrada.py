import json
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from app.pagamentos import (
    assinatura_valida,
    calcular_assinatura,
    validar_e_normalizar_evento_pagamento,
)

SEGREDO_PDF = "segredo-de-exemplo"
CORPO_PDF = (
    b'{"evento_id":"evt_0001","pedido_id":"66f0c2a1e4b0a1b2c3d4e5f7",'
    b'"tipo":"pago","ocorrido_em":"2026-10-01T12:00:00Z"}'
)
ASSINATURA_PDF = "bcb4b6f50d0ad32b6e2988d50fca256a72fd31196164ea4c210214966da968d7"


def evento_valido(**alteracoes: Any) -> dict[str, Any]:
    evento = {
        "evento_id": "evt_0001",
        "pedido_id": "pedido-que-nao-precisa-ser-object-id",
        "tipo": "pago",
        "ocorrido_em": "2026-10-01T15:00:00+03:00",
    }
    evento.update(alteracoes)
    return evento


def test_normaliza_evento_para_utc_sem_exigir_object_id() -> None:
    evento = validar_e_normalizar_evento_pagamento(evento_valido())

    assert evento.evento_id == "evt_0001"
    assert evento.pedido_id == "pedido-que-nao-precisa-ser-object-id"
    assert evento.tipo == "pago"
    assert evento.ocorrido_em == datetime(2026, 10, 1, 12, tzinfo=UTC)


@pytest.mark.parametrize(
    "alteracoes",
    [
        {"evento_id": ""},
        {"evento_id": "   "},
        {"evento_id": 123},
        {"pedido_id": ""},
        {"pedido_id": "   "},
        {"pedido_id": 123},
        {"tipo": "pendente"},
        {"ocorrido_em": "2026-10-01T12:00:00"},
    ],
)
def test_rejeita_campos_invalidos(alteracoes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        validar_e_normalizar_evento_pagamento(evento_valido(**alteracoes))


def test_rejeita_campo_extra() -> None:
    with pytest.raises(ValidationError):
        validar_e_normalizar_evento_pagamento(evento_valido(campo_extra=True))


def test_vetor_fixo_do_pdf_usa_os_114_bytes_originais() -> None:
    assert len(CORPO_PDF) == 114
    assert calcular_assinatura(CORPO_PDF, SEGREDO_PDF) == ASSINATURA_PDF
    assert assinatura_valida(CORPO_PDF, ASSINATURA_PDF, SEGREDO_PDF) is True


@pytest.mark.parametrize(
    ("assinatura", "segredo"),
    [
        (None, SEGREDO_PDF),
        ("g" * 64, SEGREDO_PDF),
        ("a" * 63, SEGREDO_PDF),
        ("a" * 65, SEGREDO_PDF),
        (ASSINATURA_PDF, "segredo-errado"),
    ],
)
def test_rejeita_assinatura_ausente_malformada_ou_de_outro_segredo(
    assinatura: str | None,
    segredo: str,
) -> None:
    assert assinatura_valida(CORPO_PDF, assinatura, segredo) is False


def test_json_equivalente_com_espacos_exige_nova_assinatura() -> None:
    corpo_com_espacos = CORPO_PDF.replace(b'":', b'": ')
    assert json.loads(corpo_com_espacos) == json.loads(CORPO_PDF)

    assert assinatura_valida(corpo_com_espacos, ASSINATURA_PDF, SEGREDO_PDF) is False
    nova_assinatura = calcular_assinatura(corpo_com_espacos, SEGREDO_PDF)
    assert assinatura_valida(corpo_com_espacos, nova_assinatura, SEGREDO_PDF) is True
