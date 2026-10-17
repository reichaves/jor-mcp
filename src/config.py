"""Application configuration constants.

All values are sourced from environment variables. Defaults are safe
for local development; production deployments must override them via
Cloud Run environment variable configuration.
"""

import os

# ---------------------------------------------------------------------------
# Firestore / Rate Limiting
# ---------------------------------------------------------------------------

FIRESTORE_DATABASE_ID: str = os.environ.get("FIRESTORE_DATABASE_ID", "(default)")
"""Firestore database ID. Override when using a named database (e.g. 'jor-mcp')."""

RATE_LIMIT_COLLECTION: str = os.environ.get("RATE_LIMIT_COLLECTION", "rate_limits")
"""Firestore collection used to store monthly fixed-window user counters."""

# Rate-limit quotas per tier: monthly request allowance (Fixed Window)
RATE_LIMIT_BASIC: int = int(os.environ.get("RATE_LIMIT_BASIC_REQUESTS", "500"))
"""Monthly request quota for 'basic' tier users."""
RATE_LIMIT_PRO: int = int(os.environ.get("RATE_LIMIT_PRO_REQUESTS", "2000"))
"""Monthly request quota for 'pro' tier users."""

TIER_QUOTAS: dict[str, int] = {
    "basic": RATE_LIMIT_BASIC,
    "pro": RATE_LIMIT_PRO,
}
"""Map of tier (role) name -> monthly request quota.

Single definition of which roles exist: the authentication middleware rejects
any token whose ``tier`` claim is not a key here, and the rate limiter reads the
quota from the same mapping. Roles are assigned manually by the instance
administrators on the ``allowed_users`` Firestore documents.
"""

# ---------------------------------------------------------------------------
# IP Rate Limiting (unauthenticated routes)
# ---------------------------------------------------------------------------

IP_RATE_LIMIT_COLLECTION: str = os.environ.get("IP_RATE_LIMIT_COLLECTION", "ip_rate_limits")
"""Firestore collection used to store short fixed-window counters keyed by client IP."""

IP_RATE_LIMIT_REQUESTS: int = int(os.environ.get("IP_RATE_LIMIT_REQUESTS", "60"))
"""Maximum requests a single IP may send to unauthenticated routes per window."""

IP_RATE_LIMIT_WINDOW_SECONDS: int = int(os.environ.get("IP_RATE_LIMIT_WINDOW_SECONDS", "60"))
"""Length in seconds of the fixed window applied to the per-IP counter."""

IP_RATE_LIMIT_TRUSTED_PROXIES: int = int(os.environ.get("IP_RATE_LIMIT_TRUSTED_PROXIES", "1"))
"""Number of trusted proxies appending to ``X-Forwarded-For`` at the right end.

Google Cloud Load Balancing rewrites the header as
``<supplied-value>, <client-ip>, <load-balancer-ip>``, so the real client IP is
the entry ``IP_RATE_LIMIT_TRUSTED_PROXIES + 1`` positions from the right. Taking
the left-most entry instead would let any caller spoof its identity and bypass
the limiter. Set to ``0`` when the container is reached directly without a proxy.
"""

# ---------------------------------------------------------------------------
# CORS (OAuth consent portal)
# ---------------------------------------------------------------------------

CORS_ALLOWED_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,https://jormcp.ambiental.media",
    ).split(",")
    if origin.strip()
]
"""Browser origins allowed to call the OAuth proxy endpoints via CORS.

Comma-separated list provided through the ``CORS_ALLOWED_ORIGINS`` environment
variable. Defaults to the local Next.js dev portal (``http://localhost:3000``)
and the production consent portal (``https://jormcp.ambiental.media``).
"""

# ---------------------------------------------------------------------------
# OAuth 2.1 Proxy
# ---------------------------------------------------------------------------

OAUTH_SERVER_BASE_URL: str = os.environ.get(
    "OAUTH_SERVER_BASE_URL", "https://jormcp.ambiental.media"
).rstrip("/")
"""Public base URL of this backend (OAuth issuer / resource server).

Used to build the absolute token and registration endpoint URLs advertised in
the discovery metadata. Override in dev (e.g. ``http://localhost:8080``).
"""

OAUTH_PORTAL_BASE_URL: str = os.environ.get(
    "OAUTH_PORTAL_BASE_URL", "https://jormcp.ambiental.media"
).rstrip("/")
"""Public base URL of the Next.js consent portal (``jor-mcp-site``).

Used to build the ``authorization_endpoint`` advertised in the discovery
metadata. Override in dev (e.g. ``http://localhost:3000``).
"""

OAUTH_CLIENTS_COLLECTION: str = os.environ.get("OAUTH_CLIENTS_COLLECTION", "oauth_clients")
"""Firestore collection storing dynamically registered OAuth clients (DCR)."""

OAUTH_CODES_COLLECTION: str = os.environ.get("OAUTH_CODES_COLLECTION", "oauth_codes")
"""Firestore collection storing short-lived authorization codes and PKCE state."""

OAUTH_CODE_TTL_SECONDS: int = int(os.environ.get("OAUTH_CODE_TTL_SECONDS", "600"))
"""Lifetime of an issued authorization code before it is considered expired."""

ALLOWED_USERS_COLLECTION: str = os.environ.get("ALLOWED_USERS_COLLECTION", "allowed_users")
"""Firestore collection whitelisting who may complete consent.

Each document id is a user email; the user is granted access only when the
document exists, its ``status`` field equals ``"active"`` and its ``tier`` names
a known role. Managed manually by the instance administrators (e.g. via the
Firebase console)."""

FIREBASE_WEB_API_KEY: str = os.environ.get("FIREBASE_WEB_API_KEY", "")
"""Firebase Web API key used by the token endpoint to exchange a custom token for
real ID/refresh tokens via the Google Identity Toolkit REST API. Same value as
the portal's ``NEXT_PUBLIC_FIREBASE_API_KEY``."""

FIREBASE_SERVICE_ACCOUNT_ID: str = os.environ.get("FIREBASE_SERVICE_ACCOUNT_ID", "")
"""Service account the Firebase Admin SDK signs custom tokens as, via IAM ``signBlob``.

Leave empty on Cloud Run, where the runtime service account is discovered. Set it
when the server runs with impersonated Application Default Credentials (local
testing): the SDK cannot sign with those directly, so the token exchange fails
unless the account is named here.
"""

IDENTITY_TOOLKIT_BASE_URL: str = os.environ.get(
    "IDENTITY_TOOLKIT_BASE_URL", "https://identitytoolkit.googleapis.com/v1"
).rstrip("/")
"""Base URL for the Google Identity Toolkit REST API (override for the emulator)."""

SECURE_TOKEN_BASE_URL: str = os.environ.get(
    "SECURE_TOKEN_BASE_URL", "https://securetoken.googleapis.com/v1"
).rstrip("/")
"""Base URL for the Google Secure Token REST API used by the refresh_token grant."""

# ---------------------------------------------------------------------------
# HTTP Client
# ---------------------------------------------------------------------------

HTTP_TIMEOUT: float = float(os.environ.get("HTTP_TIMEOUT", "10.0"))
"""Default timeout in seconds applied to all outbound HTTP requests."""

HTTP_MAX_KEEPALIVE_CONNECTIONS: int = int(os.environ.get("HTTP_MAX_KEEPALIVE_CONNECTIONS", "50"))
"""Maximum number of idle keep-alive connections retained in the pool."""

HTTP_MAX_CONNECTIONS: int = int(os.environ.get("HTTP_MAX_CONNECTIONS", "100"))
"""Maximum total concurrent connections allowed in the pool."""

# ---------------------------------------------------------------------------
# WordPress REST API
# ---------------------------------------------------------------------------

WP_API_BASE_URL: str = (
    os.environ.get("WORDPRESS_API_URL", "https://ambiental.media/wp-json")
    .rstrip("/")
    .removesuffix("/wp/v2")
)
"""Base URL for the WordPress REST API (no trailing slash, without /wp/v2).

Accepts both ``https://ambiental.media/wp-json`` and
``https://ambiental.media/wp-json/wp/v2`` — the ``/wp/v2`` suffix is
normalised away so service code can safely append ``/wp/v2/<resource>``.
"""

# ---------------------------------------------------------------------------
# GitHub API
# ---------------------------------------------------------------------------

GITHUB_TOKEN: str | None = os.environ.get("MCP_GITHUB_TOKEN")
"""Personal Access Token for the GitHub API. Optional for public repos.

Environment variable: ``MCP_GITHUB_TOKEN``.
"""

GITHUB_REPOS: str = os.environ.get("MCP_GITHUB_REPOS", "")
"""Comma-separated list of GitHub repositories (owner/repo format) to index.

Example: ambiental-media/microsite-amazonia,ambiental-media/microsite-pantanal

Environment variable: ``MCP_GITHUB_REPOS``.
"""

GITHUB_API_BASE_URL: str = os.environ.get(
    "MCP_GITHUB_API_BASE_URL", "https://api.github.com"
).rstrip("/")
"""Base URL for the GitHub REST API (no trailing slash).

Environment variable: ``MCP_GITHUB_API_BASE_URL``.
"""


GITHUB_FILE_EXTENSIONS: tuple[str, ...] = (".json", ".csv", ".md", ".markdown")
"""File extensions the GitHub source can parse (see ``src.services.github``)."""


def parse_github_filenames(raw: str) -> frozenset[str]:
    """Parse comma-separated file-name patterns, keeping only supported extensions.

    Each entry is an exact name (``pt.json``) or an ``fnmatch`` pattern matched
    against the file name (``*.csv``, ``dados-*.json``). Entries whose extension
    the GitHub source cannot parse could never return results and are dropped.
    """
    names = (name.strip() for name in raw.split(","))
    return frozenset(name for name in names if name.lower().endswith(GITHUB_FILE_EXTENSIONS))


GITHUB_FILENAMES: frozenset[str] = parse_github_filenames(
    os.environ.get("MCP_GITHUB_FILENAMES", "pt.json,en.json")
)
"""File-name patterns searched in each GitHub repository, matched at any depth.

Comma-separated exact names or ``fnmatch`` patterns ending in ``.json``,
``.csv``, ``.md`` or ``.markdown``. Defaults to the ``pt.json`` and ``en.json``
message files used by Ambiental Media's microsites.

Environment variable: ``MCP_GITHUB_FILENAMES``.
"""


def parse_github_exclude(raw: str) -> frozenset[str]:
    """Parse comma-separated ``fnmatch`` exclusion patterns, dropping blanks."""
    return frozenset(pattern.strip() for pattern in raw.split(",") if pattern.strip())


GITHUB_EXCLUDE: frozenset[str] = parse_github_exclude(os.environ.get("MCP_GITHUB_EXCLUDE", ""))
"""Patterns of files left out of the GitHub search even when their name matches.

Comma-separated ``fnmatch`` patterns compared with the file's full path in the
repository (``.claude/*``, ``docs/drafts/*``); a pattern without ``/`` is also
compared with the file name at any depth (``CLAUDE.md``). Matching is
case-sensitive and ``*`` also crosses ``/``. Empty by default.

Environment variable: ``MCP_GITHUB_EXCLUDE``.
"""

GITHUB_MAX_RESULTS: int = int(os.environ.get("MCP_GITHUB_MAX_RESULTS", "10"))
"""Most GitHub files returned by one search; ``0`` returns every match.

Files are ranked by how many times the query appears before the cut, and the
search adds a notice with the total when results are left out. Matches the
WordPress search, which returns at most 10 posts.

Environment variable: ``MCP_GITHUB_MAX_RESULTS``.
"""

GITHUB_MAX_FILE_BYTES: int = int(os.environ.get("MCP_GITHUB_MAX_FILE_BYTES", "1000000"))
"""Largest file, in bytes, fetched from GitHub; larger matches are skipped.

The default matches the Contents API, which only returns Base64 content for files
up to 1 MB.

Environment variable: ``MCP_GITHUB_MAX_FILE_BYTES``.
"""

GITHUB_MAX_FILES_PER_REPO: int = int(os.environ.get("MCP_GITHUB_MAX_FILES_PER_REPO", "50"))
"""Most matching files fetched per repository; the rest are skipped with a warning.

Environment variable: ``MCP_GITHUB_MAX_FILES_PER_REPO``.
"""

GITHUB_CACHE_SECONDS: int = int(os.environ.get("MCP_GITHUB_CACHE_SECONDS", "300"))
"""How long fetched GitHub content is reused before it is downloaded again.

Each search otherwise downloads every matching file of every repository. ``0``
disables the cache. The cache lives in memory, so each Cloud Run instance keeps
its own.

Environment variable: ``MCP_GITHUB_CACHE_SECONDS``.
"""

# ---------------------------------------------------------------------------
# OpenTelemetry
# ---------------------------------------------------------------------------

OTEL_EXPORTER_OTLP_ENDPOINT: str | None = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
"""OTLP/HTTP collector endpoint for exporting traces (e.g. http://localhost:4318).

Only read when ``OTEL_TRACES_EXPORTER`` is ``otlp``; on its own it exports
nothing.
"""

OTEL_SERVICE_NAME: str = os.environ.get("OTEL_SERVICE_NAME", "jor-mcp")
"""Logical service name embedded in every exported span's resource attributes."""

OTEL_TRACES_EXPORTER: str = os.environ.get("OTEL_TRACES_EXPORTER", "none").lower()
"""Span exporter to use: ``otlp``, ``console`` or ``none`` (the default).

Exporting is opt-in: setting ``OTEL_EXPORTER_OTLP_ENDPOINT`` alone changes
nothing, this variable must be set to ``otlp`` as well. Silence is the safe
default because an endpoint that refuses connections makes every batch retry,
fail, and flood the log with transient errors — which is what a stale
development endpoint did in production. Use ``console`` to inspect spans
locally; it prints one line per span.
"""

GCP_PROJECT_ID: str = os.environ.get("GCP_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT", "")
"""Google Cloud project ID used to build Cloud Logging trace correlation fields.

When set, log records include ``logging.googleapis.com/trace`` in the
``projects/<project-id>/traces/<trace-id>`` format required by Cloud Logging.
Cloud Run does not inject this value, so :mod:`src.telemetry` falls back to the
project bound to the ambient credentials when this variable is empty.
"""

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").upper()
"""Minimum level of the root logger configured by :mod:`src.telemetry`."""

CLOUD_RUN_SERVICE: str = os.environ.get("K_SERVICE", "")
"""Cloud Run service name, injected by the platform. Empty anywhere else.

Used only to tell whether the GCP metadata server is reachable before querying
it for the project ID.
"""
