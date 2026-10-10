from typing import Any

import httpx
import pytest

pytestmark = pytest.mark.integracao


def test_healthz_confirma_api_e_mongo_reais(cliente_http: httpx.Client) -> None:
    resposta = cliente_http.get("/healthz")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


@pytest.mark.negocio
def test_seed_real_esta_persistido(documento_feira: dict[str, Any]) -> None:
    livros = documento_feira["livros"]

    assert documento_feira["_id"] == "principal"
    assert documento_feira["versao"] == 0
    assert len(documento_feira["geracao"]) > 0
    assert [
        (
            livro["sku"],
            livro["titulo"],
            livro["preco_centavos"],
            livro["estoque"],
            livro["disponivel"],
        )
        for livro in livros
    ] == [
        ("QND-001", "O Jardim de Dentro", 3990, 10, 10),
        ("QND-002", "Bicho-Palavra", 2990, 10, 10),
        ("QND-003", "A Casa que Anda", 1995, 10, 10),
        ("QND-004", "Kit Primeira Leitura", 8990, 3, 3),
        ("QND-005", "A Lua no Bolso — edição numerada", 12900, 1, 1),
    ]
    assert documento_feira["reservas"] == []
    assert documento_feira["pedidos"] == []
    assert documento_feira["eventos"] == []
