import logging
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient


def _make_fake_firestore() -> MagicMock:
    """Return a MagicMock that satisfies the Firestore async interface.

    ``close()`` is deliberately synchronous: AsyncClient inherits the plain
    ``google.cloud.client.Client.close()``, and an AsyncMock here would accept an
    ``await`` that raises TypeError against the real client.
    """
    fake_firestore = MagicMock()
    fake_firestore.close = MagicMock(return_value=None)
    return fake_firestore


@patch("src.server.setup_telemetry")
def test_health_endpoint(_mock_setup: MagicMock) -> None:
    from src.server import app

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "jor-mcp"}


# ---------------------------------------------------------------------------
# server_lifespan branch coverage
# ---------------------------------------------------------------------------


@patch("src.server.setup_telemetry")
@patch("firebase_admin.get_app", side_effect=ValueError("No app"))
@patch("firebase_admin.initialize_app")
@patch("src.server._mcp_http_app")
@patch("src.server.FirestoreAsyncClient")
@patch("httpx.AsyncClient")
async def test_server_lifespan_initializes_firebase_when_not_present(
    mock_http_client_cls: MagicMock,
    mock_firestore_cls: MagicMock,
    mock_mcp_app: MagicMock,
    mock_init: MagicMock,
    _mock_get_app: MagicMock,
    _mock_setup: MagicMock,
) -> None:
    """server_lifespan calls initialize_app() when no Firebase app exists yet."""
    from src.server import server_lifespan

    @asynccontextmanager
    async def fake_mcp_lifespan(app):  # type: ignore[no-untyped-def]
        yield

    fake_firestore = _make_fake_firestore()
    fake_http_client = AsyncMock()
    mock_firestore_cls.return_value = fake_firestore
    mock_http_client_cls.return_value = fake_http_client
    mock_mcp_app.lifespan = fake_mcp_lifespan

    async with server_lifespan(MagicMock()):
        pass

    mock_init.assert_called_once()
    fake_http_client.aclose.assert_awaited_once()
    fake_firestore.close.assert_called_once()
    _mock_setup.assert_called_once()


@patch("src.server.setup_telemetry")
@patch("firebase_admin.get_app")
@patch("firebase_admin.initialize_app")
@patch("src.server._mcp_http_app")
@patch("src.server.FirestoreAsyncClient")
@patch("httpx.AsyncClient")
async def test_server_lifespan_skips_init_when_firebase_already_present(
    mock_http_client_cls: MagicMock,
    mock_firestore_cls: MagicMock,
    mock_mcp_app: MagicMock,
    mock_init: MagicMock,
    _mock_get_app: MagicMock,
    _mock_setup: MagicMock,
) -> None:
    """server_lifespan does NOT call initialize_app() when Firebase is already initialized."""
    from src.server import server_lifespan

    @asynccontextmanager
    async def fake_mcp_lifespan(app):  # type: ignore[no-untyped-def]
        yield

    fake_firestore = _make_fake_firestore()
    fake_http_client = AsyncMock()
    mock_firestore_cls.return_value = fake_firestore
    mock_http_client_cls.return_value = fake_http_client
    mock_mcp_app.lifespan = fake_mcp_lifespan

    async with server_lifespan(MagicMock()):
        pass

    mock_init.assert_not_called()
    fake_http_client.aclose.assert_awaited_once()
    fake_firestore.close.assert_called_once()
    _mock_setup.assert_called_once()


@patch("src.server.setup_telemetry")
def test_get_firestore_client_returns_the_active_client(_mock_setup: MagicMock) -> None:
    """get_firestore_client() hands back the client stored during startup."""
    import src.server as server_mod

    fake_firestore = _make_fake_firestore()
    original = server_mod._firestore_client
    server_mod._firestore_client = fake_firestore
    try:
        assert server_mod.get_firestore_client() is fake_firestore
    finally:
        server_mod._firestore_client = original


# ---------------------------------------------------------------------------
# _warn_on_ambiental_defaults
# ---------------------------------------------------------------------------

_OWN_URL = "https://mcp.example.org"


def _patch_urls(wordpress: str, server: str, portal: str):  # type: ignore[no-untyped-def]
    return (
        patch("src.server.WP_API_BASE_URL", wordpress),
        patch("src.server.OAUTH_SERVER_BASE_URL", server),
        patch("src.server.OAUTH_PORTAL_BASE_URL", portal),
    )


def test_warn_on_ambiental_defaults_lists_leftover_variables(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Another project still using Ambiental Media's URLs gets one warning naming them."""
    from src.server import _warn_on_ambiental_defaults

    wp, server, portal = _patch_urls(
        "https://ambiental.media/wp-json", _OWN_URL, "https://jormcp.ambiental.media"
    )
    with wp, server, portal, caplog.at_level(logging.WARNING, logger="src.server"):
        _warn_on_ambiental_defaults("my-newsroom-project")

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert warnings[0].variables == ["WORDPRESS_API_URL", "OAUTH_PORTAL_BASE_URL"]  # type: ignore[attr-defined]


def test_warn_on_ambiental_defaults_silent_in_ambiental_project(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Ambiental Media's own project keeps its defaults without a warning."""
    from src.server import _warn_on_ambiental_defaults

    url = "https://jormcp.ambiental.media"
    wp, server, portal = _patch_urls(url, url, url)
    with wp, server, portal, caplog.at_level(logging.WARNING, logger="src.server"):
        _warn_on_ambiental_defaults("jor-mcp")

    assert not caplog.records


def test_warn_on_ambiental_defaults_silent_when_configured(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A fully configured instance, even without a known project, logs nothing.

    ``notambiental.media`` only shares a suffix with the domain and must not match.
    """
    from src.server import _warn_on_ambiental_defaults

    wp, server, portal = _patch_urls("https://notambiental.media/wp-json", _OWN_URL, _OWN_URL)
    with wp, server, portal, caplog.at_level(logging.WARNING, logger="src.server"):
        _warn_on_ambiental_defaults("")

    assert not caplog.records


@patch("src.server.setup_telemetry")
@patch("src.server._resolve_gcp_project_id", return_value="my-newsroom-project")
@patch("src.server._warn_on_ambiental_defaults")
@patch("src.server._mcp_http_app")
@patch("src.server.FirestoreAsyncClient")
@patch("httpx.AsyncClient")
async def test_server_lifespan_checks_ambiental_defaults(
    mock_http_client_cls: MagicMock,
    mock_firestore_cls: MagicMock,
    mock_mcp_app: MagicMock,
    mock_warn: MagicMock,
    _mock_project: MagicMock,
    _mock_setup: MagicMock,
) -> None:
    """server_lifespan runs the Ambiental-defaults check with the resolved project."""
    from src.server import server_lifespan

    @asynccontextmanager
    async def fake_mcp_lifespan(app):  # type: ignore[no-untyped-def]
        yield

    mock_firestore_cls.return_value = _make_fake_firestore()
    mock_http_client_cls.return_value = AsyncMock()
    mock_mcp_app.lifespan = fake_mcp_lifespan

    async with server_lifespan(MagicMock()):
        pass

    mock_warn.assert_called_once_with("my-newsroom-project")
