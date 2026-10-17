"""GitHub Content API service layer.

Fetches JSON, CSV and Markdown files from the GitHub repositories listed in
``MCP_GITHUB_REPOS`` and consolidates their content for use in the unified
search tool.

File discovery is performed via the GitHub Git Trees API, which returns the
full recursive tree of the default branch.  Any file whose name matches one of
the ``MCP_GITHUB_FILENAMES`` patterns (by default ``pt.json`` and ``en.json``)
is fetched, regardless of its depth or directory, within the size and count
limits.  The Contents API returns file data encoded in Base64; this module
decodes it defensively and parses it by extension into a structure the search
tool can walk.  Results are cached in memory for ``MCP_GITHUB_CACHE_SECONDS``.
"""

import asyncio
import base64
import csv
import io
import json
import logging
from fnmatch import fnmatchcase
from pathlib import Path
from time import monotonic
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ValidationError

from src.config import (
    GITHUB_API_BASE_URL,
    GITHUB_CACHE_SECONDS,
    GITHUB_EXCLUDE,
    GITHUB_FILENAMES,
    GITHUB_MAX_FILE_BYTES,
    GITHUB_MAX_FILES_PER_REPO,
    GITHUB_REPOS,
    GITHUB_TOKEN,
)
from src.http_client import get_http_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class _GitHubContentResponse(BaseModel):
    """Minimal validated representation of a GitHub Contents API response."""

    name: str
    path: str
    encoding: str
    content: str


class _GitHubTreeItem(BaseModel):
    """A single entry returned by the GitHub Git Trees API."""

    path: str
    type: str  # "blob" (file) or "tree" (directory)
    size: int | None = None  # bytes; only present for blobs


class _GitHubTreeResponse(BaseModel):
    """Minimal validated representation of a GitHub Git Trees API response."""

    tree: list[_GitHubTreeItem]
    truncated: bool


class GitHubFileResult(BaseModel):
    """A successfully parsed file from a GitHub repository."""

    repo: str
    path: str
    data: dict[str, Any] | list[Any]


# In-memory cache of the consolidated content: (monotonic time stored, content).
_cache: tuple[float, list[dict[str, Any]]] | None = None
_cache_lock = asyncio.Lock()


def clear_cache() -> None:
    """Drop the cached GitHub content, so the next search downloads it again."""
    global _cache, _cache_lock
    _cache = None
    _cache_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _build_auth_headers() -> dict[str, str]:
    """Return Authorization headers if a token is configured.

    Returns:
        A dict with the ``Authorization`` header when ``GITHUB_TOKEN`` is set,
        otherwise an empty dict.
    """
    if GITHUB_TOKEN:
        return {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    return {}


def _decode_base64_content(raw: str) -> bytes:
    """Decode Base64-encoded content returned by the GitHub Contents API.

    The API concatenates the encoded content across multiple lines separated
    by ``\\n``.  This helper strips whitespace before decoding to handle that
    format defensively.

    Args:
        raw: The raw ``content`` string from the GitHub API response.

    Returns:
        The decoded bytes.

    Raises:
        ValueError: If the string is not valid Base64.
    """
    return base64.b64decode(raw.replace("\n", "").strip())


def _parse_content(path: str, text: str) -> dict[str, Any] | list[Any]:
    """Turn a file's text into a structure the search tool can walk.

    JSON keeps its own structure (object or array), CSV becomes a list of rows
    keyed by the header, and Markdown becomes ``{"text": ...}``.

    Args:
        path: The file path, whose extension selects the parser.
        text: The decoded file content.

    Returns:
        The parsed content.

    Raises:
        ValueError: If the content cannot be parsed for its extension.
    """
    suffix = Path(path).suffix.lower()
    if suffix == ".json":
        data = json.loads(text)
        if not isinstance(data, dict | list):
            raise ValueError("JSON root must be an object or an array")
        return data
    if suffix == ".csv":
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise ValueError("CSV file has no header row")
        return [dict(row) for row in reader]
    if suffix in (".md", ".markdown"):
        return {"text": text}
    raise ValueError(f"Unsupported file type: {suffix or path}")


def _matches_patterns(path: str) -> bool:
    """Return True when the file name matches one of the configured patterns."""
    name = Path(path).name
    return any(fnmatchcase(name, pattern) for pattern in GITHUB_FILENAMES)


def _is_excluded(path: str) -> bool:
    """Return True when the path matches an ``MCP_GITHUB_EXCLUDE`` pattern.

    Patterns are compared with the full path; one without ``/`` is also compared
    with the file name, so ``CLAUDE.md`` excludes that file at any depth.
    """
    name = Path(path).name
    return any(
        fnmatchcase(path, pattern) or ("/" not in pattern and fnmatchcase(name, pattern))
        for pattern in GITHUB_EXCLUDE
    )


async def _fetch_file(
    client: httpx.AsyncClient,
    repo: str,
    path: str,
) -> GitHubFileResult | None:
    """Attempt to fetch and decode a single file from a GitHub repository.

    Args:
        client: The shared async HTTP client.
        repo: Repository identifier in ``owner/repo`` format.
        path: Path to the file inside the repository.

    Returns:
        A ``GitHubFileResult`` when the file exists and decodes successfully,
        or ``None`` if the file does not exist (HTTP 404) or cannot be parsed.
    """
    url = f"{GITHUB_API_BASE_URL}/repos/{repo}/contents/{quote(path)}"
    try:
        response = await client.get(url, headers=_build_auth_headers())
    except httpx.RequestError as exc:
        logger.warning(
            "Network error fetching GitHub file",
            extra={"repo": repo, "path": path, "error": str(exc)},
        )
        return None

    if response.status_code == 404:
        logger.debug(
            "GitHub file not found",
            extra={"repo": repo, "path": path},
        )
        return None

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "HTTP error fetching GitHub file",
            extra={"repo": repo, "path": path, "status": exc.response.status_code},
        )
        return None

    try:
        response_data = response.json()
        payload = _GitHubContentResponse.model_validate(response_data)
    except (ValueError, ValidationError) as exc:
        logger.warning(
            "Unexpected or invalid GitHub API response",
            extra={"repo": repo, "path": path, "error": str(exc)},
        )
        return None

    if payload.encoding != "base64":
        logger.warning(
            "Unsupported GitHub file encoding",
            extra={"repo": repo, "path": path, "encoding": payload.encoding},
        )
        return None

    try:
        raw_bytes = _decode_base64_content(payload.content)
        decoded_str = raw_bytes.decode("utf-8", errors="ignore")
        data = _parse_content(path, decoded_str)
    except (ValueError, csv.Error) as exc:
        # json.JSONDecodeError is a ValueError subclass.
        logger.warning(
            "Failed to decode GitHub file content",
            extra={"repo": repo, "path": path, "error": str(exc)},
        )
        return None

    return GitHubFileResult(repo=repo, path=path, data=data)


async def _discover_i18n_paths(
    client: httpx.AsyncClient,
    repo: str,
) -> list[str]:
    """Discover matching file paths inside a repository via the Git Trees API.

    Fetches the full recursive tree of the default branch and returns the path
    of every file whose name matches an ``MCP_GITHUB_FILENAMES`` pattern,
    regardless of directory depth, unless it matches an ``MCP_GITHUB_EXCLUDE``
    pattern.  Files larger than ``MCP_GITHUB_MAX_FILE_BYTES`` are skipped and at
    most ``MCP_GITHUB_MAX_FILES_PER_REPO`` paths are kept.

    Args:
        client: The shared async HTTP client.
        repo: Repository identifier in ``owner/repo`` format.

    Returns:
        A list of matching file paths.  Returns an empty list on any error so
        callers can degrade gracefully.
    """
    url = f"{GITHUB_API_BASE_URL}/repos/{repo}/git/trees/HEAD"
    try:
        response = await client.get(
            url,
            headers=_build_auth_headers(),
            params={"recursive": "1"},
        )
    except httpx.RequestError as exc:
        logger.warning(
            "Network error fetching repo tree",
            extra={"repo": repo, "error": str(exc)},
        )
        return []

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "HTTP error fetching repo tree",
            extra={
                "repo": repo,
                "status": exc.response.status_code,
                "body": exc.response.text[:500],
            },
        )
        return []

    try:
        response_data = response.json()
        payload = _GitHubTreeResponse.model_validate(response_data)
    except (ValueError, ValidationError) as exc:
        logger.warning(
            "Unexpected or invalid GitHub API response",
            extra={"repo": repo, "error": str(exc)},
        )
        return []

    if payload.truncated:
        logger.warning(
            "GitHub tree response was truncated; some i18n files may be missed",
            extra={"repo": repo},
        )

    paths: list[str] = []
    for item in payload.tree:
        if item.type != "blob" or not _matches_patterns(item.path) or _is_excluded(item.path):
            continue
        if item.size is not None and item.size > GITHUB_MAX_FILE_BYTES:
            logger.warning(
                "Skipping GitHub file larger than MCP_GITHUB_MAX_FILE_BYTES",
                extra={"repo": repo, "path": item.path, "size": item.size},
            )
            continue
        paths.append(item.path)

    if len(paths) > GITHUB_MAX_FILES_PER_REPO:
        logger.warning(
            "Too many matching GitHub files; keeping the first MCP_GITHUB_MAX_FILES_PER_REPO",
            extra={"repo": repo, "matched": len(paths), "kept": GITHUB_MAX_FILES_PER_REPO},
        )
        paths = paths[:GITHUB_MAX_FILES_PER_REPO]
    return paths


async def _fetch_repo_files(
    client: httpx.AsyncClient,
    repo: str,
) -> list[GitHubFileResult]:
    """Fetch all matching files found in a single repository.

    Discovers candidate paths via the Git Trees API, then fetches and parses
    each one via the Contents API.

    Args:
        client: The shared async HTTP client.
        repo: Repository identifier in ``owner/repo`` format.

    Returns:
        A list of ``GitHubFileResult`` objects (may be empty).
    """
    paths = await _discover_i18n_paths(client, repo)
    results: list[GitHubFileResult] = []

    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(_fetch_file(client, repo, path)) for path in paths]

    for task in tasks:
        if (result := task.result()) is not None:
            results.append(result)

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def fetch_github_i18n_content() -> list[dict[str, Any]]:
    """Fetch and consolidate content from all configured repositories.

    Reads ``GITHUB_REPOS`` (a comma-separated list of ``owner/repo`` strings),
    then for each repository retrieves every file matching the configured
    patterns via the GitHub Contents API.  A non-empty result is reused for
    ``MCP_GITHUB_CACHE_SECONDS``; an empty one is not cached, so a transient
    failure does not hide the content until the cache expires.

    Failures for individual repositories are logged at WARNING level and do
    **not** raise exceptions, allowing the remaining repositories to return
    successfully (graceful degradation).

    Returns:
        A flat list of dicts, each representing one successfully fetched file.
        Keys: ``repo`` (str), ``path`` (str), ``data`` (dict or list).
        On complete failure (e.g. empty ``GITHUB_REPOS``), returns an empty
        list.
    """
    global _cache
    if not GITHUB_REPOS.strip():
        logger.warning("GITHUB_REPOS is not configured; skipping GitHub ingestion")
        return []
    if not GITHUB_FILENAMES:
        logger.warning(
            "MCP_GITHUB_FILENAMES has no supported file patterns; skipping GitHub ingestion"
        )
        return []

    repos = [r.strip() for r in GITHUB_REPOS.split(",") if r.strip()]
    if GITHUB_CACHE_SECONDS <= 0:
        return await _fetch_all_repos(repos)

    # The lock makes concurrent searches wait for one download instead of each
    # fetching every repository.
    async with _cache_lock:
        now = monotonic()
        if _cache is not None and now - _cache[0] < GITHUB_CACHE_SECONDS:
            logger.info("Served GitHub content from cache", extra={"files": len(_cache[1])})
            return _cache[1]
        content = await _fetch_all_repos(repos)
        logger.info("Fetched GitHub content", extra={"repos": len(repos), "files": len(content)})
        _cache = (now, content) if content else None
        return content


async def _fetch_all_repos(repos: list[str]) -> list[dict[str, Any]]:
    """Fetch every repository concurrently and flatten their files."""
    client = get_http_client()
    consolidated: list[dict[str, Any]] = []

    # tasks is initialised here so the result-collection loop below is always
    # safe even in the unlikely event that the TaskGroup context itself raises
    # before the list comprehension completes.
    tasks: list[asyncio.Task[list[GitHubFileResult]]] = []
    try:
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(_fetch_repo_files(client, repo)) for repo in repos]
    except* Exception as eg:
        # Last-resort boundary guard: _fetch_repo_files handles all httpx and
        # validation errors internally and never propagates them, so this block
        # can only be reached by truly unexpected conditions (e.g. event-loop
        # cancellation or a programming bug).  Catching ExceptionGroup broadly
        # here is intentional so that a single broken repository cannot kill
        # the entire ingestion pipeline; the successfully-completed tasks are
        # still harvested in the loop below.
        logger.exception(
            "Unexpected error fetching GitHub repo content",
            extra={"errors": [str(e) for e in eg.exceptions]},
        )

    for task in tasks:
        if not task.cancelled() and task.exception() is None:
            for file_result in task.result():
                consolidated.append(file_result.model_dump())

    return consolidated
