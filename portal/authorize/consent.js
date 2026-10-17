// Pure consent-flow logic for the reference portal: no DOM, no network.
// Kept separate from authorize.js so it can be tested with `node --test`.

const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

// Hosts whose callbacks are expected for a jor-mcp instance besides loopback.
export const KNOWN_CALLBACK_HOSTS = new Set(["claude.ai"]);

/**
 * Normalize a URL host the way the server does: 127.0.0.1 becomes localhost.
 * @param {string} hostname
 * @returns {string}
 */
export function normalizeHost(hostname) {
  const host = hostname.toLowerCase();
  return host === "127.0.0.1" ? "localhost" : host;
}

/**
 * Parse an http(s) URL, or return null for anything else (javascript:, data:, junk).
 * @param {string} value
 * @returns {URL | null}
 */
export function parseHttpUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url : null;
  } catch {
    return null;
  }
}

/**
 * Validate the OAuth authorization request carried in the page URL.
 *
 * redirect_uri is required here, although the server falls back to the first
 * registered URI, because the user must see where the code will be sent.
 *
 * @param {string} search location.search
 * @returns {{ok: true, params: {clientId: string, codeChallenge: string,
 *   redirectUri: string, state: string | null}} | {ok: false, error: string}}
 */
export function parseAuthorizeParams(search) {
  const query = new URLSearchParams(search);
  const clientId = query.get("client_id");
  const codeChallenge = query.get("code_challenge");
  const method = query.get("code_challenge_method");
  const redirectUri = query.get("redirect_uri");
  const responseType = query.get("response_type");

  if (!clientId) return { ok: false, error: "Missing client_id." };
  if (!codeChallenge) return { ok: false, error: "Missing code_challenge." };
  if (method !== "S256") return { ok: false, error: "code_challenge_method must be S256." };
  if (responseType !== null && responseType !== "code") {
    return { ok: false, error: "response_type must be code." };
  }
  if (!redirectUri || !parseHttpUrl(redirectUri)) {
    return { ok: false, error: "Missing or invalid redirect_uri." };
  }
  return {
    ok: true,
    params: { clientId, codeChallenge, redirectUri, state: query.get("state") },
  };
}

/**
 * Describe where the authorization code will be sent.
 * @param {string} redirectUri an http(s) URL already accepted by parseAuthorizeParams
 * @returns {{host: string, trusted: boolean}} trusted is false for any host that
 *   is neither loopback nor a known callback host, so the page can warn the user.
 */
export function describeDestination(redirectUri) {
  const host = normalizeHost(new URL(redirectUri).hostname);
  const trusted = LOOPBACK_HOSTS.has(host) || KNOWN_CALLBACK_HOSTS.has(host);
  return { host, trusted };
}

/**
 * Return the URL to redirect to after approval, or null when it must not be used.
 *
 * Only the redirect_uri returned by /approve is ever followed, and only when it
 * is http(s) and points at the same host the user was shown.
 *
 * @param {unknown} responseRedirectUri redirect_uri from the /approve response
 * @param {string} expectedHost host shown to the user (from describeDestination)
 * @returns {string | null}
 */
export function safeRedirectTarget(responseRedirectUri, expectedHost) {
  if (typeof responseRedirectUri !== "string") return null;
  const url = parseHttpUrl(responseRedirectUri);
  if (!url || normalizeHost(url.hostname) !== expectedHost) return null;
  return url.href;
}

/**
 * Message shown when /approve does not answer 200.
 * @param {number} status
 * @returns {string}
 */
export function approvalErrorMessage(status) {
  if (status === 403) return "This account is not authorized to use this server.";
  if (status === 401) return "Your sign-in expired. Reload the page and try again.";
  if (status === 400) return "The authorization request is invalid. Start again from your client.";
  if (status === 429) return "Too many requests. Wait a minute and try again.";
  return "The server could not approve the request. Try again later.";
}
