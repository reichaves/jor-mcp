// Run with: node --test "portal/tests/*.test.js"
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

import {
  approvalErrorMessage,
  describeDestination,
  normalizeHost,
  parseAuthorizeParams,
  parseHttpUrl,
  safeRedirectTarget,
} from "../authorize/consent.js";

const VALID = {
  client_id: "client-123",
  code_challenge: "abc",
  code_challenge_method: "S256",
  redirect_uri: "http://localhost:54321/callback",
  response_type: "code",
  state: "xyz",
};

const search = (overrides = {}) => {
  const query = new URLSearchParams({ ...VALID, ...overrides });
  for (const [key, value] of Object.entries(overrides)) {
    if (value === undefined) query.delete(key);
  }
  return `?${query}`;
};

describe("parseAuthorizeParams", () => {
  it("accepts a complete S256 request", () => {
    assert.deepEqual(parseAuthorizeParams(search()), {
      ok: true,
      params: {
        clientId: "client-123",
        codeChallenge: "abc",
        redirectUri: "http://localhost:54321/callback",
        state: "xyz",
      },
    });
  });

  it("keeps state null when absent and accepts a missing response_type", () => {
    const parsed = parseAuthorizeParams(search({ state: undefined, response_type: undefined }));
    assert.equal(parsed.ok, true);
    assert.equal(parsed.params.state, null);
  });

  for (const [name, overrides] of [
    ["client_id is missing", { client_id: undefined }],
    ["code_challenge is missing", { code_challenge: undefined }],
    ["the method is plain", { code_challenge_method: "plain" }],
    ["the method is missing", { code_challenge_method: undefined }],
    ["response_type is token", { response_type: "token" }],
    ["redirect_uri is missing", { redirect_uri: undefined }],
    ["redirect_uri is javascript:", { redirect_uri: "javascript:alert(1)" }],
    ["redirect_uri is not a URL", { redirect_uri: "not a url" }],
  ]) {
    it(`rejects the request when ${name}`, () => {
      const parsed = parseAuthorizeParams(search(overrides));
      assert.equal(parsed.ok, false);
      assert.equal(typeof parsed.error, "string");
    });
  }
});

describe("parseHttpUrl and normalizeHost", () => {
  it("accepts only http and https", () => {
    assert.ok(parseHttpUrl("https://claude.ai/cb"));
    assert.equal(parseHttpUrl("data:text/html,hi"), null);
    assert.equal(parseHttpUrl("ftp://example.org"), null);
  });

  it("maps 127.0.0.1 to localhost like the server", () => {
    assert.equal(normalizeHost("127.0.0.1"), "localhost");
    assert.equal(normalizeHost("Claude.AI"), "claude.ai");
  });
});

describe("describeDestination (R14)", () => {
  it("trusts loopback and known callback hosts", () => {
    for (const uri of [
      "http://localhost:3000/cb",
      "http://127.0.0.1:3000/cb",
      "http://[::1]:3000/cb",
      "https://claude.ai/api/mcp/auth_callback",
    ]) {
      assert.equal(describeDestination(uri).trusted, true, uri);
    }
  });

  it("flags any other host, including look-alikes", () => {
    for (const uri of [
      "https://evil.example/cb",
      "https://claude.ai.evil.example/cb",
      "https://evilclaude.ai/cb",
    ]) {
      assert.equal(describeDestination(uri).trusted, false, uri);
    }
  });

  it("reports the normalized host shown to the user", () => {
    assert.equal(describeDestination("http://127.0.0.1:9/cb").host, "localhost");
  });
});

describe("safeRedirectTarget (R12)", () => {
  it("follows the server's URI when it matches the host shown", () => {
    const uri = "http://localhost:54321/callback?code=c&state=s";
    assert.equal(safeRedirectTarget(uri, "localhost"), uri);
  });

  it("treats 127.0.0.1 in the response as the localhost shown", () => {
    assert.ok(safeRedirectTarget("http://127.0.0.1:1/cb?code=c", "localhost"));
  });

  it("refuses a different host, a non-http scheme or a missing value", () => {
    assert.equal(safeRedirectTarget("https://evil.example/cb?code=c", "localhost"), null);
    assert.equal(safeRedirectTarget("javascript:alert(1)", "localhost"), null);
    assert.equal(safeRedirectTarget(undefined, "localhost"), null);
    assert.equal(safeRedirectTarget(42, "localhost"), null);
  });
});

describe("approvalErrorMessage", () => {
  it("explains a 403 as an unauthorized account", () => {
    assert.match(approvalErrorMessage(403), /not authorized/);
  });

  it("returns a message for every status", () => {
    for (const status of [400, 401, 429, 500, 502]) {
      assert.ok(approvalErrorMessage(status).length > 0);
    }
  });
});

describe("page safety (R13, R15)", () => {
  const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
  // Comments may name the APIs the code avoids; only check the code itself.
  const stripComments = (source) =>
    source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
  const script = stripComments(read("../authorize/authorize.js") + read("../authorize/consent.js"));
  const html = read("../authorize/index.html");

  it("never writes HTML from strings or touches browser storage", () => {
    for (const forbidden of [
      "innerHTML",
      "outerHTML",
      "insertAdjacentHTML",
      "document.write",
      "localStorage",
      "sessionStorage",
      "eval(",
    ]) {
      assert.equal(script.includes(forbidden), false, forbidden);
    }
  });

  it("loads every third-party script with an integrity hash", () => {
    const external = [...html.matchAll(/<script\s+[^>]*src="https:[^>]*>/g)].map((m) => m[0]);
    assert.ok(external.length >= 2);
    for (const tag of external) {
      assert.match(tag, /integrity="sha384-[A-Za-z0-9+/=]+"/);
      assert.match(tag, /crossorigin="anonymous"/);
    }
  });

  it("declares a CSP without inline scripts and a no-referrer policy", () => {
    const csp = html.match(/http-equiv="Content-Security-Policy"\s+content="([^"]+)"/)[1];
    assert.match(csp, /default-src 'self'/);
    assert.doesNotMatch(csp, /unsafe-inline|unsafe-eval/);
    assert.match(html, /<meta name="referrer" content="no-referrer" \/>/);
    assert.doesNotMatch(html, /<script>(?!<\/script>)/);
  });
});
