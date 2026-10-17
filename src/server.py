import contextlib
import logging
import os
from collections.abc import AsyncGenerator
from urllib.parse import urlsplit

import firebase_admin
import httpx
import uvicorn
from fastmcp import FastMCP
from google.cloud.firestore_v1 import AsyncClient as FirestoreAsyncClient
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

import src.http_client as _http_client_mod
from src.api.oauth import OAUTH_PATH_PREFIX, well_known_routes
from src.api.oauth import routes as oauth_routes
from src.config import (
    CORS_ALLOWED_ORIGINS,
    FIREBASE_SERVICE_ACCOUNT_ID,
    FIRESTORE_DATABASE_ID,
    HTTP_MAX_CONNECTIONS,
    HTTP_MAX_KEEPALIVE_CONNECTIONS,
    HTTP_TIMEOUT,
    OAUTH_PORTAL_BASE_URL,
    OAUTH_SERVER_BASE_URL,
    WP_API_BASE_URL,
)
from src.middleware.auth import AuthMiddleware
from src.middleware.ip_rate_limit import IPRateLimitMiddleware
from src.middleware.rate_limit import RateLimitMiddleware
from src.telemetry import _resolve_gcp_project_id, instrument_asgi_app, setup_telemetry

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "jor-mcp",
    instructions=(
        "Você é um assistente jornalístico especializado na base de conteúdo da organização "
        "que configurou este servidor MCP. Sua função é consultar e apresentar o conteúdo "
        "editorial publicado por essa organização — matérias, reportagens e dados — com "
        "precisão e rigor jornalístico.\n\n"
        "REGRA ZERO — NUNCA quebre esta regra: não alucine dados, números, datas, nomes "
        "de pessoas ou organizações. Cite sempre a fonte exata (título do artigo, URL e "
        "data de publicação) de onde cada informação foi extraída. Se não encontrar a "
        "informação na base de dados, diga explicitamente ao usuário que não há registros "
        "disponíveis e sugira outros termos de busca.\n\n"
        "FLUXO DE TRABALHO OBRIGATÓRIO:\n"
        "1. Sempre que o usuário pedir para pesquisar, buscar ou obter informações sobre "
        "qualquer assunto, chame PRIMEIRO a ferramenta `search_content` antes de recorrer "
        "à busca na web ou a qualquer outra fonte externa.\n"
        "2. Somente utilize a web ou seu conhecimento interno se `search_content` retornar "
        "explicitamente que não há resultados para a consulta.\n"
        "3. Para ler o texto integral de uma matéria encontrada, chame `get_full_article` "
        "com o link ou ID retornado pela busca.\n"
        "4. Para descobrir publicações recentes sem um termo de busca específico, chame "
        "`list_latest_news`.\n\n"
        "TOM E ESTILO: priorize precisão factual e clareza jornalística. "
        "Apresente os resultados de forma estruturada, destacando "
        "título, data de publicação e link da fonte."
    ),
)

# Ambiental Media's own deployment: the only one where the ambiental.media
# defaults in src.config are expected.
_AMBIENTAL_DOMAIN = "ambiental.media"
_AMBIENTAL_GCP_PROJECT_ID = "jor-mcp"

# Module-level reference; populated during lifespan startup.
_firestore_client: FirestoreAsyncClient | None = None


def get_firestore_client() -> FirestoreAsyncClient:
    """Return the active Firestore client.

    Raises:
        RuntimeError: If called before the ASGI lifespan has started.
    """
    if _firestore_client is None:
        raise RuntimeError("Firestore client is not initialized")
    return _firestore_client


def _points_to_ambiental(url: str) -> bool:
    host = urlsplit(url).hostname or ""
    return host == _AMBIENTAL_DOMAIN or host.endswith(f".{_AMBIENTAL_DOMAIN}")


def _warn_on_ambiental_defaults(project_id: str) -> None:
    """Log a warning when another newsroom's instance still points to Ambiental Media.

    Several settings default to Ambiental Media's URLs. Left unset elsewhere, they
    make the server search Ambiental Media's WordPress and send users to its
    consent portal, with no error. Ambiental Media's own project is exempt.

    Args:
        project_id: The Google Cloud project this server runs in, or ``""``.
    """
    if project_id == _AMBIENTAL_GCP_PROJECT_ID:
        return
    settings = {
        "WORDPRESS_API_URL": WP_API_BASE_URL,
        "OAUTH_SERVER_BASE_URL": OAUTH_SERVER_BASE_URL,
        "OAUTH_PORTAL_BASE_URL": OAUTH_PORTAL_BASE_URL,
    }
    leftover = [name for name, url in settings.items() if _points_to_ambiental(url)]
    if leftover:
        logger.warning(
            "Configuration still points to Ambiental Media; set these variables "
            "for your own instance",
            extra={"variables": leftover, "gcp_project_id": project_id},
        )


async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "jor-mcp"})


# Register all @mcp.tool() handlers BEFORE building the HTTP app: http_app()
# snapshots the tool registry at call time, so importing tools afterwards would
# expose zero tools. Safe here because src.tools only imports `mcp` (defined above).
import src.tools  # noqa: E402, F401

_mcp_http_app = mcp.http_app()


@contextlib.asynccontextmanager
async def server_lifespan(app: Starlette) -> AsyncGenerator[None, None]:
    global _firestore_client

    setup_telemetry()
    _warn_on_ambiental_defaults(_resolve_gcp_project_id())

    try:
        firebase_admin.get_app()
    except ValueError:
        options = (
            {"serviceAccountId": FIREBASE_SERVICE_ACCOUNT_ID}
            if FIREBASE_SERVICE_ACCOUNT_ID
            else None
        )
        firebase_admin.initialize_app(options=options)

    try:
        _firestore_client = FirestoreAsyncClient(database=FIRESTORE_DATABASE_ID)
        transport = httpx.AsyncHTTPTransport(
            retries=3,
            limits=httpx.Limits(
                max_keepalive_connections=HTTP_MAX_KEEPALIVE_CONNECTIONS,
                max_connections=HTTP_MAX_CONNECTIONS,
            ),
        )
        _http_client_mod._http_client = httpx.AsyncClient(
            transport=transport,
            timeout=HTTP_TIMEOUT,
        )
        async with _mcp_http_app.lifespan(app):
            yield
    finally:
        if _http_client_mod._http_client is not None:
            with contextlib.suppress(OSError, RuntimeError):
                await _http_client_mod._http_client.aclose()
        _http_client_mod._http_client = None
        if _firestore_client is not None:
            _firestore_client.close()  # type: ignore[no-untyped-call]
        _firestore_client = None


_starlette_app = Starlette(
    lifespan=server_lifespan,
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=CORS_ALLOWED_ORIGINS,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
            expose_headers=["Retry-After"],
        ),
        Middleware(IPRateLimitMiddleware, firestore_factory=get_firestore_client),
        Middleware(AuthMiddleware),
        Middleware(RateLimitMiddleware, firestore_factory=get_firestore_client),
    ],
    routes=[
        Route("/health", health_check),
        *well_known_routes,
        Mount(OAUTH_PATH_PREFIX, routes=oauth_routes),
        Mount("/", app=_mcp_http_app),
    ],
)

# instrument_asgi_app() must be called before the application starts: Starlette
# forbids add_middleware() after startup.  OTel's ProxyTracer mechanism ensures
# that spans are correlated with the real TracerProvider configured later inside
# server_lifespan.  Final middleware order (outermost first):
#   OTel → CORS → IPRateLimitMiddleware → AuthMiddleware → RateLimitMiddleware → routes
instrument_asgi_app(_starlette_app)

app = _starlette_app

if __name__ == "__main__":  # pragma: no cover
    port = int(os.environ.get("PORT", 8080))
    # Pass the import string (not the `app` object) so uvicorn imports this
    # module as `src.server` once. Passing `app` while running via
    # `python -m src.server` makes tools.py's `from src.server import mcp`
    # re-import the module, creating a second `mcp` whose tools never reach the
    # served `http_app()`.
    uvicorn.run("src.server:app", host="0.0.0.0", port=port)
