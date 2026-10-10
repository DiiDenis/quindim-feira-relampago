from datetime import datetime

import pytest
from bson import ObjectId

from app.erros import ErroNegocio
from app.formatos import interpretar_id_recurso, serializar_data_utc


def test_interpreta_object_id_hexadecimal() -> None:
    texto = "66f0c2a1e4b0a1b2c3d4e5f7"

    resultado = interpretar_id_recurso(texto)

    assert isinstance(resultado, ObjectId)
    assert str(resultado) == texto


@pytest.mark.parametrize(
    "valor",
    ["", "123", "g" * 24, "a" * 23, "a" * 25],
)
def test_id_invalido_eh_recurso_nao_encontrado(valor: str) -> None:
    with pytest.raises(ErroNegocio) as captura:
        interpretar_id_recurso(valor)

    assert captura.value.status_http == 404
    assert captura.value.codigo == "nao_encontrado"


def test_serializa_data_com_offset_em_utc_sem_perder_fracao() -> None:
    data = datetime.fromisoformat("2026-10-01T15:00:00.123456+03:00")

    resultado = serializar_data_utc(data)

    assert resultado == "2026-10-01T12:00:00.123456Z"


def test_rejeita_data_sem_fuso() -> None:
    data = datetime.fromisoformat("2026-10-01T12:00:00.123")

    with pytest.raises(ValueError, match="deve informar o fuso horário"):
        serializar_data_utc(data)
