"""Tests for src.services.github."""

import base64
import json
import logging
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.config import parse_github_filenames
from src.services.github import (
    GitHubFileResult,
    _build_auth_headers,
    _decode_base64_content,
    _discover_i18n_paths,
    _fetch_file,
    _fetch_repo_files,
    _parse_content,
    clear_cache,
    fetch_github_i18n_content,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_DATA: dict[str, str] = {"title": "Amazônia em Chamas", "body": "Conteúdo."}  # noqa: RUF012
_REPO = "ambiental-media/microsite-test"
_PATH = "locales/pt.json"


def _encode_content(data: dict[str, str]) -> str:
    """Return Base64-encoded JSON (with newlines as the API produces)."""
    raw = json.dumps(data).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def _make_response(
    status_code: int = 200,
    json_body: object = None,
) -> MagicMock:
    """Build a minimal mock of httpx.Response."""
    mock = MagicMock(spec=httpx.Response)
    mock.status_code = status_code
    mock.json.return_value = json_body
    if status_code >= 400:
        mock.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}",
            request=MagicMock(),
            response=mock,
        )
    else:
        mock.raise_for_status.return_value = None
    return mock


def _content_response(path: str = _PATH, data: dict[str, str] | None = None) -> dict[str, object]:
    """Return a dict that matches the GitHub Contents API schema."""
    return {
        "name": path.split("/")[-1],
        "path": path,
        "encoding": "base64",
        "content": _encode_content(data or _SAMPLE_DATA),
    }


def _tree_response(
    paths: list[str],
    truncated: bool = False,
) -> dict[str, object]:
    """Return a dict matching the GitHub Git Trees API schema."""
    return {
        "tree": [{"path": p, "type": "blob"} for p in paths],
        "truncated": truncated,
    }


@pytest.fixture(autouse=True)
def _fresh_cache() -> Generator[None, None, None]:
    """Start and end every test with an empty GitHub content cache."""
    clear_cache()
    yield
    clear_cache()


@pytest.fixture
def mock_client() -> Generator[AsyncMock, None, None]:
    """Inject a mock AsyncClient, bypassing the lifespan initialisation."""
    client = AsyncMock(spec=httpx.AsyncClient)
    with patch("src.services.github.get_http_client", return_value=client):
        yield client


# ---------------------------------------------------------------------------
# _build_auth_headers
# ---------------------------------------------------------------------------


def test_build_auth_headers_with_token() -> None:
    with patch("src.services.github.GITHUB_TOKEN", "secret-token"):
        headers = _build_auth_headers()
    assert headers == {"Authorization": "Bearer secret-token"}


def test_build_auth_headers_without_token() -> None:
    with patch("src.services.github.GITHUB_TOKEN", None):
        headers = _build_auth_headers()
    assert headers == {}


# ---------------------------------------------------------------------------
# _decode_base64_content
# ---------------------------------------------------------------------------


def test_decode_base64_content_clean() -> None:
    raw = base64.b64encode(b"hello world").decode("ascii")
    assert _decode_base64_content(raw) == b"hello world"


def test_decode_base64_content_with_newlines() -> None:
    """The GitHub API wraps encoded content in newlines."""
    raw = base64.b64encode(b"hello world").decode("ascii")
    wrapped = "\n".join(raw[i : i + 60] for i in range(0, len(raw), 60)) + "\n"
    assert _decode_base64_content(wrapped) == b"hello world"


def test_decode_base64_content_invalid_raises() -> None:
    with pytest.raises(ValueError):
        _decode_base64_content("!!!not-base64!!!")


# ---------------------------------------------------------------------------
# _fetch_file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_file_success(mock_client: AsyncMock) -> None:
    mock_client.get.return_value = _make_response(200, _content_response())
    result = await _fetch_file(mock_client, _REPO, _PATH)
    assert isinstance(result, GitHubFileResult)
    assert result.repo == _REPO
    assert result.path == _PATH
    assert result.data == _SAMPLE_DATA


@pytest.mark.asyncio
async def test_fetch_file_404_returns_none(mock_client: AsyncMock) -> None:
    mock_client.get.return_value = _make_response(404)
    result = await _fetch_file(mock_client, _REPO, _PATH)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_file_http_error_returns_none(mock_client: AsyncMock) -> None:
    mock_client.get.return_value = _make_response(500)
    result = await _fetch_file(mock_client, _REPO, _PATH)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_file_network_error_returns_none(mock_client: AsyncMock) -> None:
    mock_client.get.side_effect = httpx.RequestError("connection refused")
    result = await _fetch_file(mock_client, _REPO, _PATH)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_file_bad_schema_returns_none(mock_client: AsyncMock) -> None:
    mock_client.get.return_value = _make_response(200, {"unexpected": "schema"})
    result = await _fetch_file(mock_client, _REPO, _PATH)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_file_unsupported_encoding_returns_none(
    mock_client: AsyncMock,
) -> None:
    payload = _content_response()
    payload["encoding"] = "utf-8"  # not base64
    mock_client.get.return_value = _make_response(200, payload)
    result = await _fetch_file(mock_client, _REPO, _PATH)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_file_invalid_json_returns_none(mock_client: AsyncMock) -> None:
    payload = {
        "name": "pt.json",
        "path": _PATH,
        "encoding": "base64",
        "content": base64.b64encode(b"not-json").decode("ascii"),
    }
    mock_client.get.return_value = _make_response(200, payload)
    result = await _fetch_file(mock_client, _REPO, _PATH)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_file_json_array_content_is_accepted(mock_client: AsyncMock) -> None:
    """A JSON array at the root is searchable data, like a CSV exported to JSON."""
    array_payload = {
        "name": "pt.json",
        "path": _PATH,
        "encoding": "base64",
        "content": base64.b64encode(json.dumps([{"a": "x"}]).encode("utf-8")).decode("ascii"),
    }
    mock_client.get.return_value = _make_response(200, array_payload)
    result = await _fetch_file(mock_client, _REPO, _PATH)
    assert result is not None
    assert result.data == [{"a": "x"}]


@pytest.mark.asyncio
async def test_fetch_file_json_scalar_content_returns_none(mock_client: AsyncMock) -> None:
    """A JSON scalar at the root has nothing to search and is rejected."""
    payload = {
        "name": "pt.json",
        "path": _PATH,
        "encoding": "base64",
        "content": base64.b64encode(b"42").decode("ascii"),
    }
    mock_client.get.return_value = _make_response(200, payload)
    assert await _fetch_file(mock_client, _REPO, _PATH) is None


@pytest.mark.asyncio
async def test_fetch_file_response_json_decode_error_returns_none(
    mock_client: AsyncMock,
) -> None:
    """A JSONDecodeError from response.json() must be trapped and return None."""
    mock_response = _make_response(200)
    mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)
    mock_client.get.return_value = mock_response
    result = await _fetch_file(mock_client, _REPO, _PATH)
    assert result is None


# ---------------------------------------------------------------------------
# _discover_i18n_paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discover_i18n_paths_returns_matching_files(mock_client: AsyncMock) -> None:
    """Only files named pt.json or en.json are returned, at any depth."""
    mock_client.get.return_value = _make_response(
        200,
        _tree_response(
            [
                "messages/pt.json",
                "messages/en.json",
                "package.json",  # excluded: not a target filename
                "src/components/Button.tsx",  # excluded: wrong extension
            ]
        ),
    )
    paths = await _discover_i18n_paths(mock_client, _REPO)
    assert set(paths) == {"messages/pt.json", "messages/en.json"}


@pytest.mark.asyncio
async def test_discover_i18n_paths_uses_configured_filenames(mock_client: AsyncMock) -> None:
    """MCP_GITHUB_FILENAMES replaces the default pt.json/en.json names."""
    mock_client.get.return_value = _make_response(
        200, _tree_response(["data/data.json", "messages/pt.json"])
    )
    with patch("src.services.github.GITHUB_FILENAMES", frozenset({"data.json"})):
        paths = await _discover_i18n_paths(mock_client, _REPO)
    assert paths == ["data/data.json"]


@pytest.mark.asyncio
async def test_discover_i18n_paths_http_error_returns_empty(mock_client: AsyncMock) -> None:
    mock_client.get.return_value = _make_response(403)
    paths = await _discover_i18n_paths(mock_client, _REPO)
    assert paths == []


@pytest.mark.asyncio
async def test_discover_i18n_paths_network_error_returns_empty(mock_client: AsyncMock) -> None:
    mock_client.get.side_effect = httpx.RequestError("timeout")
    paths = await _discover_i18n_paths(mock_client, _REPO)
    assert paths == []


@pytest.mark.asyncio
async def test_discover_i18n_paths_bad_schema_returns_empty(mock_client: AsyncMock) -> None:
    mock_client.get.return_value = _make_response(200, {"unexpected": "schema"})
    paths = await _discover_i18n_paths(mock_client, _REPO)
    assert paths == []


@pytest.mark.asyncio
async def test_discover_i18n_paths_truncated_logs_warning(
    mock_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_client.get.return_value = _make_response(
        200, _tree_response(["messages/pt.json"], truncated=True)
    )
    with caplog.at_level(logging.WARNING, logger="src.services.github"):
        paths = await _discover_i18n_paths(mock_client, _REPO)
    assert paths == ["messages/pt.json"]
    assert any("truncated" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_discover_i18n_paths_no_matches_returns_empty(mock_client: AsyncMock) -> None:
    mock_client.get.return_value = _make_response(
        200, _tree_response(["package.json", "README.md"])
    )
    paths = await _discover_i18n_paths(mock_client, _REPO)
    assert paths == []


# ---------------------------------------------------------------------------
# _fetch_repo_files
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_repo_files_returns_found_files(mock_client: AsyncMock) -> None:
    """Files discovered via the tree are fetched and returned."""
    mock_client.get.return_value = _make_response(200, _content_response(_PATH))
    with patch(
        "src.services.github._discover_i18n_paths",
        new=AsyncMock(return_value=[_PATH]),
    ):
        results = await _fetch_repo_files(mock_client, _REPO)
    assert len(results) == 1
    assert results[0].path == _PATH
    assert results[0].repo == _REPO


@pytest.mark.asyncio
async def test_fetch_repo_files_all_missing_returns_empty(mock_client: AsyncMock) -> None:
    """No files to fetch when discovery returns an empty list."""
    with patch(
        "src.services.github._discover_i18n_paths",
        new=AsyncMock(return_value=[]),
    ):
        results = await _fetch_repo_files(mock_client, _REPO)
    assert results == []


# ---------------------------------------------------------------------------
# fetch_github_i18n_content
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_github_i18n_content_empty_repos(mock_client: AsyncMock) -> None:
    with patch("src.services.github.GITHUB_REPOS", ""):
        result = await fetch_github_i18n_content()
    assert result == []


@pytest.mark.asyncio
async def test_fetch_github_i18n_content_no_filenames(
    mock_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An MCP_GITHUB_FILENAMES with no .json names skips ingestion with a warning."""
    with (
        patch("src.services.github.GITHUB_REPOS", _REPO),
        patch("src.services.github.GITHUB_FILENAMES", frozenset()),
        caplog.at_level(logging.WARNING, logger="src.services.github"),
    ):
        result = await fetch_github_i18n_content()
    assert result == []
    mock_client.get.assert_not_called()
    assert any("MCP_GITHUB_FILENAMES" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_fetch_github_i18n_content_success(mock_client: AsyncMock) -> None:
    mock_client.get.return_value = _make_response(200, _content_response(_PATH))
    with (
        patch("src.services.github.GITHUB_REPOS", _REPO),
        patch("src.services.github.GITHUB_TOKEN", "tok"),
        patch(
            "src.services.github._discover_i18n_paths",
            new=AsyncMock(return_value=[_PATH]),
        ),
    ):
        result = await fetch_github_i18n_content()

    assert isinstance(result, list)
    assert any(item["repo"] == _REPO for item in result)
    assert all("data" in item for item in result)


@pytest.mark.asyncio
async def test_fetch_github_i18n_content_graceful_degradation(
    mock_client: AsyncMock,
) -> None:
    """An error in one repo must not prevent others from returning results.

    ``_discover_i18n_paths`` already traps all network/HTTP errors internally
    and returns an empty list on failure, so the TaskGroup is never exposed to
    an unhandled exception during normal operation.  This test simulates that
    contract: the bad repo yields no paths (as the real function would after
    catching an error) while the good repo contributes its file.
    """

    async def _fake_discover(client: AsyncMock, repo: str) -> list[str]:
        if "repo-bad" in repo:
            # Real _discover_i18n_paths catches errors and returns [] — mirror that.
            return []
        return [_PATH]

    mock_client.get.return_value = _make_response(200, _content_response(_PATH))
    repos = "ambiental-media/repo-bad,ambiental-media/repo-good"
    with (
        patch("src.services.github.GITHUB_REPOS", repos),
        patch("src.services.github._discover_i18n_paths", side_effect=_fake_discover),
    ):
        result = await fetch_github_i18n_content()

    # The good repo contributed results despite the bad one finding nothing
    assert any("repo-good" in item["repo"] for item in result)


@pytest.mark.asyncio
async def test_fetch_github_i18n_content_whitespace_repos(
    mock_client: AsyncMock,
) -> None:
    """Whitespace-only entries in GITHUB_REPOS are ignored."""
    mock_client.get.return_value = _make_response(404)
    with patch("src.services.github.GITHUB_REPOS", "  ,  "):
        result = await fetch_github_i18n_content()
    assert result == []


@pytest.mark.asyncio
async def test_fetch_github_i18n_content_survives_unexpected_task_error(
    mock_client: AsyncMock,
) -> None:
    """The TaskGroup boundary guard keeps one broken task from killing ingestion.

    ``_fetch_repo_files`` traps every httpx and validation error internally, so
    only a programming bug or a cancellation can escape it. This forces that
    path to confirm the pipeline logs and returns instead of propagating.
    """
    with (
        patch("src.services.github.GITHUB_REPOS", _REPO),
        patch(
            "src.services.github._fetch_repo_files",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ),
    ):
        result = await fetch_github_i18n_content()

    assert result == []


# ---------------------------------------------------------------------------
# parse_github_filenames (src.config)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("pt.json,en.json", {"pt.json", "en.json"}),
        (" data.json , pt.json ,", {"data.json", "pt.json"}),
        ("data.csv,notes.md,data.json", {"data.csv", "notes.md", "data.json"}),
        (
            "*.csv,*.MD,guia.markdown,dados-*.json",
            {"*.csv", "*.MD", "guia.markdown", "dados-*.json"},
        ),
        ("*,data.xlsx,notes.txt,*.json", {"*.json"}),
        ("", set()),
    ],
)
def test_parse_github_filenames(raw: str, expected: set[str]) -> None:
    """Names are trimmed, blanks dropped and only parseable extensions kept."""
    assert parse_github_filenames(raw) == frozenset(expected)


# ---------------------------------------------------------------------------
# Phase 4.5: file formats, patterns, limits and cache
# ---------------------------------------------------------------------------


def _raw_content_response(path: str, text: str) -> dict[str, object]:
    """Contents API payload for an arbitrary text file."""
    return {
        "name": path.split("/")[-1],
        "path": path,
        "encoding": "base64",
        "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
    }


def test_parse_content_csv_rows_keyed_by_header() -> None:
    rows = _parse_content("dados/municipios.csv", "municipio,area\nAltamira,159533\nBelém,1059\n")
    assert rows == [
        {"municipio": "Altamira", "area": "159533"},
        {"municipio": "Belém", "area": "1059"},
    ]


def test_parse_content_markdown_and_markdown_extension() -> None:
    assert _parse_content("README.md", "# Título\nTexto") == {"text": "# Título\nTexto"}
    assert _parse_content("docs/guia.MARKDOWN", "x") == {"text": "x"}


@pytest.mark.parametrize(
    ("path", "text"),
    [
        ("vazio.csv", ""),  # no header row
        ("dados.json", '"just a string"'),  # JSON scalar
        ("dados.json", "{not json"),
        ("planilha.xlsx", "binary"),  # unsupported extension
    ],
)
def test_parse_content_rejects_unparseable(path: str, text: str) -> None:
    with pytest.raises(ValueError):
        _parse_content(path, text)


@pytest.mark.asyncio
async def test_fetch_file_parses_csv_and_quotes_path(mock_client: AsyncMock) -> None:
    """CSV files become rows, and paths with spaces are URL-encoded."""
    path = "dados/minha planilha.csv"
    mock_client.get.return_value = _make_response(200, _raw_content_response(path, "a,b\n1,2\n"))
    result = await _fetch_file(mock_client, _REPO, path)
    assert result is not None
    assert result.data == [{"a": "1", "b": "2"}]
    called_url = mock_client.get.call_args.args[0]
    assert called_url.endswith("/contents/dados/minha%20planilha.csv")


@pytest.mark.asyncio
async def test_discover_matches_patterns_case_sensitively(mock_client: AsyncMock) -> None:
    mock_client.get.return_value = _make_response(
        200,
        _tree_response(["a/dados.csv", "b/c/notas.md", "README.MD", "pt.json", "x.txt"]),
    )
    with patch("src.services.github.GITHUB_FILENAMES", frozenset({"*.csv", "*.md"})):
        paths = await _discover_i18n_paths(mock_client, _REPO)
    assert paths == ["a/dados.csv", "b/c/notas.md"]


@pytest.mark.asyncio
async def test_discover_skips_large_files_and_caps_count(
    mock_client: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    tree = {
        "tree": [
            {"path": "grande.csv", "type": "blob", "size": 5_000_000},
            *({"path": f"f{i}.csv", "type": "blob", "size": 10} for i in range(4)),
        ],
        "truncated": False,
    }
    mock_client.get.return_value = _make_response(200, tree)
    with (
        patch("src.services.github.GITHUB_FILENAMES", frozenset({"*.csv"})),
        patch("src.services.github.GITHUB_MAX_FILES_PER_REPO", 3),
        caplog.at_level(logging.WARNING, logger="src.services.github"),
    ):
        paths = await _discover_i18n_paths(mock_client, _REPO)
    assert paths == ["f0.csv", "f1.csv", "f2.csv"]
    messages = [r.message for r in caplog.records]
    assert any("larger than MCP_GITHUB_MAX_FILE_BYTES" in m for m in messages)
    assert any("Too many matching GitHub files" in m for m in messages)


@pytest.mark.asyncio
async def test_fetch_content_is_cached_until_it_expires(mock_client: AsyncMock) -> None:
    """A second search reuses the content; after the TTL it is downloaded again."""
    discover = AsyncMock(return_value=[_PATH])
    mock_client.get.return_value = _make_response(200, _content_response(_PATH))
    with (
        patch("src.services.github.GITHUB_REPOS", _REPO),
        patch("src.services.github.GITHUB_CACHE_SECONDS", 300),
        patch("src.services.github._discover_i18n_paths", new=discover),
        patch("src.services.github.monotonic", side_effect=[1000.0, 1100.0, 1400.0]),
    ):
        first = await fetch_github_i18n_content()
        second = await fetch_github_i18n_content()  # 100 s later: cache hit
        third = await fetch_github_i18n_content()  # 400 s later: expired
    assert first == second == third
    assert discover.await_count == 2


@pytest.mark.asyncio
async def test_fetch_content_cache_disabled_with_zero(mock_client: AsyncMock) -> None:
    discover = AsyncMock(return_value=[_PATH])
    mock_client.get.return_value = _make_response(200, _content_response(_PATH))
    with (
        patch("src.services.github.GITHUB_REPOS", _REPO),
        patch("src.services.github.GITHUB_CACHE_SECONDS", 0),
        patch("src.services.github._discover_i18n_paths", new=discover),
    ):
        await fetch_github_i18n_content()
        await fetch_github_i18n_content()
    assert discover.await_count == 2


@pytest.mark.asyncio
async def test_fetch_content_does_not_cache_empty_results(mock_client: AsyncMock) -> None:
    """A transient failure (no files) must not hide the content until the TTL expires."""
    discover = AsyncMock(return_value=[])
    with (
        patch("src.services.github.GITHUB_REPOS", _REPO),
        patch("src.services.github.GITHUB_CACHE_SECONDS", 300),
        patch("src.services.github._discover_i18n_paths", new=discover),
    ):
        assert await fetch_github_i18n_content() == []
        assert await fetch_github_i18n_content() == []
    assert discover.await_count == 2
