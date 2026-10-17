<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Connect Your Newsroom's Data

`jor-mcp` is not tied to Ambiental Media's content. Any newsroom can run its own instance and point it at **its own WordPress site and its own GitHub repositories**. This guide explains the ways to connect, what each one requires, and the security checklist to follow.

---

## 1. Connection Scenarios

| # | Scenario | Data source | Who can use it | Cost and effort |
|---|---|---|---|---|
| **A** | Use Ambiental Media's instance | Ambiental Media content only | Users on Ambiental Media's allow-list | None |
| **B** | **Run your own production instance** | **Your WordPress and GitHub** | Users on your allow-list | GCP with billing: Cloud Run, Load Balancer, a domain and a consent portal |
| **C** | Run locally for testing | Your WordPress and GitHub | Only you | Free, one machine |

Scenario A does not let you search your own content. To do that, use scenario B, and scenario C to try it out first.

### 1.1 Scenario A: Ambiental Media's instance

Ask Ambiental Media to add your Google account to their allow-list, then follow [Connecting to LLMs](../1-technical/connecting-clients.md#ambiental-media-instance).

### 1.2 Scenario B: your own production instance

1.  **Project and services:** create a GCP project, add Firebase to it and create the Firestore database in **Native mode**. Enable the `identitytoolkit`, `securetoken`, `firestore`, `run` and `artifactregistry` APIs.
2.  **Authentication:** enable the Google sign-in provider and disable Email/Password ([deployment guide, section 3](deployment-guide.md#3-firebase-console-security--authentication-configuration)). Disable sign-up only after each user has signed in once (see item 4 of the checklist below).
3.  **Allow-list:** create `allowed_users/<email>` with `status: "active"` and `tier: "basic"` for each user ([deployment guide, section 5](deployment-guide.md#5-manual-allow-list-management-allowed_users)).
4.  **Runtime service account:** create `jor-mcp-runner` with the roles listed in the [deployment guide, section 2](deployment-guide.md#2-gcp-iam-service-account-permissions).
5.  **GitHub token:** create a fine-grained token (checklist item 7) and store it in Secret Manager as `MCP_GITHUB_TOKEN`.
6.  **Image and deploy:** build the image, push it to Artifact Registry and deploy with `service.yaml`, setting every variable marked as required for scenario B in [section 2](#2-required-variables-by-scenario).
7.  **Consent portal:** publish a consent portal on GCS behind the same Load Balancer ([Load Balancer configuration](load-balancer-config.md)). Ambiental Media's portal is private; use the [reference portal](#5-reference-consent-portal).
8.  **Firebase and Firestore protections:** restrict the API key, deploy the Firestore rules and configure the TTL policies (checklist items 5, 6 and 9).
9.  **Connect:** add `https://<your-domain>/mcp` as a connector in your MCP client ([section 3](#3-mcp-clients)).

### 1.3 Scenario C: local testing

1.  Repeat steps 1 to 3 of scenario B in a test project.
2.  Create a service account for local use, e.g. `jor-mcp-local@<project-id>.iam.gserviceaccount.com`, with `roles/datastore.user` and `roles/firebaseauth.admin`. Grant it `roles/iam.serviceAccountTokenCreator` on itself, and grant your own account `roles/iam.serviceAccountTokenCreator` on it.
3.  Use it through impersonation, never through a downloaded JSON key:

    ```bash
    gcloud auth application-default login \
      --impersonate-service-account=jor-mcp-local@<project-id>.iam.gserviceaccount.com
    ```

4.  Name that account for the Firebase Admin SDK, then start the server bound to localhost only. The SDK cannot sign the login flow's custom tokens with impersonated credentials directly; with `FIREBASE_SERVICE_ACCOUNT_ID` it signs through IAM instead:

    ```bash
    echo "FIREBASE_SERVICE_ACCOUNT_ID=jor-mcp-local@<project-id>.iam.gserviceaccount.com" >> .env
    uv run --env-file .env uvicorn src.server:app --host 127.0.0.1 --port 8080
    ```

5.  Serve the [reference portal](#52-run-it-locally-scenario-c) on `http://localhost:3000`.
6.  Connect with Claude Code:

    ```bash
    claude mcp add --transport http jor-mcp-local http://localhost:8080/mcp
    ```

> [!NOTE]
> This setup was validated end to end with a scripted MCP client: client registration, consent through the reference portal, code exchange (a reused code is refused) and the three tools at `/mcp`. Without `FIREBASE_SERVICE_ACCOUNT_ID`, the code exchange fails.

---

## 2. Required Variables by Scenario

Several defaults point to Ambiental Media. If you leave them unset, your instance searches Ambiental Media's WordPress and sends your users to Ambiental Media's consent portal. Set every variable marked **required** below; the server logs a warning at startup naming any that still points to `ambiental.media`. The full reference is in [Configuration and Environment](configuration-and-env.md).

| Variable | B (production) | C (local) |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | Set by Cloud Run | **Required** |
| `FIREBASE_WEB_API_KEY` | **Required** | **Required** |
| `FIREBASE_SERVICE_ACCOUNT_ID` | Leave unset | **Required** with impersonation |
| `WORDPRESS_API_URL` | **Required** (default is Ambiental Media) | **Required** (default is Ambiental Media) |
| `MCP_GITHUB_REPOS` / `MCP_GITHUB_TOKEN` | Optional | Optional |
| `MCP_GITHUB_FILENAMES` | Optional (default `pt.json,en.json`) | Optional (default `pt.json,en.json`) |
| `OAUTH_SERVER_BASE_URL` | **Required**: `https://<your-domain>` | **Required**: `http://localhost:8080` |
| `OAUTH_PORTAL_BASE_URL` | **Required**: your portal URL | **Required**: `http://localhost:3000` |
| `CORS_ALLOWED_ORIGINS` | **Required**: your portal origin | The default already allows `http://localhost:3000` |
| `IP_RATE_LIMIT_TRUSTED_PROXIES` | `1` behind the Load Balancer | `0` |
| `GCP_PROJECT_ID` | Optional on Cloud Run | Optional, needed for log and trace correlation |

---

## 3. MCP Clients

| Client | Scenarios | Notes |
|---|---|---|
| Claude Desktop and claude.ai (custom connector) | A and B | The connection starts from Anthropic's servers, so the server URL must be public HTTPS |
| Claude Code (`claude mcp add --transport http`) | A, B and C | Connects from your machine with a loopback callback. The simplest path for scenario C |
| MCP Inspector (`npx @modelcontextprotocol/inspector`) | A, B and C | Useful to debug the OAuth flow and list the tools |
| Custom agents (MCP SDK) | A, B and C | Must implement OAuth 2.1 with PKCE and Dynamic Client Registration (DCR) |

> [!NOTE]
> The server mounts the MCP endpoint at `/mcp`. Older material refers to `/mcp/sse`, which answers `404` even with a valid token on this code base.

---

## 4. Known Limitations

-   **Consent portal:** the production portal (`jor-mcp-site`) is a private repository. To complete the login flow on your own instance, you need a portal that implements the consent step described in [API Contracts](../1-technical/api-contracts.md). Use the [reference portal](#5-reference-consent-portal) or build your own.
-   **GitHub file format:** the GitHub source only reads JSON files whose names are listed in `MCP_GITHUB_FILENAMES` (default `pt.json` and `en.json`), at any depth of each repository in `MCP_GITHUB_REPOS`, and searches the string values inside them. CSV, Markdown and other formats are not supported. Repositories without matching files return no results and no error.
-   **WordPress:** the site's REST API (`/wp-json/wp/v2/posts`) must be publicly readable.

---

## 5. Reference Consent Portal

`portal/` holds a minimal consent page that implements the consent step of the [API Contracts](../1-technical/api-contracts.md). It uses no build step: plain HTML, CSS and JavaScript, with the Firebase SDK loaded from Google's CDN with integrity hashes.

```text
portal/
├── authorize/
│   ├── index.html       # served at /authorize, the endpoint advertised by the server
│   ├── authorize.js     # Google sign-in, POST /api/oauth/approve, redirect
│   ├── consent.js       # request validation and destination checks (no DOM)
│   └── authorize.css
├── config.example.js    # copy to config.js (ignored by git)
└── tests/               # node --test "portal/tests/*.test.js"
```

### 5.1 What the page enforces

-   Requires `client_id`, `code_challenge`, `code_challenge_method=S256` and an http(s) `redirect_uri`; anything else shows an error.
-   Shows the **destination domain** before sign-in and a warning when it is neither a local address nor `claude.ai`.
-   Follows only the `redirect_uri` returned by `/approve`, and only if it points to the domain the user was shown. **Deny** never redirects.
-   Writes text with `textContent` only, keeps the Firebase session in memory (no `localStorage`), declares a Content Security Policy and a `no-referrer` policy, and refuses to run inside a frame.

### 5.2 Run it locally (scenario C)

```bash
cp portal/config.example.js portal/config.js   # then fill in your Firebase web config
python3 -m http.server 3000 --bind 127.0.0.1 -d portal
```

Set `OAUTH_PORTAL_BASE_URL=http://localhost:3000` on the server. Run the tests with `node --test "portal/tests/*.test.js"` (Node.js 22 or later).

### 5.3 Publish it (scenario B)

1.  Create `portal/config.js` with your Firebase web config and `serverBaseUrl` set to your `OAUTH_SERVER_BASE_URL`.
2.  If the server is not on the same origin as the portal, add its origin to `connect-src` in the page's Content Security Policy (`portal/authorize/index.html`).
3.  Upload the contents of `portal/` (without `tests/` and `package.json`) to the GCS bucket behind your Load Balancer, so the page answers at `https://<your-domain>/authorize/`.
4.  Configure the backend bucket to send `Content-Security-Policy: frame-ancestors 'none'` as a custom response header: this protection cannot be declared in the page itself.
5.  Add your domain to **Authentication > Settings > Authorized domains** in the Firebase console.

The reference portal has no automated end-to-end test yet: the Google sign-in and the call to `/approve` are checked by hand.

---

## 6. Security Checklist for Replicators

Check every item before exposing your instance.

-   [ ] **1. Run a current release.** Use `0.13.1` or later: earlier releases do not require a valid `tier` claim on every token.
-   [ ] **2. Bind locally to `127.0.0.1`.** Never run the server with `--host 0.0.0.0` on your machine; that value belongs only in the `Dockerfile`.
-   [ ] **3. Revoke users completely.** When someone leaves, follow the [three-step revocation](deployment-guide.md#52-revoking-a-user) instead of only editing `allowed_users`. `scripts/revoke_user.py` runs all three steps.
-   [ ] **4. Disable sign-up and keep Google as the only provider.** Disabling sign-up also blocks the first Google login of allow-listed users who have never signed in, so disable it after each user's first login and re-enable it briefly when onboarding someone new ([deployment guide, section 3.1](deployment-guide.md#31-disabling-self-registration)).
-   [ ] **5. Restrict the Firebase API key** to your portal's domains (HTTP referrers) and to the `identitytoolkit` and `securetoken` APIs only.
-   [ ] **6. Deploy Firestore rules that deny all client access:** publish the repository's `firestore.rules` ([deployment guide, section 4](deployment-guide.md#4-understanding-the-non-secret-nature-of-firebase-configurations)). The server uses the Admin SDK, which these rules do not affect.
-   [ ] **7. Use least privilege.** A dedicated runtime service account (`jor-mcp-runner`), impersonation instead of JSON keys on developer machines, and a fine-grained GitHub token with `Contents: read` only, limited to the repositories in `MCP_GITHUB_REPOS`, expiring in 90 days or less.
-   [ ] **8. Index only what every user may read.** Every allow-listed user, and the AI provider behind their client, can read everything in the configured repositories. Record this decision.
-   [ ] **9. Configure TTL and HTTPS.** Firestore TTL policies on `oauth_codes.expires_at` and `ip_rate_limits.expires_at`, and HTTPS on every public URL.
-   [ ] **10. Deploy without long-lived keys.** Prefer [Workload Identity Federation](deployment-guide.md#83-keyless-authentication-with-workload-identity-federation) over the `GCP_SA_KEY` secret in GitHub Actions.
