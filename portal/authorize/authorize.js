// Reference consent page for jor-mcp: Google sign-in through Firebase, then
// POST /api/oauth/approve and a redirect to the URI the server returns.
// Uses the Firebase compat SDK loaded by index.html (global `firebase`) and the
// instance settings from /config.js (global JOR_MCP_PORTAL_CONFIG).

import {
  approvalErrorMessage,
  describeDestination,
  parseAuthorizeParams,
  safeRedirectTarget,
} from "./consent.js";

const $ = (id) => document.getElementById(id);

function showOnly(sectionId) {
  for (const section of document.querySelectorAll("[data-step]")) {
    section.hidden = section.id !== sectionId;
  }
  // The request details stay visible while the user is deciding.
  $("request").hidden = sectionId !== "step-sign-in" && sectionId !== "step-consent";
}

function fail(message) {
  $("error-message").textContent = message;
  showOnly("step-error");
}

function setBusy(button, busy) {
  button.disabled = busy;
  button.setAttribute("aria-busy", String(busy));
}

async function approve(auth, params, destination) {
  const config = window.JOR_MCP_PORTAL_CONFIG;
  const serverBaseUrl = String(config.serverBaseUrl).replace(/\/+$/, "");
  const idToken = await auth.currentUser.getIdToken();
  const body = {
    client_id: params.clientId,
    code_challenge: params.codeChallenge,
    code_challenge_method: "S256",
    redirect_uri: params.redirectUri,
  };
  if (params.state !== null) body.state = params.state;

  const response = await fetch(`${serverBaseUrl}/api/oauth/approve`, {
    method: "POST",
    headers: { Authorization: `Bearer ${idToken}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
    credentials: "omit",
  });
  if (!response.ok) {
    fail(approvalErrorMessage(response.status));
    return;
  }

  const data = await response.json();
  const target = safeRedirectTarget(data.redirect_uri, destination.host);
  if (!target) {
    fail("The server returned an unexpected destination. Access was not granted.");
    return;
  }
  await auth.signOut();
  window.location.assign(target);
}

async function main() {
  // A consent page must never run inside another site's frame (clickjacking).
  if (window.top !== window.self) {
    fail("This page cannot be displayed inside another page.");
    return;
  }

  const config = window.JOR_MCP_PORTAL_CONFIG;
  if (!config || !config.firebaseConfig || !config.serverBaseUrl) {
    fail("The portal is not configured: copy config.example.js to config.js.");
    return;
  }
  if (typeof firebase === "undefined") {
    fail("The Firebase SDK did not load. Check the network and the page's integrity hashes.");
    return;
  }

  const parsed = parseAuthorizeParams(window.location.search);
  if (!parsed.ok) {
    fail(`Invalid authorization request. ${parsed.error}`);
    return;
  }
  const { params } = parsed;
  const destination = describeDestination(params.redirectUri);
  $("client-id").textContent = params.clientId;
  $("destination").textContent = destination.host;
  $("destination-warning").hidden = destination.trusted;

  firebase.initializeApp(config.firebaseConfig);
  const auth = firebase.auth();
  // Keep the session in memory only: nothing is written to localStorage or IndexedDB.
  // Started now but awaited only on sign-in, so the page renders without waiting on it.
  const persistenceReady = auth.setPersistence(firebase.auth.Auth.Persistence.NONE);
  persistenceReady.catch(() => {}); // A failure surfaces when the user clicks sign-in.

  $("sign-in").addEventListener("click", async () => {
    setBusy($("sign-in"), true);
    try {
      await persistenceReady;
      const result = await auth.signInWithPopup(new firebase.auth.GoogleAuthProvider());
      $("account").textContent = result.user.email ?? "";
      showOnly("step-consent");
    } catch {
      fail("Google sign-in was cancelled or failed. Reload the page to try again.");
    } finally {
      setBusy($("sign-in"), false);
    }
  });

  $("allow").addEventListener("click", async () => {
    setBusy($("allow"), true);
    setBusy($("deny"), true);
    try {
      await approve(auth, params, destination);
    } catch {
      fail("Could not reach the server. Check your connection and try again.");
    }
  });

  // Denying never redirects: the only redirect this page follows is the one
  // returned by /approve.
  $("deny").addEventListener("click", async () => {
    await auth.signOut();
    showOnly("step-denied");
  });

  showOnly("step-sign-in");
}

main().catch(() => fail("The page could not start. Reload it to try again."));
