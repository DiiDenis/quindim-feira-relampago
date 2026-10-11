import os
from collections.abc import Iterator
from urllib.parse import urlparse

import httpx
import pytest
from playwright.sync_api import Browser, Page, Request, Response, sync_playwright
from pymongo import MongoClient
from pymongo.database import Database

URL_API_INTERNA = "http://api:8000"
URL_FRONTEND_INTERNA = "http://frontend:3000"
ERROS_HTTP_ESPERADOS = ("409 (Conflict)", "410 (Gone)")


@pytest.fixture(scope="session")
def url_api() -> str:
    url = os.environ.get("API_URL", URL_API_INTERNA).rstrip("/")
    if url != URL_API_INTERNA:
        pytest.fail(f"API_URL insegura para reset de navegador: {url}.", pytrace=False)
    return url


@pytest.fixture(scope="session")
def url_frontend() -> str:
    url = os.environ.get("FRONTEND_URL", URL_FRONTEND_INTERNA).rstrip("/")
    if url != URL_FRONTEND_INTERNA:
        pytest.fail(f"FRONTEND_URL inesperada para o runner: {url}.", pytrace=False)
    return url


@pytest.fixture(scope="session")
def token_admin() -> str:
    token = os.environ.get("ADMIN_TOKEN", "").strip()
    if not token:
        pytest.fail("ADMIN_TOKEN não foi definido para o runner.", pytrace=False)
    return token


@pytest.fixture(scope="session")
def segredo_webhook() -> str:
    segredo = os.environ.get("WEBHOOK_SEGREDO", "").strip()
    if not segredo:
        pytest.fail("WEBHOOK_SEGREDO não foi definido para o runner.", pytrace=False)
    return segredo


@pytest.fixture(scope="session")
def cliente_api(url_api: str) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=url_api, timeout=10.0) as cliente:
        resposta = cliente.get("/healthz")
        resposta.raise_for_status()
        yield cliente


@pytest.fixture(scope="session")
def banco_mongo() -> Iterator[Database[dict]]:
    cliente = MongoClient(
        os.environ.get("MONGO_URI", "mongodb://mongo:27017"),
        serverSelectionTimeoutMS=5_000,
    )
    cliente.admin.command("ping")
    try:
        yield cliente[os.environ.get("MONGO_BANCO", "quindim")]
    finally:
        cliente.close()


@pytest.fixture(autouse=True)
def feira_limpa(cliente_api: httpx.Client, token_admin: str) -> Iterator[None]:
    def resetar() -> None:
        resposta = cliente_api.post(
            "/v1/admin/reset",
            headers={"X-Admin-Token": token_admin},
        )
        assert resposta.status_code == 204
        assert resposta.content == b""

    resetar()
    yield
    resetar()


@pytest.fixture(scope="session")
def navegador() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def pagina(
    navegador: Browser,
    url_frontend: str,
    token_admin: str,
    segredo_webhook: str,
) -> Iterator[Page]:
    contexto = navegador.new_context(locale="pt-BR")
    pagina = contexto.new_page()
    requisicoes: list[tuple[str, str]] = []
    respostas: list[Response] = []
    erros_console: list[str] = []

    def registrar_requisicao(requisicao: Request) -> None:
        requisicoes.append((requisicao.url, requisicao.post_data or ""))

    def registrar_resposta(resposta: Response) -> None:
        if resposta.request.resource_type in {"document", "fetch", "xhr"}:
            respostas.append(resposta)

    def registrar_console(mensagem: object) -> None:
        tipo = getattr(mensagem, "type", "")
        texto = getattr(mensagem, "text", str(mensagem))
        if texto.startswith("Failed to load resource") and any(
            status in texto for status in ERROS_HTTP_ESPERADOS
        ):
            return
        if tipo in {"error", "warning"} or "hydration" in texto.lower():
            erros_console.append(f"{tipo}: {texto}")

    pagina.on("request", registrar_requisicao)
    pagina.on("response", registrar_resposta)
    pagina.on("console", registrar_console)
    pagina.on("pageerror", lambda erro: erros_console.append(f"pageerror: {erro}"))

    yield pagina

    origem_frontend = urlparse(url_frontend)
    for url, corpo in requisicoes:
        destino = urlparse(url)
        if destino.scheme in {"http", "https"}:
            assert (destino.hostname, destino.port) == (
                origem_frontend.hostname,
                origem_frontend.port,
            ), f"O navegador saiu do Nuxt: {url}"
        assert token_admin not in corpo
        assert segredo_webhook not in corpo

    conteudos_publicos = [pagina.content()]
    for resposta in respostas:
        tipo_conteudo = resposta.headers.get("content-type", "")
        if "json" in tipo_conteudo or "html" in tipo_conteudo:
            conteudos_publicos.append(resposta.text())

    for conteudo in conteudos_publicos:
        assert token_admin not in conteudo
        assert segredo_webhook not in conteudo
        assert "ADMIN_TOKEN" not in conteudo
        assert "WEBHOOK_SEGREDO" not in conteudo
        assert "http://api:8000" not in conteudo

    assert erros_console == []
    contexto.close()
